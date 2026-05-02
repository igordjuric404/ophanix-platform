import { expect, test } from "@playwright/test";

test("dev login and top-level navigation smoke", async ({ page }) => {
  await page.route("**/api/v1/auth/dev-login", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        access_token: "token",
        token_type: "bearer",
        expires_at: 1,
        user: {
          id: "user_1",
          email: "admin@example.com",
          display_name: "admin",
          roles: ["Platform Admin"]
        }
      }
    });
  });
  await page.route("**/api/v1/auth/me", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        id: "user_1",
        email: "admin@example.com",
        display_name: "admin",
        roles: ["Platform Admin"]
      }
    });
  });
  await page.route("**/api/v1/system/dependencies", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: [{ name: "database", status: "healthy", details: "sqlite ready" }]
    });
  });
  await page.route("**/api/v1/version", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: { build_sha: "test-sha", environment: "test" }
    });
  });

  await page.goto("/login");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();

  for (const name of ["Agents", "Policies", "MCP Security", "Runtime", "Demo Lab"]) {
    await page.getByRole("link", { name }).click();
    await expect(page.getByRole("heading", { name })).toBeVisible();
  }
});
