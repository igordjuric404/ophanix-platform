import assert from "node:assert/strict";
import test from "node:test";

import {
  drawerForAuditEvent,
  mcpCallDrawer,
  policyDecisionDrawer,
  runtimeActionDrawer
} from "../src/auditDrawers.js";
import { renderDrawer } from "../src/drawers.js";

test("component policy decision shows matched rule and reason", () => {
  const html = renderDrawer(policyDecisionDrawer({ event: policyEvent() }));

  assert.match(html, /data-policy-decision/);
  assert.match(html, /allow-read/);
  assert.match(html, /Read-only action/);
  assert.match(html, /Audit Explorer/);
  assert.match(html, /event_id=evt_policy/);
});

test("component MCP call shows tool and decision", () => {
  const html = renderDrawer(mcpCallDrawer({ event: mcpEvent() }));

  assert.match(html, /data-mcp-call/);
  assert.match(html, /read_file/);
  assert.match(html, /deny/);
  assert.match(html, /sensitive/);
  assert.match(html, /redact/);
});

test("component runtime action shows ring and sandbox status", () => {
  const html = renderDrawer(runtimeActionDrawer({ event: runtimeEvent() }));

  assert.match(html, /data-runtime-action/);
  assert.match(html, /shell.exec/);
  assert.match(html, /ring-2/);
  assert.match(html, /contained/);
  assert.match(html, /saga_123/);
});

test("audit event router selects specialized drawer variants", () => {
  assert.equal(drawerForAuditEvent({ event: policyEvent() }).kind, "policy-decision");
  assert.equal(drawerForAuditEvent({ event: mcpEvent() }).kind, "mcp-call");
  assert.equal(drawerForAuditEvent({ event: runtimeEvent() }).kind, "runtime-action");
});

function baseEvent(overrides) {
  return {
    id: "evt_base",
    organization_id: "org_default",
    environment_id: "env_default",
    event_type: "test.event",
    source_component: "tests",
    actor_type: "system",
    actor_id: null,
    agent_id: "agent_1",
    resource_type: "resource",
    resource_id: "resource_1",
    decision: "allow",
    severity: "info",
    correlation_id: "corr_1",
    payload_json: {},
    created_at: "2026-04-30T00:00:00+00:00",
    ...overrides
  };
}

function policyEvent() {
  return baseEvent({
    id: "evt_policy",
    event_type: "policy.decision",
    source_component: "policy-engine",
    resource_type: "policy",
    resource_id: "policy_1",
    policy_id: "policy_1",
    payload_json: {
      matched_rule: "allow-read",
      reason: "Read-only action"
    }
  });
}

function mcpEvent() {
  return baseEvent({
    id: "evt_mcp",
    event_type: "mcp.call",
    source_component: "mcp-proxy",
    resource_type: "mcp_server",
    resource_id: "server_1",
    decision: "deny",
    payload_json: {
      tool_name: "read_file",
      params_classification: "sensitive",
      sanitizer_action: "redact"
    }
  });
}

function runtimeEvent() {
  return baseEvent({
    id: "evt_runtime",
    event_type: "runtime.action",
    source_component: "runtime-control",
    resource_type: "runtime_session",
    resource_id: "session_1",
    payload_json: {
      action: "shell.exec",
      ring: "ring-2",
      sandbox_status: "contained",
      saga_id: "saga_123"
    }
  });
}
