import { DRAWER_KINDS, openDrawer } from "./drawers.js";
import { escapeHtml } from "./html.js";

export function auditEventDrawer({ event, verification = null, relatedEvents = [] }) {
  const hashStatus = verification?.valid === true ? "Hash verified" : "Hash pending";
  return openDrawer({
    kind: DRAWER_KINDS.AUDIT_EVENT,
    resourceId: event.id,
    title: event.event_type,
    subtitle: event.id,
    status: event.decision ?? event.severity ?? hashStatus,
    state: "ready",
    content: renderAuditEventContent({ event, verification, relatedEvents }),
    actions: [
      {
        label: "Audit Explorer",
        href: `/observability?event_id=${encodeURIComponent(event.id)}`
      }
    ]
  });
}

export function drawerForAuditEvent({ event, verification = null, relatedEvents = [] }) {
  if (event.event_type === "policy.decision") {
    return policyDecisionDrawer({ event, verification, relatedEvents });
  }
  if (event.event_type === "mcp.call") {
    return mcpCallDrawer({ event, verification, relatedEvents });
  }
  if (event.event_type === "runtime.action") {
    return runtimeActionDrawer({ event, verification, relatedEvents });
  }
  return auditEventDrawer({ event, verification, relatedEvents });
}

export function policyDecisionDrawer({ event, verification = null, relatedEvents = [] }) {
  return openDrawer({
    kind: DRAWER_KINDS.POLICY_DECISION,
    resourceId: event.id,
    title: "Policy Decision",
    subtitle: event.policy_id ?? event.resource_id ?? event.id,
    status: event.decision ?? event.severity,
    state: "ready",
    content: `${renderPolicyDecisionContent(event)}${renderAuditEventContent({
      event,
      verification,
      relatedEvents
    })}`,
    actions: auditExplorerAction(event.id)
  });
}

export function mcpCallDrawer({ event, verification = null, relatedEvents = [] }) {
  return openDrawer({
    kind: DRAWER_KINDS.MCP_CALL,
    resourceId: event.id,
    title: "MCP Call",
    subtitle: event.resource_id ?? event.id,
    status: event.decision ?? event.severity,
    state: "ready",
    content: `${renderMcpCallContent(event)}${renderAuditEventContent({
      event,
      verification,
      relatedEvents
    })}`,
    actions: auditExplorerAction(event.id)
  });
}

export function runtimeActionDrawer({ event, verification = null, relatedEvents = [] }) {
  return openDrawer({
    kind: DRAWER_KINDS.RUNTIME_ACTION,
    resourceId: event.id,
    title: "Runtime Action",
    subtitle: event.resource_id ?? event.id,
    status: event.decision ?? event.severity,
    state: "ready",
    content: `${renderRuntimeActionContent(event)}${renderAuditEventContent({
      event,
      verification,
      relatedEvents
    })}`,
    actions: auditExplorerAction(event.id)
  });
}

export async function loadAuditEventDrawer({ apiClient, eventId }) {
  try {
    const event = await apiClient.getAuditEvent(eventId);
    const [verification, relatedEvents] = await Promise.all([
      apiClient.verifyAuditEvent(eventId),
      event.correlation_id
        ? apiClient.listAuditEvents({ correlation_id: event.correlation_id })
        : Promise.resolve([])
    ]);
    return drawerForAuditEvent({ event, verification, relatedEvents });
  } catch (error) {
    return openDrawer({
      kind: DRAWER_KINDS.AUDIT_EVENT,
      resourceId: eventId,
      title: "Audit Event",
      subtitle: eventId,
      status: "Error",
      state: "error",
      error: error?.message ?? "Unable to load audit event."
    });
  }
}

export function renderPolicyDecisionContent(event) {
  const payload = event.payload_json ?? {};
  return `
    <section class="audit-drawer-section" data-policy-decision>
      <h3>Policy Decision</h3>
      <dl class="metadata-grid">
        ${metadataRow("Policy", event.policy_id ?? event.resource_id)}
        ${metadataRow("Decision", event.decision)}
        ${metadataRow("Matched rule", payload.matched_rule)}
        ${metadataRow("Reason", payload.reason)}
      </dl>
    </section>
  `;
}

export function renderMcpCallContent(event) {
  const payload = event.payload_json ?? {};
  return `
    <section class="audit-drawer-section" data-mcp-call>
      <h3>MCP Call</h3>
      <dl class="metadata-grid">
        ${metadataRow("Server", event.resource_id)}
        ${metadataRow("Tool", payload.tool_name)}
        ${metadataRow("Decision", event.decision)}
        ${metadataRow("Params classification", payload.params_classification ?? payload.classification)}
        ${metadataRow("Sanitizer action", payload.sanitizer_action)}
      </dl>
    </section>
  `;
}

export function renderRuntimeActionContent(event) {
  const payload = event.payload_json ?? {};
  return `
    <section class="audit-drawer-section" data-runtime-action>
      <h3>Runtime Action</h3>
      <dl class="metadata-grid">
        ${metadataRow("Session", event.resource_id)}
        ${metadataRow("Action", payload.action)}
        ${metadataRow("Ring", payload.ring)}
        ${metadataRow("Sandbox", payload.sandbox_status ?? payload.sandbox)}
        ${metadataRow("Saga", payload.saga_id)}
      </dl>
    </section>
  `;
}

export function renderAuditEventContent({ event, verification = null, relatedEvents = [] }) {
  return `
    <section class="audit-drawer-section" data-audit-metadata>
      <h3>Metadata</h3>
      <dl class="metadata-grid">
        ${metadataRow("Event type", event.event_type)}
        ${metadataRow("Source", event.source_component)}
        ${metadataRow("Actor", [event.actor_type, event.actor_id].filter(Boolean).join(" / "))}
        ${metadataRow("Agent", event.agent_id)}
        ${metadataRow("Resource", [event.resource_type, event.resource_id].filter(Boolean).join(" / "))}
        ${metadataRow("Decision", event.decision)}
        ${metadataRow("Severity", event.severity)}
        ${metadataRow("Correlation", event.correlation_id)}
        ${metadataRow("Created", event.created_at)}
      </dl>
    </section>
    <section class="audit-drawer-section" data-audit-hash>
      <h3>Hash Verification</h3>
      <p>${renderVerification(verification)}</p>
    </section>
    <section class="audit-drawer-section" data-audit-payload>
      <h3>Raw Payload</h3>
      <pre>${escapeHtml(JSON.stringify(event.payload_json ?? {}, null, 2))}</pre>
    </section>
    <section class="audit-drawer-section" data-related-events>
      <h3>Related Events</h3>
      ${renderRelatedEvents(event.id, relatedEvents)}
    </section>
  `;
}

function metadataRow(label, value) {
  return `
    <dt>${escapeHtml(label)}</dt>
    <dd>${escapeHtml(value || "n/a")}</dd>
  `;
}

function renderVerification(verification) {
  if (!verification) {
    return "Hash verification has not run.";
  }
  if (verification.valid) {
    return `Valid hash chain, ${verification.checked_count} event(s) checked.`;
  }
  return `Hash verification failed: ${verification.reason ?? "unknown"}.`;
}

function renderRelatedEvents(currentEventId, relatedEvents) {
  const related = relatedEvents
    .filter((event) => event.id !== currentEventId)
    .sort((left, right) => String(left.created_at).localeCompare(String(right.created_at)));
  if (related.length === 0) {
    return '<p class="empty-inline">No related events</p>';
  }
  return `
    <ol class="related-event-timeline">
      ${related
        .map(
          (event) => `
            <li>
              <button type="button" data-related-event-id="${escapeHtml(event.id)}">
                <span>${escapeHtml(event.event_type)}</span>
                <strong>${escapeHtml(event.id)}</strong>
                <small>${escapeHtml(event.created_at ?? "")}</small>
              </button>
            </li>
          `
        )
        .join("")}
    </ol>
  `;
}

function auditExplorerAction(eventId) {
  return [
    {
      label: "Audit Explorer",
      href: `/observability?event_id=${encodeURIComponent(eventId)}`
    }
  ];
}
