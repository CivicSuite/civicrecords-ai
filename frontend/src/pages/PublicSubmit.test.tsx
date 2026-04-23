import { render, screen, fireEvent, act } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import PublicSubmit from "./PublicSubmit";

/**
 * T5D — PublicSubmit tests.
 *
 * Covers:
 * * unauthenticated visit redirects to /public/register (no anonymous
 *   walk-up submission, per Scott 2026-04-22 Option A)
 * * authenticated form renders with label/input association
 * * < 10-char description shows an actionable ``role="alert"`` error and
 *   does not POST
 * * successful submission shows the tracking ID returned by the server
 */

describe("PublicSubmit (T5D)", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(() =>
        Promise.resolve({
          ok: true,
          json: () => Promise.resolve({}),
        })
      )
    );
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  function renderSubmit(token: string | null) {
    return render(
      <MemoryRouter initialEntries={["/public/submit"]}>
        <Routes>
          <Route path="/public/submit" element={<PublicSubmit token={token} />} />
          <Route
            path="/public/register"
            element={<div data-testid="register-page">register</div>}
          />
        </Routes>
      </MemoryRouter>
    );
  }

  it("unauthenticated visit: redirects to /public/register (no anonymous submission)", () => {
    renderSubmit(null);
    expect(screen.getByTestId("register-page")).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: /submit a records request/i })
    ).not.toBeInTheDocument();
  });

  it("authenticated: renders form with labeled inputs", () => {
    renderSubmit("FAKE.JWT.TOKEN");

    const description = screen.getByLabelText(
      /describe the records you want/i
    ) as HTMLTextAreaElement;
    expect(description.id).toBe("public-submit-description");
    expect(description.getAttribute("aria-required")).toBe("true");

    const phone = screen.getByLabelText(/phone/i) as HTMLInputElement;
    expect(phone.id).toBe("public-submit-phone");
  });

  it("short description: role=alert error surfaces, no POST", async () => {
    const mockFetch = vi.fn();
    vi.stubGlobal("fetch", mockFetch);
    renderSubmit("FAKE.JWT.TOKEN");

    fireEvent.change(screen.getByLabelText(/describe the records you want/i), {
      target: { value: "too short" }, // 9 chars
    });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /submit request/i }));
    });

    const alert = screen.getByRole("alert");
    expect(alert.textContent).toMatch(/at least 10 characters/i);
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("successful submission: shows the tracking ID returned by the server", async () => {
    const mockFetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          request_id: "11111111-2222-3333-4444-555555555555",
          status: "received",
          submitted_at: "2026-04-22T21:00:00+00:00",
          message: "Your request has been submitted. Save your tracking id.",
        }),
    });
    vi.stubGlobal("fetch", mockFetch);

    renderSubmit("FAKE.JWT.TOKEN");

    fireEvent.change(screen.getByLabelText(/describe the records you want/i), {
      target: { value: "All City Council minutes from January 2026." },
    });

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /submit request/i }));
    });

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [callArgs] = mockFetch.mock.calls;
    expect(callArgs[0]).toMatch(/\/api\/public\/requests$/);

    // Tracking ID surfaces on screen after success.
    expect(
      screen.getByText(/11111111-2222-3333-4444-555555555555/)
    ).toBeInTheDocument();
    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /submit another request/i })
    ).toBeInTheDocument();
  });
});
