import assert from "node:assert/strict";
import test from "node:test";

import { createApiClient } from "../src/apiClient.js";
import {
  observabilityChaosExperimentPayloadFromValues,
  observabilityChaosRunPayloadFromValues,
  observabilityCostBudgetPayloadFromValues,
  observabilityCostEventPayloadFromValues,
  observabilityIncidentPayloadFromValues,
  observabilityIncidentResolvePayloadFromValues,
  observabilityRolloutAdvancePayloadFromValues,
  observabilityRolloutPayloadFromValues,
  observabilityRolloutRollbackPayloadFromValues,
  observabilitySloPayloadFromValues,
  renderChaosPanel,
  renderCostRollups,
  renderIncidentPanel,
  renderObservabilityPage,
  renderRolloutTimeline,
  renderSloPanel
} from "../src/observability.js";

const slo = {
  id: "slo_1",
  organization_id: "org_default",
  environment_id: "env_default",
  name: "Demo agent task success",
  target_type: "agent",
  target_id: "agent_demo",
  sli: "task_success_rate",
  target_value: 0.99,
  window: "30d",
  status: "exhausted",
  created_by: "user_admin",
  created_at: "2026-05-01T00:00:00Z",
  updated_at: "2026-05-01T00:10:00Z",
  measurements: [
    {
      id: "slomeas_1",
      slo_id: "slo_1",
      value: 0.95,
      good_events: 95,
      total_events: 100,
      error_budget_remaining: 0,
      burn_rate: 5,
      status: "exhausted",
      metadata: {},
      measured_at: "2026-05-01T00:10:00Z"
    }
  ]
};

const costs = {
  budgets: [
    {
      id: "costbud_1",
      organization_id: "org_default",
      environment_id: "env_default",
      target_type: "agent",
      target_id: "agent_demo",
      period: "monthly",
      amount_limit: 1,
      used_amount: 1.25,
      action_on_breach: "kill_switch",
      breach_action: "kill_switch",
      status: "breached",
      created_by: "user_admin",
      created_at: "2026-05-01T00:00:00Z",
      updated_at: "2026-05-01T00:20:00Z"
    }
  ],
  events: [
    {
      id: "costevt_1",
      organization_id: "org_default",
      environment_id: "env_default",
      target_type: "agent",
      target_id: "agent_demo",
      provider: "openai",
      model: "gpt-5.4",
      amount: 1.25,
      units: 1000,
      correlation_id: "corr_cost_1",
      created_at: "2026-05-01T00:20:00Z"
    }
  ],
  total_amount: 1.25,
  by_target: { "agent:agent_demo": 1.25 },
  by_provider: { openai: 1.25 },
  by_model: { "gpt-5.4": 1.25 }
};

const incident = {
  id: "inc_1",
  organization_id: "org_default",
  environment_id: "env_default",
  severity: "critical",
  status: "open",
  title: "Repeated denials",
  summary: "Policy denials crossed the incident threshold.",
  owner_user_id: null,
  correlation_id: "corr_denials",
  source_event_id: "evt_1",
  resolution_note: null,
  started_at: "2026-05-01T00:30:00Z",
  acknowledged_at: null,
  resolved_at: null,
  updated_at: "2026-05-01T00:30:00Z",
  related_event_ids: ["evt_1", "evt_2"]
};

const chaosExperiment = {
  id: "chaos_1",
  organization_id: "org_default",
  environment_id: "env_default",
  name: "Demo latency",
  fault_type: "latency",
  target_type: "agent",
  target_id: "agent_demo",
  blast_radius: { max_agents: 1, environment: "demo" },
  guardrails: { max_error_rate: 0.05 },
  status: "ready",
  created_by: "user_admin",
  created_at: "2026-05-01T00:40:00Z",
  updated_at: "2026-05-01T00:40:00Z"
};

const chaosRun = {
  id: "chaosrun_1",
  experiment_id: "chaos_1",
  status: "completed",
  started_at: "2026-05-01T00:41:00Z",
  finished_at: "2026-05-01T00:41:01Z",
  result: {
    guardrail_breached: false,
    breached_guardrails: [],
    fault_type: "latency"
  }
};

const rollout = {
  id: "rollout_1",
  organization_id: "org_default",
  environment_id: "env_default",
  name: "Model canary",
  target_type: "agent",
  target_id: "agent_demo",
  strategy: "canary",
  status: "running",
  current_stage: 25,
  config: {
    stages: [5, 25, 100],
    gates: { require_slo_healthy: true }
  },
  created_by: "user_admin",
  created_at: "2026-05-01T00:50:00Z",
  updated_at: "2026-05-01T00:55:00Z",
  events: [
    {
      id: "rollevent_1",
      rollout_id: "rollout_1",
      stage: 25,
      decision: "advanced",
      metrics: { to_stage: 25 },
      created_at: "2026-05-01T00:55:00Z"
    }
  ]
};

test("component SLO table renders burn rate", () => {
  const html = renderSloPanel({ slos: [slo] });

  assert.match(html, /data-observability-slo-row="slo_1"/);
  assert.match(html, /Demo agent task success/);
  assert.match(html, /exhausted/);
  assert.match(html, />5<\/td>/);
});

test("component cost chart handles empty state", () => {
  const html = renderCostRollups({ by_provider: {}, by_model: {} });

  assert.match(html, /data-observability-cost-chart-empty/);
  assert.match(html, /No cost chart/);
});

test("component incident resolve requires note", () => {
  const html = renderIncidentPanel({ incidents: [incident] });

  assert.match(html, /data-observability-incident-row="inc_1"/);
  assert.match(html, /data-observability-incident-resolve-form/);
  assert.match(html, /name="resolution_note" placeholder="Resolution note" required/);
});

test("component chaos run confirmation requires blast-radius acknowledgement", () => {
  const html = renderChaosPanel({ experiments: [chaosExperiment], runs: [chaosRun] });

  assert.match(html, /data-observability-chaos-row="chaos_1"/);
  assert.match(html, /data-observability-chaos-run-modal="chaos_1"/);
  assert.match(html, /name="acknowledge_blast_radius" value="yes" required/);
  assert.match(html, /data-observability-chaos-run-detail="chaosrun_1"/);
});

test("component rollout timeline renders stages", () => {
  const html = renderRolloutTimeline(rollout);

  assert.match(html, /data-observability-rollout-timeline="rollout_1"/);
  assert.match(html, /data-stage="5"/);
  assert.match(html, /data-stage="25"/);
  assert.match(html, /data-stage="100"/);
  assert.match(html, /class="is-complete"/);
});

test("observability route renders overview slos costs and incidents", () => {
  const html = renderObservabilityPage({
    observabilitySlos: [slo],
    observabilityCosts: costs,
    observabilityIncidents: [incident],
    observabilityChaosExperiments: [chaosExperiment],
    observabilityChaosRuns: [chaosRun],
    observabilityRollouts: [rollout]
  });

  assert.match(html, /data-route-page="\/observability"/);
  assert.match(html, /data-observability-overview/);
  assert.match(html, /data-observability-slos/);
  assert.match(html, /data-observability-costs/);
  assert.match(html, /data-observability-incidents/);
  assert.match(html, /data-observability-chaos/);
  assert.match(html, /data-observability-rollouts/);
});

test("payload helpers normalize observability forms", () => {
  assert.deepEqual(
    observabilitySloPayloadFromValues({
      name: " Demo ",
      target_type: " agent ",
      target_id: " agent_demo ",
      sli: " task_success_rate ",
      target_value: "0.99",
      window: "30d"
    }),
    {
      name: "Demo",
      target_type: "agent",
      target_id: "agent_demo",
      sli: "task_success_rate",
      target_value: 0.99,
      window: "30d"
    }
  );
  assert.equal(observabilityCostBudgetPayloadFromValues({ amount_limit: "12.5" }).amount_limit, 12.5);
  assert.equal(observabilityCostEventPayloadFromValues({ amount: "1.25", units: "1000" }).units, 1000);
  assert.deepEqual(observabilityIncidentPayloadFromValues({ title: " T ", summary: " S " }), {
    severity: "warning",
    title: "T",
    summary: "S",
    correlation_id: null
  });
  assert.deepEqual(observabilityIncidentResolvePayloadFromValues({ resolution_note: " Done " }), {
    resolution_note: "Done"
  });
  assert.deepEqual(
    observabilityChaosExperimentPayloadFromValues({
      name: " Demo ",
      target_id: " agent_demo ",
      blast_radius_json: '{"max_agents":1}',
      guardrails_json: '{"max_error_rate":0.05}'
    }).blast_radius,
    { max_agents: 1 }
  );
  assert.deepEqual(
    observabilityChaosRunPayloadFromValues({
      acknowledge_blast_radius: "yes",
      error_rate: "0.02"
    }),
    {
      observed_metrics: { error_rate: 0.02 },
      acknowledgement: "blast-radius-acknowledged"
    }
  );
  assert.deepEqual(
    observabilityRolloutPayloadFromValues({
      name: " Canary ",
      target_id: " agent_demo ",
      stages: "5, 25, 100",
      gates_json: '{"require_slo_healthy":true}'
    }).config,
    { stages: [5, 25, 100], gates: { require_slo_healthy: true } }
  );
  assert.deepEqual(
    observabilityRolloutAdvancePayloadFromValues({
      slo_status: "healthy",
      policy_deny_rate: "0",
      trust_score: "1000",
      open_incidents: "0"
    }),
    { metrics: { slo_status: "healthy", policy_deny_rate: 0, trust_score: 1000, open_incidents: 0 } }
  );
  assert.deepEqual(observabilityRolloutRollbackPayloadFromValues({ reason: " Back " }), {
    reason: "Back"
  });
});

test("api client observability endpoints use expected paths", async () => {
  const calls = [];
  const api = createApiClient({
    fetchImpl: async (url, options = {}) => {
      calls.push({ url, method: options.method ?? "GET" });
      return new Response(JSON.stringify([]), {
        status: 200,
        headers: { "content-type": "application/json" }
      });
    }
  });

  await api.createObservabilitySlo({ name: "Demo" });
  await api.listObservabilitySlos({ status: "exhausted" });
  await api.createObservabilitySloMeasurement("slo_1", { value: 0.95 });
  await api.createObservabilityCostBudget({ target_id: "agent_demo" });
  await api.listObservabilityCostBudgets({ status: "breached" });
  await api.createObservabilityCostEvent({ target_id: "agent_demo" });
  await api.getObservabilityCosts();
  await api.createObservabilityIncident({ title: "Demo" });
  await api.createObservabilityIncidentFromEvent({ source_event_id: "evt_1" });
  await api.listObservabilityIncidents({ status: "open" });
  await api.acknowledgeObservabilityIncident("inc_1");
  await api.resolveObservabilityIncident("inc_1", { resolution_note: "Done" });
  await api.createObservabilityChaosExperiment({ name: "Demo" });
  await api.listObservabilityChaosExperiments({ status: "ready" });
  await api.runObservabilityChaosExperiment("chaos_1", { observed_metrics: {} });
  await api.stopObservabilityChaosRun("chaosrun_1");
  await api.createObservabilityRollout({ name: "Canary" });
  await api.listObservabilityRollouts({ target_type: "agent" });
  await api.advanceObservabilityRollout("rollout_1", { metrics: {} });
  await api.rollbackObservabilityRollout("rollout_1", { reason: "Bad canary" });

  assert.deepEqual(calls, [
    { url: "/api/v1/observability/slo", method: "POST" },
    { url: "/api/v1/observability/slo?status=exhausted", method: "GET" },
    { url: "/api/v1/observability/slo/slo_1/measurements", method: "POST" },
    { url: "/api/v1/observability/cost-budgets", method: "POST" },
    { url: "/api/v1/observability/cost-budgets?status=breached", method: "GET" },
    { url: "/api/v1/observability/cost-events", method: "POST" },
    { url: "/api/v1/observability/costs", method: "GET" },
    { url: "/api/v1/observability/incidents", method: "POST" },
    { url: "/api/v1/observability/incidents/from-event", method: "POST" },
    { url: "/api/v1/observability/incidents?status=open", method: "GET" },
    { url: "/api/v1/observability/incidents/inc_1/ack", method: "POST" },
    { url: "/api/v1/observability/incidents/inc_1/resolve", method: "POST" },
    { url: "/api/v1/observability/chaos/experiments", method: "POST" },
    { url: "/api/v1/observability/chaos/experiments?status=ready", method: "GET" },
    { url: "/api/v1/observability/chaos/experiments/chaos_1/run", method: "POST" },
    { url: "/api/v1/observability/chaos/runs/chaosrun_1/stop", method: "POST" },
    { url: "/api/v1/observability/rollouts", method: "POST" },
    { url: "/api/v1/observability/rollouts?target_type=agent", method: "GET" },
    { url: "/api/v1/observability/rollouts/rollout_1/advance", method: "POST" },
    { url: "/api/v1/observability/rollouts/rollout_1/rollback", method: "POST" }
  ]);
});
