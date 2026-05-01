import { escapeHtml } from "./html.js";

const RINGS = [0, 1, 2, 3];

export function renderRuntimePage(state) {
  const sessions = state?.runtimeSessions ?? [];
  const selectedSession = state?.selectedRuntimeSession ?? sessions[0] ?? null;
  const decisions = state?.runtimeRingDecisions ?? [];
  const rules = state?.runtimeRingRules ?? [];
  const sagas = state?.runtimeSagas ?? [];
  const selectedSaga = state?.selectedRuntimeSaga ?? sagas[0] ?? null;
  const sandboxProfiles = state?.runtimeSandboxProfiles ?? [];
  const selectedSandboxProfile = state?.selectedRuntimeSandboxProfile ?? sandboxProfiles[0] ?? null;
  const killSwitchEvents = state?.runtimeKillSwitchEvents ?? [];
  return `
    <section class="page-heading" data-route-page="/runtime">
      <p class="section-label">Operations</p>
      <h1>Runtime</h1>
      <p>Runtime sessions, sagas, ring enforcement decisions, and rule configuration.</p>
    </section>
    <section class="runtime-workspace" aria-label="Runtime workspace">
      ${renderRuntimeSessionsPanel({ sessions })}
      ${renderRuntimeSessionDetail(selectedSession)}
      ${renderRuntimeSagasPanel({ sagas, selectedSaga })}
      ${renderRuntimeSagaMonitor(selectedSaga)}
      ${renderRuntimeSandboxPanel({
        profiles: sandboxProfiles,
        selectedProfile: selectedSandboxProfile,
        decision: state?.runtimeSandboxDecision ?? null
      })}
      ${renderRuntimeKillSwitchPanel({ events: killSwitchEvents })}
      ${renderRuntimeRingDecisionsPanel({ decisions })}
      ${renderRuntimeRingRulesPanel({ rules })}
    </section>
  `;
}

export function renderRuntimeSessionsPanel({ sessions = [] } = {}) {
  const rows = sessions
    .map(
      (session) => `
        <tr data-runtime-session-row="${escapeHtml(session.id)}">
          <td><strong>${escapeHtml(session.agent_name ?? session.agent_id)}</strong><small>${escapeHtml(session.id)}</small></td>
          <td><span class="status-pill">${escapeHtml(session.state)}</span></td>
          <td>${escapeHtml(String(session.ring))}</td>
          <td>${escapeHtml(session.started_at)}</td>
          <td>${escapeHtml(session.ended_at ?? "active")}</td>
        </tr>
      `
    )
    .join("");
  return `
    <article class="workspace-panel runtime-sessions" data-runtime-sessions>
      <header class="panel-header">
        <div>
          <p class="section-label">Sessions</p>
          <h2>Runtime Sessions</h2>
        </div>
      </header>
      <form class="bridge-form-grid" data-runtime-session-form>
        <label><span>Agent ID</span><input name="agent_id" required></label>
        <label><span>Ring</span><select name="ring">${ringOptions(2)}</select></label>
        <label><span>Sponsor</span><input name="sponsor_user_id"></label>
        <button type="submit">Start</button>
      </form>
      ${
        sessions.length
          ? `<table class="data-table">
              <thead><tr><th>Agent</th><th>State</th><th>Ring</th><th>Started</th><th>Ended</th></tr></thead>
              <tbody>${rows}</tbody>
            </table>`
          : '<div class="empty-state" data-runtime-sessions-empty><strong>No sessions</strong><span>Start a runtime session</span></div>'
      }
    </article>
  `;
}

export function renderRuntimeSessionDetail(session) {
  if (!session) {
    return `
      <article class="workspace-panel runtime-session-detail" data-runtime-session-detail>
        <header class="panel-header">
          <div>
            <p class="section-label">Timeline</p>
            <h2>Session Timeline</h2>
          </div>
        </header>
        <div class="empty-state"><strong>No session selected</strong><span>Start a session to submit actions</span></div>
      </article>
    `;
  }
  const actions = session.actions ?? [];
  const actionRows = actions
    .map(
      (action) => `
        <tr data-runtime-action-row="${escapeHtml(action.id)}">
          <td><strong>${escapeHtml(action.action_name)}</strong><small>${escapeHtml(action.resource_type)}</small></td>
          <td><span class="status-pill">${escapeHtml(action.decision)}</span></td>
          <td>${escapeHtml(String(action.required_ring ?? "n/a"))}</td>
          <td>${escapeHtml(action.ring_decision ? String(action.ring_decision.assigned_ring) : "n/a")}</td>
          <td>${escapeHtml(action.reason)}</td>
        </tr>
      `
    )
    .join("");
  return `
    <article class="workspace-panel runtime-session-detail" data-runtime-session-detail="${escapeHtml(session.id)}">
      <header class="panel-header">
        <div>
          <p class="section-label">Timeline</p>
          <h2>Session Timeline</h2>
        </div>
      </header>
      <dl class="metadata-grid">
        <dt>Agent</dt><dd>${escapeHtml(session.agent_name ?? session.agent_id)}</dd>
        <dt>State</dt><dd>${escapeHtml(session.state)}</dd>
        <dt>Assigned Ring</dt><dd>${escapeHtml(String(session.ring))}</dd>
      </dl>
      <form class="bridge-form-grid" data-runtime-action-form data-session-id="${escapeHtml(session.id)}">
        <label><span>Action</span><input name="action_name" required></label>
        <label><span>Resource</span><input name="resource_type" value="runtime-action" required></label>
        <label><span>Reversibility</span><select name="reversibility"><option value="none">none</option><option value="partial">partial</option><option value="full">full</option></select></label>
        <label class="checkbox-row"><input name="is_read_only" type="checkbox"><span>Read only</span></label>
        <label class="checkbox-row"><input name="is_admin" type="checkbox"><span>Admin</span></label>
        <button type="submit">Evaluate</button>
      </form>
      ${
        actions.length
          ? `<table class="data-table">
              <thead><tr><th>Action</th><th>Decision</th><th>Required</th><th>Assigned</th><th>Reason</th></tr></thead>
              <tbody>${actionRows}</tbody>
            </table>`
          : '<div class="empty-state" data-runtime-actions-empty><strong>No actions</strong><span>Submit an action for ring evaluation</span></div>'
      }
    </article>
  `;
}

export function renderRuntimeRingDecisionsPanel({ decisions = [] } = {}) {
  const counts = decisionCounts(decisions);
  const rows = decisions
    .map(
      (decision) => `
        <tr data-runtime-ring-decision-row="${escapeHtml(decision.id)}">
          <td><strong>${escapeHtml(decision.action_name)}</strong><small>${escapeHtml(decision.agent_id)}</small></td>
          <td><span class="status-pill">${escapeHtml(decision.result)}</span></td>
          <td>${escapeHtml(String(decision.required_ring))}</td>
          <td>${escapeHtml(String(decision.assigned_ring))}</td>
          <td>${escapeHtml(String(decision.agent_trust_score))}</td>
          <td>${escapeHtml(decision.reason)}</td>
        </tr>
      `
    )
    .join("");
  return `
    <article class="workspace-panel runtime-ring-decisions" data-runtime-ring-decisions>
      <header class="panel-header">
        <div>
          <p class="section-label">Rings</p>
          <h2>Ring Decisions</h2>
        </div>
      </header>
      <div class="metric-grid" data-runtime-ring-chart>
        <div><strong>${escapeHtml(String(counts.allowed))}</strong><span>allowed</span></div>
        <div><strong>${escapeHtml(String(counts.denied))}</strong><span>denied</span></div>
      </div>
      ${
        decisions.length
          ? `<table class="data-table">
              <thead><tr><th>Action</th><th>Result</th><th>Required</th><th>Assigned</th><th>Trust</th><th>Reason</th></tr></thead>
              <tbody>${rows}</tbody>
            </table>`
          : '<div class="empty-state" data-runtime-ring-decisions-empty><strong>No decisions</strong><span>Evaluated actions will appear here</span></div>'
      }
    </article>
  `;
}

export function renderRuntimeRingRulesPanel({ rules = [] } = {}) {
  const rows = rules
    .map(
      (rule) => `
        <tr data-runtime-ring-rule-row="${escapeHtml(rule.id)}">
          <td><strong>${escapeHtml(rule.action_pattern)}</strong></td>
          <td>${escapeHtml(String(rule.required_ring))}</td>
          <td>${escapeHtml(String(rule.min_trust_score))}</td>
          <td><span class="status-pill">${escapeHtml(rule.enabled ? "enabled" : "disabled")}</span></td>
        </tr>
      `
    )
    .join("");
  return `
    <article class="workspace-panel runtime-ring-rules" data-runtime-ring-rules>
      <header class="panel-header">
        <div>
          <p class="section-label">Rules</p>
          <h2>Ring Rule Editor</h2>
        </div>
      </header>
      <form class="bridge-form-grid" data-runtime-ring-rule-form>
        <label><span>Pattern</span><input name="action_pattern" required></label>
        <label><span>Required Ring</span><select name="required_ring">${ringOptions(2)}</select></label>
        <label><span>Min Trust</span><input name="min_trust_score" type="number" min="0" max="1000" value="0" required></label>
        <label class="checkbox-row"><input name="enabled" type="checkbox" checked><span>Enabled</span></label>
        <button type="submit">Create</button>
      </form>
      ${
        rules.length
          ? `<table class="data-table">
              <thead><tr><th>Pattern</th><th>Ring</th><th>Min Trust</th><th>Status</th></tr></thead>
              <tbody>${rows}</tbody>
            </table>`
          : '<div class="empty-state" data-runtime-ring-rules-empty><strong>No rules</strong><span>Create a ring override</span></div>'
      }
    </article>
  `;
}

export function renderRuntimeSagasPanel({ sagas = [], selectedSaga = null } = {}) {
  const rows = sagas
    .map(
      (saga) => `
        <tr data-runtime-saga-row="${escapeHtml(saga.id)}">
          <td><strong>${escapeHtml(saga.name)}</strong><small>${escapeHtml(saga.id)}</small></td>
          <td><span class="status-pill">${escapeHtml(saga.status)}</span></td>
          <td>${escapeHtml(saga.runtime_session_id ?? "unlinked")}</td>
          <td>${escapeHtml(saga.correlation_id ?? "n/a")}</td>
          <td><button type="button" data-runtime-saga-open="${escapeHtml(saga.id)}" ${selectedSaga?.id === saga.id ? "disabled" : ""}>Open</button></td>
        </tr>
      `
    )
    .join("");
  return `
    <article class="workspace-panel runtime-sagas" data-runtime-sagas>
      <header class="panel-header">
        <div>
          <p class="section-label">Sagas</p>
          <h2>Saga Builder</h2>
        </div>
      </header>
      <form class="bridge-form-grid" data-runtime-saga-form>
        <label><span>Name</span><input name="name" required></label>
        <label><span>Runtime Session</span><input name="runtime_session_id"></label>
        <label><span>Correlation</span><input name="correlation_id"></label>
        <button type="submit">Create</button>
      </form>
      ${
        sagas.length
          ? `<table class="data-table">
              <thead><tr><th>Saga</th><th>Status</th><th>Session</th><th>Correlation</th><th></th></tr></thead>
              <tbody>${rows}</tbody>
            </table>`
          : '<div class="empty-state" data-runtime-sagas-empty><strong>No sagas</strong><span>Create a saga</span></div>'
      }
    </article>
  `;
}

export function renderRuntimeSagaMonitor(saga) {
  if (!saga) {
    return `
      <article class="workspace-panel runtime-saga-monitor" data-runtime-saga-monitor>
        <header class="panel-header">
          <div>
            <p class="section-label">Monitor</p>
            <h2>Saga Monitor</h2>
          </div>
        </header>
        <div class="empty-state"><strong>No saga selected</strong><span>Create or open a saga</span></div>
      </article>
    `;
  }
  const steps = saga.steps ?? [];
  const events = saga.events ?? [];
  const nextOrder = nextSagaStepOrder(steps);
  const stepRows = steps
    .map(
      (step) => `
        <tr data-runtime-saga-step-row="${escapeHtml(step.id)}">
          <td><button type="button" data-runtime-saga-step-detail-open="${escapeHtml(`${saga.id}:${step.id}`)}">${escapeHtml(step.name)}</button><small>${escapeHtml(step.action_name)}</small></td>
          <td><span class="status-pill">${escapeHtml(step.status)}</span></td>
          <td>${escapeHtml(step.target_agent_name ?? step.target_agent_id)}</td>
          <td>${escapeHtml(step.required_capability ?? "n/a")}</td>
          <td>${escapeHtml(step.compensation_action ?? "none")}</td>
        </tr>
      `
    )
    .join("");
  const eventRows = events
    .map(
      (event) => `
        <tr data-runtime-saga-event-row="${escapeHtml(event.id)}">
          <td><strong>${escapeHtml(event.event_type)}</strong><small>${escapeHtml(event.created_at)}</small></td>
          <td>${escapeHtml(event.message)}</td>
        </tr>
      `
    )
    .join("");
  return `
    <article class="workspace-panel runtime-saga-monitor" data-runtime-saga-monitor="${escapeHtml(saga.id)}">
      <header class="panel-header">
        <div>
          <p class="section-label">Monitor</p>
          <h2>${escapeHtml(saga.name)}</h2>
        </div>
        <span class="status-pill">${escapeHtml(saga.status)}</span>
      </header>
      <dl class="metadata-grid">
        <dt>Runtime Session</dt><dd>${escapeHtml(saga.runtime_session_id ?? "unlinked")}</dd>
        <dt>Correlation</dt><dd>${escapeHtml(saga.correlation_id ?? "n/a")}</dd>
        <dt>Started</dt><dd>${escapeHtml(saga.started_at ?? "not started")}</dd>
        <dt>Finished</dt><dd>${escapeHtml(saga.finished_at ?? "not finished")}</dd>
      </dl>
      <form class="bridge-form-grid" data-runtime-saga-step-form data-saga-id="${escapeHtml(saga.id)}">
        <label><span>Order</span><input name="step_order" type="number" min="1" value="${escapeHtml(String(nextOrder))}" required></label>
        <label><span>Name</span><input name="name" required></label>
        <label><span>Action</span><input name="action_name" required></label>
        <label><span>Target Agent</span><input name="target_agent_id" required></label>
        <label><span>Capability</span><input name="required_capability"></label>
        <label><span>Compensation</span><input name="compensation_action"></label>
        <label><span>Timeout</span><input name="timeout_seconds" type="number" min="1" value="300" required></label>
        <label><span>Retries</span><input name="retry_count" type="number" min="0" value="0" required></label>
        <button type="submit" ${saga.status !== "draft" ? "disabled" : ""}>Add Step</button>
      </form>
      <div class="inline-actions">
        <form class="inline-form" data-runtime-saga-execute-form data-saga-id="${escapeHtml(saga.id)}">
          <label><span>Failure Actions</span><input name="failure_actions"></label>
          <button type="submit">Execute / Retry</button>
        </form>
        <form class="inline-form" data-runtime-saga-cancel-form data-saga-id="${escapeHtml(saga.id)}">
          <label><span>Reason</span><input name="reason"></label>
          <button type="submit">Cancel</button>
        </form>
      </div>
      ${
        steps.length
          ? `<table class="data-table saga-step-table">
              <thead><tr><th>Step</th><th>Status</th><th>Agent</th><th>Capability</th><th>Compensation</th></tr></thead>
              <tbody>${stepRows}</tbody>
            </table>`
          : '<div class="empty-state" data-runtime-saga-steps-empty><strong>No steps</strong><span>Add an ordered step</span></div>'
      }
      ${
        events.length
          ? `<table class="data-table saga-event-table">
              <thead><tr><th>Event</th><th>Message</th></tr></thead>
              <tbody>${eventRows}</tbody>
            </table>`
          : '<div class="empty-state" data-runtime-saga-events-empty><strong>No events</strong><span>Execution events will appear here</span></div>'
      }
    </article>
  `;
}

export function renderRuntimeSagaStepDetail(step) {
  if (!step) {
    return '<div class="drawer-state">Step not found</div>';
  }
  return `
    <dl class="metadata-grid">
      <dt>Action</dt><dd>${escapeHtml(step.action_name)}</dd>
      <dt>Status</dt><dd>${escapeHtml(step.status)}</dd>
      <dt>Agent</dt><dd>${escapeHtml(step.target_agent_name ?? step.target_agent_id)}</dd>
      <dt>Capability</dt><dd>${escapeHtml(step.required_capability ?? "n/a")}</dd>
      <dt>Compensation</dt><dd>${escapeHtml(step.compensation_action ?? "none")}</dd>
      <dt>Timeout</dt><dd>${escapeHtml(String(step.timeout_seconds))}</dd>
      <dt>Retries</dt><dd>${escapeHtml(String(step.retry_count))}</dd>
    </dl>
    <pre class="json-preview">${escapeHtml(JSON.stringify(step.result ?? {}, null, 2))}</pre>
  `;
}

export function renderRuntimeSandboxPanel({ profiles = [], selectedProfile = null, decision = null } = {}) {
  const rows = profiles
    .map(
      (profile) => `
        <tr data-runtime-sandbox-profile-row="${escapeHtml(profile.id)}">
          <td><strong>${escapeHtml(profile.name)}</strong><small>${escapeHtml(profile.id)}</small></td>
          <td><span class="status-pill">${escapeHtml(profile.provider_type)}</span></td>
          <td>${escapeHtml(profile.blocked_imports.join(", ") || "none")}</td>
          <td>${escapeHtml(profile.allowed_paths.join(", ") || "none")}</td>
          <td><span class="status-pill">${escapeHtml(profile.status)}</span></td>
        </tr>
      `
    )
    .join("");
  const profileWarning = selectedProfile?.provider_warning
    ? `<p class="inline-warning" data-runtime-sandbox-warning>${escapeHtml(selectedProfile.provider_warning)}</p>`
    : "";
  return `
    <article class="workspace-panel runtime-sandbox" data-runtime-sandbox>
      <header class="panel-header">
        <div>
          <p class="section-label">Sandbox</p>
          <h2>Sandbox Profiles</h2>
        </div>
      </header>
      <form class="bridge-form-grid" data-runtime-sandbox-profile-form>
        <label><span>Name</span><input name="name" required></label>
        <label><span>Provider</span><select name="provider_type"><option value="subprocess">subprocess</option><option value="noop">noop</option></select></label>
        <label><span>Allowed Imports</span><input name="allowed_imports"></label>
        <label><span>Blocked Imports</span><input name="blocked_imports" value="os, subprocess, socket"></label>
        <label><span>Allowed Paths</span><input name="allowed_paths"></label>
        <label><span>Network Egress</span><input name="network_egress" value="deny"></label>
        <label><span>Timeout</span><input name="timeout_seconds" type="number" min="1" value="5"></label>
        <label><span>Memory MB</span><input name="memory_mb" type="number" min="1" value="128"></label>
        <button type="submit">Create</button>
      </form>
      ${profileWarning}
      ${
        selectedProfile
          ? `<form class="bridge-form-grid" data-runtime-sandbox-test-form data-profile-id="${escapeHtml(selectedProfile.id)}">
              <label><span>Agent ID</span><input name="agent_id"></label>
              <label><span>Action</span><input name="action_name"></label>
              <label class="wide-field"><span>Sample Code</span><textarea name="code" required rows="4"></textarea></label>
              <button type="submit">Test</button>
            </form>`
          : ""
      }
      ${
        decision
          ? `<div class="inline-status" data-runtime-sandbox-decision>
              <strong>${escapeHtml(decision.decision)}</strong>
              <span>${escapeHtml(decision.reason)}</span>
            </div>`
          : ""
      }
      ${
        profiles.length
          ? `<table class="data-table">
              <thead><tr><th>Profile</th><th>Provider</th><th>Blocked</th><th>Paths</th><th>Status</th></tr></thead>
              <tbody>${rows}</tbody>
            </table>`
          : '<div class="empty-state" data-runtime-sandbox-empty><strong>No sandbox profiles</strong><span>Create a sandbox profile</span></div>'
      }
    </article>
  `;
}

export function renderRuntimeKillSwitchPanel({ events = [] } = {}) {
  const rows = events
    .map(
      (event) => `
        <tr data-runtime-kill-switch-event-row="${escapeHtml(event.id)}">
          <td><strong>${escapeHtml(event.target_type)}</strong><small>${escapeHtml(event.target_id)}</small></td>
          <td>${escapeHtml(event.scope)}</td>
          <td>${escapeHtml(event.reason)}</td>
          <td><span class="status-pill">${escapeHtml(event.status)}</span></td>
          <td>${escapeHtml(event.created_at)}</td>
        </tr>
      `
    )
    .join("");
  return `
    <article class="workspace-panel runtime-kill-switch" data-runtime-kill-switch>
      <header class="panel-header">
        <div>
          <p class="section-label">Emergency</p>
          <h2>Kill Switch</h2>
        </div>
      </header>
      <form class="bridge-form-grid" data-runtime-kill-switch-form>
        <label><span>Target Type</span><select name="target_type"><option value="session">session</option><option value="agent">agent</option><option value="mcp_server">mcp_server</option><option value="tool">tool</option><option value="plugin">plugin</option></select></label>
        <label><span>Target ID</span><input name="target_id" required></label>
        <label><span>Scope</span><input name="scope" value="target" required></label>
        <label><span>Reason</span><input name="reason" required></label>
        <label><span>Confirmation</span><input name="confirmation" required></label>
        <button type="submit">Trigger</button>
      </form>
      ${
        events.length
          ? `<table class="data-table">
              <thead><tr><th>Target</th><th>Scope</th><th>Reason</th><th>Status</th><th>Created</th></tr></thead>
              <tbody>${rows}</tbody>
            </table>`
          : '<div class="empty-state" data-runtime-kill-switch-empty><strong>No kill-switch events</strong><span>Triggered events appear here</span></div>'
      }
    </article>
  `;
}

export function runtimeSessionPayloadFromForm(form) {
  return runtimeSessionPayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function runtimeSessionPayloadFromValues(values) {
  return {
    agent_id: String(values.agent_id ?? "").trim(),
    ring: Number.parseInt(String(values.ring ?? "2"), 10),
    sponsor_user_id: emptyToNull(values.sponsor_user_id),
    metadata: {}
  };
}

export function runtimeActionPayloadFromForm(form) {
  return runtimeActionPayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function runtimeActionPayloadFromValues(values) {
  return {
    action_name: String(values.action_name ?? "").trim(),
    resource_type: String(values.resource_type ?? "runtime-action").trim(),
    reversibility: String(values.reversibility ?? "none").trim(),
    is_read_only: values.is_read_only === "on" || values.is_read_only === true,
    is_admin: values.is_admin === "on" || values.is_admin === true
  };
}

export function runtimeRingRulePayloadFromForm(form) {
  return runtimeRingRulePayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function runtimeRingRulePayloadFromValues(values) {
  return {
    action_pattern: String(values.action_pattern ?? "").trim(),
    required_ring: Number.parseInt(String(values.required_ring ?? "2"), 10),
    min_trust_score: Number.parseInt(String(values.min_trust_score ?? "0"), 10),
    enabled: values.enabled === "on" || values.enabled === true
  };
}

export function runtimeSagaPayloadFromForm(form) {
  return runtimeSagaPayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function runtimeSagaPayloadFromValues(values) {
  return {
    name: String(values.name ?? "").trim(),
    runtime_session_id: emptyToNull(values.runtime_session_id),
    correlation_id: emptyToNull(values.correlation_id)
  };
}

export function runtimeSagaStepPayloadFromForm(form) {
  return runtimeSagaStepPayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function runtimeSagaStepPayloadFromValues(values) {
  return {
    step_order: Number.parseInt(String(values.step_order ?? "1"), 10),
    name: String(values.name ?? "").trim(),
    action_name: String(values.action_name ?? "").trim(),
    target_agent_id: String(values.target_agent_id ?? "").trim(),
    required_capability: emptyToNull(values.required_capability),
    timeout_seconds: Number.parseInt(String(values.timeout_seconds ?? "300"), 10),
    retry_count: Number.parseInt(String(values.retry_count ?? "0"), 10),
    compensation_action: emptyToNull(values.compensation_action)
  };
}

export function runtimeSagaExecutePayloadFromForm(form) {
  return runtimeSagaExecutePayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function runtimeSagaExecutePayloadFromValues(values) {
  return {
    runtime_session_id: emptyToNull(values.runtime_session_id),
    failure_actions: String(values.failure_actions ?? "")
      .split(/[,\n]+/)
      .map((item) => item.trim())
      .filter(Boolean)
  };
}

export function runtimeSagaCancelPayloadFromForm(form) {
  return runtimeSagaCancelPayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function runtimeSagaCancelPayloadFromValues(values) {
  return {
    reason: emptyToNull(values.reason)
  };
}

export function runtimeSandboxProfilePayloadFromForm(form) {
  return runtimeSandboxProfilePayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function runtimeSandboxProfilePayloadFromValues(values) {
  const networkEgress = emptyToNull(values.network_egress);
  const timeout = Number.parseInt(String(values.timeout_seconds ?? ""), 10);
  const memory = Number.parseInt(String(values.memory_mb ?? ""), 10);
  return {
    name: String(values.name ?? "").trim(),
    provider_type: String(values.provider_type ?? "subprocess").trim(),
    allowed_imports: splitList(values.allowed_imports),
    blocked_imports: splitList(values.blocked_imports),
    allowed_paths: splitList(values.allowed_paths),
    network_policy: networkEgress ? { egress: networkEgress } : {},
    resource_limits: {
      ...(Number.isFinite(timeout) ? { timeout_seconds: timeout } : {}),
      ...(Number.isFinite(memory) ? { memory_mb: memory } : {})
    }
  };
}

export function runtimeSandboxTestPayloadFromForm(form) {
  return runtimeSandboxTestPayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function runtimeSandboxTestPayloadFromValues(values) {
  return {
    code: String(values.code ?? "").trim(),
    agent_id: emptyToNull(values.agent_id),
    action_name: emptyToNull(values.action_name)
  };
}

export function runtimeKillSwitchPayloadFromForm(form) {
  return runtimeKillSwitchPayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function runtimeKillSwitchPayloadFromValues(values) {
  return {
    target_type: String(values.target_type ?? "").trim(),
    target_id: String(values.target_id ?? "").trim(),
    scope: String(values.scope ?? "target").trim(),
    reason: String(values.reason ?? "").trim(),
    confirmation: String(values.confirmation ?? "").trim()
  };
}

function ringOptions(selected) {
  return RINGS.map((ring) => `<option value="${ring}" ${ring === selected ? "selected" : ""}>${ring}</option>`).join("");
}

function nextSagaStepOrder(steps) {
  return steps.reduce((maxOrder, step) => Math.max(maxOrder, Number(step.step_order ?? 0)), 0) + 1;
}

function splitList(value) {
  return String(value ?? "")
    .split(/[,\n]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function decisionCounts(decisions) {
  return decisions.reduce(
    (counts, decision) => {
      if (decision.result === "allowed") {
        counts.allowed += 1;
      }
      if (decision.result === "denied") {
        counts.denied += 1;
      }
      return counts;
    },
    { allowed: 0, denied: 0 }
  );
}

function emptyToNull(value) {
  const stripped = String(value ?? "").trim();
  return stripped || null;
}
