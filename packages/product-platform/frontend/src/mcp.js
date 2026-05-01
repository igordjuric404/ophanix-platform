import { escapeHtml } from "./html.js";

const AUTH_TYPES = ["none", "api_key", "bearer", "oauth", "mtls", "custom"];
const SERVER_STATUSES = ["registered", "active", "disabled", "error"];
const FINDING_STATUSES = ["", "open", "accepted_risk", "resolved", "false_positive"];
const FINDING_SEVERITIES = ["", "critical", "warning", "info"];
const TRAFFIC_DECISIONS = ["", "allowed", "denied", "escalated"];
const RATE_LIMIT_TARGET_TYPES = ["agent", "mcp-server", "mcp-tool"];

export function renderMcpPage(state) {
  const servers = state?.mcpServers ?? [];
  const tools = state?.mcpTools ?? [];
  const scanRuns = state?.mcpScanRuns ?? [];
  const findings = state?.mcpFindings ?? [];
  const findingFilter = state?.mcpFindingFilter ?? {};
  const traffic = state?.mcpTraffic ?? [];
  const trafficFilter = state?.mcpTrafficFilter ?? {};
  const approvals = state?.mcpApprovals ?? [];
  const rateLimits = state?.mcpRateLimits ?? [];
  return `
    <section class="page-heading" data-route-page="/mcp">
      <p class="section-label">Security</p>
      <h1>MCP Security</h1>
      <p>MCP servers, tools, calls, policy decisions, and blocked activity.</p>
    </section>
    <section class="mcp-workspace" aria-label="MCP Security workspace">
      ${renderMcpServersPanel({ servers, scanRuns })}
      ${renderMcpToolsPanel({ tools, findings })}
      ${renderMcpScanRunsPanel({ scanRuns })}
      ${renderMcpFindingsPanel({ findings, filter: findingFilter })}
      ${renderMcpTrafficPanel({ traffic, filter: trafficFilter })}
      ${renderMcpApprovalsPanel({ approvals })}
      ${renderMcpRateLimitsPanel({ rateLimits })}
    </section>
  `;
}

export function renderMcpServersPanel({ servers = [], scanRuns = [] } = {}) {
  const latestScanByServer = latestScanRunsByServer(scanRuns);
  const rows = servers
    .map((server) => {
      const latestScan = latestScanByServer.get(server.id);
      return `
        <tr data-mcp-server-row="${escapeHtml(server.id)}">
          <td><strong>${escapeHtml(server.name)}</strong><small>${escapeHtml(server.endpoint_url)}</small></td>
          <td><span class="status-pill">${escapeHtml(server.status)}</span></td>
          <td>${escapeHtml(server.owner_display_name ?? server.owner_user_id)}</td>
          <td>${escapeHtml(String(server.tool_count ?? 0))}</td>
          <td><span class="status-pill">${escapeHtml(latestScan?.status ?? "not_scanned")}</span><small>${escapeHtml(String(latestScan?.summary?.finding_count ?? 0))} findings</small></td>
          <td>
            <div class="inline-actions">
              <button type="button" data-mcp-discover-tools="${escapeHtml(server.id)}">Discover</button>
              <button type="button" data-mcp-run-scan="${escapeHtml(server.id)}">Scan</button>
            </div>
          </td>
        </tr>
      `;
    })
    .join("");
  return `
    <article class="workspace-panel mcp-servers" data-mcp-servers>
      <header class="panel-header">
        <div>
          <p class="section-label">Servers</p>
          <h2>Server Registry</h2>
        </div>
      </header>
      <form class="bridge-form-grid" data-mcp-server-register-form>
        <label><span>Name</span><input name="name" required></label>
        <label><span>Endpoint</span><input name="endpoint_url" type="url" required></label>
        <label><span>Owner</span><input name="owner_user_id" required></label>
        <label><span>Auth</span><select name="auth_type">${options(AUTH_TYPES, "none")}</select></label>
        <label><span>Status</span><select name="status">${options(SERVER_STATUSES, "registered")}</select></label>
        <label><span>Policy Pack</span><input name="policy_pack_id"></label>
        <button type="submit">Register</button>
      </form>
      ${
        servers.length
          ? `<table class="data-table">
              <thead><tr><th>Server</th><th>Status</th><th>Owner</th><th>Tools</th><th>Latest Scan</th><th>Action</th></tr></thead>
              <tbody>${rows}</tbody>
            </table>`
          : '<div class="empty-state" data-mcp-servers-empty><strong>No servers</strong><span>Register a server</span></div>'
      }
    </article>
  `;
}

export function renderMcpToolsPanel({ tools = [], findings = [] } = {}) {
  const findingCounts = openFindingCountsByTool(findings);
  const rows = tools
    .map(
      (tool) => `
        <tr data-mcp-tool-row="${escapeHtml(tool.id)}">
          <td><strong>${escapeHtml(tool.name)}</strong><small>${escapeHtml(tool.server_name ?? tool.server_id)}</small></td>
          <td>${escapeHtml(tool.current_version?.schema_hash ?? "not discovered")}</td>
          <td><span class="status-pill">${escapeHtml(tool.risk_level)}</span></td>
          <td>${escapeHtml(tool.policy_status ?? "inherited")}</td>
          <td><span class="status-pill" data-mcp-tool-finding-badge="${escapeHtml(tool.id)}">${escapeHtml(findingBadgeText(findingCounts.get(tool.id) ?? 0))}</span></td>
          <td><span class="status-pill">${escapeHtml(tool.status)}</span></td>
          <td><button type="button" data-mcp-tool-detail-open="${escapeHtml(tool.id)}">Details</button></td>
        </tr>
      `
    )
    .join("");
  return `
    <article class="workspace-panel mcp-tools" data-mcp-tools>
      <header class="panel-header">
        <div>
          <p class="section-label">Tools</p>
          <h2>Tool Registry</h2>
        </div>
      </header>
      ${
        tools.length
          ? `<table class="data-table">
              <thead><tr><th>Tool</th><th>Schema Hash</th><th>Risk</th><th>Policy</th><th>Findings</th><th>Status</th><th>Detail</th></tr></thead>
              <tbody>${rows}</tbody>
            </table>`
          : '<div class="empty-state" data-mcp-tools-empty><strong>No tools</strong><span>Run discovery</span></div>'
      }
    </article>
  `;
}

export function renderMcpScanRunsPanel({ scanRuns = [] } = {}) {
  const rows = scanRuns
    .map(
      (scan) => `
        <tr data-mcp-scan-row="${escapeHtml(scan.id)}">
          <td><strong>${escapeHtml(scan.server_name ?? scan.server_id)}</strong><small>${escapeHtml(scan.started_at)}</small></td>
          <td><span class="status-pill">${escapeHtml(scan.status)}</span></td>
          <td>${escapeHtml(String(scan.summary?.tools_scanned ?? 0))}</td>
          <td>${escapeHtml(String(scan.summary?.finding_count ?? 0))}</td>
          <td>${escapeHtml(scan.finished_at ?? "running")}</td>
        </tr>
      `
    )
    .join("");
  return `
    <article class="workspace-panel mcp-scans" data-mcp-scans>
      <header class="panel-header">
        <div>
          <p class="section-label">Security Scans</p>
          <h2>Scan History</h2>
        </div>
      </header>
      ${
        scanRuns.length
          ? `<table class="data-table">
              <thead><tr><th>Server</th><th>Status</th><th>Tools</th><th>Findings</th><th>Finished</th></tr></thead>
              <tbody>${rows}</tbody>
            </table>`
          : '<div class="empty-state" data-mcp-scans-empty><strong>No scans</strong><span>Run a server scan</span></div>'
      }
    </article>
  `;
}

export function renderMcpFindingsPanel({ findings = [], filter = {} } = {}) {
  const rows = findings
    .map(
      (finding) => `
        <tr data-mcp-finding-row="${escapeHtml(finding.id)}">
          <td><strong>${escapeHtml(finding.title)}</strong><small>${escapeHtml(finding.finding_type)}</small></td>
          <td>${escapeHtml(finding.tool_name ?? finding.tool_id)}<small>${escapeHtml(finding.server_name ?? finding.server_id)}</small></td>
          <td><span class="status-pill">${escapeHtml(finding.severity)}</span></td>
          <td><span class="status-pill">${escapeHtml(finding.status)}</span></td>
          <td>${escapeHtml(finding.created_at)}</td>
          <td><button type="button" data-mcp-finding-detail-open="${escapeHtml(finding.id)}">Details</button></td>
        </tr>
      `
    )
    .join("");
  return `
    <article class="workspace-panel mcp-findings" data-mcp-findings>
      <header class="panel-header">
        <div>
          <p class="section-label">Findings</p>
          <h2>Security Findings</h2>
        </div>
      </header>
      <form class="filter-bar" data-mcp-finding-filter-form>
        <label><span>Status</span><select name="status">${options(FINDING_STATUSES, filter.status ?? "", "All statuses")}</select></label>
        <label><span>Severity</span><select name="severity">${options(FINDING_SEVERITIES, filter.severity ?? "", "All severities")}</select></label>
        <label><span>Server</span><input name="server_id" value="${escapeHtml(filter.server_id ?? "")}"></label>
        <label><span>Tool</span><input name="tool_id" value="${escapeHtml(filter.tool_id ?? "")}"></label>
        <button type="submit">Apply</button>
      </form>
      ${
        findings.length
          ? `<table class="data-table">
              <thead><tr><th>Finding</th><th>Tool</th><th>Severity</th><th>Status</th><th>Created</th><th>Detail</th></tr></thead>
              <tbody>${rows}</tbody>
            </table>`
          : '<div class="empty-state" data-mcp-findings-empty><strong>No findings</strong><span>Run a security scan</span></div>'
      }
    </article>
  `;
}

export function renderMcpTrafficPanel({ traffic = [], filter = {} } = {}) {
  const rows = traffic
    .map(
      (call) => `
        <tr data-mcp-traffic-row="${escapeHtml(call.id)}">
          <td><strong>${escapeHtml(call.tool_name ?? call.tool_id)}</strong><small>${escapeHtml(call.server_name ?? call.server_id)}</small></td>
          <td>${escapeHtml(call.source_agent_name ?? call.source_agent_id)}</td>
          <td><span class="status-pill">${escapeHtml(call.decision)}</span></td>
          <td>${escapeHtml(call.reason)}</td>
          <td>${escapeHtml(call.matched_policy_id ?? "none")}</td>
          <td>${escapeHtml(call.sanitizer_action ?? "none")}</td>
          <td>${escapeHtml(call.created_at)}</td>
        </tr>
      `
    )
    .join("");
  return `
    <article class="workspace-panel mcp-traffic" data-mcp-traffic>
      <header class="panel-header">
        <div>
          <p class="section-label">Proxy</p>
          <h2>Proxy Traffic</h2>
        </div>
      </header>
      <form class="filter-bar" data-mcp-traffic-filter-form>
        <label><span>Decision</span><select name="decision">${options(TRAFFIC_DECISIONS, filter.decision ?? "", "All decisions")}</select></label>
        <label><span>Server</span><input name="server_id" value="${escapeHtml(filter.server_id ?? "")}"></label>
        <label><span>Tool</span><input name="tool_id" value="${escapeHtml(filter.tool_id ?? "")}"></label>
        <label><span>Agent</span><input name="source_agent_id" value="${escapeHtml(filter.source_agent_id ?? "")}"></label>
        <button type="submit">Apply</button>
      </form>
      ${
        traffic.length
          ? `<table class="data-table">
              <thead><tr><th>Tool</th><th>Agent</th><th>Decision</th><th>Reason</th><th>Policy</th><th>Sanitizer</th><th>Created</th></tr></thead>
              <tbody>${rows}</tbody>
            </table>`
          : '<div class="empty-state" data-mcp-traffic-empty><strong>No traffic</strong><span>Proxy calls will appear here</span></div>'
      }
    </article>
  `;
}

export function renderMcpApprovalsPanel({ approvals = [] } = {}) {
  const rows = approvals
    .map(
      (approval) => {
        const call = approval.tool_call ?? {};
        return `
          <tr data-mcp-approval-row="${escapeHtml(approval.id)}">
            <td><strong>${escapeHtml(call.tool_name ?? approval.tool_call_id)}</strong><small>${escapeHtml(call.server_name ?? "")}</small></td>
            <td>${escapeHtml(approval.requested_by_agent_name ?? approval.requested_by_agent_id)}</td>
            <td><span class="status-pill">${escapeHtml(approval.status)}</span></td>
            <td>${escapeHtml(call.matched_policy_id ?? "none")}</td>
            <td>${escapeHtml(String(call.trust_score ?? "unknown"))}</td>
            <td><code>${escapeHtml(JSON.stringify(call.params_summary ?? {}))}</code></td>
            <td>
              <div class="inline-actions">
                <button type="button" data-mcp-approval-approve-open="${escapeHtml(approval.id)}">Approve</button>
                <button type="button" data-mcp-approval-deny-open="${escapeHtml(approval.id)}">Deny</button>
              </div>
              ${renderMcpApprovalDialogs(approval)}
            </td>
          </tr>
        `;
      }
    )
    .join("");
  return `
    <article class="workspace-panel mcp-approvals" data-mcp-approvals>
      <header class="panel-header">
        <div>
          <p class="section-label">Approvals</p>
          <h2>Approval Queue</h2>
        </div>
      </header>
      ${
        approvals.length
          ? `<table class="data-table">
              <thead><tr><th>Tool</th><th>Agent</th><th>Status</th><th>Policy</th><th>Trust</th><th>Params</th><th>Action</th></tr></thead>
              <tbody>${rows}</tbody>
            </table>`
          : '<div class="empty-state" data-mcp-approvals-empty><strong>No approvals</strong><span>Escalated calls will appear here</span></div>'
      }
    </article>
  `;
}

export function renderMcpRateLimitsPanel({ rateLimits = [] } = {}) {
  const rows = rateLimits
    .map(
      (limit) => `
        <tr data-mcp-rate-limit-row="${escapeHtml(limit.id)}">
          <td><strong>${escapeHtml(limit.target_type)}</strong><small>${escapeHtml(limit.target_id)}</small></td>
          <td>${escapeHtml(String(limit.window_seconds))}s</td>
          <td>${escapeHtml(String(limit.max_calls))}</td>
          <td><span class="status-pill">${escapeHtml(limit.enabled ? "enabled" : "disabled")}</span></td>
        </tr>
      `
    )
    .join("");
  return `
    <article class="workspace-panel mcp-rate-limits" data-mcp-rate-limits>
      <header class="panel-header">
        <div>
          <p class="section-label">Rate Limits</p>
          <h2>Rate Limit Configuration</h2>
        </div>
      </header>
      <form class="bridge-form-grid" data-mcp-rate-limit-form>
        <label><span>Target Type</span><select name="target_type">${options(RATE_LIMIT_TARGET_TYPES, "mcp-tool")}</select></label>
        <label><span>Target ID</span><input name="target_id" required></label>
        <label><span>Window</span><input name="window_seconds" type="number" min="1" value="60"></label>
        <label><span>Max Calls</span><input name="max_calls" type="number" min="1" value="60"></label>
        <label class="checkbox-row"><input name="enabled" type="checkbox" checked><span>Enabled</span></label>
        <button type="submit">Create</button>
      </form>
      ${
        rateLimits.length
          ? `<table class="data-table">
              <thead><tr><th>Target</th><th>Window</th><th>Max Calls</th><th>Status</th></tr></thead>
              <tbody>${rows}</tbody>
            </table>`
          : '<div class="empty-state" data-mcp-rate-limits-empty><strong>No rate limits</strong><span>Create a target limit</span></div>'
      }
    </article>
  `;
}

export function renderMcpToolDetail(tool) {
  const versions = tool?.versions ?? [];
  const versionRows = versions
    .map(
      (version) => `
        <tr data-mcp-tool-version-row="${escapeHtml(version.id)}">
          <td>${escapeHtml(version.discovered_at)}</td>
          <td>${escapeHtml(version.schema_hash)}</td>
          <td>${escapeHtml(version.scan_status)}</td>
        </tr>
      `
    )
    .join("");
  return `
    <section class="drawer-detail" data-mcp-tool-detail="${escapeHtml(tool.id)}">
      <dl class="metadata-grid">
        <dt>Tool</dt><dd>${escapeHtml(tool.name)}</dd>
        <dt>Server</dt><dd>${escapeHtml(tool.server_name ?? tool.server_id)}</dd>
        <dt>Status</dt><dd>${escapeHtml(tool.status)}</dd>
        <dt>Risk</dt><dd>${escapeHtml(tool.risk_level)}</dd>
        <dt>Current Hash</dt><dd>${escapeHtml(tool.current_version?.schema_hash ?? "not discovered")}</dd>
      </dl>
      <section class="schema-viewer" data-mcp-tool-schema>
        <h3>Schema</h3>
        <pre>${escapeHtml(JSON.stringify(tool.current_version?.schema ?? {}, null, 2))}</pre>
      </section>
      <section class="version-history" data-mcp-tool-version-history>
        <h3>Versions</h3>
        ${
          versions.length
            ? `<table class="data-table">
                <thead><tr><th>Discovered</th><th>Hash</th><th>Scan</th></tr></thead>
                <tbody>${versionRows}</tbody>
              </table>`
            : '<div class="empty-state"><strong>No versions</strong><span>Run discovery</span></div>'
        }
      </section>
    </section>
  `;
}

function renderMcpApprovalDialogs(approval) {
  const title = approval.tool_call?.tool_name ?? approval.tool_call_id;
  return `
    <dialog class="policy-exception-dialog mcp-action-dialog" data-mcp-approval-approve-modal="${escapeHtml(approval.id)}">
      <form method="dialog" class="dialog-close-row"><button type="submit">Close</button></form>
      <form data-mcp-approval-approve-form data-approval-id="${escapeHtml(approval.id)}">
        <h3>${escapeHtml(title)}</h3>
        <label><span>Reason</span><textarea name="reason" required placeholder="Approval justification"></textarea></label>
        <button type="submit">Approve</button>
      </form>
    </dialog>
    <dialog class="policy-exception-dialog mcp-action-dialog" data-mcp-approval-deny-modal="${escapeHtml(approval.id)}">
      <form method="dialog" class="dialog-close-row"><button type="submit">Close</button></form>
      <form data-mcp-approval-deny-form data-approval-id="${escapeHtml(approval.id)}">
        <h3>${escapeHtml(title)}</h3>
        <label><span>Reason</span><textarea name="reason" required placeholder="Denial reason"></textarea></label>
        <button type="submit">Deny</button>
      </form>
    </dialog>
  `;
}

export function renderMcpFindingDetail(finding) {
  return `
    <section class="drawer-detail" data-mcp-finding-detail="${escapeHtml(finding.id)}">
      <dl class="metadata-grid">
        <dt>Finding</dt><dd>${escapeHtml(finding.title)}</dd>
        <dt>Tool</dt><dd>${escapeHtml(finding.tool_name ?? finding.tool_id)}</dd>
        <dt>Server</dt><dd>${escapeHtml(finding.server_name ?? finding.server_id)}</dd>
        <dt>Severity</dt><dd>${escapeHtml(finding.severity)}</dd>
        <dt>Status</dt><dd>${escapeHtml(finding.status)}</dd>
        <dt>Tool Version</dt><dd>${escapeHtml(finding.tool_version_id ?? "unversioned")}</dd>
      </dl>
      <section class="finding-copy">
        <h3>Description</h3>
        <p>${escapeHtml(finding.description)}</p>
        <h3>Recommendation</h3>
        <p>${escapeHtml(finding.recommendation)}</p>
      </section>
      <section class="schema-viewer" data-mcp-finding-evidence>
        <h3>Evidence</h3>
        <pre>${escapeHtml(JSON.stringify(finding.evidence ?? {}, null, 2))}</pre>
      </section>
      <section class="mcp-finding-actions" data-mcp-finding-actions>
        <button type="button" data-mcp-accept-risk-open="${escapeHtml(finding.id)}">Accept Risk</button>
        <form data-mcp-finding-resolve-form data-finding-id="${escapeHtml(finding.id)}">
          <label><span>Resolution Note</span><input name="reason" placeholder="Fixed, removed, or no longer reproducible"></label>
          <button type="submit">Resolve</button>
        </form>
        <dialog class="policy-exception-dialog mcp-action-dialog" data-mcp-accept-risk-modal="${escapeHtml(finding.id)}">
          <form method="dialog" class="dialog-close-row">
            <button type="submit">Close</button>
          </form>
          <form data-mcp-finding-accept-risk-form data-finding-id="${escapeHtml(finding.id)}">
            <h3>${escapeHtml(finding.title)}</h3>
            <label>
              <span>Reason</span>
              <textarea name="reason" required placeholder="Business justification for accepting this schema version"></textarea>
            </label>
            <button type="submit">Accept Risk</button>
          </form>
        </dialog>
      </section>
    </section>
  `;
}

export function mcpServerPayloadFromForm(form) {
  return mcpServerPayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function mcpServerPayloadFromValues(values) {
  return {
    name: String(values.name ?? "").trim(),
    endpoint_url: String(values.endpoint_url ?? "").trim(),
    owner_user_id: String(values.owner_user_id ?? "").trim(),
    auth_type: String(values.auth_type ?? "none").trim().toLowerCase(),
    status: String(values.status ?? "registered").trim().toLowerCase(),
    policy_pack_id: emptyToNull(values.policy_pack_id)
  };
}

export function mcpFindingFilterParamsFromForm(form) {
  return mcpFindingFilterParamsFromValues(Object.fromEntries(new FormData(form)));
}

export function mcpFindingFilterParamsFromValues(values) {
  return {
    status: emptyToNull(values.status),
    severity: emptyToNull(values.severity),
    server_id: emptyToNull(values.server_id),
    tool_id: emptyToNull(values.tool_id)
  };
}

export function mcpFindingActionPayloadFromForm(form) {
  return mcpFindingActionPayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function mcpFindingActionPayloadFromValues(values) {
  return {
    reason: emptyToNull(values.reason)
  };
}

export function mcpTrafficFilterParamsFromForm(form) {
  return mcpTrafficFilterParamsFromValues(Object.fromEntries(new FormData(form)));
}

export function mcpTrafficFilterParamsFromValues(values) {
  return {
    decision: emptyToNull(values.decision),
    server_id: emptyToNull(values.server_id),
    tool_id: emptyToNull(values.tool_id),
    source_agent_id: emptyToNull(values.source_agent_id)
  };
}

export function mcpApprovalDecisionPayloadFromForm(form) {
  return mcpApprovalDecisionPayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function mcpApprovalDecisionPayloadFromValues(values) {
  return mcpFindingActionPayloadFromValues(values);
}

export function mcpRateLimitPayloadFromForm(form) {
  return mcpRateLimitPayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function mcpRateLimitPayloadFromValues(values) {
  return {
    target_type: String(values.target_type ?? "").trim(),
    target_id: String(values.target_id ?? "").trim(),
    window_seconds: Number.parseInt(String(values.window_seconds ?? "60"), 10),
    max_calls: Number.parseInt(String(values.max_calls ?? "60"), 10),
    enabled: values.enabled === "on" || values.enabled === true
  };
}

function options(values, selected, emptyLabel = null) {
  return values
    .map((value) => {
      const label = value === "" && emptyLabel ? emptyLabel : value;
      return `<option value="${escapeHtml(value)}" ${value === selected ? "selected" : ""}>${escapeHtml(label)}</option>`;
    })
    .join("");
}

function emptyToNull(value) {
  const stripped = String(value ?? "").trim();
  return stripped || null;
}

function latestScanRunsByServer(scanRuns) {
  const latest = new Map();
  for (const scan of scanRuns) {
    if (!latest.has(scan.server_id)) {
      latest.set(scan.server_id, scan);
    }
  }
  return latest;
}

function openFindingCountsByTool(findings) {
  const counts = new Map();
  for (const finding of findings) {
    if (finding.status !== "open") {
      continue;
    }
    counts.set(finding.tool_id, (counts.get(finding.tool_id) ?? 0) + 1);
  }
  return counts;
}

function findingBadgeText(count) {
  return count === 0 ? "clear" : `${count} open`;
}
