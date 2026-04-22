import { render, screen, act, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { AppShell } from "./app-shell";

/**
 * T4A — Responsive AppShell.
 *
 * Below the md breakpoint (< 768px) the sidebar must collapse into a
 * drawer that opens via an accessible hamburger button. The drawer must
 * expose a dialog role for focus trapping, ARIA controls must wire the
 * button to the drawer, and the hamburger must be hidden on desktop.
 */
describe("AppShell — responsive drawer (T4A)", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  function renderShell() {
    return render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <AppShell userEmail="admin@example.gov" userRole="admin" onSignOut={vi.fn()}>
          <div data-testid="content">Main content</div>
        </AppShell>
      </MemoryRouter>
    );
  }

  it("renders a hamburger button with accessible name 'Open navigation'", () => {
    renderShell();
    const btn = screen.getByRole("button", { name: /open navigation/i });
    expect(btn).toBeInTheDocument();
    // It targets the mobile nav container via aria-controls.
    expect(btn.getAttribute("aria-controls")).toBe("app-mobile-nav");
    // Initially collapsed.
    expect(btn.getAttribute("aria-expanded")).toBe("false");
  });

  it("opens the mobile drawer when hamburger is clicked and exposes a dialog role", () => {
    renderShell();
    const btn = screen.getByRole("button", { name: /open navigation/i });
    act(() => {
      fireEvent.click(btn);
    });
    // aria-expanded flips to true
    expect(btn.getAttribute("aria-expanded")).toBe("true");
    // A dialog appears (Base UI renders the Popup with role=dialog)
    const dialog = screen.getByRole("dialog");
    expect(dialog).toBeInTheDocument();
    // It is labelled "Primary navigation"
    expect(dialog.getAttribute("aria-label")).toBe("Primary navigation");
  });

  it("closes the mobile drawer when the Close button is clicked", () => {
    renderShell();
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: /open navigation/i }));
    });
    expect(screen.getByRole("dialog")).toBeInTheDocument();

    act(() => {
      fireEvent.click(screen.getByRole("button", { name: /close navigation/i }));
    });
    // Drawer is gone
    expect(screen.queryByRole("dialog")).toBeNull();
    // Hamburger collapsed again
    expect(screen.getByRole("button", { name: /open navigation/i }).getAttribute("aria-expanded")).toBe("false");
  });

  it("renders the desktop sidebar with accessible name 'Primary navigation'", () => {
    renderShell();
    // The desktop <aside> is aria-labelled even though it's hidden on mobile.
    const aside = screen.getByRole("complementary", { name: /primary navigation/i });
    expect(aside).toBeInTheDocument();
  });
});
