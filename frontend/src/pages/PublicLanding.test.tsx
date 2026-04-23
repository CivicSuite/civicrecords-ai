import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect, vi } from "vitest";
import PublicLanding from "./PublicLanding";

/**
 * T5D — PublicLanding tests.
 *
 * Covers the two states that matter for the locked B4 minimal surface:
 * unauthenticated (shows register + sign-in CTAs) and authenticated
 * resident (shows submit + sign-out CTAs). No anonymous-submission copy
 * anywhere — residents must register or sign in before submitting.
 */

describe("PublicLanding (T5D)", () => {
  function renderLanding(authenticated: boolean, onSignOut = vi.fn()) {
    return render(
      <MemoryRouter initialEntries={["/public"]}>
        <PublicLanding authenticated={authenticated} onSignOut={onSignOut} />
      </MemoryRouter>
    );
  }

  it("unauthenticated: shows register + sign-in CTAs, no submission button", () => {
    renderLanding(false);

    expect(
      screen.getByRole("heading", { name: /records request portal/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /create a resident account/i })
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument();
    // Must NOT show a submit CTA to an unauthenticated visitor.
    expect(
      screen.queryByRole("button", { name: /submit a records request/i })
    ).not.toBeInTheDocument();
  });

  it("authenticated: shows submit CTA and sign-out, no register CTA", () => {
    const onSignOut = vi.fn();
    renderLanding(true, onSignOut);

    expect(
      screen.getByRole("button", { name: /submit a records request/i })
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sign out/i })).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /create a resident account/i })
    ).not.toBeInTheDocument();
  });

  it("authenticated: sign-out button invokes the handler", () => {
    const onSignOut = vi.fn();
    renderLanding(true, onSignOut);

    fireEvent.click(screen.getByRole("button", { name: /sign out/i }));
    expect(onSignOut).toHaveBeenCalledTimes(1);
  });

  it("copy states plainly that a resident account is required — no anonymous language", () => {
    renderLanding(false);
    // Regression: prior planning debated anonymous submission. Scott
    // Option A 2026-04-22 = register-first; copy must not contradict.
    const html = document.body.innerHTML.toLowerCase();
    expect(html).toContain("resident account is required");
    expect(html).not.toContain("anonymous");
  });
});
