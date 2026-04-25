import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import Settings from "./Settings";

/**
 * QA-001 — Settings must only display rows backed by real backend fields.
 *
 * The /admin/status endpoint returns exactly:
 *   version, database, ollama, redis, user_count, audit_log_count.
 *
 * Earlier revisions of Settings.tsx rendered "SMTP Configuration",
 * "Audit Retention", "Data Sovereignty", and "Current Model" rows whose
 * values were derived from fields the backend never returned — producing
 * labels like "Not configured" / "Verified" / "Default" that looked like
 * sourced facts but were rendered from `undefined`. These tests pin the
 * page to truthful content: only the four system-info rows render, and the
 * fake rows are gone.
 */

const HEALTH_OK = { status: "ok", version: "1.3.0" };
const STATUS_HEALTHY = {
  version: "1.3.0",
  database: "connected",
  ollama: "connected",
  redis: "connected",
  user_count: 3,
  audit_log_count: 42,
};

function stubFetch() {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation((url: string) => {
      if (url.includes("/health")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(HEALTH_OK) });
      }
      if (url.includes("/admin/status")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(STATUS_HEALTHY) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    })
  );
}

describe("Settings — System Info truth surface (QA-001)", () => {
  beforeEach(() => {
    stubFetch();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders exactly the four rows backed by real backend fields", async () => {
    render(<Settings token="test-token" />);

    // Wait for the content to load.
    await waitFor(() => {
      expect(screen.getByText("Version")).toBeInTheDocument();
    });

    // The four legitimate rows.
    expect(screen.getByText("Version")).toBeInTheDocument();
    expect(screen.getByText("Database (PostgreSQL)")).toBeInTheDocument();
    expect(screen.getByText("Ollama (LLM Engine)")).toBeInTheDocument();
    expect(screen.getByText("Redis (Task Queue)")).toBeInTheDocument();

    // Values come through verbatim from the backend — no invented text.
    expect(screen.getByText("v1.3.0")).toBeInTheDocument();
    expect(screen.getAllByText("connected").length).toBe(3);
  });

  it("does NOT render rows whose values would be synthesized from undefined", async () => {
    render(<Settings token="test-token" />);
    await waitFor(() => {
      expect(screen.getByText("Database (PostgreSQL)")).toBeInTheDocument();
    });

    // None of these labels or synthesized values must appear on the page —
    // they depend on fields the backend does not return.
    expect(screen.queryByText(/smtp configuration/i)).toBeNull();
    expect(screen.queryByText(/audit retention/i)).toBeNull();
    expect(screen.queryByText(/data sovereignty/i)).toBeNull();
    expect(screen.queryByText(/current model/i)).toBeNull();

    // And the specific guessed labels must not appear either.
    expect(screen.queryByText(/not configured/i)).toBeNull();
    expect(screen.queryByText(/^verified$/i)).toBeNull();
    expect(screen.queryByText(/not verified/i)).toBeNull();
  });

  it("System Info is the only Card on the page", async () => {
    const { container } = render(<Settings token="test-token" />);
    await waitFor(() => {
      expect(screen.getByText("System Info")).toBeInTheDocument();
    });

    // Every Card in this page renders a CardTitle. There must be exactly one
    // CardTitle ("System Info") — no other "Email & Notifications", "Audit &
    // Compliance", or "AI / LLM Configuration" cards.
    const titles = container.querySelectorAll('[data-slot="card-title"]');
    expect(titles.length).toBe(1);
    expect(titles[0].textContent).toBe("System Info");
  });
});
