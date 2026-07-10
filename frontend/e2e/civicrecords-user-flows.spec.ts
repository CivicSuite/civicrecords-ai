import { expect, test, type Page } from "@playwright/test";

function fakeJwt(role: string) {
  const header = btoa(JSON.stringify({ alg: "none", typ: "JWT" }));
  const payload = btoa(
    JSON.stringify({
      sub: "user-1",
      email: `${role}@example.gov`,
      exp: Math.floor(Date.now() / 1000) + 3600,
    }),
  );
  return `${header}.${payload}.signature`;
}

async function mockApi(page: Page, role: "admin" | "public" = "admin") {
  await page.route("**/api/config/portal-mode", route =>
    route.fulfill({ json: { mode: "public" } }),
  );
  await page.route("**/api/users/me", route =>
    route.fulfill({ json: { email: `${role}@example.gov`, full_name: `${role} user`, role } }),
  );
  await page.route("**/api/admin/status", route =>
    route.fulfill({
      json: {
        version: "1.6.0-recovery",
        database: "connected",
        redis: "connected",
        ollama: "connected",
        user_count: 4,
        audit_log_count: 12,
      },
    }),
  );
  await page.route("**/api/analytics/operational", route =>
    route.fulfill({
      json: {
        average_response_time_days: 2.5,
        median_response_time_days: 2,
        requests_by_status: { new: 3, in_review: 2 },
        requests_by_department: { Clerk: 5 },
        deadline_compliance_rate: 98.5,
        total_open: 5,
        total_closed: 9,
        total_overdue: 0,
        clarification_frequency: 1,
        top_request_topics: ["permits"],
      },
    }),
  );
  await page.route("**/api/admin/audit-log?limit=10", route => route.fulfill({ json: [] }));
  await page.route("**/api/admin/coverage-gaps", route =>
    route.fulfill({
      json: {
        jurisdictions_without_rules: [],
        departments_without_staff: [],
        uncovered_categories: [],
        total_gaps: 0,
      },
    }),
  );
  await page.route("**/api/requests/?limit=100", route => route.fulfill({ json: [] }));
  await page.route("**/api/public/requests", async route => {
    const body = route.request().postDataJSON();
    if (!body.description || body.description.length < 10) {
      await route.fulfill({ status: 422, json: { detail: "Description is too short." } });
      return;
    }
    await route.fulfill({
      json: {
        request_id: "REQ-2026-0001",
        status: "submitted",
        submitted_at: "2026-05-07T12:00:00Z",
        message: "Save this tracking ID before closing the page.",
      },
    });
  });
}

test.describe("CivicSunshine user flows (mock-labeled)", () => {
  test("staff can load dashboard and navigate with keyboard-visible shell", async ({ page }) => {
    await mockApi(page, "admin");
    await page.addInitScript(token => localStorage.setItem("token", token), fakeJwt("admin"));
    await page.goto("/");

    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
    await expect(page.getByText("CivicSunshine v1.6.0-recovery")).toBeVisible();
    await expect(page.getByText("Database (PostgreSQL)")).toBeVisible();

    await page.keyboard.press("Tab");
    await expect(page.getByRole("link", { name: "Skip to main content" })).toBeFocused();

    if (page.viewportSize()?.width && page.viewportSize()!.width < 768) {
      await page.getByRole("button", { name: "Open navigation" }).click();
      await expect(page.getByRole("dialog", { name: "Primary navigation" })).toBeVisible();
      await page.getByRole("button", { name: "Close navigation" }).click();
    }
  });

  test("resident public request flow shows validation, success, and tracking ID", async ({ page }) => {
    await mockApi(page, "public");
    await page.addInitScript(token => localStorage.setItem("token", token), fakeJwt("public"));
    await page.goto("/public/submit");

    await expect(page.getByRole("heading", { name: "Submit a records request" })).toBeVisible();
    await page.getByRole("button", { name: "Submit request" }).click();
    await expect(page.getByRole("alert")).toContainText("Please describe your request");

    await page.getByLabel("Describe the records you want").fill("All City Council packets for April 2026.");
    await page.getByRole("button", { name: "Submit request" }).click();
    await expect(page.getByRole("status")).toContainText("Your request has been submitted");
    await expect(page.getByText("REQ-2026-0001")).toBeVisible();
    await expect(page.getByRole("button", { name: "Submit another request" })).toBeVisible();
  });
});
