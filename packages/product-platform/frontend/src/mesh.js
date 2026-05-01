import { escapeHtml } from "./html.js";

const ROUTE_PROTOCOLS = ["a2a", "mcp", "iatp", "acp"];
const BRIDGE_TYPES = ["mcp", "a2a", "iatp", "acp", "custom"];

export function renderMeshPage(state) {
  const topology = state?.meshTopology ?? { nodes: [], edges: [] };
  const messages = state?.meshMessages ?? [];
  const handoffs = state?.meshHandoffs ?? [];
  const protocolBridges = state?.protocolBridges ?? [];
  const selectedProtocolBridge = state?.selectedProtocolBridge ?? protocolBridges[0] ?? null;
  return `
    <section class="page-heading" data-route-page="/mesh">
      <p class="section-label">Operations</p>
      <h1>Mesh</h1>
      <p>Agent mesh topology, routes, discovery, and cross-agent coordination.</p>
    </section>
    <section class="mesh-workspace" aria-label="Mesh workspace">
      ${renderMeshTopologyGraph(topology)}
      ${renderProtocolBridgesPanel({
        bridges: protocolBridges,
        selectedBridge: selectedProtocolBridge,
        agents: state?.protocolBridgeAgents ?? []
      })}
      ${renderMeshMessagesTable({ messages, filters: state?.meshMessageFilter ?? {} })}
      ${renderMeshHandoffsTable({ handoffs, filters: state?.meshHandoffFilter ?? {} })}
    </section>
  `;
}

export function renderMeshTopologyGraph(topology = { nodes: [], edges: [] }) {
  return `
    <article class="workspace-panel mesh-topology" data-mesh-topology>
      <header class="panel-header">
        <div>
          <p class="section-label">Topology</p>
          <h2>Live Edges</h2>
        </div>
        <span class="status-pill">${escapeHtml(String(topology.message_count ?? 0))} messages</span>
      </header>
      <div class="topology-grid">
        <div class="topology-nodes">
          ${(topology.nodes ?? [])
            .map(
              (node) => `
                <article data-topology-node="${escapeHtml(node.agent_id)}">
                  <strong>${escapeHtml(node.name ?? node.agent_id)}</strong>
                  <span>${escapeHtml(node.status ?? "unknown")} · ${escapeHtml(node.trust_tier ?? "unscored")}</span>
                </article>
              `
            )
            .join("") || '<div class="empty-state"><strong>No nodes</strong><span>No messages</span></div>'}
        </div>
        <div class="topology-edges">
          ${(topology.edges ?? [])
            .map(
              (edge) => `
                <article data-topology-edge="${escapeHtml(edge.source_agent_id)}:${escapeHtml(edge.target_agent_id)}:${escapeHtml(edge.protocol)}">
                  <strong>${escapeHtml(edge.source_agent_id)} -> ${escapeHtml(edge.target_agent_id)}</strong>
                  <span>${escapeHtml(edge.protocol)} · ${escapeHtml(String(edge.volume))} · ${escapeHtml(percent(edge.deny_rate))}</span>
                </article>
              `
            )
            .join("") || '<div class="empty-state"><strong>No edges</strong><span>No traffic</span></div>'}
        </div>
      </div>
    </article>
  `;
}

export function renderMeshMessagesTable({ messages = [], filters = {} } = {}) {
  const rows = messages
    .map(
      (message) => `
        <tr data-mesh-message-row="${escapeHtml(message.id)}">
          <td><strong>${escapeHtml(message.source_agent_name ?? message.source_agent_id)}</strong><small>to ${escapeHtml(message.target_agent_name ?? message.target_agent_id)}</small></td>
          <td>${escapeHtml(message.protocol)}</td>
          <td>${escapeHtml(message.action)}</td>
          <td><span class="status-pill">${escapeHtml(message.decision)}</span></td>
          <td>${escapeHtml(String(message.latency_ms))}</td>
          <td><button type="button" data-mesh-message-detail-open="${escapeHtml(message.id)}">Details</button></td>
        </tr>
      `
    )
    .join("");
  return `
    <article class="workspace-panel mesh-messages" data-mesh-messages>
      <header class="panel-header">
        <div>
          <p class="section-label">Messages</p>
          <h2>Message Feed</h2>
        </div>
      </header>
      <form class="filter-bar" data-mesh-message-filter>
        <label><span>Source</span><input name="source_agent_id" value="${escapeHtml(filters.source_agent_id ?? "")}"></label>
        <label><span>Target</span><input name="target_agent_id" value="${escapeHtml(filters.target_agent_id ?? "")}"></label>
        <label><span>Protocol</span><input name="protocol" value="${escapeHtml(filters.protocol ?? "")}"></label>
        <label><span>Decision</span><input name="decision" value="${escapeHtml(filters.decision ?? "")}"></label>
        <button type="submit">Filter</button>
      </form>
      ${
        messages.length
          ? `<table class="data-table">
              <thead><tr><th>Route</th><th>Protocol</th><th>Action</th><th>Decision</th><th>Latency</th><th>Detail</th></tr></thead>
              <tbody>${rows}</tbody>
            </table>`
          : '<div class="empty-state" data-mesh-messages-empty><strong>No messages</strong><span>Awaiting traffic</span></div>'
      }
    </article>
  `;
}

export function renderMeshHandoffsTable({ handoffs = [], filters = {} } = {}) {
  const rows = handoffs
    .map(
      (handoff) => `
        <tr data-mesh-handoff-row="${escapeHtml(handoff.id)}">
          <td><strong>${escapeHtml(handoff.source_agent_name ?? handoff.source_agent_id)}</strong><small>to ${escapeHtml(handoff.target_agent_name ?? handoff.target_agent_id)}</small></td>
          <td>${escapeHtml(handoff.task_type)}</td>
          <td>${escapeHtml(handoff.trust_result)} / ${escapeHtml(handoff.policy_result)}</td>
          <td><span class="status-pill">${escapeHtml(handoff.status)}</span></td>
          <td>${escapeHtml(handoff.reason)}</td>
          <td><button type="button" data-mesh-handoff-detail-open="${escapeHtml(handoff.id)}">Details</button></td>
        </tr>
      `
    )
    .join("");
  return `
    <article class="workspace-panel mesh-handoffs" data-mesh-handoffs>
      <header class="panel-header">
        <div>
          <p class="section-label">Handoffs</p>
          <h2>Task Transfers</h2>
        </div>
      </header>
      <form class="filter-bar" data-mesh-handoff-filter>
        <label><span>Source</span><input name="source_agent_id" value="${escapeHtml(filters.source_agent_id ?? "")}"></label>
        <label><span>Target</span><input name="target_agent_id" value="${escapeHtml(filters.target_agent_id ?? "")}"></label>
        <label><span>Status</span><input name="status" value="${escapeHtml(filters.status ?? "")}"></label>
        <button type="submit">Filter</button>
      </form>
      ${
        handoffs.length
          ? `<table class="data-table">
              <thead><tr><th>Route</th><th>Task</th><th>Trust / Policy</th><th>Status</th><th>Reason</th><th>Detail</th></tr></thead>
              <tbody>${rows}</tbody>
            </table>`
          : '<div class="empty-state" data-mesh-handoffs-empty><strong>No handoffs</strong><span>Awaiting transfers</span></div>'
      }
    </article>
  `;
}

export function renderProtocolBridgesPanel({ bridges = [], selectedBridge = null, agents = [] } = {}) {
  const selected = selectedBridge ?? bridges[0] ?? null;
  const rows = bridges
    .map((bridge) => {
      const health = bridge.current_health?.status ?? bridge.status ?? "unknown";
      return `
        <tr data-protocol-bridge-row="${escapeHtml(bridge.id)}">
          <td><strong>${escapeHtml(bridge.name)}</strong><small>${escapeHtml(bridge.bridge_type)}</small></td>
          <td><span class="status-pill">${escapeHtml(health)}</span></td>
          <td>${escapeHtml(bridge.current_health?.checked_at ?? "not checked")}</td>
          <td><button type="button" data-protocol-bridge-open="${escapeHtml(bridge.id)}">Details</button></td>
        </tr>
      `;
    })
    .join("");
  return `
    <article class="workspace-panel protocol-bridges" data-protocol-bridges>
      <header class="panel-header">
        <div>
          <p class="section-label">Protocol Bridges</p>
          <h2>Bridge Control</h2>
        </div>
      </header>
      <form class="bridge-form-grid" data-protocol-bridge-create-form>
        <label><span>Name</span><input name="name" required></label>
        <label><span>Type</span><select name="bridge_type">${BRIDGE_TYPES.map((type) => `<option value="${type}">${type.toUpperCase()}</option>`).join("")}</select></label>
        <label><span>Endpoint</span><input name="endpoint" type="url"></label>
        <label><span>Secret Id</span><input name="secret_id"></label>
        <button type="submit">Register</button>
      </form>
      <div class="bridge-management-grid">
        <section class="bridge-list-panel" data-protocol-bridge-list>
          ${
            bridges.length
              ? `<table class="data-table">
                  <thead><tr><th>Bridge</th><th>Health</th><th>Checked</th><th>Detail</th></tr></thead>
                  <tbody>${rows}</tbody>
                </table>`
              : '<div class="empty-state" data-protocol-bridge-empty><strong>No bridges</strong><span>Register a bridge</span></div>'
          }
        </section>
        ${renderProtocolBridgeDetail(selected, agents)}
      </div>
    </article>
  `;
}

export function renderProtocolBridgeDetail(bridge, agents = []) {
  if (!bridge) {
    return '<section class="bridge-detail-panel empty-state" data-protocol-bridge-detail><strong>No bridge selected</strong><span>Register or select a bridge</span></section>';
  }
  const health = bridge.current_health;
  const routes = bridge.routes ?? [];
  const routeRows = routes
    .map(
      (route) => `
        <tr data-protocol-bridge-route-row="${escapeHtml(route.id)}">
          <td>${escapeHtml(route.source_protocol)} -> ${escapeHtml(route.target_protocol)}</td>
          <td>${escapeHtml(route.source_agent_name ?? route.source_agent_id ?? "any")}</td>
          <td>${escapeHtml(route.target_agent_name ?? route.target_agent_id ?? "any")}</td>
          <td><span class="status-pill">${route.enabled ? "enabled" : "disabled"}</span></td>
        </tr>
      `
    )
    .join("");
  return `
    <section class="bridge-detail-panel" data-protocol-bridge-detail="${escapeHtml(bridge.id)}">
      <div class="inline-warning" data-protocol-bridge-limited-warning>
        <strong>Limited runtime</strong>
        <span>AgentMesh bridge adapters are placeholder/pass-through implementations, so runtime delivery is limited and not reported as healthy.</span>
      </div>
      <dl class="metadata-grid">
        <dt>Name</dt><dd>${escapeHtml(bridge.name)}</dd>
        <dt>Type</dt><dd>${escapeHtml(bridge.bridge_type)}</dd>
        <dt>Status</dt><dd>${escapeHtml(bridge.status)}</dd>
        <dt>Endpoint</dt><dd>${escapeHtml(bridge.config?.endpoint ?? bridge.config?.url ?? "not configured")}</dd>
      </dl>
      <section class="bridge-health-panel" data-protocol-bridge-health-panel>
        <header class="subsection-header">
          <h3>Health</h3>
          <button type="button" data-protocol-bridge-health-check="${escapeHtml(bridge.id)}">Run Check</button>
        </header>
        <p class="inline-status">
          <strong>${escapeHtml(health?.status ?? "not checked")}</strong>
          <span>${escapeHtml(health?.message ?? "No health check has been recorded.")}</span>
        </p>
      </section>
      <section class="bridge-routes-panel">
        <header class="subsection-header">
          <h3>Routes</h3>
        </header>
        ${
          routes.length
            ? `<table class="data-table">
                <thead><tr><th>Protocol</th><th>Source</th><th>Target</th><th>Status</th></tr></thead>
                <tbody>${routeRows}</tbody>
              </table>`
            : '<div class="empty-state" data-protocol-bridge-routes-empty><strong>No routes</strong><span>Add a route</span></div>'
        }
        <form class="route-editor-grid" data-protocol-bridge-route-form data-bridge-id="${escapeHtml(bridge.id)}">
          <label><span>Source Protocol</span><select name="source_protocol" data-protocol-source-protocol>${protocolOptions("a2a")}</select></label>
          <label><span>Target Protocol</span><select name="target_protocol" data-protocol-target-protocol>${protocolOptions("mcp")}</select></label>
          <label><span>Source Agent</span><select name="source_agent_id">${agentOptions(agents)}</select></label>
          <label><span>Target Agent</span><select name="target_agent_id">${agentOptions(agents)}</select></label>
          <label><span>Policy Binding</span><input name="policy_binding_id"></label>
          <button type="submit">Add Route</button>
        </form>
      </section>
    </section>
  `;
}

export function renderMeshMessageDetail(message) {
  return `
    <section class="mesh-detail" data-mesh-message-detail="${escapeHtml(message.id)}">
      <dl class="metadata-grid">
        <dt>Route</dt><dd>${escapeHtml(message.source_agent_id)} -> ${escapeHtml(message.target_agent_id)}</dd>
        <dt>Protocol</dt><dd>${escapeHtml(message.protocol)}</dd>
        <dt>Decision</dt><dd>${escapeHtml(message.decision)}</dd>
        <dt>Correlation</dt><dd>${escapeHtml(message.correlation_id ?? "none")}</dd>
      </dl>
      <pre class="json-preview">${escapeHtml(JSON.stringify(message.payload_summary ?? {}, null, 2))}</pre>
    </section>
  `;
}

export function renderMeshHandoffDetail(handoff) {
  return `
    <section class="mesh-detail" data-mesh-handoff-detail="${escapeHtml(handoff.id)}">
      <dl class="metadata-grid">
        <dt>Route</dt><dd>${escapeHtml(handoff.source_agent_id)} -> ${escapeHtml(handoff.target_agent_id)}</dd>
        <dt>Task</dt><dd>${escapeHtml(handoff.task_type)}</dd>
        <dt>Status</dt><dd>${escapeHtml(handoff.status)}</dd>
        <dt>Reason</dt><dd>${escapeHtml(handoff.reason)}</dd>
      </dl>
      <pre class="json-preview">${escapeHtml(JSON.stringify(handoff.metadata ?? {}, null, 2))}</pre>
    </section>
  `;
}

export function meshMessageParamsFromForm(form) {
  return meshMessageParamsFromValues(Object.fromEntries(new FormData(form)));
}

export function meshMessageParamsFromValues(values) {
  return {
    source_agent_id: String(values.source_agent_id ?? ""),
    target_agent_id: String(values.target_agent_id ?? ""),
    protocol: String(values.protocol ?? ""),
    decision: String(values.decision ?? "")
  };
}

export function meshHandoffParamsFromForm(form) {
  return meshHandoffParamsFromValues(Object.fromEntries(new FormData(form)));
}

export function meshHandoffParamsFromValues(values) {
  return {
    source_agent_id: String(values.source_agent_id ?? ""),
    target_agent_id: String(values.target_agent_id ?? ""),
    status: String(values.status ?? "")
  };
}

export function protocolBridgePayloadFromForm(form) {
  return protocolBridgePayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function protocolBridgePayloadFromValues(values) {
  const config = {};
  const endpoint = String(values.endpoint ?? "").trim();
  const secretId = String(values.secret_id ?? "").trim();
  if (endpoint) {
    config.endpoint = endpoint;
  }
  if (secretId) {
    config.secret_id = secretId;
  }
  return {
    name: String(values.name ?? "").trim(),
    bridge_type: String(values.bridge_type ?? "mcp").trim().toLowerCase(),
    config
  };
}

export function protocolBridgeRoutePayloadFromForm(form) {
  return protocolBridgeRoutePayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function protocolBridgeRoutePayloadFromValues(values) {
  const sourceProtocol = normalizeRouteProtocol(values.source_protocol);
  const targetProtocol = normalizeRouteProtocol(values.target_protocol);
  return {
    source_protocol: sourceProtocol,
    target_protocol: targetProtocol,
    source_agent_id: optionalString(values.source_agent_id),
    target_agent_id: optionalString(values.target_agent_id),
    policy_binding_id: optionalString(values.policy_binding_id),
    enabled: values.enabled === undefined ? true : values.enabled !== "false"
  };
}

function percent(value) {
  return `${Math.round(Number(value ?? 0) * 100)}% denied`;
}

function protocolOptions(selectedProtocol) {
  return ROUTE_PROTOCOLS.map(
    (protocol) =>
      `<option value="${protocol}"${protocol === selectedProtocol ? " selected" : ""}>${protocol.toUpperCase()}</option>`
  ).join("");
}

function agentOptions(agents = []) {
  return [
    '<option value="">Any agent</option>',
    ...agents.map(
      (agent) =>
        `<option value="${escapeHtml(agent.id)}">${escapeHtml(agent.name ?? agent.id)}</option>`
    )
  ].join("");
}

function normalizeRouteProtocol(value) {
  const protocol = String(value ?? "").trim().toLowerCase();
  if (!ROUTE_PROTOCOLS.includes(protocol)) {
    throw new Error("Unsupported route protocol.");
  }
  return protocol;
}

function optionalString(value) {
  const text = String(value ?? "").trim();
  return text || null;
}
