import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import Dashboard from "./Dashboard";

/**
 * T4B — Dashboard service health indicators.
 *
 * The backend /admin/status endpoint returns flat string fields:
 *   { database: "connected", ollama: "connected", redis: "connected", ... }
 *
 * These tests pin the contract so a future refactor can't silently revert
 * Dashboard to the old nested {status: string} shape, which caused every
 * service to render as "disconnected" regardless of actual health.
 */

const HEALTHY_STATUS = {
  version: "1.3.0",
  database: "connected",
  ollama: "connected",
  redis: "connected",
  user_count: 3,
  audit_log_count: 42,
};

const DEGRADED_STATUS = {
  ...HEALTHY_STATUS,
  ollama: "error: connection refused",
  redis: "disconnected",
};

function stubFetch(systemStatus: Record<string, unknown>) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation((url: string) => {
      if (url.includes("/admin/status")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(systemStatus) });
      }
      // All other dashboard fetches return empty / null so we focus on services.
      if (url.includes("/analytics/operational")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(null) });
      }
      if (url.includes("/admin/audit-log")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
      }
      if (url.includes("/admin/coverage-gaps")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(null) });
      }
      if (url.includes("/requests")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    })
  );
}

describe("Dashboard — service health indicators (T4B)", () => {
  beforeEach(() => {
    vi.useRealTimers();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders all three services as connected when backend returns flat 'connected' strings", async () => {
    stubFetch(HEALTHY_STATUS);
    render(<Dashboard token="test-token" />);

    // Wait for Services card to appear
    await waitFor(() => {
      expect(screen.getByText("Database (PostgreSQL)")).toBeInTheDocument();
    });

    // Each service row contains a lucide-check-circle (not lucide-circle-x).
    // Query the SERVICES section and count success icons.
    const dbRow = screen.getByText("Database (PostgreSQL)").parentElement!;
    const ollamaRow = screen.getByText("Ollama (LLM Engine)").parentElement!;
    const redisRow = screen.getByText("Redis (Task Queue)").parentElement!;

    expect(dbRow.querySelector(".lucide-circle-check-big")).toBeTruthy();
    expect(ollamaRow.querySelector(".lucide-circle-check-big")).toBeTruthy();
    expect(redisRow.querySelector(".lucide-circle-check-big")).toBeTruthy();

    // And there should be NO XCircle (destructive) icons in those rows.
    expect(dbRow.querySelector(".lucide-circle-x")).toBeFalsy();
    expect(ollamaRow.querySelector(".lucide-circle-x")).toBeFalsy();
    expect(redisRow.querySelector(".lucide-circle-x")).toBeFalsy();
  });

  it("renders degraded services with destructive icon when backend reports disconnected/error", async () => {
    stubFetch(DEGRADED_STATUS);
    render(<Dashboard token="test-token" />);

    await waitFor(() => {
      expect(screen.getByText("Database (PostgreSQL)")).toBeInTheDocument();
    });

    const dbRow = screen.getByText("Database (PostgreSQL)").parentElement!;
    const ollamaRow = screen.getByText("Ollama (LLM Engine)").parentElement!;
    const redisRow = screen.getByText("Redis (Task Queue)").parentElement!;

    // Database is connected → check icon
    expect(dbRow.querySelector(".lucide-circle-check-big")).toBeTruthy();
    // Ollama errored → x icon
    expect(ollamaRow.querySelector(".lucide-circle-x")).toBeTruthy();
    // Redis disconnected → x icon
    expect(redisRow.querySelector(".lucide-circle-x")).toBeTruthy();
  });

  it("regression: does NOT treat nested {status: ...} objects as connected", async () => {
    // If the shape ever regresses, this stub simulates the old broken contract.
    // With the current flat-string code, both readings should surface as
    // non-connected because "[object Object]" isn't one of the healthy values.
    stubFetch({
      version: "1.3.0",
      database: { status: "connected" } as unknown as string,
      ollama: { status: "connected" } as unknown as string,
      redis: { status: "connected" } as unknown as string,
      user_count: 0,
      audit_log_count: 0,
    });
    render(<Dashboard token="test-token" />);

    await waitFor(() => {
      expect(screen.getByText("Database (PostgreSQL)")).toBeInTheDocument();
    });

    // Flat-string code sees an object, not "connected" — so it must render x icons.
    // This is the intentional guard: any future refactor that accepts nested
    // objects silently (the old bug) will flip this back to lucide-circle-check-big
    // and this test will fail.
    const dbRow = screen.getByText("Database (PostgreSQL)").parentElement!;
    expect(dbRow.querySelector(".lucide-circle-x")).toBeTruthy();
  });
});
