import { fireEvent, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithQueryClient } from "../../test/test-utils";
import {
  ObservabilityPage,
  observabilityRolloutPayloadFromValues
} from "./ObservabilityPage";

const slo = {
  id: "slo_1",
  organization_id: "org_default",
  environment_id: "env_default",
  name: "Task Success",
  target_type: "agent",
  target_id: "agent_1",
  sli: "task_success_rate",
  target_value: 0.95,
  window: "30d",
  status: "healthy",
  created_by: "user_1",
  created_at: "2026-05-01T00:00:00Z",
  updated_at: "2026-05-01T00:00:00Z",
  measurements: [
    {
      id: "slomeas_1",
      slo_id: "slo_1",
      value: 0.98,
      good_events: 98,
      total_events: 100,
      error_budget_remaining: 0.9,
      burn_rate: 0.1,
      status: "healthy",
      metadata: { source: "test" },
      measured_at: "2026-05-02T00:00:00Z"
    },
    {
      id: "slomeas_0",
      slo_id: "slo_1",
      value: 0.97,
      good_events: 97,
      total_events: 100,
      error_budget_remaining: 0.8,
      burn_rate: 0.2,
      status: "healthy",
      metadata: { source: "test" },
      measured_at: "2026-05-01T00:00:00Z"
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
      target_id: "agent_1",
      period: "monthly",
      amount_limit: 100,
      used_amount: 12.5,
      action_on_breach: "warn",
      breach_action: "none",
      status: "healthy",
      created_by: "user_1",
      created_at: "2026-05-01T00:00:00Z",
      updated_at: "2026-05-01T00:00:00Z"
    }
  ],
  events: [
    {
      id: "costevt_1",
      organization_id: "org_default",
      environment_id: "env_default",
      target_type: "agent",
      target_id: "agent_1",
      provider: "openai",
      model: "gpt",
      amount: 1.25,
      units: 1000,
      correlation_id: "corr_cost",
      created_at: "2026-05-01T00:00:00Z"
    }
  ],
  total_amount: 12.5,
  by_target: { agent_1: 12.5 },
  by_provider: { openai: 12.5 },
  by_model: { gpt: 12.5 }
};

const emptyCosts = {
  budgets: [],
  events: [],
  total_amount: 0,
  by_target: {},
  by_provider: {},
  by_model: {}
};

const incident = {
  id: "inc_1",
  organization_id: "org_default",
  environment_id: "env_default",
  severity: "critical",
  status: "open",
  title: "Denial Spike",
  summary: "Policy denials crossed the incident threshold.",
  owner_user_id: null,
  correlation_id: "corr_inc",
  source_event_id: "evt_1",
  resolution_note: null,
  started_at: "2026-05-01T00:00:00Z",
  acknowledged_at: null,
  resolved_at: null,
  updated_at: "2026-05-01T00:00:00Z",
  related_event_ids: ["evt_1"]
};

const experiment = {
  id: "chaos_1",
  organization_id: "org_default",
  environment_id: "env_default",
  name: "Latency Drill",
  fault_type: "latency",
  target_type: "agent",
  target_id: "agent_1",
  blast_radius: { max_agents: 1 },
  guardrails: { max_error_rate: 0.05 },
  status: "ready",
  created_by: "user_1",
  created_at: "2026-05-01T00:00:00Z",
  updated_at: "2026-05-01T00:00:00Z"
};

const chaosRun = {
  id: "chaosrun_1",
  experiment_id: "chaos_1",
  status: "completed",
  started_at: "2026-05-01T00:00:00Z",
  finished_at: "2026-05-01T00:00:05Z",
  result: { guardrail_breached: false }
};

const rollout = {
  id: "rollout_1",
  organization_id: "org_default",
  environment_id: "env_default",
  name: "Claims Canary",
  target_type: "agent",
  target_id: "agent_1",
  strategy: "canary",
  status: "active",
  current_stage: 5,
  config: { stages: [5, 25, 100], gates: { require_slo_healthy: true } },
  created_by: "user_1",
  created_at: "2026-05-01T00:00:00Z",
  updated_at: "2026-05-01T00:00:00Z",
  events: [
    {
      id: "rollevent_1",
      rollout_id: "rollout_1",
      stage: 5,
      decision: "advanced",
      metrics: { slo_status: "healthy" },
      created_at: "2026-05-01T00:00:00Z"
    }
  ]
};

describe("ObservabilityPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders SLOs, costs, incidents, chaos experiments, and rollouts", async () => {
    mockObservabilityFetch();

    renderWithQueryClient(<ObservabilityPage />);

    expect(await screen.findByRole("heading", { name: "SLO Objectives" })).toBeInTheDocument();
    expect(await screen.findByText("Task Success")).toBeInTheDocument();
    expect(screen.getByText("SLO Trend")).toBeInTheDocument();
    expect(screen.getByText("98.00%")).toBeInTheDocument();
    expect(screen.getByText("Cost Distribution")).toBeInTheDocument();
    expect(screen.getByText("openai")).toBeInTheDocument();
    expect(screen.getByText("gpt")).toBeInTheDocument();
    expect(screen.getByText("agent_1")).toBeInTheDocument();
    expect(screen.getAllByText("$12.50").length).toBeGreaterThan(0);
    expect(await screen.findByText("Denial Spike")).toBeInTheDocument();
    expect(await screen.findByText("Latency Drill")).toBeInTheDocument();
    expect(await screen.findByText("Claims Canary")).toBeInTheDocument();
  });

  it("renders an SLO trend fallback when measurements are missing", async () => {
    mockObservabilityFetch({ slos: [{ ...slo, measurements: [] }] });

    renderWithQueryClient(<ObservabilityPage />);

    expect(await screen.findByText("SLO trend unavailable")).toBeInTheDocument();
    expect(screen.getByText("Record at least two measurements to draw a trend chart.")).toBeInTheDocument();
  });

  it("renders a cost distribution fallback when no cost events exist", async () => {
    mockObservabilityFetch({ costs: emptyCosts });

    renderWithQueryClient(<ObservabilityPage />);

    expect(await screen.findByText("No cost events")).toBeInTheDocument();
    expect(
      screen.getByText("Record cost events to chart provider, model, and target spend.")
    ).toBeInTheDocument();
  });

  it("submits observability operations through the typed API surface", async () => {
    const requests = mockObservabilityFetch();

    renderWithQueryClient(<ObservabilityPage />);
    await screen.findByText("Task Success");

    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Latency SLO" } });
    fireEvent.change(screen.getByLabelText("Target ID"), { target: { value: "agent_1" } });
    fireEvent.click(screen.getByRole("button", { name: "Create SLO" }));
    expect(await screen.findByText("SLO created")).toBeInTheDocument();

    const sloRow = document.querySelector('[data-observability-slo-row="slo_1"]');
    expect(sloRow).not.toBeNull();
    fireEvent.click(within(sloRow as HTMLElement).getByRole("button", { name: "Record" }));
    expect(await screen.findByText("SLO measurement recorded")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Budget Target ID"), { target: { value: "agent_1" } });
    fireEvent.click(screen.getByRole("button", { name: "Create Budget" }));
    expect(await screen.findByText("Cost budget created")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Cost Target ID"), { target: { value: "agent_1" } });
    fireEvent.change(screen.getByLabelText("Provider"), { target: { value: "openai" } });
    fireEvent.change(screen.getByLabelText("Model"), { target: { value: "gpt" } });
    fireEvent.click(screen.getByRole("button", { name: "Record Cost" }));
    expect(await screen.findByText("Cost event recorded")).toBeInTheDocument();

    const incidentRow = document.querySelector('[data-observability-incident-row="inc_1"]');
    expect(incidentRow).not.toBeNull();
    fireEvent.click(within(incidentRow as HTMLElement).getByRole("button", { name: "Ack" }));
    expect(await screen.findByText("Incident acknowledged")).toBeInTheDocument();
    fireEvent.change(within(incidentRow as HTMLElement).getByLabelText("Denial Spike resolution"), {
      target: { value: "Resolved by rollback" }
    });
    fireEvent.click(within(incidentRow as HTMLElement).getByRole("button", { name: "Resolve" }));
    expect(await screen.findByText("Incident resolved")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("checkbox", { name: "Acknowledge blast radius" }));
    fireEvent.click(screen.getByRole("button", { name: "Run Experiment" }));
    expect(await screen.findByText("Chaos experiment run completed")).toBeInTheDocument();
    expect(screen.getByText("chaosrun_1")).toBeInTheDocument();

    const rolloutRow = document.querySelector('[data-observability-rollout-row="rollout_1"]');
    expect(rolloutRow).not.toBeNull();
    fireEvent.click(within(rolloutRow as HTMLElement).getByRole("button", { name: "Advance" }));
    expect(await screen.findByText("Rollout advanced")).toBeInTheDocument();
    fireEvent.change(within(rolloutRow as HTMLElement).getByLabelText("Claims Canary rollback reason"), {
      target: { value: "Guardrail breach" }
    });
    fireEvent.click(within(rolloutRow as HTMLElement).getByRole("button", { name: "Rollback" }));
    expect(await screen.findByText("Rollout rolled back")).toBeInTheDocument();

    expect(requests.some((request) => request.url.endsWith("/observability/slo"))).toBe(true);
    expect(requests.some((request) => request.url.endsWith("/measurements"))).toBe(true);
    expect(requests.some((request) => request.url.endsWith("/cost-budgets"))).toBe(true);
    expect(requests.some((request) => request.url.endsWith("/cost-events"))).toBe(true);
    expect(requests.some((request) => request.url.endsWith("/ack"))).toBe(true);
    expect(requests.some((request) => request.url.endsWith("/resolve"))).toBe(true);
    expect(requests.some((request) => request.url.endsWith("/run"))).toBe(true);
    expect(requests.some((request) => request.url.endsWith("/advance"))).toBe(true);
    expect(requests.some((request) => request.url.endsWith("/rollback"))).toBe(true);
  });

  it("normalizes rollout stages and gate JSON", () => {
    expect(
      observabilityRolloutPayloadFromValues({
        name: " Test ",
        target_id: " agent_1 ",
        stages: "5, 25,100",
        gates_json: '{"require_slo_healthy":true}'
      })
    ).toEqual({
      name: "Test",
      target_type: "agent",
      target_id: "agent_1",
      strategy: "canary",
      config: {
        stages: [5, 25, 100],
        gates: { require_slo_healthy: true }
      }
    });
  });
});

function mockObservabilityFetch(
  overrides: {
    slos?: unknown[];
    costs?: unknown;
    incidents?: unknown[];
    experiments?: unknown[];
    rollouts?: unknown[];
  } = {}
) {
  const requests: Array<{ url: string; method: string; body?: unknown }> = [];
  const slosPayload = overrides.slos ?? [slo];
  const costsPayload = overrides.costs ?? costs;
  const incidentsPayload = overrides.incidents ?? [incident];
  const experimentsPayload = overrides.experiments ?? [experiment];
  const rolloutsPayload = overrides.rollouts ?? [rollout];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = input.toString();
      const path = new URL(url, "http://localhost").pathname;
      const method = init?.method ?? "GET";
      const body = init?.body ? JSON.parse(String(init.body)) : undefined;
      requests.push({ url: path, method, body });

      if (path === "/api/v1/observability/slo" && method === "GET") {
        return json(slosPayload);
      }
      if (path === "/api/v1/observability/costs" && method === "GET") {
        return json(costsPayload);
      }
      if (path === "/api/v1/observability/incidents" && method === "GET") {
        return json(incidentsPayload);
      }
      if (path === "/api/v1/observability/chaos/experiments" && method === "GET") {
        return json(experimentsPayload);
      }
      if (path === "/api/v1/observability/rollouts" && method === "GET") {
        return json(rolloutsPayload);
      }
      if (path === "/api/v1/observability/slo" && method === "POST") {
        return json({ ...slo, id: "slo_2", name: "Latency SLO" }, 201);
      }
      if (path === "/api/v1/observability/slo/slo_1/measurements" && method === "POST") {
        return json({ ...slo.measurements[0], id: "slomeas_2" }, 201);
      }
      if (path === "/api/v1/observability/cost-budgets" && method === "POST") {
        return json({ ...costs.budgets[0], id: "costbud_2" }, 201);
      }
      if (path === "/api/v1/observability/cost-events" && method === "POST") {
        return json({ ...costs.events[0], id: "costevt_2" }, 201);
      }
      if (path === "/api/v1/observability/incidents/inc_1/ack" && method === "POST") {
        return json({ ...incident, status: "acknowledged" });
      }
      if (path === "/api/v1/observability/incidents/inc_1/resolve" && method === "POST") {
        return json({ ...incident, status: "resolved", resolution_note: "Resolved by rollback" });
      }
      if (path === "/api/v1/observability/chaos/experiments/chaos_1/run" && method === "POST") {
        return json(chaosRun, 201);
      }
      if (path === "/api/v1/observability/rollouts/rollout_1/advance" && method === "POST") {
        return json({ ...rollout, current_stage: 25 });
      }
      if (path === "/api/v1/observability/rollouts/rollout_1/rollback" && method === "POST") {
        return json({ ...rollout, status: "rolled_back" });
      }
      if (path === "/api/v1/observability/incidents" && method === "POST") {
        return json({ ...incident, id: "inc_2" }, 201);
      }
      if (path === "/api/v1/observability/chaos/experiments" && method === "POST") {
        return json({ ...experiment, id: "chaos_2" }, 201);
      }
      if (path === "/api/v1/observability/rollouts" && method === "POST") {
        return json({ ...rollout, id: "rollout_2" }, 201);
      }

      return json({ detail: `Unhandled ${method} ${path}` }, 404);
    })
  );
  return requests;
}

function json(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" }
  });
}
