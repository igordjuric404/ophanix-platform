import assert from "node:assert/strict";
import test from "node:test";

import {
  auditEventDrawer,
  loadAuditEventDrawer,
  renderAuditEventContent
} from "../src/auditDrawers.js";
import { renderDrawer } from "../src/drawers.js";

const event = {
  id: "evt_policy_1",
  organization_id: "org_default",
  environment_id: "env_default",
  event_type: "policy.decision",
  source_component: "policy-engine",
  actor_type: "user",
  actor_id: "user_admin",
  agent_id: "agent_1",
  resource_type: "policy",
  resource_id: "policy_1",
  decision: "allow",
  severity: "info",
  correlation_id: "corr_1",
  payload_json: {
    matched_rule: "allow-read",
    reason: "Read-only action."
  },
  created_at: "2026-04-30T00:00:00+00:00"
};

test("component renders audit event metadata", () => {
  const html = renderDrawer(
    auditEventDrawer({
      event,
      verification: { valid: true, checked_count: 1 },
      relatedEvents: []
    })
  );

  assert.match(html, /data-audit-metadata/);
  assert.match(html, /policy\.decision/);
  assert.match(html, /policy-engine/);
  assert.match(html, /user \/ user_admin/);
  assert.match(html, /policy \/ policy_1/);
});

test("component renders raw payload JSON and hash status", () => {
  const html = renderAuditEventContent({
    event,
    verification: { valid: true, checked_count: 1 },
    relatedEvents: []
  });

  assert.match(html, /data-audit-payload/);
  assert.match(html, /&quot;matched_rule&quot;: &quot;allow-read&quot;/);
  assert.match(html, /Valid hash chain, 1 event\(s\) checked/);
});

test("mock API loads related correlation events", async () => {
  const calls = [];
  const drawer = await loadAuditEventDrawer({
    eventId: event.id,
    apiClient: {
      getAuditEvent: async (eventId) => {
        calls.push(["get", eventId]);
        return event;
      },
      verifyAuditEvent: async (eventId) => {
        calls.push(["verify", eventId]);
        return { valid: true, checked_count: 1 };
      },
      listAuditEvents: async (params) => {
        calls.push(["list", params.correlation_id]);
        return [
          event,
          {
            ...event,
            id: "evt_related_2",
            event_type: "mcp.call"
          }
        ];
      }
    }
  });
  const html = renderDrawer(drawer);

  assert.deepEqual(calls, [
    ["get", "evt_policy_1"],
    ["verify", "evt_policy_1"],
    ["list", "corr_1"]
  ]);
  assert.match(html, /data-related-events/);
  assert.match(html, /evt_related_2/);
  assert.match(html, /mcp\.call/);
});
