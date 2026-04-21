import { render, screen, act, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import Users from "./Users";

// T3A merge gate — component test for the correct admin-create endpoint.
//
// The Users page used to POST the create-user form to /api/auth/register, the
// public self-service registration endpoint. That endpoint silently downgrades
// any submitted role to STAFF (see backend/app/schemas/user.py:UserCreate.
// force_staff_role), which produced a visible UX bug: the admin would pick
// "admin" or "reviewer" in the role dropdown, the request would succeed (201),
// and the created user would appear with role "staff" anyway.
//
// The fix points the form at the admin-only POST /api/admin/users endpoint,
// which accepts the role payload faithfully. These tests pin that contract
// with the network layer so the bug cannot recur silently.

interface FetchCall {
  url: string;
  method: string;
  body: unknown;
}

function setupFetchMock(): FetchCall[] {
  const calls: FetchCall[] = [];
  vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string, opts?: RequestInit) => {
    const method = opts?.method ?? "GET";
    let parsedBody: unknown = undefined;
    if (opts?.body && typeof opts.body === "string") {
      try {
        parsedBody = JSON.parse(opts.body);
      } catch {
        parsedBody = opts.body;
      }
    }
    calls.push({ url, method, body: parsedBody });

    // Initial GET /api/admin/users — empty list so the form is reachable
    if (url.endsWith("/admin/users") && method === "GET") {
      return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
    }
    // Initial GET /api/departments/ — empty list
    if (url.endsWith("/departments/") && method === "GET") {
      return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
    }
    // POST /api/admin/users — admin-create response
    if (url.endsWith("/admin/users") && method === "POST") {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          id: "new-user-id",
          email: "newadmin@example.gov",
          full_name: "New Admin",
          role: "admin",
          is_active: true,
        }),
      });
    }
    // Anything else — let it surface as a failure so the test can assert on it
    return Promise.resolve({
      ok: false,
      statusText: "Unexpected URL",
      json: () => Promise.resolve({ detail: `Unexpected URL: ${method} ${url}` }),
    });
  }));
  return calls;
}

describe("Users — create-user endpoint contract (T3A)", () => {
  beforeEach(() => {
    // Force token validity check elsewhere in the app to behave; we don't
    // import isTokenValid here, just pass any string token to the component.
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("posts the create-user form to /admin/users (not /auth/register)", async () => {
    const calls = setupFetchMock();

    render(<Users token="test-token" />);

    // Wait for initial loads to complete and the empty state to render
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /create first user/i })).toBeInTheDocument();
    });

    // Open the Create User dialog
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /create first user/i }));
    });

    // Fill the form
    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });
    fireEvent.change(screen.getByLabelText(/full name/i), { target: { value: "New Admin" } });
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: "newadmin@example.gov" } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: "S3cure!Pwd-2026" } });
    // Role select defaults to "read_only"; the role payload assertion lives in
    // a separate test below where we explicitly switch the role.

    // Submit
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /^create user$/i }));
    });

    // Assert the POST went to /admin/users — the heart of T3A
    const postCalls = calls.filter((c) => c.method === "POST");
    expect(postCalls.length).toBeGreaterThan(0);
    const createCall = postCalls[0];
    expect(createCall.url).toContain("/admin/users");
    expect(createCall.url).not.toContain("/auth/register");

    // Assert the payload shape matches AdminUserCreateRequest
    expect(createCall.body).toMatchObject({
      email: "newadmin@example.gov",
      password: "S3cure!Pwd-2026",
      full_name: "New Admin",
      role: "read_only",
    });
  });

  it("sends the non-default role the admin selected (admin), not the form default", async () => {
    // This test pins the actual T3A regression: the prior code path POSTed
    // through /auth/register, where UserCreate.force_staff_role silently
    // downgraded any submitted role to STAFF. An admin who picked "admin" in
    // the role dropdown got back a "staff" user with no error. Asserting that
    // the captured request body carries role: "admin" — exactly what the
    // admin selected — proves the new endpoint preserves the role end-to-end.
    const calls = setupFetchMock();
    const user = userEvent.setup();

    render(<Users token="test-token" />);
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /create first user/i })).toBeInTheDocument();
    });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /create first user/i }));
    });
    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText(/full name/i), { target: { value: "Promoted Admin" } });
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: "promoted@example.gov" } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: "S3cure!Pwd-2026" } });

    // Open the role dropdown and pick "Admin" — the option that exposed the
    // silent downgrade in the original bug.
    await user.click(screen.getByLabelText(/user role/i));
    await waitFor(() => {
      expect(screen.getByRole("option", { name: /^admin$/i })).toBeInTheDocument();
    });
    await user.click(screen.getByRole("option", { name: /^admin$/i }));

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /^create user$/i }));
    });

    const createCall = calls.find((c) => c.method === "POST");
    expect(createCall).toBeDefined();
    expect(createCall!.url).toContain("/admin/users");
    expect(createCall!.body).toHaveProperty("role", "admin");
  });
});
