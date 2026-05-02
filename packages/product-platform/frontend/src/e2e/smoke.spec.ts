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
  await page.route("**/api/v1/organizations", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: [{ id: "org_default", name: "Ophanix Demo" }]
    });
  });
  await page.route("**/api/v1/environments", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: [{ id: "env_default", organization_id: "org_default", name: "Development" }]
    });
  });
  await page.route("**/api/v1/agents?**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: [
        {
          id: "agent_smoke",
          name: "Smoke Agent",
          status: "active",
          framework: "langgraph",
          owner_user_id: "owner_1",
          sponsor_user_id: "sponsor_1",
          credential_status: "active",
          capability_count: 1
        }
      ]
    });
  });
  await page.route("**/api/v1/agents/agent_smoke", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        summary: {
          id: "agent_smoke",
          name: "Smoke Agent",
          status: "active",
          framework: "langgraph",
          owner_user_id: "owner_1",
          sponsor_user_id: "sponsor_1",
          credential_status: "active"
        },
        identity: { did: "did:mesh:smoke", public_key_fingerprint: "fingerprint_smoke" },
        capabilities: [{ capability_name: "claims:read" }],
        lifecycle_events: [],
        auditEvents: []
      }
    });
  });
  await page.route("**/api/v1/agents/agent_smoke/timeline", async (route) => {
    await route.fulfill({ contentType: "application/json", json: [] });
  });
  await page.route("**/api/v1/agents/agent_smoke/audit", async (route) => {
    await route.fulfill({ contentType: "application/json", json: [] });
  });
  await page.route("**/api/v1/agents/agent_smoke/credentials", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: [
        {
          id: "cred_smoke",
          status: "active",
          issuer: "local-agentmesh",
          expires_at: "2026-05-02T12:00:00Z",
          scopes: [{ scope: "claims:read" }]
        }
      ]
    });
  });
  await page.route("**/api/v1/credentials/expiring?**", async (route) => {
    await route.fulfill({ contentType: "application/json", json: [] });
  });
  await page.route("**/api/v1/discovery/scanners", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: [
        {
          id: "scanner_config",
          scanner_type: "config",
          name: "Config Scanner",
          status: "available",
          available: true,
          required_config: ["paths"]
        }
      ]
    });
  });
  await page.route("**/api/v1/discovery/targets", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: [
        {
          id: "target_smoke",
          scanner_type: "config",
          target_type: "filesystem",
          target_value: "/repo",
          schedule_mode: "manual"
        }
      ]
    });
  });
  await page.route("**/api/v1/discovery/runs", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: [
        {
          id: "run_smoke",
          scanner_type: "config",
          target_id: "target_smoke",
          status: "succeeded",
          started_at: "2026-05-02T10:00:00Z",
          finished_at: "2026-05-02T10:00:02Z",
          raw_finding_count: 1,
          raw_findings: [
            {
              id: "raw_smoke",
              fingerprint: "fp_smoke",
              raw_payload_json: { name: "Smoke Crew" }
            }
          ]
        }
      ]
    });
  });
  await page.route("**/api/v1/discovery/findings**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: [
        {
          id: "finding_smoke",
          fingerprint: "fp_smoke",
          detected_name: "Smoke Crew",
          status: "shadow_candidate",
          risk_level: "critical",
          risk_score: 80,
          source: "/repo/agentmesh.yaml",
          risk_factors: ["No assigned owner"],
          evidence: [{ id: "evd_smoke", evidence_type: "config_file", evidence_value: "/repo/agentmesh.yaml" }]
        }
      ]
    });
  });

  await page.goto("/login");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();

  for (const name of ["Agents", "Discovery", "Policies", "MCP Security", "Runtime", "Demo Lab"]) {
    await page.getByRole("link", { name }).click();
    await expect(page.getByRole("heading", { name })).toBeVisible();
  }
  await page.getByRole("link", { name: "Agents" }).click();
  await expect(page.getByRole("heading", { name: "Smoke Agent" })).toBeVisible();
  await page.getByRole("link", { name: "Discovery" }).click();
  await expect(page.getByText("Config Scanner")).toBeVisible();
  await expect(page.getByRole("cell", { name: "Smoke Crew" })).toBeVisible();
});
