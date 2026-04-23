import { render, screen, fireEvent, act } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import PublicRegister from "./PublicRegister";

/**
 * T5D — PublicRegister tests.
 *
 * Covers label/input association (a11y), client-side validation with a
 * ``role="alert"`` actionable error message, and the success path where
 * register → login → onLogin callback fires.
 */

describe("PublicRegister (T5D)", () => {
  beforeEach(() => {
    // Default fetch stub: unused by tests that don't submit.
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

  function renderRegister(onLogin = vi.fn()) {
    return render(
      <MemoryRouter initialEntries={["/public/register"]}>
        <PublicRegister onLogin={onLogin} />
      </MemoryRouter>
    );
  }

  it("associates each label with its input via htmlFor/id", () => {
    renderRegister();

    const email = screen.getByLabelText(/email/i) as HTMLInputElement;
    expect(email.id).toBe("public-register-email");
    expect(email.getAttribute("aria-required")).toBe("true");

    const name = screen.getByLabelText(/full name/i) as HTMLInputElement;
    expect(name.id).toBe("public-register-name");

    const password = screen.getByLabelText(/^password$/i) as HTMLInputElement;
    expect(password.id).toBe("public-register-password");
    expect(password.getAttribute("aria-required")).toBe("true");
  });

  it("short password surfaces an actionable role=alert error and does not POST", async () => {
    const mockFetch = vi.fn();
    vi.stubGlobal("fetch", mockFetch);
    renderRegister();

    fireEvent.change(screen.getByLabelText(/email/i), {
      target: { value: "resident@example.com" },
    });
    fireEvent.change(screen.getByLabelText(/^password$/i), {
      target: { value: "short" },
    });
    fireEvent.click(screen.getByRole("button", { name: /create account/i }));

    const alert = screen.getByRole("alert");
    expect(alert.textContent).toMatch(/at least 8 characters/i);
    // Validation should short-circuit before network traffic.
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("empty email surfaces an actionable error", () => {
    renderRegister();

    fireEvent.change(screen.getByLabelText(/^password$/i), {
      target: { value: "longEnoughPassword" },
    });
    fireEvent.click(screen.getByRole("button", { name: /create account/i }));

    const alert = screen.getByRole("alert");
    expect(alert.textContent).toMatch(/email/i);
  });

  it("successful register + login fires onLogin with the returned token", async () => {
    const onLogin = vi.fn();

    // Two sequential fetches: register then login.
    const mockFetch = vi.fn()
      // POST /api/auth/register
      .mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            id: "00000000-0000-0000-0000-000000000001",
            email: "resident@example.com",
            role: "public",
          }),
      })
      // POST /api/auth/jwt/login
      .mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({ access_token: "FAKE.JWT.TOKEN", token_type: "bearer" }),
      });
    vi.stubGlobal("fetch", mockFetch);

    renderRegister(onLogin);

    fireEvent.change(screen.getByLabelText(/email/i), {
      target: { value: "resident@example.com" },
    });
    fireEvent.change(screen.getByLabelText(/full name/i), {
      target: { value: "Test Resident" },
    });
    fireEvent.change(screen.getByLabelText(/^password$/i), {
      target: { value: "longEnoughPassword" },
    });

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /create account/i }));
    });

    // Register was called with POST to /api/auth/register.
    expect(mockFetch).toHaveBeenCalledTimes(2);
    const [firstCall] = mockFetch.mock.calls;
    expect(firstCall[0]).toMatch(/\/api\/auth\/register$/);
    // onLogin was fired with the JWT from the login call.
    expect(onLogin).toHaveBeenCalledWith("FAKE.JWT.TOKEN");
  });
});
