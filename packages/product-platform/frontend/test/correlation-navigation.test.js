import assert from "node:assert/strict";
import test from "node:test";

import { loadAuditEventDrawer, renderAuditEventContent } from "../src/auditDrawers.js";
import { backDrawer, replaceDrawerContent, renderDrawer } from "../src/drawers.js";

test("related-events timeline renders clickable related events", () => {
  const html = renderAuditEventContent({
    event: event("evt_1", "policy.decision", "2026-04-30T00:00:02+00:00"),
    verification: { valid: true, checked_count: 1 },
    relatedEvents: [
      event("evt_1", "policy.decision", "2026-04-30T00:00:02+00:00"),
      event("evt_2", "mcp.call", "2026-04-30T00:00:01+00:00")
    ]
  });

  assert.match(html, /related-event-timeline/);
  assert.match(html, /data-related-event-id="evt_2"/);
  assert.match(html, /mcp\.call/);
});

test("clicking related event can replace drawer content with back stack", async () => {
  const first = await loadAuditEventDrawer({
    eventId: "evt_1",
    apiClient: clientForEvents([
      event("evt_1", "policy.decision", "2026-04-30T00:00:01+00:00"),
      event("evt_2", "mcp.call", "2026-04-30T00:00:02+00:00")
    ])
  });
  const second = await loadAuditEventDrawer({
    eventId: "evt_2",
    apiClient: clientForEvents([
      event("evt_1", "policy.decision", "2026-04-30T00:00:01+00:00"),
      event("evt_2", "mcp.call", "2026-04-30T00:00:02+00:00")
    ])
  });
  const replaced = replaceDrawerContent(first, second);
  const html = renderDrawer(replaced);

  assert.equal(replaced.resourceId, "evt_2");
  assert.equal(replaced.backStack.length, 1);
  assert.equal(replaced.backStack[0].resourceId, "evt_1");
  assert.match(html, /data-drawer-back/);
  assert.match(html, /MCP Call/);
});

test("back navigation returns to original event", async () => {
  const first = await loadAuditEventDrawer({
    eventId: "evt_1",
    apiClient: clientForEvents([event("evt_1", "policy.decision")])
  });
  const second = await loadAuditEventDrawer({
    eventId: "evt_2",
    apiClient: clientForEvents([event("evt_2", "runtime.action")])
  });
  const replaced = replaceDrawerContent(first, second);
  const restored = backDrawer(replaced);

  assert.equal(restored.resourceId, "evt_1");
  assert.equal(restored.backStack.length, 0);
});

test("integration related timeline handles empty result", async () => {
  const drawer = await loadAuditEventDrawer({
    eventId: "evt_lonely",
    apiClient: clientForEvents([event("evt_lonely", "policy.decision")])
  });
  const html = renderDrawer(drawer);

  assert.match(html, /data-related-events/);
  assert.match(html, /No related events/);
});

function event(id, eventType, createdAt = "2026-04-30T00:00:00+00:00") {
  return {
    id,
    organization_id: "org_default",
    environment_id: "env_default",
    event_type: eventType,
    source_component: "tests",
    actor_type: "system",
    actor_id: null,
    agent_id: "agent_1",
    resource_type: eventType === "runtime.action" ? "runtime_session" : "policy",
    resource_id: eventType === "runtime.action" ? "session_1" : "policy_1",
    decision: "allow",
    severity: "info",
    correlation_id: "corr_1",
    payload_json: {
      matched_rule: "allow-read",
      reason: "Read-only action",
      tool_name: "read_file",
      action: "shell.exec",
      ring: "ring-2",
      sandbox_status: "contained"
    },
    created_at: createdAt
  };
}

function clientForEvents(events) {
  return {
    getAuditEvent: async (eventId) => events.find((candidate) => candidate.id === eventId),
    verifyAuditEvent: async () => ({ valid: true, checked_count: 1 }),
    listAuditEvents: async () => events
  };
}
