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

  for (const name of ["Agents", "Discovery", "Policies", "Trust", "Mesh", "Compliance", "MCP Security", "Runtime", "Demo Lab"]) {
    await page.getByRole("link", { name }).click();
    await expect(page.getByRole("heading", { name, exact: true })).toBeVisible();
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
});
