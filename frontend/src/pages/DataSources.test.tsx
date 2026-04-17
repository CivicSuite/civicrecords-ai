import { describe, it, expect } from "vitest";
import { formatNextRun } from "./DataSources";

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
