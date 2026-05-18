import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CurrentUserProvider } from "../../app/userContext";
import { TenantQueryScopeProvider } from "../../api/queryScope";
import type { UserPrincipal } from "../../api/types";
import { renderWithQueryClient } from "../../test/test-utils";
import {
  PoliciesPage,
  policyBindingCreatePayloadFromForm,
  policyBindingPromotePayloadFromForm,
  policyEvaluationMatchesFilters,
  upsertPolicyEvaluationFeed
} from "./PoliciesPage";

const policy = {
  id: "policy_1",
  organization_id: "org_default",
  name: "Runtime Guardrails",
  slug: "runtime-guardrails",
  description: "Blocks risky runtime actions.",
  scope: "runtime-action",
  owner_user_id: "user_admin",
  status: "active",
  tags: ["runtime", "safety"],
  active_version_id: "pver_2",
  active_version_number: 2,
  version_count: 2,
  versions: [
    {
      id: "pver_2",
      policy_id: "policy_1",
      version_number: 2,
      body_format: "yaml",
      body_text: "version: '1.0'\nname: runtime\nrules: []\n",
      backend: "native",
      checksum: "sha256:def",
      status: "active",
      created_by: "user_admin",
      created_at: "2026-05-01T00:01:00+00:00",
      activated_at: "2026-05-01T00:02:00+00:00"
    },
    {
      id: "pver_1",
      policy_id: "policy_1",
      version_number: 1,
      body_format: "yaml",
      body_text: "version: '1.0'\nname: runtime\nrules: []\n",
      backend: "native",
      checksum: "sha256:abc",
      status: "inactive",
      created_by: "user_admin",
      created_at: "2026-05-01T00:00:00+00:00",
      activated_at: "2026-05-01T00:00:30+00:00"
    }
  ]
};

const binding = {
  id: "pbind_1",
  policy_id: "policy_1",
  policy_version_id: "pver_2",
  target_type: "agent",
  target_id: "agent_1",
  mode: "shadow",
  rollout_percentage: 25,
  priority: 10,
  status: "active"
};

const evaluation = {
  id: "peval_1",
  organization_id: "org_default",
  environment_id: "env_default",
  policy_id: "policy_1",
  policy_version_id: "pver_2",
  binding_id: "pbind_1",
  binding_mode: "enforce",
  agent_id: "agent_1",
  target_type: "mcp-tool",
  target_id: "demo.delete_customer",
  action: "mcp.tool_call",
  resource_type: "mcp-tool",
  resource_id: "demo.delete_customer",
  context: { tool_name: "delete_customer" },
  decision: "deny",
  policy_action: "deny",
  matched_rule: "deny_delete_customer",
  reason: "Customer deletion requires approval.",
  latency_ms: 3.2,
  mode: "simulate",
  correlation_id: "corr-policy-eval",
  backend: "native",
  error: false,
  audit_preview: {},
  created_at: "2026-05-01T00:00:00+00:00"
};

const summary = {
  total_count: 4,
  decision_counts: { allow: 3, deny: 1 },
  mode_counts: { live: 2, simulate: 2 },
  action_counts: { "mcp.tool_call": 3, "runtime.action": 1 },
  time_buckets: [
    {
      bucket: "2026-05-01",
      total_count: 3,
      decision_counts: { allow: 2, deny: 1 }
    },
    {
      bucket: "2026-05-02",
      total_count: 1,
      decision_counts: { allow: 1, deny: 0 }
    }
  ]
};

const tenantContext = { organizationId: "org_default", environmentId: "env_default" };
const adminUser: UserPrincipal = {
  id: "user_admin",
  display_name: "Admin",
  email: "admin@example.com",
  organization_id: "org_default",
  roles: ["Platform Admin"]
};

const viewerUser: UserPrincipal = {
  ...adminUser,
  id: "user_viewer",
  display_name: "Viewer",
  email: "viewer@example.com",
  roles: ["Viewer"]
};

describe("PoliciesPage", () => {
  beforeEach(() => {
    window.history.replaceState(null, "", "/policies");
    vi.stubGlobal("EventSource", undefined);
    mockPolicyFetch();
  });

  it("renders library, versions, editor, bindings, simulator, and feed", async () => {
    renderPoliciesPage();

    expect((await screen.findAllByText("Runtime Guardrails")).length).toBeGreaterThan(0);
    expect(screen.getByText("Policy Library")).toBeInTheDocument();
    expect(screen.getByText("Version History")).toBeInTheDocument();
    expect(screen.getByText("Policy Editor")).toBeInTheDocument();
    expect(screen.getByText("Policy Bindings")).toBeInTheDocument();
    expect(screen.getByText("Policy Simulator")).toBeInTheDocument();
    expect(screen.getByText("Policy Decisions")).toBeInTheDocument();
    expect(screen.getByText("Decision Trend")).toBeInTheDocument();
    expect(screen.getByText("Action Distribution")).toBeInTheDocument();
    expect(screen.getAllByText("2026-05-02").length).toBeGreaterThan(0);
    expect(screen.getAllByText("mcp.tool_call").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Claims Agent").length).toBeGreaterThan(0);
    expect(screen.getByText("maintenance")).toBeInTheDocument();
    expect(screen.getByText("deny_delete_customer")).toBeInTheDocument();
    expect(screen.getByText("allow: 3, deny: 1")).toBeInTheDocument();
  });

  it("lints, disables fatal saves, simulates decisions, filters, and opens detail", async () => {
    const calls = mockPolicyFetch();
    renderPoliciesPage();

    expect((await screen.findAllByText("Runtime Guardrails")).length).toBeGreaterThan(0);
    fireEvent.click(within(policyRow("policy_1")).getByRole("button", { name: "Open" }));

    fireEvent.click(await screen.findByRole("button", { name: "Lint" }));
    expect(await screen.findByText("schema.unknown_operator")).toBeInTheDocument();
    expect(screen.getByText("line 7")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save Version" })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "Simulate" }));
    expect(await screen.findByText("Simulated denial.")).toBeInTheDocument();

    fireEvent.change(screen.getAllByLabelText("Decision").at(-1)!, { target: { value: "deny" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Filter" }).at(-1)!);
    await waitFor(() => expect(calls).toContain("/api/v1/policy-evaluations?decision=deny"));

    const evaluationRow = (await screen.findByText("corr-policy-eval")).closest("tr");
    expect(evaluationRow).toBeTruthy();
    fireEvent.click(within(evaluationRow as HTMLElement).getByRole("button", { name: "Open" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("corr-policy-eval")).toBeInTheDocument();
    expect(within(dialog).getByText("mcp-tool / demo.delete_customer")).toBeInTheDocument();
    expect(within(dialog).getByText(/"tool_name": "delete_customer"/)).toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole("button", { name: "Close policy evaluation detail" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("requires confirmation before archiving a policy version", async () => {
    const calls = mockPolicyFetch();
    renderPoliciesPage();

    expect((await screen.findAllByText("Runtime Guardrails")).length).toBeGreaterThan(0);
    fireEvent.click(within(policyRow("policy_1")).getByRole("button", { name: "Open" }));

    const versionRow = (await screen.findAllByText("v2"))
      .find((element) => element.closest("[data-policy-version-row='pver_2']"))
      ?.closest("tr");
    expect(versionRow).toBeTruthy();

    fireEvent.click(within(versionRow as HTMLElement).getByRole("button", { name: "Archive" }));
    expect(calls).not.toContain("/api/v1/policies/policy_1/versions/pver_2/archive");

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("Archive policy version?")).toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole("button", { name: "Archive" }));

    await waitFor(() =>
      expect(calls).toContain("/api/v1/policies/policy_1/versions/pver_2/archive")
    );
  });

  it("hides policy write controls for read-only users", async () => {
    renderPoliciesPage(viewerUser);

    expect((await screen.findAllByText("Runtime Guardrails")).length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Export" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Import" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Save Version" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Create Binding" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Simulate" })).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Archive" })).not.toBeInTheDocument();
  });

  it("keeps streamed evaluation rows deterministic", () => {
    const streamed = { ...evaluation, id: "peval_2", correlation_id: "corr-streamed" };

    expect(policyEvaluationMatchesFilters(streamed, { decision: "deny", mode: "simulate" })).toBe(
      true
    );
    expect(policyEvaluationMatchesFilters(streamed, { decision: "allow" })).toBe(false);
    expect(policyEvaluationMatchesFilters(streamed, { environment_id: "env_other" })).toBe(false);
    expect(upsertPolicyEvaluationFeed([evaluation], streamed).map((row) => row.id)).toEqual([
      "peval_2",
      "peval_1"
    ]);
    expect(
      upsertPolicyEvaluationFeed([evaluation, streamed], { ...streamed, reason: "Updated" }).map(
        (row) => row.id
      )
    ).toEqual(["peval_2", "peval_1"]);
  });

  it("rejects invalid policy binding numeric values", () => {
    expect(() =>
      policyBindingCreatePayloadFromForm(
        formWithValues({
          mode: "shadow",
          policy_id: "policy_1",
          priority: "first",
          rollout_percentage: "50",
          target_id: "agent_1",
          target_type: "agent"
        })
      )
    ).toThrow("Priority must be a valid integer.");

    expect(() =>
      policyBindingCreatePayloadFromForm(
        formWithValues({
          mode: "shadow",
          policy_id: "policy_1",
          priority: "1",
          rollout_percentage: "150",
          target_id: "agent_1",
          target_type: "agent"
        })
      )
    ).toThrow("Rollout must be at most 100.");

    expect(() =>
      policyBindingPromotePayloadFromForm(
        formWithValues({
          mode: "enforce",
          reason: "promote",
          rollout_percentage: "-1"
        }),
        binding
      )
    ).toThrow("Rollout must be at least 0.");
  });

  it("renders live evaluation rows emitted through the shared event stream", async () => {
    const calls = mockPolicyFetch();
    FakeEventSource.instances = [];
    vi.stubGlobal("EventSource", FakeEventSource);

    renderPoliciesPage();

    expect(await screen.findByText("corr-policy-eval")).toBeInTheDocument();
    expect(FakeEventSource.instances).toHaveLength(1);
    expect(FakeEventSource.instances[0].url).toBe(
      "/api/v1/policy-evaluations/stream?organization_id=org_default&environment_id=env_default"
    );

    act(() => {
      FakeEventSource.instances[0].emit("policy_evaluation", {
        ...evaluation,
        environment_id: "env_other",
        id: "peval_other_environment",
        correlation_id: "corr-other-environment"
      });
    });

    expect(screen.queryByText("corr-other-environment")).not.toBeInTheDocument();

    act(() => {
      FakeEventSource.instances[0].emit("policy_evaluation", {
        ...evaluation,
        id: "peval_live",
        mode: "live",
        correlation_id: "corr-live-policy",
        reason: "Live denial."
      });
    });

    expect(await screen.findByText("corr-live-policy")).toBeInTheDocument();
    await waitFor(() =>
      expect(
        calls.filter((path) => path.startsWith("/api/v1/policy-evaluations/summary")).length
      ).toBeGreaterThan(1)
    );
  });
});

function renderPoliciesPage(user = adminUser) {
  return renderWithQueryClient(
    <CurrentUserProvider user={user}>
      <TenantQueryScopeProvider context={tenantContext}>
        <PoliciesPage />
      </TenantQueryScopeProvider>
    </CurrentUserProvider>
  );
}

class FakeEventSource {
  static instances: FakeEventSource[] = [];

  readonly listeners = new Map<string, Set<(event: MessageEvent) => void>>();
  readonly url: string;
  closed = false;

  constructor(url: string) {
    this.url = url;
    FakeEventSource.instances.push(this);
  }

  addEventListener(eventName: string, listener: (event: MessageEvent) => void) {
    const listeners = this.listeners.get(eventName) ?? new Set();
    listeners.add(listener);
    this.listeners.set(eventName, listeners);
  }

  removeEventListener(eventName: string, listener: (event: MessageEvent) => void) {
    this.listeners.get(eventName)?.delete(listener);
  }

  close() {
    this.closed = true;
  }

  emit(eventName: string, payload: unknown) {
    const event = new MessageEvent(eventName, { data: JSON.stringify(payload) });
    for (const listener of this.listeners.get(eventName) ?? []) {
      listener(event);
    }
  }
}

function mockPolicyFetch() {
  const calls: string[] = [];
  vi.stubGlobal("fetch", async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const parsed = new URL(url, "http://test.local");
    const path = `${parsed.pathname}${parsed.search}`;
    calls.push(path);

    if (path.startsWith("/api/v1/policies?") || path === "/api/v1/policies") {
      return json([policy]);
    }
    if (path === "/api/v1/policies/policy_1") {
      return json(policy);
    }
    if (path === "/api/v1/policies/policy_1/affected-resources") {
      return json({
        policy_id: "policy_1",
        active_binding_count: 1,
        resources: [
          {
            target_type: "agent",
            target_id: "agent_1",
            label: "Claims Agent",
            status: "active",
            mode: "shadow",
            environment_id: "env_default"
          }
        ]
      });
    }
    if (path === "/api/v1/policy-bindings") {
      return json([binding]);
    }
    if (path === "/api/v1/policy-exceptions") {
      return json([
        {
          id: "pex_1",
          binding_id: "pbind_1",
          target_type: "agent",
          target_id: "agent_1",
          reason: "maintenance",
          expires_at: "2026-05-02T00:00:00+00:00"
        }
      ]);
    }
    if (path === "/api/v1/agents") {
      return json([{ id: "agent_1", name: "Claims Agent", status: "active" }]);
    }
    if (path === "/api/v1/environments") {
      return json([{ id: "env_default", organization_id: "org_default", name: "Development" }]);
    }
    if (path.startsWith("/api/v1/policy-evaluations/summary")) {
      return json(summary);
    }
    if (path === "/api/v1/policy-evaluations/peval_1") {
      return json(evaluation);
    }
    if (path.startsWith("/api/v1/policy-evaluations")) {
      if (init?.method === "POST" && path === "/api/v1/policy-evaluations/simulate") {
        return json({
          ...evaluation,
          id: "peval_sim",
          reason: "Simulated denial."
        });
      }
      return json([evaluation]);
    }
    if (path === "/api/v1/policies/lint" && init?.method === "POST") {
      return json({
        passed: false,
        error_count: 1,
        warning_count: 0,
        issues: [
          {
            severity: "error",
            code: "schema.unknown_operator",
            message: "Rule block: unknown operator around",
            path: "$.rules[0].condition.operator",
            line: 7,
            fatal: true
          }
        ]
      });
    }
    if (path === "/api/v1/policies/policy_1/versions/draft" && init?.method === "POST") {
      return json({ ...policy.versions[0], id: "pver_3", version_number: 3, status: "draft" });
    }
    if (path === "/api/v1/policies/policy_1/versions/pver_3/lint" && init?.method === "POST") {
      return json({ passed: true, error_count: 0, warning_count: 0, issues: [] });
    }
    if (path === "/api/v1/policies/policy_1/versions/pver_2/archive" && init?.method === "POST") {
      return json({ ...policy.versions[0], status: "archived" });
    }
    return json({});
  });
  return calls;
}

function json(body: unknown, status = 200) {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      headers: { "Content-Type": "application/json" },
      status
    })
  );
}

function policyRow(policyId: string) {
  const row = document.querySelector(`[data-policy-row="${policyId}"]`);
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
