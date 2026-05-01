import { escapeHtml } from "./html.js";
import { renderAgentTrustTab } from "./trust.js";
import { renderMeshHandoffsTable, renderMeshMessagesTable } from "./mesh.js";

export function renderAgentsPage(state) {
  return `
    <section class="page-heading" data-route-page="/agents">
      <p class="section-label">Governance</p>
      <h1>Agents</h1>
      <p>Inventory, lifecycle, credentials, ownership, and capability requests.</p>
    </section>
    <section class="agent-workspace" aria-label="Agent registry workspace">
      ${renderAgentInventory(state?.agentInventory ?? [])}
      ${renderLifecycleWorkspace({
        agents: state?.agentInventory ?? [],
        orphanCandidates: state?.orphanCandidates ?? [],
        timeline: state?.agentTimeline ?? []
      })}
      ${renderCredentialWorkspace({
        credentials: state?.agentCredentials ?? [],
        expiringCredentials: state?.expiringCredentials ?? []
      })}
      ${renderAgentRegistrationWizard(state)}
      <article class="workspace-panel agent-queue" data-agent-approval-queue>
        <h2>Approval Queue</h2>
        <ul class="compact-list">
          <li><span>Pending approval</span><strong data-agent-queue-count>0</strong></li>
          <li><span>Credential tasks</span><strong>Queued after activation</strong></li>
          <li><span>Lifecycle audit</span><strong>Enabled</strong></li>
        </ul>
      </article>
    </section>
  `;
}

export function renderLifecycleWorkspace({ agents = [], orphanCandidates = [], timeline = [] } = {}) {
  return `
    <section class="workspace-panel lifecycle-workspace" data-agent-lifecycle-workspace>
      <header class="panel-header">
        <div>
          <p class="section-label">Lifecycle</p>
          <h2>Lifecycle Operations</h2>
        </div>
      </header>
      ${renderLifecycleFunnel(agents)}
      <div class="lifecycle-grid">
        ${renderApprovalQueue(agents.filter((agent) => agent.status === "pending_approval"))}
        ${renderOrphanCandidates(orphanCandidates)}
        ${renderLifecycleTimeline(timeline)}
      </div>
    </section>
  `;
}

export function renderLifecycleFunnel(agents = []) {
  const statuses = ["draft", "pending_approval", "provisioned", "active", "suspended", "orphaned"];
  const counts = new Map();
  for (const agent of agents) {
    counts.set(agent.status, (counts.get(agent.status) ?? 0) + 1);
  }
  return `
    <ol class="lifecycle-funnel" data-lifecycle-funnel>
      ${statuses
        .map(
          (status) => `
            <li>
              <span>${escapeHtml(status)}</span>
              <strong>${escapeHtml(String(counts.get(status) ?? 0))}</strong>
            </li>
          `
        )
        .join("")}
    </ol>
  `;
}

export function renderApprovalQueue(agents = []) {
  return `
    <article data-approval-queue>
      <h3>Approval Queue</h3>
      ${
        agents.length
          ? `<ul class="compact-list">${agents
              .map(
                (agent) => `
                  <li>
                    <a href="/agents?agent_id=${encodeURIComponent(agent.id)}">${escapeHtml(agent.name)}</a>
                    <strong>${escapeHtml(agent.framework)}</strong>
                  </li>
                `
              )
              .join("")}</ul>`
          : '<div class="empty-state"><strong>No pending agents</strong><span>0</span></div>'
      }
    </article>
  `;
}

export function renderOrphanCandidates(agents = []) {
  return `
    <article data-orphan-candidates>
      <h3>Orphan Candidates</h3>
      ${
        agents.length
          ? `<ul class="compact-list">${agents
              .map(
                (agent) => `
                  <li>
                    <a href="/agents?agent_id=${encodeURIComponent(agent.id)}">${escapeHtml(agent.name)}</a>
                    <strong>${escapeHtml(agent.last_heartbeat_at ?? "stale")}</strong>
                  </li>
                `
              )
              .join("")}</ul>`
          : '<div class="empty-state"><strong>No orphan candidates</strong><span>Clear</span></div>'
      }
    </article>
  `;
}

export function renderLifecycleTimeline(events = []) {
  return `
    <article data-lifecycle-timeline>
      <h3>Timeline</h3>
      ${
        events.length
          ? `<ul class="related-event-timeline">${events
              .map(
                (event) => `
                  <li>
                    <button type="button" data-related-event-id="${escapeHtml(event.id)}">
                      <span>${escapeHtml(event.event_type)}</span>
                      <strong>${escapeHtml(event.next_state ?? event.source)}</strong>
                      <small>${escapeHtml(event.created_at)}</small>
                    </button>
                  </li>
                `
              )
              .join("")}</ul>`
          : '<div class="empty-state"><strong>No lifecycle events</strong><span>Pending activity</span></div>'
      }
    </article>
  `;
}

export function renderLifecycleActionModal(agent, action) {
  const requiresReason = ["suspend", "decommission"].includes(action);
  return `
    <form class="lifecycle-action" data-lifecycle-action="${escapeHtml(action)}">
      <input type="hidden" name="agent_id" value="${escapeHtml(agent.id)}">
      <label>
        <span>Reason</span>
        <input name="reason" ${requiresReason ? "required" : ""}>
      </label>
      <button type="submit">${escapeHtml(action)}</button>
    </form>
  `;
}

export function renderAgentInventory(agents = []) {
  return `
    <article class="workspace-panel agent-inventory" data-agent-inventory>
      <header class="panel-header">
        <div>
          <p class="section-label">Inventory</p>
          <h2>Agent Inventory</h2>
        </div>
      </header>
      ${renderAgentFilterBar()}
      <div data-agent-inventory-table-region>
        ${
          agents.length
            ? renderAgentInventoryTable(agents)
            : '<div class="empty-state" data-agent-inventory-empty><strong>No agents</strong><span>Register Agent</span></div>'
        }
      </div>
    </article>
  `;
}

export function renderAgentInventoryTable(agents = []) {
  const rows = agents
    .map(
      (agent) => `
        <tr data-agent-row="${escapeHtml(agent.id)}">
          <td><strong>${escapeHtml(agent.name)}</strong><small>${escapeHtml(agent.id)}</small></td>
          <td>${escapeHtml(agent.status)}</td>
          <td>${escapeHtml(agent.framework)}</td>
          <td>${escapeHtml(agent.owner_user_id)}</td>
          <td>${escapeHtml(agent.sponsor_user_id)}</td>
          <td>${escapeHtml(agent.trust_tier ?? "pending")}</td>
          <td>
            <span class="status-pill">${escapeHtml(agent.credential_status ?? "pending")}</span>
            <small>${escapeHtml(agent.credential_expires_at ?? "no expiry")}</small>
          </td>
          <td>${escapeHtml(agent.last_heartbeat_at ?? "none")}</td>
          <td>${escapeHtml(String(agent.capability_count ?? 0))}</td>
          <td class="row-actions">
            <a href="/agents?agent_id=${encodeURIComponent(agent.id)}" data-agent-open="${escapeHtml(agent.id)}">Open</a>
            <button type="button" disabled>Suspend</button>
            <button type="button" disabled>Rotate</button>
            <button type="button" disabled>Owner</button>
            <button type="button" disabled>Decommission</button>
          </td>
        </tr>
      `
    )
    .join("");
  return `
    <table class="data-table" data-agent-inventory-table>
      <thead>
        <tr>
          <th>Name</th>
          <th>Status</th>
          <th>Framework</th>
          <th>Owner</th>
          <th>Sponsor</th>
          <th>Trust</th>
          <th>Credential</th>
          <th>Heartbeat</th>
          <th>Caps</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

export function renderAgentFilterBar() {
  return `
    <form class="filter-bar" data-agent-inventory-filter>
      <label>
        <span>Status</span>
        <select name="status">
          <option value="">Any</option>
          <option value="draft">Draft</option>
          <option value="pending_approval">Pending</option>
          <option value="provisioned">Provisioned</option>
          <option value="active">Active</option>
          <option value="suspended">Suspended</option>
        </select>
      </label>
      <label>
        <span>Framework</span>
        <input name="framework" placeholder="langgraph">
      </label>
      <label>
        <span>Capability</span>
        <input name="capability" placeholder="claims:read">
      </label>
      <label>
        <span>Sort</span>
        <select name="sort">
          <option value="name">Name</option>
          <option value="status">Status</option>
          <option value="-last_heartbeat">Heartbeat</option>
          <option value="credential_expiry">Credential Expiry</option>
          <option value="-trust_score">Trust Score</option>
        </select>
      </label>
      <button type="submit">Filter</button>
    </form>
  `;
}

export function agentInventoryParamsFromForm(form) {
  const values = Object.fromEntries(new FormData(form));
  return {
    status: String(values.status ?? ""),
    framework: String(values.framework ?? ""),
    capability: String(values.capability ?? ""),
    sort: String(values.sort ?? "name") || "name"
  };
}

export const AGENT_DETAIL_TABS = [
  "overview",
  "identity",
  "policies",
  "credentials",
  "mesh",
  "trust",
  "audit",
  "runtime",
  "integrations"
];

export function renderAgentDetail(detail, activeTab = "overview") {
  const safeTab = AGENT_DETAIL_TABS.includes(activeTab) ? activeTab : "overview";
  return `
    <article class="workspace-panel agent-detail" data-agent-detail="${escapeHtml(detail.summary.id)}">
      <header class="panel-header">
        <div>
          <p class="section-label">Agent Detail</p>
          <h2>${escapeHtml(detail.summary.name)}</h2>
        </div>
        <span class="drawer-status">${escapeHtml(detail.summary.status)}</span>
      </header>
      <nav class="detail-tabs" aria-label="Agent detail tabs">
        ${AGENT_DETAIL_TABS.map(
          (tab) => `
            <a href="/agents?agent_id=${encodeURIComponent(detail.summary.id)}&tab=${escapeHtml(tab)}"
              class="${tab === safeTab ? "is-active" : ""}"
              data-agent-detail-tab="${escapeHtml(tab)}"
              ${tab === safeTab ? 'aria-current="page"' : ""}
            >${escapeHtml(tab)}</a>
          `
        ).join("")}
      </nav>
      <section class="detail-tab-panel" data-agent-detail-panel="${escapeHtml(safeTab)}">
        ${renderAgentDetailTab(detail, safeTab)}
      </section>
    </article>
  `;
}

export function renderAgentDetailTab(detail, activeTab) {
  if (activeTab === "identity") {
    return renderIdentityTab(detail);
  }
  if (activeTab === "credentials") {
    return renderCredentialsTab(detail.credentials ?? []);
  }
  if (activeTab === "audit") {
    return renderAuditTab(detail.auditEvents ?? []);
  }
  if (activeTab === "trust") {
    return renderAgentTrustTab({
      trustScore: detail.trustScore ?? null,
      trustEvents: detail.trustEvents ?? [],
      currentTrustCard: detail.currentTrustCard ?? null
    });
  }
  if (activeTab === "mesh") {
    return renderAgentMeshTab({
      messages: detail.meshMessages ?? [],
      handoffs: detail.meshHandoffs ?? []
    });
  }
  if (activeTab === "runtime") {
    return renderAgentRuntimeTab(detail);
  }
  if (activeTab === "overview") {
    return renderOverviewTab(detail);
  }
  return `
    <div class="empty-state" data-agent-detail-placeholder="${escapeHtml(activeTab)}">
      <strong>${escapeHtml(activeTab)}</strong>
      <span>Pending linked feature</span>
    </div>
  `;
}

export function renderAgentMeshTab({ messages = [], handoffs = [] } = {}) {
  return `
    <div data-agent-mesh-activity>
      ${renderMeshMessagesTable({ messages })}
      ${renderMeshHandoffsTable({ handoffs })}
    </div>
  `;
}

export function renderAgentRuntimeTab(detail) {
  const agent = detail.summary;
  return `
    <div data-agent-runtime-tab>
      <dl class="metadata-grid">
        <dt>Runtime</dt><dd>${escapeHtml(agent.runtime_type ?? "service")}</dd>
        <dt>Framework</dt><dd>${escapeHtml(agent.framework ?? "unknown")}</dd>
        <dt>Trust Tier</dt><dd>${escapeHtml(agent.trust_tier ?? "unrated")}</dd>
        <dt>Status</dt><dd>${escapeHtml(agent.status)}</dd>
      </dl>
      <a class="primary-action" href="/runtime" data-route="/runtime">Open Runtime</a>
    </div>
  `;
}

export function renderCredentialWorkspace({ credentials = [], expiringCredentials = [] } = {}) {
  return `
    <section class="workspace-panel credential-workspace" data-agent-credentials-workspace>
      <header class="panel-header">
        <div>
          <p class="section-label">Credentials</p>
          <h2>Credential Operations</h2>
        </div>
        <button class="primary-action" type="button" data-credential-issue>Issue</button>
      </header>
      <div class="credential-grid">
        ${renderCredentialTable(credentials)}
        ${renderRotationQueue(expiringCredentials)}
        ${renderScopeReviewPanel(credentials)}
      </div>
    </section>
  `;
}

export function renderCredentialsTab(credentials = []) {
  return `
    <div data-agent-credentials-tab>
      ${renderCredentialTable(credentials)}
      ${renderScopeReviewPanel(credentials)}
    </div>
  `;
}

export function renderCredentialTable(credentials = []) {
  if (!credentials.length) {
    return '<div class="empty-state" data-agent-credentials-empty><strong>No credentials</strong><span>Issue credential</span></div>';
  }
  const rows = credentials
    .map(
      (credential) => `
        <tr data-credential-row="${escapeHtml(credential.id)}">
          <td><strong>${escapeHtml(credential.id)}</strong><small>${escapeHtml(credential.issuer ?? "unknown issuer")}</small></td>
          <td>${escapeHtml(credential.credential_type ?? "bearer")}</td>
          <td><span class="status-pill">${escapeHtml(credential.status)}</span></td>
          <td>${escapeHtml(credential.expires_at ?? "none")}</td>
          <td>${escapeHtml(renderScopeSummary(credential.scopes ?? []))}</td>
          <td class="row-actions">
            <button type="button" data-credential-rotate="${escapeHtml(credential.id)}">Rotate</button>
            <button type="button" data-credential-revoke="${escapeHtml(credential.id)}">Revoke</button>
          </td>
        </tr>
      `
    )
    .join("");
  return `
    <table class="data-table" data-agent-credentials-table>
      <thead>
        <tr>
          <th>Credential</th>
          <th>Type</th>
          <th>Status</th>
          <th>Expires</th>
          <th>Scopes</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

function renderRotationQueue(credentials = []) {
  return `
    <article data-credential-rotation-queue>
      <h3>Rotation Queue</h3>
      ${
        credentials.length
          ? `<ul class="compact-list">${credentials
              .map(
                (credential) => `
                  <li>
                    <span>${escapeHtml(credential.id)}</span>
                    <strong>${escapeHtml(credential.expires_at ?? "pending")}</strong>
                  </li>
                `
              )
              .join("")}</ul>`
          : '<div class="empty-state"><strong>No expiring credentials</strong><span>Clear</span></div>'
      }
    </article>
  `;
}

function renderScopeReviewPanel(credentials = []) {
  const scopes = credentials.flatMap((credential) =>
    (credential.scopes ?? []).map((scope) => ({
      credentialId: credential.id,
      ...scope
    }))
  );
  return `
    <article data-credential-scope-review>
      <h3>Scope Review</h3>
      ${
        scopes.length
          ? `<ul class="compact-list">${scopes
              .map(
                (scope) => `
                  <li>
                    <span>${escapeHtml(scope.scope)}</span>
                    <strong>${escapeHtml(scope.resource_id ?? scope.resource_type ?? "agent")}</strong>
                  </li>
                `
              )
              .join("")}</ul>`
          : '<div class="empty-state"><strong>No scopes</strong><span>Issue credential</span></div>'
      }
    </article>
  `;
}

export function renderCredentialActionModal(credential, action) {
  const requiresReason = ["rotate", "revoke"].includes(action);
  return `
    <form class="credential-action" data-credential-action="${escapeHtml(action)}">
      <input type="hidden" name="credential_id" value="${escapeHtml(credential.id)}">
      <label>
        <span>Reason</span>
        <input name="reason" ${requiresReason ? "required" : ""}>
      </label>
      <button type="submit">${escapeHtml(action)}</button>
    </form>
  `;
}

function renderScopeSummary(scopes = []) {
  if (!scopes.length) {
    return "none";
  }
  return scopes.map((scope) => scope.scope).join(", ");
}

function renderOverviewTab(detail) {
  const summary = detail.summary;
  return `
    <dl class="metadata-grid" data-agent-overview>
      <dt>Status</dt><dd>${escapeHtml(summary.status)}</dd>
      <dt>Trust</dt><dd>${escapeHtml(summary.trust_tier ?? "pending")}</dd>
      <dt>Owner</dt><dd>${escapeHtml(summary.owner_user_id)}</dd>
      <dt>Sponsor</dt><dd>${escapeHtml(summary.sponsor_user_id)}</dd>
      <dt>Last heartbeat</dt><dd>${escapeHtml(detail.latest_heartbeat?.observed_at ?? summary.last_heartbeat_at ?? "none")}</dd>
      <dt>Credential</dt><dd>${escapeHtml(summary.credential_status ?? "pending")}</dd>
      <dt>Capabilities</dt><dd>${escapeHtml(String(detail.capabilities?.length ?? 0))}</dd>
    </dl>
  `;
}

function renderIdentityTab(detail) {
  if (!detail.identity) {
    return '<div class="empty-state" data-agent-identity-empty><strong>No identity</strong><span>Register Agent</span></div>';
  }
  return `
    <dl class="metadata-grid" data-agent-identity>
      <dt>DID</dt><dd>${escapeHtml(detail.identity.did)}</dd>
      <dt>Fingerprint</dt><dd>${escapeHtml(detail.identity.public_key_fingerprint)}</dd>
      <dt>Key type</dt><dd>${escapeHtml(detail.identity.key_type)}</dd>
      <dt>Status</dt><dd>${escapeHtml(detail.identity.identity_status)}</dd>
    </dl>
  `;
}

function renderAuditTab(events) {
  if (!events.length) {
    return '<div class="empty-state" data-agent-audit-empty><strong>No audit events</strong><span>Events appear after lifecycle actions</span></div>';
  }
  return `
    <ul class="related-event-timeline" data-agent-audit-events>
      ${events
        .map(
          (event) => `
            <li>
              <button type="button" data-related-event-id="${escapeHtml(event.id)}">
                <span>${escapeHtml(event.event_type)}</span>
                <strong>${escapeHtml(event.severity ?? "info")}</strong>
                <small>${escapeHtml(event.created_at)}</small>
              </button>
            </li>
          `
        )
        .join("")}
    </ul>
  `;
}

export function renderAgentRegistrationWizard(state) {
  const userId = state?.currentUser?.id ?? "";
  return `
    <form class="workspace-panel agent-wizard" data-agent-registration-form>
      <header class="panel-header">
        <div>
          <p class="section-label">Registration</p>
          <h2>Register Agent</h2>
        </div>
        <button class="primary-action" type="submit" data-agent-wizard-submit>Submit</button>
      </header>
      <div class="wizard-steps" aria-label="Registration steps">
        ${renderStep("1", "Agent Details", [
          field("name", "Name", "Claims Assistant"),
          field("description", "Description", "Triages incoming claims"),
          field("endpoint_url", "Endpoint", "https://agents.example.test/claims")
        ])}
        ${renderStep("2", "Runtime And Framework", [
          selectField("framework", "Framework", ["langgraph", "langchain", "crewai", "agentmesh"]),
          selectField("runtime_type", "Runtime", ["service", "job", "desktop", "mcp-server"])
        ])}
        ${renderStep("3", "Identity", [
          field("owner_user_id", "Owner", userId),
          field("sponsor_user_id", "Sponsor", userId)
        ])}
        ${renderStep("4", "Capabilities", [
          field("capability_name", "Capability", "claims:read"),
          field("resource_type", "Resource", "claim")
        ])}
        ${renderStep("5", "Policies", [
          selectField("policy_id", "Policy", [
            "policy_placeholder_default_allow",
            "policy_placeholder_sensitive_tools"
          ])
        ])}
        ${renderStep("6", "Bootstrap", [
          '<output class="bootstrap-output" data-agent-registration-result>Ready</output>'
        ])}
      </div>
    </form>
  `;
}

export function registrationPayloadFromForm(form) {
  const values = Object.fromEntries(new FormData(form));
  return {
    draft: {
      name: String(values.name ?? ""),
      description: String(values.description ?? ""),
      framework: String(values.framework ?? ""),
      runtime_type: String(values.runtime_type ?? ""),
      endpoint_url: String(values.endpoint_url ?? ""),
      owner_user_id: String(values.owner_user_id ?? ""),
      sponsor_user_id: String(values.sponsor_user_id ?? "")
    },
    selections: {
      capabilities: [
        {
          capability_name: String(values.capability_name ?? ""),
          resource_type: String(values.resource_type ?? "agent")
        }
      ],
      policy_selections: [
        {
          policy_id: String(values.policy_id ?? ""),
          selection_type: "policy_binding"
        }
      ]
    }
  };
}

function renderStep(index, title, controls) {
  return `
    <fieldset class="wizard-step" data-agent-wizard-step="${escapeHtml(index)}">
      <legend><span>${escapeHtml(index)}</span>${escapeHtml(title)}</legend>
      <div class="form-grid">${controls.join("")}</div>
    </fieldset>
  `;
}

function field(name, label, value) {
  return `
    <label>
      <span>${escapeHtml(label)}</span>
      <input name="${escapeHtml(name)}" value="${escapeHtml(value)}">
    </label>
  `;
}

function selectField(name, label, options) {
  return `
    <label>
      <span>${escapeHtml(label)}</span>
      <select name="${escapeHtml(name)}">
        ${options
          .map((option) => `<option value="${escapeHtml(option)}">${escapeHtml(option)}</option>`)
          .join("")}
      </select>
    </label>
  `;
}
