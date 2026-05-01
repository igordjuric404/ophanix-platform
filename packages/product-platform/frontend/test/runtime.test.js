import assert from "node:assert/strict";
import test from "node:test";

import { createApiClient } from "../src/apiClient.js";
import {
  renderRuntimePage,
  renderRuntimeRingDecisionsPanel,
  renderRuntimeRingRulesPanel,
  renderRuntimeSagaMonitor,
  renderRuntimeSagasPanel,
  renderRuntimeSagaStepDetail,
  renderRuntimeSandboxPanel,
  renderRuntimeKillSwitchPanel,
  renderRuntimeSessionsPanel,
  runtimeKillSwitchPayloadFromValues,
  runtimeActionPayloadFromValues,
  runtimeRingRulePayloadFromValues,
  runtimeSagaCancelPayloadFromValues,
  runtimeSagaExecutePayloadFromValues,
  runtimeSagaPayloadFromValues,
  runtimeSagaStepPayloadFromValues,
  runtimeSandboxProfilePayloadFromValues,
  runtimeSandboxTestPayloadFromValues,
  runtimeSessionPayloadFromValues
} from "../src/runtime.js";

const ringDecision = {
  id: "rtdcsn_1",
  runtime_action_id: "rtact_1",
  session_id: "rtssn_1",
  agent_id: "agent_high",
  action_name: "reports.read_balance",
  resource_type: "report",
  agent_trust_score: 820,
  required_ring: 1,
  assigned_ring: 2,
  result: "denied",
  reason: "Agent ring 2 insufficient for required ring 1",
  created_at: "2026-05-01T00:10:00Z"
};

const runtimeAction = {
  id: "rtact_1",
  session_id: "rtssn_1",
  action_name: "reports.read_balance",
  resource_type: "report",
  required_ring: 1,
  decision: "denied",
  reason: "Agent ring 2 insufficient for required ring 1",
  latency_ms: 2,
  correlation_id: "corr-runtime",
  created_at: "2026-05-01T00:10:00Z",
  ring_decision: ringDecision
};

const runtimeSession = {
  id: "rtssn_1",
  organization_id: "org_default",
  environment_id: "env_default",
  agent_id: "agent_high",
  agent_name: "High Trust Runtime Agent",
  state: "active",
  ring: 2,
  sponsor_user_id: "user_admin",
  started_at: "2026-05-01T00:09:00Z",
  ended_at: null,
  metadata: { purpose: "demo" },
  actions: [runtimeAction]
};

const runtimeRule = {
  id: "rtrule_1",
  organization_id: "org_default",
  environment_id: "env_default",
  action_pattern: "reports.read_*",
  required_ring: 1,
  min_trust_score: 700,
  enabled: true,
  created_at: "2026-05-01T00:08:00Z",
  updated_at: "2026-05-01T00:08:00Z"
};

const sagaStep = {
  id: "sgstep_1",
  saga_id: "saga_1",
  step_order: 1,
  name: "Issue refund",
  action_name: "claims.issue_refund",
  target_agent_id: "agent_claims",
  target_agent_name: "Claims Agent",
  required_capability: "claims.refund",
  timeout_seconds: 300,
  retry_count: 0,
  compensation_action: "claims.reverse_refund",
  status: "compensated",
  result: { action_name: "claims.reverse_refund", mode: "compensation" },
  created_at: "2026-05-01T00:11:00Z",
  updated_at: "2026-05-01T00:12:00Z"
};

const saga = {
  id: "saga_1",
  organization_id: "org_default",
  environment_id: "env_default",
  runtime_session_id: "rtssn_1",
  name: "Refund Saga",
  status: "compensated",
  created_by: "user_admin",
  started_at: "2026-05-01T00:11:00Z",
  finished_at: "2026-05-01T00:12:00Z",
  correlation_id: "order-demo-001",
  created_at: "2026-05-01T00:10:00Z",
  updated_at: "2026-05-01T00:12:00Z",
  steps: [
    sagaStep,
    {
      ...sagaStep,
      id: "sgstep_2",
      step_order: 2,
      name: "Send email",
      action_name: "notifications.send_email",
      required_capability: "notifications.email",
      compensation_action: null,
      status: "failed",
      result: { error: "Configured demo failure" }
    }
  ],
  events: [
    {
      id: "sgevt_1",
      saga_id: "saga_1",
      step_id: "sgstep_1",
      event_type: "saga.step.compensated",
      message: "Step 1 compensated.",
      payload: {},
      created_at: "2026-05-01T00:12:00Z"
    }
  ]
};

const sandboxProfile = {
  id: "sbxprof_1",
  organization_id: "org_default",
  environment_id: "env_default",
  name: "Strict Sandbox",
  provider_type: "subprocess",
  allowed_imports: ["json"],
  blocked_imports: ["os", "subprocess"],
  allowed_paths: ["/tmp/ophanix-demo"],
  network_policy: { egress: "deny" },
  resource_limits: { timeout_seconds: 5, memory_mb: 128 },
  status: "active",
  provider_warning: "Subprocess sandbox is demo-only and does not provide production isolation.",
  created_at: "2026-05-01T00:13:00Z",
  updated_at: "2026-05-01T00:13:00Z"
};

const sandboxDecision = {
  id: "sbxdcsn_1",
  profile_id: "sbxprof_1",
  agent_id: "agent_claims",
  action_name: "demo.unsafe_shell",
  decision: "denied",
  reason: "Import of blocked module 'subprocess'",
  violations: [],
  provider_warning: sandboxProfile.provider_warning,
  created_at: "2026-05-01T00:14:00Z"
};

const killSwitchEvent = {
  id: "kill_1",
  organization_id: "org_default",
  environment_id: "env_default",
  target_type: "session",
  target_id: "rtssn_1",
  scope: "target",
  reason: "Emergency stop test",
  actor_id: "security@example.com",
  status: "triggered",
  created_at: "2026-05-01T00:15:00Z"
};

test("component sessions table renders state", () => {
  const html = renderRuntimeSessionsPanel({ sessions: [runtimeSession] });

  assert.match(html, /data-runtime-session-row="rtssn_1"/);
  assert.match(html, /High Trust Runtime Agent/);
  assert.match(html, /active/);
  assert.match(html, /data-runtime-session-form/);
});

test("runtime route renders sessions timeline decisions and rules", () => {
  const html = renderRuntimePage({
    runtimeSessions: [runtimeSession],
    selectedRuntimeSession: runtimeSession,
    runtimeRingDecisions: [ringDecision],
    runtimeRingRules: [runtimeRule],
    runtimeSagas: [saga],
    selectedRuntimeSaga: saga,
    runtimeSandboxProfiles: [sandboxProfile],
    selectedRuntimeSandboxProfile: sandboxProfile,
    runtimeSandboxDecision: sandboxDecision,
    runtimeKillSwitchEvents: [killSwitchEvent]
  });

  assert.match(html, /data-route-page="\/runtime"/);
  assert.match(html, /data-runtime-sessions/);
  assert.match(html, /data-runtime-session-detail="rtssn_1"/);
  assert.match(html, /data-runtime-sagas/);
  assert.match(html, /data-runtime-saga-monitor="saga_1"/);
  assert.match(html, /data-runtime-sandbox/);
  assert.match(html, /data-runtime-kill-switch/);
  assert.match(html, /data-runtime-ring-decisions/);
  assert.match(html, /data-runtime-ring-rules/);
  assert.match(html, /data-runtime-action-row="rtact_1"/);
});

test("component ring decision shows reason", () => {
  const html = renderRuntimeRingDecisionsPanel({ decisions: [ringDecision] });

  assert.match(html, /data-runtime-ring-decision-row="rtdcsn_1"/);
  assert.match(html, /Agent ring 2 insufficient/);
  assert.match(html, /data-runtime-ring-chart/);
});

test("component ring decision explains public preview Ring 0 denial", () => {
  const html = renderRuntimeRingDecisionsPanel({
    decisions: [
      {
        ...ringDecision,
        id: "rtdcsn_ring0",
        required_ring: 0,
        result: "denied",
        reason: "Ring 0 actions are not available in Public Preview"
      }
    ]
  });

  assert.match(html, /data-runtime-ring-decision-row="rtdcsn_ring0"/);
  assert.match(html, /Ring 0 actions are not available in Public Preview/);
});

test("component ring rule form validates threshold bounds", () => {
  const html = renderRuntimeRingRulesPanel({ rules: [runtimeRule] });

  assert.match(html, /data-runtime-ring-rule-form/);
  assert.match(html, /name="min_trust_score" type="number" min="0" max="1000"/);
  assert.match(html, /data-runtime-ring-rule-row="rtrule_1"/);
});

test("runtime payload helpers normalize values", () => {
  assert.deepEqual(runtimeSessionPayloadFromValues({ agent_id: " agent_high ", ring: "2", sponsor_user_id: "" }), {
    agent_id: "agent_high",
    ring: 2,
    sponsor_user_id: null,
    metadata: {}
  });
  assert.deepEqual(runtimeActionPayloadFromValues({
    action_name: " reports.read ",
    resource_type: " report ",
    reversibility: "none",
    is_read_only: "on"
  }), {
    action_name: "reports.read",
    resource_type: "report",
    reversibility: "none",
    is_read_only: true,
    is_admin: false
  });
  assert.deepEqual(runtimeRingRulePayloadFromValues({
    action_pattern: " reports.* ",
    required_ring: "1",
    min_trust_score: "700",
    enabled: "on"
  }), {
    action_pattern: "reports.*",
    required_ring: 1,
    min_trust_score: 700,
    enabled: true
  });
  assert.deepEqual(runtimeSagaPayloadFromValues({
    name: " Refund Saga ",
    runtime_session_id: "",
    correlation_id: " order-1 "
  }), {
    name: "Refund Saga",
    runtime_session_id: null,
    correlation_id: "order-1"
  });
  assert.deepEqual(runtimeSagaStepPayloadFromValues({
    step_order: "2",
    name: " Email ",
    action_name: " notifications.send_email ",
    target_agent_id: " agent_claims ",
    required_capability: " notifications.email ",
    timeout_seconds: "60",
    retry_count: "1",
    compensation_action: ""
  }), {
    step_order: 2,
    name: "Email",
    action_name: "notifications.send_email",
    target_agent_id: "agent_claims",
    required_capability: "notifications.email",
    timeout_seconds: 60,
    retry_count: 1,
    compensation_action: null
  });
  assert.deepEqual(runtimeSagaExecutePayloadFromValues({
    runtime_session_id: "",
    failure_actions: "notifications.send_email, claims.issue_refund"
  }), {
    runtime_session_id: null,
    failure_actions: ["notifications.send_email", "claims.issue_refund"]
  });
  assert.deepEqual(runtimeSagaCancelPayloadFromValues({ reason: " done " }), { reason: "done" });
  assert.deepEqual(runtimeSandboxProfilePayloadFromValues({
    name: " Strict ",
    provider_type: "subprocess",
    allowed_imports: "json, datetime",
    blocked_imports: "os\nsubprocess",
    allowed_paths: "/tmp/demo, /var/tmp/demo",
    network_egress: "deny",
    timeout_seconds: "5",
    memory_mb: "128"
  }), {
    name: "Strict",
    provider_type: "subprocess",
    allowed_imports: ["json", "datetime"],
    blocked_imports: ["os", "subprocess"],
    allowed_paths: ["/tmp/demo", "/var/tmp/demo"],
    network_policy: { egress: "deny" },
    resource_limits: { timeout_seconds: 5, memory_mb: 128 }
  });
  assert.deepEqual(runtimeSandboxTestPayloadFromValues({
    code: " import json ",
    agent_id: "",
    action_name: " demo.safe "
  }), {
    code: "import json",
    agent_id: null,
    action_name: "demo.safe"
  });
  assert.deepEqual(runtimeKillSwitchPayloadFromValues({
    target_type: "session",
    target_id: "rtssn_1",
    scope: "target",
    reason: " stop ",
    confirmation: " KILL session:rtssn_1 "
  }), {
    target_type: "session",
    target_id: "rtssn_1",
    scope: "target",
    reason: "stop",
    confirmation: "KILL session:rtssn_1"
  });
});

test("component saga builder renders list and form", () => {
  const html = renderRuntimeSagasPanel({ sagas: [saga], selectedSaga: saga });

  assert.match(html, /data-runtime-saga-form/);
  assert.match(html, /data-runtime-saga-row="saga_1"/);
  assert.match(html, /Refund Saga/);
  assert.match(html, /compensated/);
});

test("component saga monitor renders failed compensation flow", () => {
  const html = renderRuntimeSagaMonitor(saga);

  assert.match(html, /data-runtime-saga-monitor="saga_1"/);
  assert.match(html, /data-runtime-saga-step-form/);
  assert.match(html, /data-runtime-saga-execute-form/);
  assert.match(html, /data-runtime-saga-cancel-form/);
  assert.match(html, /data-runtime-saga-step-row="sgstep_1"/);
  assert.match(html, /claims.reverse_refund/);
  assert.match(html, /saga.step.compensated/);
});

test("component saga step detail shows result payload", () => {
  const html = renderRuntimeSagaStepDetail(sagaStep);

  assert.match(html, /claims.issue_refund/);
  assert.match(html, /compensated/);
  assert.match(html, /claims.reverse_refund/);
  assert.match(html, /&quot;mode&quot;: &quot;compensation&quot;/);
});

test("component sandbox editor shows warning and test decision", () => {
  const html = renderRuntimeSandboxPanel({
    profiles: [sandboxProfile],
    selectedProfile: sandboxProfile,
    decision: sandboxDecision
  });

  assert.match(html, /data-runtime-sandbox-profile-form/);
  assert.match(html, /data-runtime-sandbox-test-form/);
  assert.match(html, /data-runtime-sandbox-warning/);
  assert.match(html, /does not provide production isolation/);
  assert.match(html, /data-runtime-sandbox-decision/);
  assert.match(html, /denied/);
});

test("component kill switch requires typed confirmation", () => {
  const html = renderRuntimeKillSwitchPanel({ events: [] });

  assert.match(html, /data-runtime-kill-switch-form/);
  assert.match(html, /name="confirmation" required/);
  assert.match(html, /name="target_type"/);
});

test("component kill event appears in history", () => {
  const html = renderRuntimeKillSwitchPanel({ events: [killSwitchEvent] });

  assert.match(html, /data-runtime-kill-switch-event-row="kill_1"/);
  assert.match(html, /Emergency stop test/);
  assert.match(html, /triggered/);
});

test("api client runtime methods call expected endpoints", async () => {
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

  await client.createRuntimeSession({ agent_id: "agent high" });
  await client.listRuntimeSessions({ state: "active" });
  await client.getRuntimeSession("rtssn 1");
  await client.endRuntimeSession("rtssn 1", { reason: "done" });
  await client.createRuntimeAction("rtssn 1", { action_name: "reports.read" });
  await client.listRuntimeRingDecisions({ result: "denied" });
  await client.listRuntimeRingRules({ enabled: true });
  await client.createRuntimeRingRule({ action_pattern: "reports.*" });
  await client.createRuntimeSaga({ name: "Refund Saga" });
  await client.listRuntimeSagas({ status: "draft" });
  await client.getRuntimeSaga("saga 1");
  await client.addRuntimeSagaStep("saga 1", { step_order: 1 });
  await client.executeRuntimeSaga("saga 1", { failure_actions: [] });
  await client.cancelRuntimeSaga("saga 1", { reason: "done" });
  await client.createRuntimeSandboxProfile({ name: "Strict" });
  await client.listRuntimeSandboxProfiles({ status: "active" });
  await client.patchRuntimeSandboxProfile("sbx 1", { status: "disabled" });
  await client.testRuntimeSandboxProfile("sbx 1", { code: "import json" });
  await client.triggerRuntimeKillSwitch({ target_type: "session" });
  await client.listRuntimeKillSwitchEvents({ limit: 10 });

  assert.deepEqual(calls, [
    ["/api/v1/runtime/sessions", "POST", { agent_id: "agent high" }],
    ["/api/v1/runtime/sessions?state=active", "GET", null],
    ["/api/v1/runtime/sessions/rtssn%201", "GET", null],
    ["/api/v1/runtime/sessions/rtssn%201/end", "POST", { reason: "done" }],
    ["/api/v1/runtime/sessions/rtssn%201/actions", "POST", { action_name: "reports.read" }],
    ["/api/v1/runtime/ring-decisions?result=denied", "GET", null],
    ["/api/v1/runtime/ring-rules?enabled=true", "GET", null],
    ["/api/v1/runtime/ring-rules", "POST", { action_pattern: "reports.*" }],
    ["/api/v1/runtime/sagas", "POST", { name: "Refund Saga" }],
    ["/api/v1/runtime/sagas?status=draft", "GET", null],
    ["/api/v1/runtime/sagas/saga%201", "GET", null],
    ["/api/v1/runtime/sagas/saga%201/steps", "POST", { step_order: 1 }],
    ["/api/v1/runtime/sagas/saga%201/execute", "POST", { failure_actions: [] }],
    ["/api/v1/runtime/sagas/saga%201/cancel", "POST", { reason: "done" }],
    ["/api/v1/runtime/sandbox-profiles", "POST", { name: "Strict" }],
    ["/api/v1/runtime/sandbox-profiles?status=active", "GET", null],
    ["/api/v1/runtime/sandbox-profiles/sbx%201", "PATCH", { status: "disabled" }],
    ["/api/v1/runtime/sandbox-profiles/sbx%201/test", "POST", { code: "import json" }],
    ["/api/v1/runtime/kill-switch", "POST", { target_type: "session" }],
    ["/api/v1/runtime/kill-switch/events?limit=10", "GET", null]
  ]);
});
