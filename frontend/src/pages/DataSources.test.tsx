import { render, screen, act, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import DataSources, { formatNextRun } from "./DataSources";

describe("formatNextRun", () => {
  it("returns a next-run string for a valid cron expression", () => {
    const result = formatNextRun("0 2 * * *"); // nightly at 2am UTC
    // Must be non-empty and contain 'Next:' with a time reference
    expect(result).toMatch(/^Next:/);
    expect(result).toMatch(/2:00 AM UTC/);
    expect(result).toContain("UTC");
  });

  it("returns empty string for an invalid cron expression", () => {
    expect(formatNextRun("not-a-cron")).toBe("");
    expect(formatNextRun("99 99 99 99 99")).toBe("");
  });

  it("shows data-testid=cron-preview content format", () => {
    const result = formatNextRun("*/15 * * * *");
    // Every 15 min — should produce a non-empty preview
    expect(result).toMatch(/^Next:/);
  });
});

/**
 * T4C — Add Data Source wizard: labels must be programmatically
 * associated with their inputs, and validation errors must announce
 * via role="alert" with actionable copy instead of silently blocking.
 */
describe("DataSources — Add Source wizard accessibility + validation (T4C)", () => {
  beforeEach(() => {
    // All GETs return empty so the page renders the empty state quickly.
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((_url: string, _opts?: RequestInit) => {
        return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
      })
    );
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  async function openWizard() {
    render(<DataSources token="test-token" />);
    // Wait past the loading skeleton
    const addBtn = await screen.findByRole("button", { name: /add source/i });
    await act(async () => {
      fireEvent.click(addBtn);
    });
  }

  it("associates the Source Name label with its input via htmlFor/id", async () => {
    await openWizard();

    const nameInput = screen.getByLabelText(/source name/i) as HTMLInputElement;
    // getByLabelText only returns a match when label → input is programmatically linked.
    expect(nameInput).toBeInTheDocument();
    expect(nameInput.id).toBe("ds-name");
    expect(nameInput.getAttribute("aria-required")).toBe("true");
  });

  it("exposes the Source Type group as a radiogroup with aria-checked radios", async () => {
    await openWizard();

    const group = screen.getByRole("radiogroup", { name: /source type/i });
    expect(group).toBeInTheDocument();

    const radios = screen.getAllByRole("radio");
    expect(radios.length).toBeGreaterThanOrEqual(4);
    // Default selection is File System → must be aria-checked="true"
    const fileSystem = screen.getByRole("radio", { name: /file system/i });
    expect(fileSystem.getAttribute("aria-checked")).toBe("true");
    // Others must be aria-checked="false"
    const restApi = screen.getByRole("radio", { name: /rest api/i });
    expect(restApi.getAttribute("aria-checked")).toBe("false");
  });

  it("blocks Next on empty name and announces an actionable role=alert error", async () => {
    await openWizard();

    const next = screen.getByRole("button", { name: /^next$/i });
    await act(async () => {
      fireEvent.click(next);
    });

    // Must surface a role=alert with actionable copy, NOT silently stay put.
    const alert = screen.getByRole("alert");
    expect(alert.textContent).toMatch(/enter a name/i);
    expect(alert.textContent).toMatch(/identify it later/i);

    // Input must be marked aria-invalid so ATs read it as invalid
    const nameInput = screen.getByLabelText(/source name/i);
    expect(nameInput.getAttribute("aria-invalid")).toBe("true");
    expect(nameInput.getAttribute("aria-describedby")).toContain("ds-name-error");
  });

  it("clears the field error as soon as the user starts typing a valid value", async () => {
    await openWizard();

    // Trigger the error
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /^next$/i }));
    });
    expect(screen.getByRole("alert").textContent).toMatch(/enter a name/i);

    // User starts fixing it
    const nameInput = screen.getByLabelText(/source name/i);
    await act(async () => {
      fireEvent.change(nameInput, { target: { value: "City Clerk Archive" } });
    });

    // Error should be gone, aria-invalid gone.
    expect(screen.queryByRole("alert")).toBeNull();
    expect(nameInput.getAttribute("aria-invalid")).toBeNull();
  });

  it("step 2 Directory Path: blocks Next with an actionable role=alert error", async () => {
    await openWizard();

    // Fill step 1 name and advance to step 2
    const nameInput = screen.getByLabelText(/source name/i);
    await act(async () => {
      fireEvent.change(nameInput, { target: { value: "My Source" } });
    });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /^next$/i }));
    });

    // Step 2: empty path → Next should not advance, error must show
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /^next$/i }));
    });

    const pathInput = screen.getByLabelText(/directory path/i);
    expect(pathInput.id).toBe("ds-path");
    expect(pathInput.getAttribute("aria-invalid")).toBe("true");

    const alert = screen.getByRole("alert");
    expect(alert.textContent).toMatch(/enter the full directory path/i);
    expect(alert.textContent).toMatch(/\/mnt\/records/i);

    // aria-describedby should include BOTH the hint and the error id
    const describedBy = pathInput.getAttribute("aria-describedby") || "";
    expect(describedBy).toContain("ds-path-hint");
    expect(describedBy).toContain("ds-path-error");
  });
});
