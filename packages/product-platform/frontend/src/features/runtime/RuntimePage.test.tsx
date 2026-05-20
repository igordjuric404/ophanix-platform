import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithQueryClient } from "../../test/test-utils";
import {
  RuntimePage,
  killSwitchConfirmationPhrase,
  runtimeKillSwitchPayloadFromForm,
  runtimeRingRulePayloadFromForm,
  runtimeSagaStepPayloadFromForm,
  runtimeSandboxProfilePayloadFromForm
} from "./RuntimePage";

const ringDecision = {
  id: "rtdcsn_1",
  runtime_action_id: "rtact_1",
  session_id: "rtssn_1",
  agent_id: "agent_1",
  action_name: "refund.issue",
  resource_type: "runtime-action",
  agent_trust_score: 640,
  required_ring: 1,
  assigned_ring: 2,
  result: "denied",
  reason: "Ring 1 requires higher trust",
  created_at: "2026-05-01T00:00:00Z"
};

const runtimeAction = {
  id: "rtact_1",
  session_id: "rtssn_1",
  action_name: "refund.issue",
  resource_type: "runtime-action",
  required_ring: 1,
  decision: "denied",
  reason: "Ring 1 requires higher trust",
  latency_ms: 11,
  correlation_id: "corr-runtime",
  created_at: "2026-05-01T00:00:00Z",
  ring_decision: ringDecision
};

const runtimeSession = {
  id: "rtssn_1",
  agent_id: "agent_1",
  agent_name: "Claims Agent",
  state: "active",
  ring: 2,
  sponsor_user_id: "user_1",
  started_at: "2026-05-01T00:00:00Z",
  ended_at: null,
  metadata: { source: "test" },
  actions: [runtimeAction]
};

const ringRule = {
  id: "rtrule_1",
  action_pattern: "refund.*",
  required_ring: 1,
  min_trust_score: 700,
  enabled: true,
  created_at: "2026-05-01T00:00:00Z",
  updated_at: "2026-05-01T00:00:00Z"
};

const sagaStep = {
  id: "sgstp_1",
  saga_id: "saga_1",
  step_order: 1,
  name: "Lookup order",
  action_name: "order.lookup",
  target_agent_id: "agent_1",
  target_agent_name: "Claims Agent",
  required_capability: "claims:read",
  timeout_seconds: 300,
  retry_count: 1,
  compensation_action: "refund.revert",
  status: "failed",
  result: {
    error: "demo failure",
    worker_job_id: "job_saga_activity_1",
    idempotency_key: "saga:saga_1:step:sgstp_1:mode:execute:action:order.lookup",
    external_operation_id: "saga-op-1234567890abcdef"
  },
  created_at: "2026-05-01T00:00:00Z",
  updated_at: "2026-05-01T00:00:00Z"
};

const saga = {
  id: "saga_1",
  runtime_session_id: "rtssn_1",
  name: "Refund Saga",
  status: "draft",
  created_by: "user_1",
  started_at: null,
  finished_at: null,
  correlation_id: "corr-saga",
  created_at: "2026-05-01T00:00:00Z",
  updated_at: "2026-05-01T00:00:00Z",
  steps: [sagaStep],
  events: [
    {
      id: "sgev_1",
      saga_id: "saga_1",
      step_id: "sgstp_1",
      event_type: "saga.step.compensated",
      message: "Compensation queued",
      payload: { compensation_action: "refund.revert" },
      created_at: "2026-05-01T00:00:00Z"
    }
  ]
};

const sandboxProfile = {
  id: "sbx_1",
  name: "Python Restricted",
  provider_type: "subprocess",
  allowed_imports: ["json"],
  blocked_imports: ["os", "subprocess", "socket"],
  allowed_paths: ["/tmp/claims"],
  network_policy: { egress: "deny" },
  resource_limits: { timeout_seconds: 5, memory_mb: 128 },
  status: "active",
  provider_warning: "Subprocess sandbox is demo-only and does not provide production isolation.",
  created_at: "2026-05-01T00:00:00Z",
  updated_at: "2026-05-01T00:00:00Z"
};

const sandboxDecision = {
  id: "sbxd_1",
  profile_id: "sbx_1",
  agent_id: "agent_1",
  action_name: "script.run",
  decision: "denied",
  reason: "Blocked import detected",
  violations: [
    {
      line: 1,
      column: 1,
      violation_type: "blocked_import",
      description: "Import os is blocked",
      severity: "critical"
    }
  ],
  provider_warning: sandboxProfile.provider_warning,
  created_at: "2026-05-01T00:00:00Z"
};

const killSwitchEvent = {
  id: "kill_1",
  target_type: "session",
  target_id: "rtssn_1",
  scope: "target",
  reason: "operator stop",
  actor_id: "user_1",
  status: "triggered",
  created_at: "2026-05-01T00:00:00Z"
};

describe("RuntimePage", () => {
  beforeEach(() => {
    window.history.replaceState(null, "", "/runtime");
    mockRuntimeFetch();
  });

  it("renders sessions, rings, sagas, sandbox controls, and kill switch state", async () => {
    renderWithQueryClient(<RuntimePage />);

    expect(await screen.findByText("Runtime Sessions")).toBeInTheDocument();
    expect((await screen.findAllByText("Claims Agent")).length).toBeGreaterThan(0);
    fireEvent.click(within(runtimeSessionRow("rtssn_1")).getByRole("button", { name: "Open" }));
    fireEvent.click(within(await waitFor(() => runtimeSagaRow("saga_1"))).getByRole("button", { name: "Open" }));
    fireEvent.click(within(runtimeSandboxProfileRow("sbx_1")).getByRole("button", { name: "Open" }));
    expect(await screen.findByText("Session Timeline")).toBeInTheDocument();
    expect(screen.getByText("Ring Decisions")).toBeInTheDocument();
    expect(screen.getAllByText("Ring 1 requires higher trust").length).toBeGreaterThan(0);
    expect(screen.getByText("Ring Rule Editor")).toBeInTheDocument();
    expect(screen.getByText("Saga Builder")).toBeInTheDocument();
    expect(screen.getAllByText("Refund Saga").length).toBeGreaterThan(0);
    expect(await screen.findByText("Lookup order")).toBeInTheDocument();
    expect(screen.getByText("job_saga_activity_1")).toBeInTheDocument();
    expect(screen.getByText("saga:saga_1:step:sgstp_1:mode:execute:action:order.lookup")).toBeInTheDocument();
    expect(screen.getByText("saga-op-1234567890abcdef")).toBeInTheDocument();
    expect(screen.getAllByText("Sandbox Profiles").length).toBeGreaterThan(0);
    expect(await screen.findByText(/demo-only/)).toBeInTheDocument();
    expect(screen.getByText("Kill Switch")).toBeInTheDocument();
    expect(screen.getByText("operator stop")).toBeInTheDocument();
  });

  it("filters and mutates runtime workflows", async () => {
    const calls = mockRuntimeFetch();
    renderWithQueryClient(<RuntimePage />);

    expect(await screen.findByText("Runtime Sessions")).toBeInTheDocument();
    expect((await screen.findAllByText("Claims Agent")).length).toBeGreaterThan(0);
    fireEvent.click(within(runtimeSessionRow("rtssn_1")).getByRole("button", { name: "Open" }));

    const sessionsPanel = document.querySelector("[data-runtime-sessions]") as HTMLElement;
    fireEvent.change(within(sessionsPanel).getByLabelText("Agent ID"), {
      target: { value: "agent_1" }
    });
    fireEvent.click(within(sessionsPanel).getByRole("button", { name: "Start" }));
    await waitFor(() =>
      expect(calls.some((call) => call.path === "/api/v1/runtime/sessions" && call.method === "POST")).toBe(true)
    );
    fireEvent.change(within(sessionsPanel).getByLabelText("State"), {
      target: { value: "active" }
    });
    fireEvent.click(within(sessionsPanel).getByRole("button", { name: "Filter" }));
    await waitFor(() =>
      expect(calls.some((call) => call.path === "/api/v1/runtime/sessions?state=active")).toBe(true)
    );

    const sessionDetail = await waitFor(() => {
      const element = document.querySelector("[data-runtime-session-detail='rtssn_1']");
      expect(element).not.toBeNull();
      return element as HTMLElement;
    });
    fireEvent.change(within(sessionDetail).getByLabelText("Action"), {
      target: { value: "refund.issue" }
    });
    fireEvent.click(within(sessionDetail).getByRole("button", { name: "Evaluate" }));
    await waitFor(() =>
      expect(calls.some((call) => call.path === "/api/v1/runtime/sessions/rtssn_1/actions" && call.body?.action_name === "refund.issue")).toBe(true)
    );
    fireEvent.change(within(sessionDetail).getByLabelText("End Reason"), {
      target: { value: "demo complete" }
    });
    fireEvent.click(within(sessionDetail).getByRole("button", { name: "End Session" }));
    await waitFor(() =>
      expect(calls.some((call) => call.path === "/api/v1/runtime/sessions/rtssn_1/end")).toBe(true)
    );

    const decisionsPanel = document.querySelector("[data-runtime-ring-decisions]") as HTMLElement;
    fireEvent.change(within(decisionsPanel).getByLabelText("Result"), {
      target: { value: "denied" }
    });
    fireEvent.click(within(decisionsPanel).getByRole("button", { name: "Filter" }));
    await waitFor(() =>
      expect(calls.some((call) => call.path === "/api/v1/runtime/ring-decisions?result=denied")).toBe(true)
    );

    const rulesPanel = document.querySelector("[data-runtime-ring-rules]") as HTMLElement;
    fireEvent.change(within(rulesPanel).getByLabelText("Pattern"), {
      target: { value: "customer.delete" }
    });
    fireEvent.change(within(rulesPanel).getByLabelText("Min Trust"), {
      target: { value: "900" }
    });
    fireEvent.click(within(rulesPanel).getByRole("button", { name: "Create" }));
    await waitFor(() =>
      expect(calls.some((call) => call.path === "/api/v1/runtime/ring-rules" && call.method === "POST")).toBe(true)
    );

    const sagasPanel = document.querySelector("[data-runtime-sagas]") as HTMLElement;
    fireEvent.change(within(sagasPanel).getByLabelText("Name"), {
      target: { value: "Claims Refund" }
    });
    fireEvent.click(within(sagasPanel).getByRole("button", { name: "Create" }));
    await waitFor(() =>
      expect(calls.some((call) => call.path === "/api/v1/runtime/sagas" && call.method === "POST")).toBe(true)
    );
    fireEvent.change(within(sagasPanel).getByLabelText("Saga Status"), {
      target: { value: "draft" }
    });
    fireEvent.click(within(sagasPanel).getByRole("button", { name: "Filter" }));
    await waitFor(() =>
      expect(calls.some((call) => call.path === "/api/v1/runtime/sagas?status=draft")).toBe(true)
    );

    fireEvent.click(within(await findRuntimeSagaRow("saga_1")).getByRole("button", { name: "Open" }));
    const sagaMonitor = await waitFor(() => {
      const element = document.querySelector("[data-runtime-saga-monitor='saga_1']");
      expect(element).not.toBeNull();
      return element as HTMLElement;
    });
    fireEvent.change(within(sagaMonitor).getByLabelText("Step Name"), {
      target: { value: "Send receipt" }
    });
    fireEvent.change(within(sagaMonitor).getByLabelText("Action"), {
      target: { value: "email.send" }
    });
    fireEvent.change(within(sagaMonitor).getByLabelText("Target Agent"), {
      target: { value: "agent_1" }
    });
    fireEvent.click(within(sagaMonitor).getByRole("button", { name: "Add Step" }));
    await waitFor(() =>
      expect(calls.some((call) => call.path === "/api/v1/runtime/sagas/saga_1/steps")).toBe(true)
    );
    fireEvent.change(within(sagaMonitor).getByLabelText("Failure Actions"), {
      target: { value: "order.lookup, email.send" }
    });
    fireEvent.click(within(sagaMonitor).getByRole("button", { name: "Execute / Retry" }));
    await waitFor(() =>
      expect(calls.some((call) => call.path === "/api/v1/runtime/sagas/saga_1/execute" && Array.isArray(call.body?.failure_actions))).toBe(true)
    );
    fireEvent.change(within(sagaMonitor).getByLabelText("Cancel Reason"), {
      target: { value: "operator cancelled" }
    });
    fireEvent.click(within(sagaMonitor).getByRole("button", { name: "Cancel" }));
    await waitFor(() =>
      expect(calls.some((call) => call.path === "/api/v1/runtime/sagas/saga_1/cancel")).toBe(true)
    );

    const sandboxPanel = document.querySelector("[data-runtime-sandbox]") as HTMLElement;
    fireEvent.click(within(runtimeSandboxProfileRow("sbx_1")).getByRole("button", { name: "Open" }));
    fireEvent.change(within(sandboxPanel).getByLabelText("Name"), {
      target: { value: "Node Restricted" }
    });
    fireEvent.click(within(sandboxPanel).getByRole("button", { name: "Create" }));
    await waitFor(() =>
      expect(calls.some((call) => call.path === "/api/v1/runtime/sandbox-profiles" && call.method === "POST")).toBe(true)
    );
    fireEvent.change(within(sandboxPanel).getByLabelText("Sample Code"), {
      target: { value: "import os" }
    });
    fireEvent.click(within(sandboxPanel).getByRole("button", { name: "Test" }));
    await waitFor(() =>
      expect(calls.some((call) => call.path === "/api/v1/runtime/sandbox-profiles/sbx_1/test")).toBe(true)
    );
    expect(await within(sandboxPanel).findByText("Blocked import detected")).toBeInTheDocument();

    const killSwitchPanel = document.querySelector("[data-runtime-kill-switch]") as HTMLElement;
    fireEvent.change(within(killSwitchPanel).getByLabelText("Target ID"), {
      target: { value: "rtssn_1" }
    });
    fireEvent.change(within(killSwitchPanel).getByLabelText("Reason"), {
      target: { value: "operator stop" }
    });
    fireEvent.change(within(killSwitchPanel).getByLabelText("Confirmation"), {
      target: { value: "KILL session:rtssn_1" }
    });
    fireEvent.click(within(killSwitchPanel).getByRole("button", { name: "Trigger" }));
    await waitFor(() =>
      expect(calls.some((call) => call.path === "/api/v1/runtime/kill-switch" && call.method === "POST")).toBe(true)
    );
  });

  it("rejects invalid numeric runtime payload fields instead of using fallbacks", () => {
    expect(() =>
      runtimeRingRulePayloadFromForm(
        formWithValues({
          action_pattern: "refund.*",
          min_trust_score: "high",
          required_ring: "2"
        })
      )
    ).toThrow("Min Trust Score must be a valid integer.");

    expect(() =>
      runtimeSagaStepPayloadFromForm(
        formWithValues({
          action_name: "email.send",
          name: "Send receipt",
          retry_count: "1.5",
          step_order: "1",
          target_agent_id: "agent_1",
          timeout_seconds: "300"
        })
      )
    ).toThrow("Retry Count must be a valid integer.");

    expect(() =>
      runtimeSandboxProfilePayloadFromForm(
        formWithValues({
          memory_mb: "128",
          name: "Node Restricted",
          timeout_seconds: "soon"
        })
      )
    ).toThrow("Timeout Seconds must be a valid integer.");
  });

  it("requires exact kill-switch confirmation text", () => {
    expect(killSwitchConfirmationPhrase("session", "rtssn_1")).toBe("KILL session:rtssn_1");

    expect(() =>
      runtimeKillSwitchPayloadFromForm(
        formWithValues({
          confirmation: "CONFIRM",
          reason: "operator stop",
          scope: "target",
          target_id: "rtssn_1",
          target_type: "session"
        })
      )
    ).toThrow("Confirmation must exactly match KILL session:rtssn_1.");

    expect(
      runtimeKillSwitchPayloadFromForm(
        formWithValues({
          confirmation: "KILL session:rtssn_1",
          reason: "operator stop",
          scope: "target",
          target_id: "rtssn_1",
          target_type: "session"
        })
      )
    ).toMatchObject({
      confirmation: "KILL session:rtssn_1",
      target_id: "rtssn_1",
      target_type: "session"
    });
  });
});

interface RecordedCall {
  path: string;
  method: string;
  body: Record<string, unknown> | null;
}

function mockRuntimeFetch() {
  const calls: RecordedCall[] = [];
  vi.stubGlobal("fetch", async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const parsed = new URL(url, "http://test.local");
    const path = `${parsed.pathname}${parsed.search}`;
    const method = init?.method ?? "GET";
    const body = typeof init?.body === "string" ? (JSON.parse(init.body) as Record<string, unknown>) : null;
    calls.push({ path, method, body });

    if (path === "/api/v1/runtime/sessions" && method === "POST") {
      return json({ ...runtimeSession, id: "rtssn_2", agent_id: body?.agent_id ?? "agent_1" }, 201);
    }
    if (path === "/api/v1/runtime/sessions/rtssn_1/actions" && method === "POST") {
      return json({ ...runtimeAction, id: "rtact_2", action_name: body?.action_name ?? "runtime.action" }, 201);
    }
    if (path === "/api/v1/runtime/sessions/rtssn_1/end" && method === "POST") {
      return json({ ...runtimeSession, state: "archived", ended_at: "2026-05-01T03:00:00Z" });
    }
    if (path === "/api/v1/runtime/sessions/rtssn_1") {
      return json(runtimeSession);
    }
    if (path.startsWith("/api/v1/runtime/sessions")) {
      return json([runtimeSession]);
    }
    if (path === "/api/v1/runtime/ring-rules" && method === "POST") {
      return json({ ...ringRule, id: "rtrule_2", action_pattern: body?.action_pattern ?? "customer.delete" }, 201);
    }
    if (path.startsWith("/api/v1/runtime/ring-rules")) {
      return json([ringRule]);
    }
    if (path.startsWith("/api/v1/runtime/ring-decisions")) {
      return json([ringDecision]);
    }
    if (path === "/api/v1/runtime/sagas" && method === "POST") {
      return json({ ...saga, id: "saga_2", name: body?.name ?? "Claims Refund" }, 201);
    }
    if (path === "/api/v1/runtime/sagas/saga_1/steps" && method === "POST") {
      return json({ ...sagaStep, id: "sgstp_2", name: body?.name ?? "Send receipt" }, 201);
    }
    if (path === "/api/v1/runtime/sagas/saga_1/execute" && method === "POST") {
      return json({
        saga_id: "saga_1",
        runtime_session_id: "rtssn_1",
        status: "compensated",
        message: "Compensation completed",
        executed_step_ids: ["sgstp_1"],
        compensated_step_ids: ["sgstp_1"],
        failed_step_id: "sgstp_1",
        saga: { ...saga, status: "compensated" }
      });
    }
    if (path === "/api/v1/runtime/sagas/saga_1/cancel" && method === "POST") {
      return json({ ...saga, status: "cancelled" });
    }
    if (path === "/api/v1/runtime/sagas/saga_1") {
      return json(saga);
    }
    if (path.startsWith("/api/v1/runtime/sagas")) {
      return json([saga]);
    }
    if (path === "/api/v1/runtime/sandbox-profiles" && method === "POST") {
      return json({ ...sandboxProfile, id: "sbx_2", name: body?.name ?? "Node Restricted" }, 201);
    }
    if (path === "/api/v1/runtime/sandbox-profiles/sbx_1/test" && method === "POST") {
      return json(sandboxDecision);
    }
    if (path.startsWith("/api/v1/runtime/sandbox-profiles")) {
      return json([sandboxProfile]);
    }
    if (path === "/api/v1/runtime/kill-switch" && method === "POST") {
      return json({ ...killSwitchEvent, id: "kill_2", reason: body?.reason ?? "operator stop" }, 201);
    }
    if (path.startsWith("/api/v1/runtime/kill-switch/events")) {
      return json([killSwitchEvent]);
    }
    return json({});
  });
  return calls;
}

function json(value: unknown, status = 200) {
  return new Response(JSON.stringify(value), {
    status,
    headers: { "Content-Type": "application/json" }
  });
}

function runtimeSessionRow(sessionId: string) {
  const row = document.querySelector(`[data-runtime-session-row="${sessionId}"]`);
  expect(row).not.toBeNull();
  return row as HTMLElement;
}

function runtimeSagaRow(sagaId: string) {
  const row = document.querySelector(`[data-runtime-saga-row="${sagaId}"]`);
  expect(row).not.toBeNull();
  return row as HTMLElement;
}

function findRuntimeSagaRow(sagaId: string) {
  return waitFor(() => runtimeSagaRow(sagaId));
}

function runtimeSandboxProfileRow(profileId: string) {
  const row = document.querySelector(`[data-runtime-sandbox-profile-row="${profileId}"]`);
  expect(row).not.toBeNull();
  return row as HTMLElement;
}

function formWithValues(values: Record<string, string>) {
  const form = document.createElement("form");
  for (const [name, value] of Object.entries(values)) {
    const input = document.createElement("input");
    input.name = name;
    input.value = value;
    form.append(input);
  }
  return form;
}
