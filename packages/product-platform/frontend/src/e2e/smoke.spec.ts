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
  await page.route("**/api/v1/agents", async (route) => {
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
  const policy = {
    id: "policy_smoke",
    organization_id: "org_default",
    name: "Smoke Guardrail",
    slug: "smoke-guardrail",
    description: "Smoke policy",
    scope: "mcp-tool",
    owner_user_id: "user_1",
    status: "active",
    tags: ["smoke"],
    active_version_id: "pver_smoke",
    active_version_number: 1,
    version_count: 1,
    versions: [
      {
        id: "pver_smoke",
        policy_id: "policy_smoke",
        version_number: 1,
        body_format: "yaml",
        body_text: "version: '1.0'\nname: smoke\nrules: []\n",
        backend: "native",
        checksum: "sha256:smoke",
        status: "active",
        created_by: "user_1",
        created_at: "2026-05-02T10:00:00Z",
        activated_at: "2026-05-02T10:01:00Z"
      }
    ]
  };
  await page.route("**/api/v1/policies", async (route) => {
    await route.fulfill({ contentType: "application/json", json: [policy] });
  });
  await page.route("**/api/v1/policies?**", async (route) => {
    await route.fulfill({ contentType: "application/json", json: [policy] });
  });
  await page.route("**/api/v1/policies/policy_smoke", async (route) => {
    await route.fulfill({ contentType: "application/json", json: policy });
  });
  await page.route("**/api/v1/policies/policy_smoke/affected-resources", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        policy_id: "policy_smoke",
        active_binding_count: 1,
        resources: [
          {
            target_type: "agent",
            target_id: "agent_smoke",
            label: "Smoke Agent",
            status: "active",
            mode: "shadow",
            environment_id: "env_default"
          }
        ]
      }
    });
  });
  await page.route("**/api/v1/policy-bindings", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: [
        {
          id: "pbind_smoke",
          policy_id: "policy_smoke",
          policy_version_id: "pver_smoke",
          target_type: "agent",
          target_id: "agent_smoke",
          mode: "shadow",
          rollout_percentage: 25,
          priority: 10,
          status: "active"
        }
      ]
    });
  });
  await page.route("**/api/v1/policy-exceptions", async (route) => {
    await route.fulfill({ contentType: "application/json", json: [] });
  });
  await page.route("**/api/v1/policy-evaluations", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: [
        {
          id: "peval_smoke",
          policy_id: "policy_smoke",
          policy_version_id: "pver_smoke",
          agent_id: "agent_smoke",
          action: "mcp.tool_call",
          resource_type: "mcp-tool",
          resource_id: "demo.delete_customer",
          context: { tool_name: "delete_customer" },
          decision: "deny",
          matched_rule: "deny_delete_customer",
          reason: "Customer deletion requires approval.",
          latency_ms: 2,
          mode: "simulate",
          correlation_id: "corr-smoke-policy",
          backend: "native",
          created_at: "2026-05-02T10:02:00Z"
        }
      ]
    });
  });
  await page.route("**/api/v1/policy-evaluations/summary**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        total_count: 1,
        decision_counts: { deny: 1 },
        mode_counts: { simulate: 1 },
        action_counts: { "mcp.tool_call": 1 },
        time_buckets: [{ bucket: "2026-05-02", total_count: 1, decision_counts: { deny: 1 } }]
      }
    });
  });
  await page.route("**/api/v1/policy-evaluations/stream**", async (route) => {
    await route.fulfill({ contentType: "text/event-stream", body: "" });
  });
  const auditEvent = {
    id: "evt_policy_smoke",
    organization_id: "org_default",
    environment_id: "env_default",
    event_type: "policy.decision",
    source_component: "policy-engine",
    actor_type: "user",
    actor_id: "user_1",
    agent_id: "agent_smoke",
    resource_type: "policy_evaluation",
    resource_id: "peval_smoke",
    decision: "deny",
    severity: "warning",
    correlation_id: "corr-smoke-policy",
    policy_id: "policy_smoke",
    policy_version_id: "pver_smoke",
    payload_json: { matched_rule: "deny_delete_customer" },
    created_at: "2026-05-02T10:03:00Z"
  };
  await page.route("**/api/v1/audit/events/evt_policy_smoke/verify", async (route) => {
    await route.fulfill({ contentType: "application/json", json: { valid: true, checked_count: 1 } });
  });
  await page.route("**/api/v1/audit/events/evt_policy_smoke", async (route) => {
    await route.fulfill({ contentType: "application/json", json: auditEvent });
  });
  await page.route("**/api/v1/audit/events**", async (route) => {
    await route.fulfill({ contentType: "application/json", json: [auditEvent] });
  });
  await page.route("**/api/v1/compliance/frameworks", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: [{ id: "cf_smoke", name: "SOC 2", version: "2026", status: "active" }]
    });
  });
  await page.route("**/api/v1/compliance/controls**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: [
        {
          id: "ctrl_smoke",
          framework_id: "cf_smoke",
          framework_name: "SOC 2",
          control_code: "CC6.6",
          title: "Policy Enforcement",
          required_evidence_types: ["policy_decision"]
        }
      ]
    });
  });
  await page.route("**/api/v1/compliance/evidence**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: [
        {
          id: "evid_smoke",
          control_id: "ctrl_smoke",
          control_code: "CC6.6",
          source_type: "audit_event",
          source_id: "evt_policy_smoke",
          title: "policy_decision evidence from policy.decision",
          summary: "policy-engine recorded policy.decision decision=deny",
          freshness_at: "2026-05-02T10:03:00Z",
          status: "fresh"
        }
      ]
    });
  });
  await page.route("**/api/v1/compliance/violations**", async (route) => {
    await route.fulfill({ contentType: "application/json", json: [] });
  });
  const complianceReport = {
    id: "crep_smoke",
    framework_id: "cf_smoke",
    framework_name: "SOC 2",
    name: "SOC 2 Smoke Report",
    status: "generated",
    date_from: "2026-01-01",
    date_to: "2026-12-31",
    artifact_uri: "compliance-report://crep_smoke.md",
    evidence_item_ids: ["evid_smoke"],
    attestation_count: 0,
    rendered_markdown: "# SOC 2 Smoke Report\n\n## Evidence\n"
  };
  await page.route("**/api/v1/compliance/reports/crep_smoke", async (route) => {
    await route.fulfill({ contentType: "application/json", json: complianceReport });
  });
  await page.route("**/api/v1/compliance/reports**", async (route) => {
    await route.fulfill({ contentType: "application/json", json: [complianceReport] });
  });
  await page.route("**/api/v1/artifacts**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: [
        {
          id: "art_smoke",
          artifact_type: "compliance.report",
          name: "crep_smoke.md",
          checksum: "sha256-smoke-report",
          links: [{ target_type: "compliance_report", target_id: "crep_smoke" }]
        }
      ]
    });
  });

  await page.goto("/login");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();

  for (const name of ["Agents", "Discovery", "Policies", "Compliance", "MCP Security", "Runtime", "Demo Lab"]) {
    await page.getByRole("link", { name }).click();
    await expect(page.getByRole("heading", { name })).toBeVisible();
  }
  await page.getByRole("link", { name: "Agents" }).click();
  await expect(page.getByRole("heading", { name: "Smoke Agent" })).toBeVisible();
  await page.getByRole("link", { name: "Discovery" }).click();
  await expect(page.getByText("Config Scanner")).toBeVisible();
  await expect(page.getByRole("cell", { name: "Smoke Crew" })).toBeVisible();
  await page.getByRole("link", { name: "Policies" }).click();
  await expect(page.getByRole("cell", { name: /Smoke Guardrail/ }).first()).toBeVisible();
  await expect(page.getByText("Policy Decisions")).toBeVisible();
  await page.getByRole("link", { name: "Compliance" }).click();
  await expect(page.getByText("policy.decision").first()).toBeVisible();
  await expect(page.getByText("SOC 2 Smoke Report").first()).toBeVisible();
});
