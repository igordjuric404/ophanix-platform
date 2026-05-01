import assert from "node:assert/strict";
import test from "node:test";

import { createApiClient } from "../src/apiClient.js";
import {
  mcpApprovalDecisionPayloadFromValues,
  mcpFindingActionPayloadFromValues,
  mcpFindingFilterParamsFromValues,
  mcpRateLimitPayloadFromValues,
  mcpServerPayloadFromValues,
  mcpTrafficFilterParamsFromValues,
  renderMcpApprovalsPanel,
  renderMcpFindingDetail,
  renderMcpFindingsPanel,
  renderMcpPage,
  renderMcpRateLimitsPanel,
  renderMcpScanRunsPanel,
  renderMcpServersPanel,
  renderMcpTrafficPanel,
  renderMcpToolDetail
} from "../src/mcp.js";

const mcpServer = {
  id: "mcpsrv_1",
  name: "Claims MCP",
  endpoint_url: "https://mcp.claims.local/rpc",
  owner_user_id: "user_admin",
  owner_display_name: "Demo Admin",
  auth_type: "oauth",
  status: "active",
  policy_pack_id: "policy_placeholder_sensitive_tools",
  tool_count: 3,
  last_discovered_at: "2026-05-01T00:00:00Z"
};

const mcpTool = {
  id: "mcptool_1",
  server_id: "mcpsrv_1",
  server_name: "Claims MCP",
  name: "claims.issue_refund",
  description: "Issue a customer refund for a claim.",
  current_version_id: "mcptv_2",
  current_version: {
    id: "mcptv_2",
    tool_id: "mcptool_1",
    schema_hash: "sha256:new",
    schema: {
      type: "object",
      properties: {
        order_id: { type: "string" },
        amount: { type: "number" },
        reason: { type: "string" }
      },
      required: ["order_id", "amount", "reason"]
    },
    definition: {},
    discovered_at: "2026-05-01T00:01:00Z",
    scan_status: "not_scanned"
  },
  versions: [
    {
      id: "mcptv_2",
      tool_id: "mcptool_1",
      schema_hash: "sha256:new",
      schema: {},
      definition: {},
      discovered_at: "2026-05-01T00:01:00Z",
      scan_status: "not_scanned"
    },
    {
      id: "mcptv_1",
      tool_id: "mcptool_1",
      schema_hash: "sha256:old",
      schema: {},
      definition: {},
      discovered_at: "2026-05-01T00:00:00Z",
      scan_status: "not_scanned"
    }
  ],
  risk_level: "unknown",
  status: "changed"
};

const mcpScanRun = {
  id: "mcpscan_1",
  server_id: "mcpsrv_1",
  server_name: "Claims MCP",
  status: "completed",
  started_at: "2026-05-01T00:02:00Z",
  finished_at: "2026-05-01T00:02:01Z",
  summary: {
    tools_scanned: 3,
    tools_flagged: 1,
    finding_count: 2
  },
  error_message: null,
  findings: []
};

const mcpFinding = {
  id: "mcpf_1",
  scan_run_id: "mcpscan_1",
  server_id: "mcpsrv_1",
  server_name: "Claims MCP",
  tool_id: "mcptool_1",
  tool_name: "claims.issue_refund",
  tool_version_id: "mcptv_2",
  finding_type: "description_injection",
  severity: "critical",
  title: "Prompt injection detected",
  description: "Instruction-like text was found in the tool description.",
  evidence: {
    matched_pattern: "ignore previous",
    details: { source: "tool description" }
  },
  recommendation: "Remove hidden instructions before exposing this tool.",
  status: "open",
  created_at: "2026-05-01T00:02:01Z",
  updated_at: "2026-05-01T00:02:01Z"
};

const mcpTrafficCall = {
  id: "mcpcall_1",
  organization_id: "org_default",
  environment_id: "env_default",
  server_id: "mcpsrv_1",
  server_name: "Claims MCP",
  tool_id: "mcptool_1",
  tool_name: "claims.lookup_order",
  source_agent_id: "agent_high",
  source_agent_name: "High Trust Agent",
  params_summary: { order_id: "ORD-100" },
  decision: "allowed",
  reason: "Allowed by policy",
  matched_policy_id: "policy_placeholder_sensitive_tools",
  matched_policy_version_id: null,
  trust_threshold_id: "threshold_mcp",
  trust_score: 820,
  gateway_stage: "allowed",
  response: { status: "ready_for_review" },
  sanitizer_action: "redacted",
  latency_ms: 4,
  correlation_id: "corr-mcp",
  created_at: "2026-05-01T00:03:00Z"
};

const mcpApproval = {
  id: "mcpappr_1",
  tool_call_id: "mcpcall_2",
  status: "pending",
  requested_by_agent_id: "agent_high",
  requested_by_agent_name: "High Trust Agent",
  approved_by_user_id: null,
  decision_reason: null,
  requested_at: "2026-05-01T00:04:00Z",
  decided_at: null,
  tool_call: {
    ...mcpTrafficCall,
    id: "mcpcall_2",
    tool_name: "claims.issue_refund",
    decision: "escalated",
    reason: "Awaiting human approval",
    sanitizer_action: null
  }
};

const mcpRateLimit = {
  id: "mcprl_1",
  organization_id: "org_default",
  environment_id: "env_default",
  target_type: "mcp-tool",
  target_id: "mcptool_1",
  window_seconds: 60,
  max_calls: 12,
  enabled: true,
  created_at: "2026-05-01T00:05:00Z",
  updated_at: "2026-05-01T00:05:00Z"
};

test("component server table renders MCP status and discovery action", () => {
  const html = renderMcpServersPanel({ servers: [mcpServer], scanRuns: [mcpScanRun] });

  assert.match(html, /data-mcp-server-row="mcpsrv_1"/);
  assert.match(html, /Claims MCP/);
  assert.match(html, /Demo Admin/);
  assert.match(html, /data-mcp-discover-tools="mcpsrv_1"/);
  assert.match(html, /data-mcp-run-scan="mcpsrv_1"/);
  assert.match(html, /completed/);
});

test("component MCP route renders servers and tools", () => {
  const html = renderMcpPage({
    mcpServers: [mcpServer],
    mcpTools: [mcpTool],
    mcpScanRuns: [mcpScanRun],
    mcpFindings: [mcpFinding],
    mcpTraffic: [mcpTrafficCall],
    mcpApprovals: [mcpApproval],
    mcpRateLimits: [mcpRateLimit]
  });

  assert.match(html, /data-route-page="\/mcp"/);
  assert.match(html, /data-mcp-servers/);
  assert.match(html, /data-mcp-tools/);
  assert.match(html, /data-mcp-scans/);
  assert.match(html, /data-mcp-findings/);
  assert.match(html, /data-mcp-traffic/);
  assert.match(html, /data-mcp-approvals/);
  assert.match(html, /data-mcp-rate-limits/);
  assert.match(html, /claims.issue_refund/);
  assert.match(html, /sha256:new/);
  assert.match(html, /1 open/);
});

test("component tool detail shows schema version history", () => {
  const html = renderMcpToolDetail(mcpTool);

  assert.match(html, /data-mcp-tool-detail="mcptool_1"/);
  assert.match(html, /data-mcp-tool-schema/);
  assert.match(html, /reason/);
  assert.match(html, /data-mcp-tool-version-history/);
  assert.match(html, /data-mcp-tool-version-row="mcptv_2"/);
  assert.match(html, /sha256:old/);
});

test("component scan history renders scan summary", () => {
  const html = renderMcpScanRunsPanel({ scanRuns: [mcpScanRun] });

  assert.match(html, /data-mcp-scan-row="mcpscan_1"/);
  assert.match(html, /Claims MCP/);
  assert.match(html, /completed/);
  assert.match(html, />3</);
  assert.match(html, />2</);
});

test("component findings table renders severity filters and rows", () => {
  const html = renderMcpFindingsPanel({
    findings: [mcpFinding],
    filter: { status: "open", severity: "critical" }
  });

  assert.match(html, /data-mcp-finding-filter-form/);
  assert.match(html, /<option value="open" selected>open<\/option>/);
  assert.match(html, /<option value="critical" selected>critical<\/option>/);
  assert.match(html, /data-mcp-finding-row="mcpf_1"/);
  assert.match(html, /Prompt injection detected/);
  assert.match(html, /critical/);
});

test("component finding drawer shows evidence and lifecycle actions", () => {
  const html = renderMcpFindingDetail(mcpFinding);

  assert.match(html, /data-mcp-finding-detail="mcpf_1"/);
  assert.match(html, /data-mcp-finding-evidence/);
  assert.match(html, /ignore previous/);
  assert.match(html, /Remove hidden instructions/);
  assert.match(html, /data-mcp-finding-resolve-form/);
});

test("component accept-risk dialog requires reason", () => {
  const html = renderMcpFindingDetail(mcpFinding);

  assert.match(html, /data-mcp-accept-risk-modal="mcpf_1"/);
  assert.match(html, /data-mcp-finding-accept-risk-form/);
  assert.match(html, /textarea name="reason" required/);
});

test("component traffic table renders allowed and denied decisions", () => {
  const denied = { ...mcpTrafficCall, id: "mcpcall_3", decision: "denied", reason: "blocked" };
  const html = renderMcpTrafficPanel({
    traffic: [mcpTrafficCall, denied],
    filter: { decision: "denied" }
  });

  assert.match(html, /data-mcp-traffic-filter-form/);
  assert.match(html, /<option value="denied" selected>denied<\/option>/);
  assert.match(html, /data-mcp-traffic-row="mcpcall_1"/);
  assert.match(html, /allowed/);
  assert.match(html, /denied/);
  assert.match(html, /redacted/);
});

test("component approval detail shows matched policy and actions", () => {
  const html = renderMcpApprovalsPanel({ approvals: [mcpApproval] });

  assert.match(html, /data-mcp-approval-row="mcpappr_1"/);
  assert.match(html, /policy_placeholder_sensitive_tools/);
  assert.match(html, /820/);
  assert.match(html, /ORD-100/);
  assert.match(html, /data-mcp-approval-approve-open="mcpappr_1"/);
  assert.match(html, /data-mcp-approval-deny-open="mcpappr_1"/);
});

test("component approval modals require reasons", () => {
  const html = renderMcpApprovalsPanel({ approvals: [mcpApproval] });

  assert.match(html, /data-mcp-approval-approve-form/);
  assert.match(html, /data-mcp-approval-deny-form/);
  assert.match(html, /textarea name="reason" required/);
});

test("component rate-limit panel renders configuration", () => {
  const html = renderMcpRateLimitsPanel({ rateLimits: [mcpRateLimit] });

  assert.match(html, /data-mcp-rate-limit-form/);
  assert.match(html, /data-mcp-rate-limit-row="mcprl_1"/);
  assert.match(html, /mcptool_1/);
  assert.match(html, /12/);
});

test("server register payload normalizes optional values", () => {
  assert.deepEqual(
    mcpServerPayloadFromValues({
      name: " Claims MCP ",
      endpoint_url: " https://mcp.claims.local/rpc ",
      owner_user_id: " user_admin ",
      auth_type: "OAUTH",
      status: "ACTIVE",
      policy_pack_id: ""
    }),
    {
      name: "Claims MCP",
      endpoint_url: "https://mcp.claims.local/rpc",
      owner_user_id: "user_admin",
      auth_type: "oauth",
      status: "active",
      policy_pack_id: null
    }
  );
});

test("finding filters and action payloads normalize optional values", () => {
  assert.deepEqual(
    mcpFindingFilterParamsFromValues({
      status: " open ",
      severity: "",
      server_id: " mcpsrv_1 ",
      tool_id: ""
    }),
    {
      status: "open",
      severity: null,
      server_id: "mcpsrv_1",
      tool_id: null
    }
  );
  assert.deepEqual(mcpFindingActionPayloadFromValues({ reason: " accepted " }), {
    reason: "accepted"
  });
  assert.deepEqual(mcpTrafficFilterParamsFromValues({ decision: "denied", server_id: "", tool_id: " tool ", source_agent_id: "" }), {
    decision: "denied",
    server_id: null,
    tool_id: "tool",
    source_agent_id: null
  });
  assert.deepEqual(mcpApprovalDecisionPayloadFromValues({ reason: " approved " }), {
    reason: "approved"
  });
});

test("rate-limit payload parses numeric fields", () => {
  assert.deepEqual(mcpRateLimitPayloadFromValues({
    target_type: "mcp-tool",
    target_id: "mcptool_1",
    window_seconds: "60",
    max_calls: "12",
    enabled: "on"
  }), {
    target_type: "mcp-tool",
    target_id: "mcptool_1",
    window_seconds: 60,
    max_calls: 12,
    enabled: true
  });
});

test("api client MCP methods call expected endpoints", async () => {
  const calls = [];
  const client = createApiClient({
    fetchImpl: async (url, init = {}) => {
      calls.push([url, init.method ?? "GET", init.body ? JSON.parse(init.body) : null]);
      return {
        ok: true,
        status: 200,
        headers: new Map([["content-type", "application/json"]]),
        json: async () => ({ id: "ok" }),
        text: async () => ""
      };
    }
  });

  await client.createMcpServer({ name: "Claims MCP" });
  await client.listMcpServers({ status: "active" });
  await client.getMcpServer("mcpsrv 1");
  await client.patchMcpServer("mcpsrv 1", { status: "disabled" });
  await client.discoverMcpServerTools("mcpsrv 1");
  await client.runMcpSecurityScan("mcpsrv 1");
  await client.listMcpScans({ server_id: "mcpsrv 1" });
  await client.getMcpScan("mcpscan 1");
  await client.listMcpFindings({ severity: "critical" });
  await client.acceptMcpFindingRisk("mcpf 1", { reason: "accepted" });
  await client.resolveMcpFinding("mcpf 1", { reason: "fixed" });
  await client.createMcpProxyCall({ tool_id: "mcptool 1" });
  await client.listMcpTraffic({ decision: "allowed" });
  await client.listMcpApprovals({ status: "pending" });
  await client.approveMcpApproval("mcpappr 1", { reason: "approved" });
  await client.denyMcpApproval("mcpappr 2", { reason: "denied" });
  await client.listMcpRateLimits({ target_type: "mcp-tool" });
  await client.createMcpRateLimit({ target_id: "mcptool 1" });
  await client.listMcpTools({ server_id: "mcpsrv 1" });
  await client.getMcpTool("mcptool 1");

  assert.deepEqual(calls, [
    ["/api/v1/mcp/servers", "POST", { name: "Claims MCP" }],
    ["/api/v1/mcp/servers?status=active", "GET", null],
    ["/api/v1/mcp/servers/mcpsrv%201", "GET", null],
    ["/api/v1/mcp/servers/mcpsrv%201", "PATCH", { status: "disabled" }],
    ["/api/v1/mcp/servers/mcpsrv%201/discover-tools", "POST", null],
    ["/api/v1/mcp/servers/mcpsrv%201/scan", "POST", null],
    ["/api/v1/mcp/scans?server_id=mcpsrv+1", "GET", null],
    ["/api/v1/mcp/scans/mcpscan%201", "GET", null],
    ["/api/v1/mcp/findings?severity=critical", "GET", null],
    ["/api/v1/mcp/findings/mcpf%201/accept-risk", "POST", { reason: "accepted" }],
    ["/api/v1/mcp/findings/mcpf%201/resolve", "POST", { reason: "fixed" }],
    ["/api/v1/mcp/proxy/call", "POST", { tool_id: "mcptool 1" }],
    ["/api/v1/mcp/traffic?decision=allowed", "GET", null],
    ["/api/v1/mcp/approvals?status=pending", "GET", null],
    ["/api/v1/mcp/approvals/mcpappr%201/approve", "POST", { reason: "approved" }],
    ["/api/v1/mcp/approvals/mcpappr%202/deny", "POST", { reason: "denied" }],
    ["/api/v1/mcp/rate-limits?target_type=mcp-tool", "GET", null],
    ["/api/v1/mcp/rate-limits", "POST", { target_id: "mcptool 1" }],
    ["/api/v1/mcp/tools?server_id=mcpsrv+1", "GET", null],
    ["/api/v1/mcp/tools/mcptool%201", "GET", null]
  ]);
});
