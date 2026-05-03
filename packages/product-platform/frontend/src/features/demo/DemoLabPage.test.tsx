import { fireEvent, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithQueryClient } from "../../test/test-utils";
import { DemoLabPage, demoResetPayloadFromValues } from "./DemoLabPage";

const scenarioSummary = {
  id: "demo_scenario_customer_support_refund",
  organization_id: "org_default",
  environment_id: "env_default",
  name: "Customer Support Refund Governance",
  slug: "customer-support-refund",
  description: "Governed refund demo.",
  value_proof: "Shows policy, runtime, and evidence.",
  status: "published",
  required_services: [
    {
      key: "product-api",
      label: "Product API",
      required: true,
      health_endpoint: "/health",
      evidence_route: "/overview"
    },
    {
      key: "sample-mcp-server",
      label: "Sample MCP server",
      required: true,
      health_endpoint: "/mcp/health",
      evidence_route: "/mcp"
    }
  ],
  created_at: "2026-05-01T00:00:00Z",
  updated_at: "2026-05-01T00:00:00Z"
};

const step = {
  id: "demo_step_refund_import_policies",
  scenario_id: "demo_scenario_customer_support_refund",
  step_order: 1,
  title: "Import refund policy pack",
  expected_result: "Refund limit and sensitive-tool policies are active.",
  action_type: "import_policies",
  action_config: {},
  proof_links: [
    {
      area: "Policies",
      label: "Policy library",
      route: "/policies?policy_slug=refund-limit",
      resource_hint: "refund-limit"
    }
  ],
  created_at: "2026-05-01T00:00:00Z",
  updated_at: "2026-05-01T00:00:00Z"
};

const scenarioDetail = {
  ...scenarioSummary,
  steps: [step]
};

const run = {
  id: "demo_run_1",
  organization_id: "org_default",
  environment_id: "env_default",
  scenario_id: "demo_scenario_customer_support_refund",
  status: "running",
  started_by: "user_admin",
  started_at: "2026-05-01T00:00:00Z",
  finished_at: null,
  summary: { completed_steps: 1, total_steps: 2 },
  created_at: "2026-05-01T00:00:00Z",
  updated_at: "2026-05-01T00:00:01Z",
  scenario: scenarioSummary,
  step_runs: [
    {
      id: "dsrun_1",
      demo_run_id: "demo_run_1",
      demo_step_id: "demo_step_refund_import_policies",
      status: "succeeded",
      result: { imported: 2 },
      started_at: "2026-05-01T00:00:00Z",
      finished_at: "2026-05-01T00:00:01Z",
      created_at: "2026-05-01T00:00:00Z",
      updated_at: "2026-05-01T00:00:01Z",
      step,
      actual_result: "Imported 2 active demo policies.",
      evidence_links: [
        {
          area: "Policies",
          label: "Policy library",
          route: "/policies?policy_slug=refund-limit&correlation_id=corr-demo",
          resource_id: "policy_refund",
          correlation_id: "corr-demo"
        }
      ],
      proof_checklist: [
        {
          area: "Policies",
          label: "Policy library",
          status: "completed",
          route: "/policies?policy_slug=refund-limit&correlation_id=corr-demo",
          expected_result: "Refund limit and sensitive-tool policies are active.",
          actual_result: "Imported 2 active demo policies."
        }
      ]
    }
  ]
};

const resetRun = {
  id: "demo_reset_1",
  organization_id: "org_default",
  environment_id: "env_default",
  status: "succeeded",
  requested_by: "user_admin",
  started_at: "2026-05-01T00:05:00Z",
  finished_at: "2026-05-01T00:05:01Z",
  summary: {
    cleared: {
      demo_runs: 1,
      demo_step_runs: 9,
      demo_lab_audit_events: 10
    },
    seeded: {
      policy_placeholders: 2,
      demo_scenarios: 1,
      demo_steps: 9
    }
  },
  created_at: "2026-05-01T00:05:00Z",
  updated_at: "2026-05-01T00:05:01Z"
};

const baselineStatus = {
  organization_id: "org_default",
  environment_id: "env_default",
  overall_status: "degraded",
  checked_at: "2026-05-01T00:00:00Z",
  checks: [
    {
      key: "policy-pack",
      label: "Seed policy pack",
      status: "healthy",
      required: true,
      detail: "Required demo policy placeholders are loaded.",
      count: 2,
      expected_count: 2,
      missing: []
    },
    {
      key: "mcp-server",
      label: "Sample MCP server",
      status: "degraded",
      required: true,
      detail: "Sample refund MCP server is missing.",
      count: 0,
      expected_count: 1,
      missing: ["mcp_demo_refund"]
    }
  ],
  missing_items: ["mcp_demo_refund"]
};

describe("DemoLabPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders scenarios, baseline prerequisites, reset history, and detail steps", async () => {
    mockDemoFetch();

    renderWithQueryClient(<DemoLabPage />);

    expect(await screen.findByRole("heading", { name: "Demo Lab" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Scenario Catalog" })).toBeInTheDocument();
    expect((await screen.findAllByText("Customer Support Refund Governance")).length).toBeGreaterThan(0);
    expect(await screen.findByText("Sample refund MCP server is missing.")).toBeInTheDocument();
    expect(await screen.findByText("Import refund policy pack")).toBeInTheDocument();
    expect((await screen.findAllByText("demo_reset_1")).length).toBeGreaterThan(0);
  });

  it("submits start, continue, cancel, and reset actions through typed API helpers", async () => {
    const requests = mockDemoFetch();

    renderWithQueryClient(<DemoLabPage />);
    await screen.findByText("Import refund policy pack");

    fireEvent.click(screen.getByRole("button", { name: /Start Scenario/ }));
    expect(await screen.findByText("Demo scenario started")).toBeInTheDocument();
    expect((await screen.findAllByText("Imported 2 active demo policies.")).length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    expect(await screen.findByText("Demo run advanced")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(await screen.findByText("Demo run canceled")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Confirmation"), { target: { value: "RESET" } });
    fireEvent.click(screen.getByRole("button", { name: /Reset Demo/ }));
    expect(await screen.findByText("Demo environment reset")).toBeInTheDocument();

    expect(requests.some((request) => request.url.endsWith("/runs") && request.method === "POST")).toBe(true);
    expect(requests.some((request) => request.url.endsWith("/continue"))).toBe(true);
    expect(requests.some((request) => request.url.endsWith("/cancel"))).toBe(true);
    expect(requests.some((request) => request.url.endsWith("/reset"))).toBe(true);
  });

  it("normalizes reset confirmation payloads", () => {
    expect(
      demoResetPayloadFromValues({
        confirmation: " RESET ",
        reason: " Demo refresh "
      })
    ).toEqual({
      confirmation: "RESET",
      reason: "Demo refresh"
    });

    expect(() => demoResetPayloadFromValues({ confirmation: "reset" })).toThrow(/Type RESET/);
  });
});

function mockDemoFetch() {
  const requests: Array<{ url: string; method: string; body?: unknown }> = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = input.toString();
      const path = new URL(url, "http://localhost").pathname;
      const method = init?.method ?? "GET";
      const body = init?.body ? JSON.parse(String(init.body)) : undefined;
      requests.push({ url: path, method, body });

      if (path === "/api/v1/demo/scenarios" && method === "GET") {
        return json([scenarioSummary]);
      }
      if (path === "/api/v1/demo/scenarios/demo_scenario_customer_support_refund" && method === "GET") {
        return json(scenarioDetail);
      }
      if (path === "/api/v1/demo/baseline-status" && method === "GET") {
        return json(baselineStatus);
      }
      if (path === "/api/v1/demo/reset-runs" && method === "GET") {
        return json([resetRun]);
      }
      if (path === "/api/v1/demo/reset-runs/demo_reset_1" && method === "GET") {
        return json(resetRun);
      }
      if (path === "/api/v1/demo/scenarios/demo_scenario_customer_support_refund/runs" && method === "POST") {
        return json(run, 201);
      }
      if (path === "/api/v1/demo/runs/demo_run_1" && method === "GET") {
        return json(run);
      }
      if (path === "/api/v1/demo/runs/demo_run_1/continue" && method === "POST") {
        return json({ ...run, summary: { completed_steps: 2, total_steps: 2 } });
      }
      if (path === "/api/v1/demo/runs/demo_run_1/cancel" && method === "POST") {
        return json({ ...run, status: "canceled" });
      }
      if (path === "/api/v1/demo/reset" && method === "POST") {
        return json(resetRun, 201);
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
