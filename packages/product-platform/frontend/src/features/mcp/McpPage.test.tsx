import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithQueryClient } from "../../test/test-utils";
import { McpPage, mcpProxyCallPayloadFromForm } from "./McpPage";

const mcpServer = {
  id: "mcpsrv_1",
  name: "Claims MCP",
  endpoint_url: "https://mcp.claims.local/rpc",
  owner_user_id: "user_1",
  owner_display_name: "Security Owner",
  auth_type: "bearer",
  status: "active",
  policy_pack_id: "pack_1",
  tool_count: 1,
  created_at: "2026-05-01T00:00:00Z",
  updated_at: "2026-05-01T00:00:00Z",
  last_discovered_at: "2026-05-01T00:00:00Z"
};

const mcpTool = {
  id: "mcptool_1",
  server_id: "mcpsrv_1",
  server_name: "Claims MCP",
  name: "claims.lookup",
  description: "Look up claim status",
  current_version_id: "mcptv_2",
  current_version: {
    id: "mcptv_2",
    tool_id: "mcptool_1",
    schema: { type: "object", properties: { claim_id: { type: "string" } } },
    schema_hash: "sha256:new",
    definition: { name: "claims.lookup" },
    discovered_at: "2026-05-01T00:00:00Z",
    scan_status: "changed"
  },
  versions: [
    {
      id: "mcptv_2",
      tool_id: "mcptool_1",
      schema: { type: "object", properties: { claim_id: { type: "string" } } },
      schema_hash: "sha256:new",
      definition: { name: "claims.lookup" },
      discovered_at: "2026-05-01T00:00:00Z",
      scan_status: "changed"
    },
    {
      id: "mcptv_1",
      tool_id: "mcptool_1",
      schema: { type: "object" },
      schema_hash: "sha256:old",
      definition: { name: "claims.lookup" },
      discovered_at: "2026-04-30T00:00:00Z",
      scan_status: "clean"
    }
  ],
  risk_level: "critical",
  status: "active",
  created_at: "2026-05-01T00:00:00Z",
  updated_at: "2026-05-01T00:00:00Z"
};

const mcpScan = {
  id: "mcpscan_1",
  server_id: "mcpsrv_1",
  server_name: "Claims MCP",
  status: "completed",
  started_at: "2026-05-01T01:00:00Z",
  finished_at: "2026-05-01T01:00:05Z",
  summary: { tools_scanned: 1, tools_flagged: 1, finding_count: 1 },
  findings: []
};

const mcpFinding = {
  id: "mcpf_1",
  scan_run_id: "mcpscan_1",
  server_id: "mcpsrv_1",
  server_name: "Claims MCP",
  tool_id: "mcptool_1",
  tool_name: "claims.lookup",
  tool_version_id: "mcptv_2",
  finding_type: "schema_change",
  severity: "critical",
  title: "Sensitive claim field exposed",
  description: "Schema exposes a sensitive field.",
  evidence: { field: "ssn" },
  recommendation: "Remove sensitive field from the tool schema.",
  status: "open",
  created_at: "2026-05-01T01:00:00Z",
  updated_at: "2026-05-01T01:00:00Z"
};

const mcpTraffic = {
  id: "mcpcall_1",
  server_id: "mcpsrv_1",
  server_name: "Claims MCP",
  tool_id: "mcptool_1",
  tool_name: "claims.lookup",
  source_agent_id: "agent_1",
  source_agent_name: "Claims Agent",
  params_summary: { claim_id: "redacted" },
  decision: "denied",
  reason: "policy blocked high-risk claim lookup",
  matched_policy_id: "policy_1",
  trust_threshold_id: "threshold_1",
  trust_score: 640,
  gateway_stage: "policy",
  sanitizer_action: "blocked",
  latency_ms: 8,
  correlation_id: "corr-mcp",
  created_at: "2026-05-01T02:00:00Z"
};

const mcpApproval = {
  id: "mcpappr_1",
  tool_call_id: "mcpcall_2",
  status: "pending",
  requested_by_agent_id: "agent_1",
  requested_by_agent_name: "Claims Agent",
  requested_at: "2026-05-01T02:10:00Z",
  tool_call: {
    ...mcpTraffic,
    id: "mcpcall_2",
    decision: "escalated",
    reason: "approval required",
    sanitizer_action: null
  }
};

const approvedMcpApproval = {
  ...mcpApproval,
  id: "mcpappr_approved",
  status: "approved",
  decision_reason: "Approved previously",
  decided_at: "2026-05-01T02:20:00Z"
};

const mcpRateLimit = {
  id: "mcprl_1",
  target_type: "mcp-tool",
  target_id: "mcptool_1",
  window_seconds: 60,
  max_calls: 20,
  enabled: true,
  created_at: "2026-05-01T00:00:00Z",
  updated_at: "2026-05-01T00:00:00Z"
};

describe("McpPage", () => {
  beforeEach(() => {
    window.history.replaceState(null, "", "/mcp");
    mockMcpFetch();
  });

  it("renders registry, scans, findings, traffic, approvals, and rate limits", async () => {
    renderWithQueryClient(<McpPage />);

    expect(await screen.findByText("Server Registry")).toBeInTheDocument();
    expect((await screen.findAllByText("Claims MCP")).length).toBeGreaterThan(0);
    expect(screen.getByText("Tool Registry")).toBeInTheDocument();
    expect(screen.getAllByText("claims.lookup").length).toBeGreaterThan(0);
    expect(screen.getAllByText("sha256:new").length).toBeGreaterThan(0);
    expect(screen.getByText("Version History")).toBeInTheDocument();
    expect(screen.getByText("Scan History")).toBeInTheDocument();
    expect(screen.getAllByText("Sensitive claim field exposed").length).toBeGreaterThan(0);
    expect(screen.getByText("Proxy Traffic")).toBeInTheDocument();
    expect(screen.getByText("Approval Queue")).toBeInTheDocument();
    expect(screen.getByText("Rate Limits")).toBeInTheDocument();
    expect(screen.getByText("policy blocked high-risk claim lookup")).toBeInTheDocument();
  });

  it("filters and mutates the MCP security workflows", async () => {
    const calls = mockMcpFetch();
    renderWithQueryClient(<McpPage />);

    expect(await screen.findByText("Server Registry")).toBeInTheDocument();
    expect((await screen.findAllByText("Claims MCP")).length).toBeGreaterThan(0);

    const serverPanel = document.querySelector("[data-mcp-servers]") as HTMLElement;
    fireEvent.change(within(serverPanel).getByLabelText("Name"), {
      target: { value: "Billing MCP" }
    });
    fireEvent.change(within(serverPanel).getByLabelText("Endpoint"), {
      target: { value: "https://mcp.billing.local/rpc" }
    });
    fireEvent.change(within(serverPanel).getByLabelText("Owner"), {
      target: { value: "user_2" }
    });
    fireEvent.click(within(serverPanel).getByRole("button", { name: "Register" }));
    await waitFor(() => expect(calls.some((call) => call.path === "/api/v1/mcp/servers" && call.method === "POST")).toBe(true));

    fireEvent.click(within(serverPanel).getByRole("button", { name: "Discover" }));
    await waitFor(() =>
      expect(calls.some((call) => call.path === "/api/v1/mcp/servers/mcpsrv_1/discover-tools")).toBe(true)
    );
    fireEvent.click(within(serverPanel).getByRole("button", { name: "Scan" }));
    await waitFor(() =>
      expect(calls.some((call) => call.path === "/api/v1/mcp/servers/mcpsrv_1/scan")).toBe(true)
    );

    const findingsPanel = document.querySelector("[data-mcp-findings]") as HTMLElement;
    fireEvent.change(within(findingsPanel).getByLabelText("Status"), {
      target: { value: "open" }
    });
    fireEvent.change(within(findingsPanel).getByLabelText("Severity"), {
      target: { value: "critical" }
    });
    fireEvent.click(within(findingsPanel).getByRole("button", { name: "Filter" }));
    await waitFor(() =>
      expect(calls.some((call) => call.path === "/api/v1/mcp/findings?status=open&severity=critical")).toBe(true)
    );
    const riskReason = await within(findingsPanel).findByLabelText("Risk Reason");
    fireEvent.change(riskReason, {
      target: { value: "Accepted for demo" }
    });
    fireEvent.click(within(findingsPanel).getByRole("button", { name: "Accept Risk" }));
    await waitFor(() =>
      expect(calls.some((call) => call.path === "/api/v1/mcp/findings/mcpf_1/accept-risk" && call.method === "POST")).toBe(true)
    );

    const trafficPanel = document.querySelector("[data-mcp-traffic]") as HTMLElement;
    fireEvent.change(within(trafficPanel).getByLabelText("Source Agent"), {
      target: { value: "agent_1" }
    });
    fireEvent.change(within(trafficPanel).getByLabelText("Server ID"), {
      target: { value: "mcpsrv_1" }
    });
    fireEvent.change(within(trafficPanel).getByLabelText("Tool ID"), {
      target: { value: "mcptool_1" }
    });
    fireEvent.change(within(trafficPanel).getByLabelText("Params JSON"), {
      target: { value: '{"claim_id":"CLM-1"}' }
    });
    fireEvent.click(within(trafficPanel).getByRole("button", { name: "Evaluate" }));
    await waitFor(() =>
      expect(calls.some((call) => call.path === "/api/v1/mcp/proxy/call" && call.body?.tool_id === "mcptool_1")).toBe(true)
    );
    fireEvent.change(within(trafficPanel).getByLabelText("Decision"), {
      target: { value: "denied" }
    });
    fireEvent.click(within(trafficPanel).getByRole("button", { name: "Filter" }));
    await waitFor(() =>
      expect(calls.some((call) => call.path === "/api/v1/mcp/traffic?decision=denied")).toBe(true)
    );

    const approvalsPanel = document.querySelector("[data-mcp-approvals]") as HTMLElement;
    fireEvent.change(within(approvalsPanel).getByLabelText("Approve Reason"), {
      target: { value: "Approved for break-glass" }
    });
    fireEvent.click(within(approvalsPanel).getByRole("button", { name: "Approve" }));
    await waitFor(() =>
      expect(calls.some((call) => call.path === "/api/v1/mcp/approvals/mcpappr_1/approve")).toBe(true)
    );
    fireEvent.change(within(approvalsPanel).getByLabelText("Deny Reason"), {
      target: { value: "Denied after review" }
    });
    fireEvent.click(within(approvalsPanel).getByRole("button", { name: "Deny" }));
    await waitFor(() =>
      expect(calls.some((call) => call.path === "/api/v1/mcp/approvals/mcpappr_1/deny")).toBe(true)
    );

    const rateLimitPanel = document.querySelector("[data-mcp-rate-limits]") as HTMLElement;
    fireEvent.change(within(rateLimitPanel).getByLabelText("Target ID"), {
      target: { value: "mcptool_1" }
    });
    fireEvent.change(within(rateLimitPanel).getByLabelText("Max Calls"), {
      target: { value: "10" }
    });
    fireEvent.click(within(rateLimitPanel).getByRole("button", { name: "Create" }));
    await waitFor(() =>
      expect(calls.some((call) => call.path === "/api/v1/mcp/rate-limits" && call.method === "POST")).toBe(true)
    );
  });

  it("does not render decision forms for final approvals", async () => {
    renderWithQueryClient(<McpPage />);

    const approvalsPanel = await screen.findByText("Approval Queue");
    const panel = approvalsPanel.closest("[data-mcp-approvals]") as HTMLElement;
    fireEvent.change(within(panel).getByLabelText("Status"), {
      target: { value: "approved" }
    });
    fireEvent.click(within(panel).getByRole("button", { name: "Filter" }));

    expect(await within(panel).findByText("Approved previously")).toBeInTheDocument();
    expect(within(panel).queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
    expect(within(panel).queryByRole("button", { name: "Deny" })).not.toBeInTheDocument();
  });

  it("rejects invalid proxy params JSON before submitting", () => {
    const form = document.createElement("form");
    form.innerHTML = `
      <input name="source_agent_id" value="agent_1" />
      <input name="server_id" value="mcpsrv_1" />
      <input name="tool_id" value="mcptool_1" />
      <textarea name="params">[]</textarea>
    `;

    expect(() => mcpProxyCallPayloadFromForm(form)).toThrow("Params JSON must be a JSON object.");
  });
});

interface RecordedCall {
  path: string;
  method: string;
  body: Record<string, unknown> | null;
}

function mockMcpFetch() {
  const calls: RecordedCall[] = [];
  vi.stubGlobal("fetch", async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const parsed = new URL(url, "http://test.local");
    const path = `${parsed.pathname}${parsed.search}`;
    const method = init?.method ?? "GET";
    const body = typeof init?.body === "string" ? (JSON.parse(init.body) as Record<string, unknown>) : null;
    calls.push({ path, method, body });

    if (path === "/api/v1/mcp/servers" && method === "POST") {
      return json({ ...mcpServer, id: "mcpsrv_2", name: body?.name ?? "Billing MCP" }, 201);
    }
    if (path.startsWith("/api/v1/mcp/servers") && path.endsWith("/discover-tools")) {
      return json({ server_id: "mcpsrv_1", discovered_count: 1, tools: [mcpTool] }, 201);
    }
    if (path.startsWith("/api/v1/mcp/servers") && path.endsWith("/scan")) {
      return json(mcpScan, 201);
    }
    if (path === "/api/v1/mcp/servers") {
      return json([mcpServer]);
    }
    if (path.startsWith("/api/v1/mcp/tools/")) {
      return json(mcpTool);
    }
    if (path.startsWith("/api/v1/mcp/tools")) {
      return json([mcpTool]);
    }
    if (path.startsWith("/api/v1/mcp/scans/")) {
      return json({ ...mcpScan, findings: [mcpFinding] });
    }
    if (path.startsWith("/api/v1/mcp/scans")) {
      return json([mcpScan]);
    }
    if (path.includes("/api/v1/mcp/findings/") && method === "POST") {
      return json({ ...mcpFinding, status: path.endsWith("/resolve") ? "resolved" : "accepted_risk" });
    }
    if (path.startsWith("/api/v1/mcp/findings")) {
      return json([mcpFinding]);
    }
    if (path === "/api/v1/mcp/proxy/call" && method === "POST") {
      return json({ ...mcpTraffic, id: "mcpcall_3", params_summary: body?.params ?? {} }, 201);
    }
    if (path.startsWith("/api/v1/mcp/traffic")) {
      return json([mcpTraffic]);
    }
    if (path.includes("/api/v1/mcp/approvals/") && method === "POST") {
      return json({ ...mcpApproval, status: path.endsWith("/approve") ? "approved" : "denied" });
    }
    if (path === "/api/v1/mcp/approvals?status=approved") {
      return json([approvedMcpApproval]);
    }
    if (path.startsWith("/api/v1/mcp/approvals")) {
      return json([mcpApproval]);
    }
    if (path === "/api/v1/mcp/rate-limits" && method === "POST") {
      return json({ ...mcpRateLimit, id: "mcprl_2", max_calls: body?.max_calls ?? 10 }, 201);
    }
    if (path.startsWith("/api/v1/mcp/rate-limits")) {
      return json([mcpRateLimit]);
    }
    return json({});
  });
  return calls;
}

function json(value: unknown, status = 200) {
  return new Response(JSON.stringify(value), {
    status,
    headers: { "Content-Type": "application/json" }
  });
}
