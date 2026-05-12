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
      json: [{ name: "database", status: "healthy", details: "postgresql ready" }]
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

  const marketplacePlugin = {
    id: "plug_smoke",
    organization_id: "org_default",
    name: "Claims Assistant",
    description: "Claims workflow governance pack",
    publisher: "Ophanix",
    plugin_type: "integration",
    status: "available",
    created_at: "2026-05-02T10:00:00Z",
    updated_at: "2026-05-02T10:00:00Z",
    versions: [
      {
        id: "plugver_smoke",
        plugin_id: "plug_smoke",
        version: "1.0.0",
        manifest: { name: "Claims Assistant", version: "1.0.0", plugin_type: "integration" },
        package_ref: "registry://claims-assistant",
        signature_status: "signed",
        quality_score: 0.91,
        trust_tier: "trusted",
        required_capabilities: ["claims.lookup"],
        permissions: ["mcp.invoke"],
        created_at: "2026-05-02T10:00:00Z",
        updated_at: "2026-05-02T10:00:00Z"
      }
    ]
  };
  const marketplaceInstallation = {
    id: "install_smoke",
    plugin_version_id: "plugver_smoke",
    plugin_name: "Claims Assistant",
    version: "1.0.0",
    environment_id: "env_default",
    target_agent_id: "agent_smoke",
    target_agent_name: "Smoke Agent",
    status: "installed",
    installed_by: "user_1",
    installed_at: "2026-05-02T10:01:00Z",
    uninstalled_at: null
  };
  const marketplaceReview = {
    id: "review_smoke",
    plugin_version_id: "plugver_smoke",
    plugin_name: "Claims Assistant",
    version: "1.0.0",
    status: "pending",
    reviewer_id: null,
    findings: [{ code: "manual_review", message: "Manual review requested" }],
    decision_reason: null,
    created_at: "2026-05-02T10:02:00Z",
    decided_at: null
  };
  const marketplaceSigningKey = {
    id: "sign_smoke",
    organization_id: "org_default",
    name: "Marketplace Root",
    public_key: "pk_smoke",
    status: "active",
    created_by: "user_1",
    created_at: "2026-05-02T10:03:00Z",
    revoked_at: null
  };
  await page.route("**/api/v1/marketplace/**", async (route) => {
    const { pathname } = new URL(route.request().url());
    if (pathname === "/api/v1/marketplace/plugins/plug_smoke") {
      await route.fulfill({ contentType: "application/json", json: marketplacePlugin });
      return;
    }
    if (pathname === "/api/v1/marketplace/plugins") {
      await route.fulfill({ contentType: "application/json", json: [marketplacePlugin] });
      return;
    }
    if (pathname === "/api/v1/marketplace/installations") {
      await route.fulfill({ contentType: "application/json", json: [marketplaceInstallation] });
      return;
    }
    if (pathname === "/api/v1/marketplace/reviews") {
      await route.fulfill({ contentType: "application/json", json: [marketplaceReview] });
      return;
    }
    if (pathname === "/api/v1/marketplace/signing-keys") {
      await route.fulfill({ contentType: "application/json", json: [marketplaceSigningKey] });
      return;
    }
    await route.fulfill({ contentType: "application/json", json: [] });
  });

  const observabilitySlo = {
    id: "slo_smoke",
    organization_id: "org_default",
    environment_id: "env_default",
    name: "Task Success",
    target_type: "agent",
    target_id: "agent_smoke",
    sli: "task_success_rate",
    target_value: 0.95,
    window: "30d",
    status: "healthy",
    created_by: "user_1",
    created_at: "2026-05-02T10:00:00Z",
    updated_at: "2026-05-02T10:00:00Z",
    measurements: [
      {
        id: "slomeas_smoke",
        slo_id: "slo_smoke",
        value: 0.97,
        good_events: 97,
        total_events: 100,
        error_budget_remaining: 0.8,
        burn_rate: 0.2,
        status: "healthy",
        metadata: { source: "smoke" },
        measured_at: "2026-05-02T10:00:00Z"
      }
    ]
  };
  const observabilityCosts = {
    budgets: [
      {
        id: "costbud_smoke",
        organization_id: "org_default",
        environment_id: "env_default",
        target_type: "agent",
        target_id: "agent_smoke",
        period: "monthly",
        amount_limit: 100,
        used_amount: 12.5,
        action_on_breach: "warn",
        breach_action: "none",
        status: "healthy",
        created_by: "user_1",
        created_at: "2026-05-02T10:00:00Z",
        updated_at: "2026-05-02T10:00:00Z"
      }
    ],
    events: [
      {
        id: "costevt_smoke",
        organization_id: "org_default",
        environment_id: "env_default",
        target_type: "agent",
        target_id: "agent_smoke",
        provider: "openai",
        model: "gpt",
        amount: 1.25,
        units: 1000,
        correlation_id: "corr_cost",
        created_at: "2026-05-02T10:00:00Z"
      }
    ],
    total_amount: 12.5,
    by_target: { agent_smoke: 12.5 },
    by_provider: { openai: 12.5 },
    by_model: { gpt: 12.5 }
  };
  const observabilityIncident = {
    id: "inc_smoke",
    organization_id: "org_default",
    environment_id: "env_default",
    severity: "critical",
    status: "open",
    title: "Denial Spike",
    summary: "Policy denials crossed the incident threshold.",
    owner_user_id: null,
    correlation_id: "corr_inc",
    source_event_id: "evt_policy_smoke",
    resolution_note: null,
    started_at: "2026-05-02T10:00:00Z",
    acknowledged_at: null,
    resolved_at: null,
    updated_at: "2026-05-02T10:00:00Z",
    related_event_ids: ["evt_policy_smoke"]
  };
  const observabilityExperiment = {
    id: "chaos_smoke",
    organization_id: "org_default",
    environment_id: "env_default",
    name: "Latency Drill",
    fault_type: "latency",
    target_type: "agent",
    target_id: "agent_smoke",
    blast_radius: { max_agents: 1 },
    guardrails: { max_error_rate: 0.05 },
    status: "ready",
    created_by: "user_1",
    created_at: "2026-05-02T10:00:00Z",
    updated_at: "2026-05-02T10:00:00Z"
  };
  const observabilityRollout = {
    id: "rollout_smoke",
    organization_id: "org_default",
    environment_id: "env_default",
    name: "Claims Canary",
    target_type: "agent",
    target_id: "agent_smoke",
    strategy: "canary",
    status: "active",
    current_stage: 5,
    config: { stages: [5, 25, 100], gates: { require_slo_healthy: true } },
    created_by: "user_1",
    created_at: "2026-05-02T10:00:00Z",
    updated_at: "2026-05-02T10:00:00Z",
    events: [
      {
        id: "rollevent_smoke",
        rollout_id: "rollout_smoke",
        stage: 5,
        decision: "advanced",
        metrics: { slo_status: "healthy" },
        created_at: "2026-05-02T10:00:00Z"
      }
    ]
  };
  await page.route("**/api/v1/observability/**", async (route) => {
    const { pathname } = new URL(route.request().url());
    if (pathname === "/api/v1/observability/slo") {
      await route.fulfill({ contentType: "application/json", json: [observabilitySlo] });
      return;
    }
    if (pathname === "/api/v1/observability/costs") {
      await route.fulfill({ contentType: "application/json", json: observabilityCosts });
      return;
    }
    if (pathname === "/api/v1/observability/incidents") {
      await route.fulfill({ contentType: "application/json", json: [observabilityIncident] });
      return;
    }
    if (pathname === "/api/v1/observability/chaos/experiments") {
      await route.fulfill({ contentType: "application/json", json: [observabilityExperiment] });
      return;
    }
    if (pathname === "/api/v1/observability/rollouts") {
      await route.fulfill({ contentType: "application/json", json: [observabilityRollout] });
      return;
    }
    await route.fulfill({ contentType: "application/json", json: [] });
  });

  const integrationFramework = {
    id: "openai_agents",
    integration_type: "framework",
    name: "OpenAI Agents",
    description: "Primary demo connector.",
    status: "primary_demo",
    supported_versions: ["0.2.x", "0.3.x"],
    setup_doc_url: "/docs/integrations/openai-agents",
    example_path: "packages/agent-os/examples/openai_agents",
    setup_snippet: "ophanix integrations init openai_agents",
    created_at: "2026-05-02T10:00:00Z",
    updated_at: "2026-05-02T10:00:00Z"
  };
  const frameworkInstance = {
    id: "fwinst_smoke",
    organization_id: "org_default",
    environment_id: "env_default",
    integration_id: "openai_agents",
    integration_name: "OpenAI Agents",
    name: "OpenAI demo connector",
    config: { project: "demo-project", token: "hidden" },
    status: "active",
    created_by: "user_1",
    created_at: "2026-05-02T10:10:00Z",
    updated_at: "2026-05-02T10:10:00Z"
  };
  const frameworkAgent = {
    id: "fwagent_smoke",
    integration_instance_id: "fwinst_smoke",
    integration_name: "OpenAI Agents",
    agent_id: "agent_smoke",
    agent_name: "Smoke Agent",
    framework_agent_ref: "assistant:smoke-support",
    sdk_version: "0.3.0",
    telemetry_status: "unknown",
    policy_coverage_status: "unknown",
    linked_at: "2026-05-02T10:20:00Z",
    updated_at: "2026-05-02T10:20:00Z"
  };
  const providerCredential = {
    id: "provcred_smoke",
    organization_id: "org_default",
    name: "OpenAI demo key",
    provider_type: "model_provider",
    secret_ref: "secref_smoke",
    masked_secret: "********",
    status: "active",
    created_by: "user_1",
    created_at: "2026-05-02T10:30:00Z",
    last_used_at: null
  };
  const integrationHealth = {
    id: "inthealth_smoke",
    organization_id: "org_default",
    environment_id: "env_default",
    target_type: "provider_credential",
    target_id: "provcred_smoke",
    status: "failed",
    latency_ms: 12,
    message: "Provider secret is invalid or missing.",
    details: {},
    checked_at: "2026-05-02T10:31:00Z"
  };
  await page.route("**/api/v1/integrations/**", async (route) => {
    const { pathname } = new URL(route.request().url());
    if (pathname === "/api/v1/integrations/frameworks") {
      await route.fulfill({ contentType: "application/json", json: [integrationFramework] });
      return;
    }
    if (pathname === "/api/v1/integrations/framework-instances") {
      await route.fulfill({ contentType: "application/json", json: [frameworkInstance] });
      return;
    }
    if (pathname === "/api/v1/integrations/framework-agents") {
      await route.fulfill({ contentType: "application/json", json: [frameworkAgent] });
      return;
    }
    if (pathname === "/api/v1/integrations/provider-credentials") {
      await route.fulfill({ contentType: "application/json", json: [providerCredential] });
      return;
    }
    if (pathname === "/api/v1/integrations/health-checks") {
      await route.fulfill({ contentType: "application/json", json: [integrationHealth] });
      return;
    }
    await route.fulfill({ contentType: "application/json", json: [] });
  });

  const workflowDefinition = {
    id: "policy_lint",
    organization_id: "org_default",
    name: "Policy Lint",
    workflow_type: "policy",
    command_ref: "python:policy.lint",
    input_schema: {
      type: "object",
      required: ["policy_body"],
      properties: {
        policy_body: { type: "string", title: "Policy Body" },
        policy_format: { type: "string", title: "Policy Format", default: "yaml" }
      }
    },
    enabled: true,
    created_at: "2026-05-02T10:00:00Z",
    updated_at: "2026-05-02T10:00:00Z"
  };
  const workflowRun = {
    id: "wrun_smoke",
    organization_id: "org_default",
    environment_id: "env_default",
    workflow_definition_id: "policy_lint",
    workflow_type: "policy",
    command_ref: "python:policy.lint",
    status: "queued",
    inputs: { policy_format: "yaml" },
    started_by: "user_1",
    started_at: "2026-05-02T10:00:01Z",
    finished_at: null,
    exit_code: null,
    summary: { passed: true, error_count: 0 },
    created_at: "2026-05-02T10:00:00Z",
    updated_at: "2026-05-02T10:00:02Z",
    logs: [
      {
        id: "wlog_smoke",
        workflow_run_id: "wrun_smoke",
        stream: "stdout",
        line_number: 1,
        message: "policy lint passed=True errors=0",
        created_at: "2026-05-02T10:00:02Z"
      }
    ]
  };
  const workflowArtifact = {
    id: "art_workflow_smoke",
    organization_id: "org_default",
    environment_id: "env_default",
    artifact_type: "workflow.output",
    name: "policy-lint-output.json",
    content_type: "application/json",
    storage_uri: "local-artifact://org_default/env_default/art_workflow_smoke/policy-lint-output.json",
    checksum: "1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
    size_bytes: 33,
    created_by: "user_1",
    created_at: "2026-05-02T10:00:03Z",
    links: [
      {
        id: "alink_smoke",
        artifact_id: "art_workflow_smoke",
        target_type: "workflow_run",
        target_id: "wrun_smoke",
        link_type: "output",
        created_at: "2026-05-02T10:00:03Z"
      }
    ],
    attestations: [
      {
        id: "aat_smoke",
        artifact_id: "art_workflow_smoke",
        attested_by: "user_1",
        statement: "Checksum reviewed.",
        signature_ref: "sig-smoke",
        created_at: "2026-05-02T10:00:04Z"
      }
    ]
  };
  const complianceArtifact = {
    id: "art_smoke",
    organization_id: "org_default",
    environment_id: "env_default",
    artifact_type: "compliance.report",
    name: "crep_smoke.md",
    content_type: "text/markdown",
    storage_uri: "compliance-report://crep_smoke.md",
    checksum: "sha256-smoke-report",
    size_bytes: 128,
    created_by: "user_1",
    created_at: "2026-05-02T10:00:00Z",
    links: [{ target_type: "compliance_report", target_id: "crep_smoke" }],
    attestations: []
  };
  await page.route("**/api/v1/workflows**", async (route) => {
    const { pathname } = new URL(route.request().url());
    if (pathname === "/api/v1/workflows") {
      await route.fulfill({ contentType: "application/json", json: [workflowDefinition] });
      return;
    }
    if (pathname === "/api/v1/workflows/policy_lint/runs") {
      await route.fulfill({ contentType: "application/json", json: workflowRun });
      return;
    }
    await route.fulfill({ contentType: "application/json", json: [] });
  });
  await page.route("**/api/v1/workflow-runs**", async (route) => {
    const { pathname } = new URL(route.request().url());
    await route.fulfill({
      contentType: "application/json",
      json: pathname.endsWith("/wrun_smoke") ? workflowRun : [workflowRun]
    });
  });

  const demoScenario = {
    id: "demo_scenario_customer_support_refund",
    organization_id: "org_default",
    environment_id: "env_default",
    name: "Customer Support Refund Governance",
    slug: "customer-support-refund",
    description: "Governed refund demo.",
    value_proof: "Shows policy, runtime, and evidence.",
    status: "published",
    required_services: [
      {
        key: "product-api",
        label: "Product API",
        required: true,
        health_endpoint: "/health",
        evidence_route: "/overview"
      },
      {
        key: "sample-mcp-server",
        label: "Sample MCP server",
        required: true,
        health_endpoint: "/mcp/health",
        evidence_route: "/mcp"
      }
    ],
    created_at: "2026-05-02T10:00:00Z",
    updated_at: "2026-05-02T10:00:00Z"
  };
  const demoStep = {
    id: "demo_step_refund_import_policies",
    scenario_id: "demo_scenario_customer_support_refund",
    step_order: 1,
    title: "Import refund policy pack",
    expected_result: "Refund limit and sensitive-tool policies are active.",
    action_type: "import_policies",
    action_config: {},
    proof_links: [
      {
        area: "Policies",
        label: "Policy library",
        route: "/policies?policy_slug=refund-limit",
        resource_hint: "refund-limit"
      }
    ],
    created_at: "2026-05-02T10:00:00Z",
    updated_at: "2026-05-02T10:00:00Z"
  };
  const demoRun = {
    id: "demo_run_smoke",
    organization_id: "org_default",
    environment_id: "env_default",
    scenario_id: "demo_scenario_customer_support_refund",
    status: "running",
    started_by: "user_1",
    started_at: "2026-05-02T10:00:00Z",
    finished_at: null,
    summary: { completed_steps: 1, total_steps: 2 },
    created_at: "2026-05-02T10:00:00Z",
    updated_at: "2026-05-02T10:00:01Z",
    scenario: demoScenario,
    step_runs: [
      {
        id: "demo_step_run_smoke",
        demo_run_id: "demo_run_smoke",
        demo_step_id: "demo_step_refund_import_policies",
        status: "succeeded",
        result: { imported: 2 },
        started_at: "2026-05-02T10:00:00Z",
        finished_at: "2026-05-02T10:00:01Z",
        created_at: "2026-05-02T10:00:00Z",
        updated_at: "2026-05-02T10:00:01Z",
        step: demoStep,
        actual_result: "Imported 2 active demo policies.",
        evidence_links: [
          {
            area: "Policies",
            label: "Policy library",
            route: "/policies?policy_slug=refund-limit&correlation_id=corr-demo",
            resource_id: "policy_refund",
            correlation_id: "corr-demo"
          }
        ],
        proof_checklist: [
          {
            area: "Policies",
            label: "Policy library",
            status: "completed",
            route: "/policies?policy_slug=refund-limit&correlation_id=corr-demo",
            expected_result: "Refund limit and sensitive-tool policies are active.",
            actual_result: "Imported 2 active demo policies."
          }
        ]
      }
    ]
  };
  const demoResetRun = {
    id: "demo_reset_smoke",
    organization_id: "org_default",
    environment_id: "env_default",
    status: "succeeded",
    requested_by: "user_1",
    started_at: "2026-05-02T10:05:00Z",
    finished_at: "2026-05-02T10:05:01Z",
    summary: {
      cleared: { demo_runs: 1, demo_step_runs: 9, demo_lab_audit_events: 10 },
      seeded: { policy_placeholders: 2, demo_scenarios: 1, demo_steps: 9 }
    },
    created_at: "2026-05-02T10:05:00Z",
    updated_at: "2026-05-02T10:05:01Z"
  };
  const demoBaselineStatus = {
    organization_id: "org_default",
    environment_id: "env_default",
    overall_status: "degraded",
    checked_at: "2026-05-02T10:00:00Z",
    checks: [
      {
        key: "policy-pack",
        label: "Seed policy pack",
        status: "healthy",
        required: true,
        detail: "Required demo policy placeholders are loaded.",
        count: 2,
        expected_count: 2,
        missing: []
      },
      {
        key: "mcp-server",
        label: "Sample MCP server",
        status: "degraded",
        required: true,
        detail: "Sample refund MCP server is missing.",
        count: 0,
        expected_count: 1,
        missing: ["mcp_demo_refund"]
      }
    ],
    missing_items: ["mcp_demo_refund"]
  };
  await page.route("**/api/v1/demo/**", async (route) => {
    const { pathname } = new URL(route.request().url());
    const method = route.request().method();
    if (pathname === "/api/v1/demo/scenarios" && method === "GET") {
      await route.fulfill({ contentType: "application/json", json: [demoScenario] });
      return;
    }
    if (pathname === "/api/v1/demo/scenarios/demo_scenario_customer_support_refund" && method === "GET") {
      await route.fulfill({
        contentType: "application/json",
        json: { ...demoScenario, steps: [demoStep] }
      });
      return;
    }
    if (pathname === "/api/v1/demo/scenarios/demo_scenario_customer_support_refund/runs" && method === "POST") {
      await route.fulfill({ contentType: "application/json", json: demoRun, status: 201 });
      return;
    }
    if (pathname === "/api/v1/demo/runs/demo_run_smoke" && method === "GET") {
      await route.fulfill({ contentType: "application/json", json: demoRun });
      return;
    }
    if (pathname === "/api/v1/demo/runs/demo_run_smoke/continue" && method === "POST") {
      await route.fulfill({
        contentType: "application/json",
        json: { ...demoRun, summary: { completed_steps: 2, total_steps: 2 } }
      });
      return;
    }
    if (pathname === "/api/v1/demo/runs/demo_run_smoke/cancel" && method === "POST") {
      await route.fulfill({ contentType: "application/json", json: { ...demoRun, status: "canceled" } });
      return;
    }
    if (pathname === "/api/v1/demo/reset" && method === "POST") {
      await route.fulfill({ contentType: "application/json", json: demoResetRun, status: 201 });
      return;
    }
    if (pathname === "/api/v1/demo/reset-runs") {
      await route.fulfill({ contentType: "application/json", json: [demoResetRun] });
      return;
    }
    if (pathname === "/api/v1/demo/reset-runs/demo_reset_smoke") {
      await route.fulfill({ contentType: "application/json", json: demoResetRun });
      return;
    }
    if (pathname === "/api/v1/demo/baseline-status") {
      await route.fulfill({ contentType: "application/json", json: demoBaselineStatus });
      return;
    }
    await route.fulfill({ contentType: "application/json", json: [] });
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
    const { pathname } = new URL(route.request().url());
    if (pathname === "/api/v1/artifacts/art_workflow_smoke/download") {
      await route.fulfill({
        contentType: "application/json",
        json: {
          artifact: workflowArtifact,
          content_base64: "e30=",
          metadata: { checksum_verified: true }
        }
      });
      return;
    }
    if (pathname === "/api/v1/artifacts/art_workflow_smoke") {
      await route.fulfill({ contentType: "application/json", json: workflowArtifact });
      return;
    }
    if (pathname === "/api/v1/artifacts/art_smoke") {
      await route.fulfill({ contentType: "application/json", json: complianceArtifact });
      return;
    }
    await route.fulfill({
      contentType: "application/json",
      json: [workflowArtifact, complianceArtifact]
    });
  });
  await page.route("**/api/v1/trust/scores", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: [
        {
          id: "tscore_smoke",
          agent_id: "agent_smoke",
          agent_name: "Smoke Agent",
          score: 735,
          tier: "trusted",
          dimensions: { policy_compliance: { score: 735, signal_count: 2 } },
          calculated_at: "2026-05-02T10:04:00Z"
        }
      ]
    });
  });
  await page.route("**/api/v1/trust/events**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: [
        {
          id: "tevt_smoke",
          agent_id: "agent_smoke",
          agent_name: "Smoke Agent",
          dimension: "policy_compliance",
          delta: 8,
          reason: "Policy decision allowed.",
          score_before: 727,
          score_after: 735,
          source_event_id: "evt_policy_smoke",
          created_at: "2026-05-02T10:04:00Z"
        }
      ]
    });
  });
  await page.route("**/api/v1/trust/rules", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: [
        {
          id: "trule_smoke",
          event_type: "policy.decision.allow",
          dimension: "policy_compliance",
          delta: 8,
          min_delta: -50,
          max_delta: 50,
          enabled: true
        }
      ]
    });
  });
  const trustCard = {
    id: "tcard_smoke",
    agent_id: "agent_smoke",
    issuer: "ophanix-demo",
    status: "active",
    signature: "signature_smoke_123456",
    valid_from: "2026-05-02T10:00:00Z",
    valid_until: "2026-06-02T10:00:00Z",
    issued_at: "2026-05-02T10:00:00Z",
    card: {
      name: "Smoke Agent",
      agent_did: "did:mesh:smoke",
      capabilities: ["claims:read"],
      trust_score: 0.735,
      metadata: { trust_score: 735 }
    }
  };
  await page.route("**/api/v1/trust/cards/tcard_smoke", async (route) => {
    await route.fulfill({ contentType: "application/json", json: trustCard });
  });
  await page.route("**/api/v1/trust/cards", async (route) => {
    await route.fulfill({ contentType: "application/json", json: [trustCard] });
  });
  await page.route("**/api/v1/trust/thresholds", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: [
        {
          id: "tthr_smoke",
          threshold_type: "handoff",
          target_type: "environment",
          target_id: null,
          min_score: 700,
          required_tier: "trusted",
          enabled: true
        }
      ]
    });
  });
  await page.route("**/api/v1/trust/handshakes**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: [
        {
          id: "hshake_smoke",
          source_agent_id: "agent_smoke",
          target_agent_id: "agent_smoke_peer",
          purpose: "handoff",
          threshold_type: "handoff",
          target_type: "environment",
          target_id: null,
          required_score: 700,
          required_tier: "trusted",
          source_score: 735,
          target_score: 720,
          result: "allowed",
          reason: "trust_threshold_satisfied",
          metadata: { mode: "smoke" },
          created_at: "2026-05-02T10:05:00Z"
        }
      ]
    });
  });
  await page.route("**/api/v1/mesh/topology**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        nodes: [
          { agent_id: "agent_smoke", name: "Smoke Agent", status: "active", trust_tier: "trusted", message_count: 1 },
          { agent_id: "agent_peer", name: "Peer Agent", status: "active", trust_tier: "standard", message_count: 1 }
        ],
        edges: [
          {
            source_agent_id: "agent_smoke",
            target_agent_id: "agent_peer",
            protocol: "mcp",
            volume: 1,
            denied_count: 0,
            deny_rate: 0,
            average_latency_ms: 24
          }
        ],
        message_count: 1,
        generated_at: "2026-05-02T10:06:00Z",
        cached: false
      }
    });
  });
  await page.route("**/api/v1/mesh/messages**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: [
        {
          id: "mmsg_smoke",
          source_agent_id: "agent_smoke",
          target_agent_id: "agent_peer",
          source_agent_name: "Smoke Agent",
          target_agent_name: "Peer Agent",
          protocol: "mcp",
          action: "tool.call",
          decision: "allow",
          latency_ms: 24,
          correlation_id: "corr-smoke-mesh",
          payload_summary: { reason: "policy_allow" },
          created_at: "2026-05-02T10:06:00Z"
        }
      ]
    });
  });
  await page.route("**/api/v1/mesh/handoffs**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: [
        {
          id: "mhnd_smoke",
          source_agent_id: "agent_smoke",
          target_agent_id: "agent_peer",
          source_agent_name: "Smoke Agent",
          target_agent_name: "Peer Agent",
          task_type: "claim_review",
          required_capabilities: ["claims:read"],
          trust_result: "allowed",
          policy_result: "allow",
          status: "completed",
          reason: "ok",
          correlation_id: "corr-smoke-mesh",
          metadata: { demo: true },
          created_at: "2026-05-02T10:06:00Z"
        }
      ]
    });
  });
  const protocolBridge = {
    id: "pbrg_smoke",
    name: "MCP Smoke Bridge",
    bridge_type: "mcp",
    status: "limited",
    config: { endpoint: "https://mcp.local/rpc" },
    current_health: {
      id: "pbhc_smoke",
      bridge_id: "pbrg_smoke",
      status: "limited",
      latency_ms: 1,
      message: "AgentMesh bridge methods are placeholder/pass-through implementations.",
      checked_at: "2026-05-02T10:06:00Z"
    },
    routes: [
      {
        id: "pbrt_smoke",
        bridge_id: "pbrg_smoke",
        source_protocol: "a2a",
        target_protocol: "mcp",
        source_agent_id: "agent_smoke",
        target_agent_id: "agent_peer",
        source_agent_name: "Smoke Agent",
        target_agent_name: "Peer Agent",
        enabled: true,
        created_at: "2026-05-02T10:06:00Z",
        updated_at: "2026-05-02T10:06:00Z"
      }
    ],
    created_at: "2026-05-02T10:06:00Z",
    updated_at: "2026-05-02T10:06:00Z"
  };
  await page.route("**/api/v1/mesh/protocol-bridges/pbrg_smoke", async (route) => {
    await route.fulfill({ contentType: "application/json", json: protocolBridge });
  });
  await page.route("**/api/v1/mesh/protocol-bridges**", async (route) => {
    await route.fulfill({ contentType: "application/json", json: [protocolBridge] });
  });
  const mcpServer = {
    id: "mcpsrv_smoke",
    name: "Claims MCP Smoke",
    endpoint_url: "https://mcp.claims.local/rpc",
    owner_user_id: "user_1",
    owner_display_name: "admin",
    auth_type: "bearer",
    status: "active",
    policy_pack_id: "pack_smoke",
    tool_count: 1,
    created_at: "2026-05-02T10:07:00Z",
    updated_at: "2026-05-02T10:07:00Z",
    last_discovered_at: "2026-05-02T10:07:00Z"
  };
  const mcpTool = {
    id: "mcptool_smoke",
    server_id: "mcpsrv_smoke",
    server_name: "Claims MCP Smoke",
    name: "claims.lookup",
    description: "Look up claim status",
    current_version_id: "mcptv_smoke",
    current_version: {
      id: "mcptv_smoke",
      tool_id: "mcptool_smoke",
      schema: { type: "object", properties: { claim_id: { type: "string" } } },
      schema_hash: "sha256:smoke",
      definition: { name: "claims.lookup" },
      discovered_at: "2026-05-02T10:07:00Z",
      scan_status: "changed"
    },
    versions: [
      {
        id: "mcptv_smoke",
        tool_id: "mcptool_smoke",
        schema: { type: "object", properties: { claim_id: { type: "string" } } },
        schema_hash: "sha256:smoke",
        definition: { name: "claims.lookup" },
        discovered_at: "2026-05-02T10:07:00Z",
        scan_status: "changed"
      }
    ],
    risk_level: "critical",
    status: "active",
    created_at: "2026-05-02T10:07:00Z",
    updated_at: "2026-05-02T10:07:00Z"
  };
  const mcpScan = {
    id: "mcpscan_smoke",
    server_id: "mcpsrv_smoke",
    server_name: "Claims MCP Smoke",
    status: "completed",
    started_at: "2026-05-02T10:07:00Z",
    finished_at: "2026-05-02T10:07:02Z",
    summary: { tools_scanned: 1, tools_flagged: 1, finding_count: 1 },
    findings: []
  };
  const mcpFinding = {
    id: "mcpf_smoke",
    scan_run_id: "mcpscan_smoke",
    server_id: "mcpsrv_smoke",
    server_name: "Claims MCP Smoke",
    tool_id: "mcptool_smoke",
    tool_name: "claims.lookup",
    tool_version_id: "mcptv_smoke",
    finding_type: "schema_change",
    severity: "critical",
    title: "Smoke schema finding",
    description: "Schema exposes a smoke field.",
    evidence: { field: "claim_id" },
    recommendation: "Review the schema.",
    status: "open",
    created_at: "2026-05-02T10:07:00Z",
    updated_at: "2026-05-02T10:07:00Z"
  };
  await page.route("**/api/v1/mcp/servers**", async (route) => {
    await route.fulfill({ contentType: "application/json", json: [mcpServer] });
  });
  await page.route("**/api/v1/mcp/tools**", async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    await route.fulfill({
      contentType: "application/json",
      json: pathname.endsWith("/mcptool_smoke") ? mcpTool : [mcpTool]
    });
  });
  await page.route("**/api/v1/mcp/scans**", async (route) => {
    await route.fulfill({ contentType: "application/json", json: [mcpScan] });
  });
  await page.route("**/api/v1/mcp/findings**", async (route) => {
    await route.fulfill({ contentType: "application/json", json: [mcpFinding] });
  });
  await page.route("**/api/v1/mcp/traffic**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: [
        {
          id: "mcpcall_smoke",
          server_id: "mcpsrv_smoke",
          server_name: "Claims MCP Smoke",
          tool_id: "mcptool_smoke",
          tool_name: "claims.lookup",
          source_agent_id: "agent_smoke",
          source_agent_name: "Smoke Agent",
          params_summary: { claim_id: "redacted" },
          decision: "denied",
          reason: "policy blocked smoke lookup",
          matched_policy_id: "policy_smoke",
          trust_score: 735,
          sanitizer_action: "blocked",
          latency_ms: 8,
          correlation_id: "corr-smoke-mcp",
          created_at: "2026-05-02T10:07:00Z"
        }
      ]
    });
  });
  await page.route("**/api/v1/mcp/approvals**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: [
        {
          id: "mcpappr_smoke",
          tool_call_id: "mcpcall_smoke",
          status: "pending",
          requested_by_agent_id: "agent_smoke",
          requested_by_agent_name: "Smoke Agent",
          requested_at: "2026-05-02T10:07:00Z",
          tool_call: null
        }
      ]
    });
  });
  await page.route("**/api/v1/mcp/rate-limits**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: [
        {
          id: "mcprl_smoke",
          target_type: "mcp-tool",
          target_id: "mcptool_smoke",
          window_seconds: 60,
          max_calls: 20,
          enabled: true,
          created_at: "2026-05-02T10:07:00Z",
          updated_at: "2026-05-02T10:07:00Z"
        }
      ]
    });
  });
  const runtimeSession = {
    id: "rtssn_smoke",
    agent_id: "agent_smoke",
    agent_name: "Smoke Agent",
    state: "active",
    ring: 2,
    sponsor_user_id: "user_1",
    started_at: "2026-05-02T10:08:00Z",
    ended_at: null,
    metadata: {},
    actions: [
      {
        id: "rtact_smoke",
        session_id: "rtssn_smoke",
        action_name: "refund.issue",
        resource_type: "runtime-action",
        required_ring: 1,
        decision: "denied",
        reason: "Ring 1 requires higher trust",
        latency_ms: 11,
        correlation_id: "corr-smoke-runtime",
        created_at: "2026-05-02T10:08:00Z",
        ring_decision: {
          id: "rtdcsn_smoke",
          runtime_action_id: "rtact_smoke",
          session_id: "rtssn_smoke",
          agent_id: "agent_smoke",
          action_name: "refund.issue",
          resource_type: "runtime-action",
          agent_trust_score: 735,
          required_ring: 1,
          assigned_ring: 2,
          result: "denied",
          reason: "Ring 1 requires higher trust",
          created_at: "2026-05-02T10:08:00Z"
        }
      }
    ]
  };
  const runtimeSaga = {
    id: "saga_smoke",
    runtime_session_id: "rtssn_smoke",
    name: "Refund Saga Smoke",
    status: "draft",
    created_by: "user_1",
    started_at: null,
    finished_at: null,
    correlation_id: "corr-smoke-saga",
    created_at: "2026-05-02T10:08:00Z",
    updated_at: "2026-05-02T10:08:00Z",
    steps: [
      {
        id: "sgstp_smoke",
        saga_id: "saga_smoke",
        step_order: 1,
        name: "Lookup order",
        action_name: "order.lookup",
        target_agent_id: "agent_smoke",
        target_agent_name: "Smoke Agent",
        required_capability: "claims:read",
        timeout_seconds: 300,
        retry_count: 1,
        compensation_action: "refund.revert",
        status: "failed",
        result: { error: "demo failure" },
        created_at: "2026-05-02T10:08:00Z",
        updated_at: "2026-05-02T10:08:00Z"
      }
    ],
    events: [
      {
        id: "sgev_smoke",
        saga_id: "saga_smoke",
        step_id: "sgstp_smoke",
        event_type: "saga.step.compensated",
        message: "Compensation queued",
        payload: {},
        created_at: "2026-05-02T10:08:00Z"
      }
    ]
  };
  await page.route("**/api/v1/runtime/sessions**", async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    await route.fulfill({
      contentType: "application/json",
      json: pathname.endsWith("/rtssn_smoke") ? runtimeSession : [runtimeSession]
    });
  });
  await page.route("**/api/v1/runtime/ring-decisions**", async (route) => {
    await route.fulfill({ contentType: "application/json", json: [runtimeSession.actions[0].ring_decision] });
  });
  await page.route("**/api/v1/runtime/ring-rules**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: [
        {
          id: "rtrule_smoke",
          action_pattern: "refund.*",
          required_ring: 1,
          min_trust_score: 700,
          enabled: true,
          created_at: "2026-05-02T10:08:00Z",
          updated_at: "2026-05-02T10:08:00Z"
        }
      ]
    });
  });
  await page.route("**/api/v1/runtime/sagas**", async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    await route.fulfill({
      contentType: "application/json",
      json: pathname.endsWith("/saga_smoke") ? runtimeSaga : [runtimeSaga]
    });
  });
  await page.route("**/api/v1/runtime/sandbox-profiles**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: [
        {
          id: "sbx_smoke",
          name: "Python Smoke Sandbox",
          provider_type: "subprocess",
          allowed_imports: ["json"],
          blocked_imports: ["os", "subprocess", "socket"],
          allowed_paths: ["/tmp/claims"],
          network_policy: { egress: "deny" },
          resource_limits: { timeout_seconds: 5, memory_mb: 128 },
          status: "active",
          provider_warning: "Subprocess sandbox is demo-only and does not provide production isolation.",
          created_at: "2026-05-02T10:08:00Z",
          updated_at: "2026-05-02T10:08:00Z"
        }
      ]
    });
  });
  await page.route("**/api/v1/runtime/kill-switch/events**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: [
        {
          id: "kill_smoke",
          target_type: "session",
          target_id: "rtssn_smoke",
          scope: "target",
          reason: "operator stop",
          actor_id: "user_1",
          status: "triggered",
          created_at: "2026-05-02T10:08:00Z"
        }
      ]
    });
  });

  await page.goto("/login");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();

  const topLevelChecks = [
    { link: "Agents", heading: "Agents" },
    { link: "Discovery", heading: "Discovery" },
    { link: "Policies", heading: "Policies" },
    { link: "Trust", heading: "Trust" },
    { link: "Mesh", heading: "Mesh" },
    { link: "Compliance", heading: "Compliance" },
    { link: "MCP Security", heading: "MCP Security" },
    { link: "Runtime", heading: "Runtime" },
    { link: "Marketplace", heading: "Marketplace Operations" },
    { link: "Observability", heading: "Observability" },
    { link: "Integrations", heading: "Integrations" },
    { link: "Workflows", heading: "Workflows" },
    { link: "Demo Lab", heading: "Demo Lab" }
  ];
  for (const { heading, link } of topLevelChecks) {
    await page.getByRole("link", { name: link }).click();
    await expect(page.getByRole("heading", { name: heading, exact: true })).toBeVisible();
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
  await page.getByRole("link", { name: "Trust" }).click();
  await expect(page.getByText("Agent Trust Scores")).toBeVisible();
  await expect(page.getByText("did:mesh:smoke").first()).toBeVisible();
  await page.getByRole("link", { name: "Mesh" }).click();
  await expect(page.getByText("Live Edges")).toBeVisible();
  await expect(page.getByText("MCP Smoke Bridge").first()).toBeVisible();
  await page.getByRole("link", { name: "MCP Security" }).click();
  await expect(page.getByRole("heading", { name: "Server Registry" })).toBeVisible();
  await expect(page.getByText("Claims MCP Smoke").first()).toBeVisible();
  await page.getByRole("link", { name: "Runtime" }).click();
  await expect(page.getByRole("heading", { name: "Runtime Sessions" })).toBeVisible();
  await expect(page.getByText("Refund Saga Smoke").first()).toBeVisible();
  await expect(page.getByText("Python Smoke Sandbox").first()).toBeVisible();
  await page.getByRole("link", { name: "Marketplace" }).click();
  await expect(page.getByRole("heading", { name: "Plugin Catalog" })).toBeVisible();
  await expect(page.getByText("Claims Assistant").first()).toBeVisible();
  await expect(page.getByText("Marketplace Root")).toBeVisible();
  await page.getByRole("link", { name: "Observability" }).click();
  await expect(page.getByRole("heading", { name: "SLO Objectives" })).toBeVisible();
  await expect(
    page.locator('[data-observability-slo-row="slo_smoke"]').getByRole("cell", { name: "Task Success" })
  ).toBeVisible();
  await expect(
    page.locator('[data-observability-incident-row="inc_smoke"]').getByText("Denial Spike", { exact: true })
  ).toBeVisible();
  await expect(
    page.locator('[data-observability-rollout-row="rollout_smoke"]').getByText("Claims Canary", { exact: true })
  ).toBeVisible();
  await page.getByRole("link", { name: "Integrations" }).click();
  await expect(page.getByRole("heading", { name: "Framework Catalog" })).toBeVisible();
  await expect(page.getByText("OpenAI demo connector")).toBeVisible();
  await expect(page.getByText("OpenAI demo key")).toBeVisible();
  await page.getByRole("link", { name: "Workflows" }).click();
  await expect(page.getByRole("heading", { name: "Workflow Catalog" })).toBeVisible();
  await expect(page.getByText("Policy Lint", { exact: true })).toBeVisible();
  await expect(page.getByText("policy lint passed=True errors=0")).toBeVisible();
  await expect(page.getByText("policy-lint-output.json").first()).toBeVisible();
  await page.getByRole("link", { name: "Demo Lab" }).click();
  await expect(page.getByRole("heading", { name: "Scenario Catalog" })).toBeVisible();
  await expect(page.getByText("Customer Support Refund Governance").first()).toBeVisible();
  await expect(page.getByText("Sample refund MCP server is missing.")).toBeVisible();
  await page.getByRole("button", { name: /Start Scenario/ }).click();
  await expect(page.getByText("Demo scenario started")).toBeVisible();
  await expect(page.getByText("Imported 2 active demo policies.").first()).toBeVisible();
  await page.getByLabel("Confirmation").fill("RESET");
  await page.getByRole("button", { name: /Reset Demo/ }).click();
  await expect(page.getByText("Demo environment reset")).toBeVisible();
});
