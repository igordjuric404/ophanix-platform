import assert from "node:assert/strict";
import test from "node:test";

import { createApiClient } from "../src/apiClient.js";
import {
  demoResetPayloadFromForm,
  renderDemoLabPage,
  renderDemoPrerequisites,
  renderDemoProofChecklist,
  renderDemoResetPanel,
  renderDemoResetResult,
  renderDemoRunTimeline,
  renderDemoScenarioCatalog
} from "../src/demo.js";

const scenario = {
  id: "demo_scenario_customer_support_refund",
  name: "Customer Support Refund Governance",
  slug: "customer-support-refund",
  description: "Governed refund demo.",
  value_proof: "Shows policy, runtime, and evidence.",
  status: "published",
  required_services: [
    { key: "product-api", label: "Product API", required: true },
    { key: "sample-mcp-server", label: "Sample MCP server", required: true }
  ],
  steps: [
    {
      id: "demo_step_refund_import_policies",
      step_order: 1,
      title: "Import refund policy pack",
      action_type: "import_policies",
      expected_result: "Refund limit and sensitive-tool policies are active."
    }
  ]
};

const stepRuns = [
  {
    id: "dsrun_1",
    demo_step_id: "demo_step_refund_import_policies",
    status: "succeeded",
    step: {
      title: "Import refund policy pack"
    },
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
  },
  {
    id: "dsrun_2",
    demo_step_id: "demo_step_refund_saga",
    status: "pending",
    step: {
      title: "Execute refund saga"
    },
    proof_checklist: [
      {
        area: "Runtime",
        label: "Saga monitor",
        status: "pending",
        route: "/runtime",
        expected_result: "The refund saga completes with compensating steps available.",
        actual_result: null
      }
    ]
  }
];

const run = {
  id: "demo_run_1",
  status: "running",
  started_at: "2026-05-01T00:00:00Z",
  summary: { completed_steps: 1, total_steps: 2 },
  step_runs: stepRuns
};

const degradedBaseline = {
  overall_status: "degraded",
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

const resetRun = {
  id: "demo_reset_1",
  status: "succeeded",
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
  }
};

test("component catalog renders scenario", () => {
  const html = renderDemoScenarioCatalog({ scenarios: [scenario], selectedScenario: scenario });

  assert.match(html, /data-demo-scenario-catalog/);
  assert.match(html, /data-demo-scenario-row="demo_scenario_customer_support_refund"/);
  assert.match(html, /Customer Support Refund Governance/);
});

test("demo lab route renders catalog detail timeline and proof", () => {
  const html = renderDemoLabPage({
    demoScenarios: [scenario],
    selectedDemoScenario: scenario,
    selectedDemoRun: run,
    demoBaselineStatus: degradedBaseline,
    demoResetRuns: [resetRun]
  });

  assert.match(html, /data-route-page="\/demo-lab"/);
  assert.match(html, /data-demo-prerequisites-panel/);
  assert.match(html, /data-demo-reset-panel/);
  assert.match(html, /data-demo-run-start="demo_scenario_customer_support_refund"/);
  assert.match(html, /data-demo-run-timeline="demo_run_1"/);
  assert.match(html, /data-demo-proof-checklist/);
});

test("component reset requires typed confirmation", () => {
  const html = renderDemoResetPanel({ resetRuns: [] });

  assert.match(html, /data-demo-reset-form/);
  assert.match(html, /data-demo-reset-confirmation/);
  assert.match(html, /pattern="RESET"/);
  assert.throws(
    () => demoResetPayloadFromForm(fakeResetForm("reset")),
    /Type RESET/
  );
  assert.deepEqual(demoResetPayloadFromForm(fakeResetForm("RESET")), { confirmation: "RESET" });
});

test("component reset progress renders", () => {
  const html = renderDemoResetResult({
    resetRun: {
      ...resetRun,
      status: "running",
      finished_at: null,
      summary: { status: "running" }
    }
  });

  assert.match(html, /data-demo-reset-progress="running"/);
  assert.match(html, /running/);
});

test("component reset result summary shows cleared and seeded counts", () => {
  const html = renderDemoResetResult({ resetRun });

  assert.match(html, /data-demo-reset-result="demo_reset_1"/);
  assert.match(html, /data-demo-reset-summary-row="cleared-demo-runs"/);
  assert.match(html, /<td>9<\/td>/);
  assert.match(html, /<td>2<\/td>/);
  assert.match(html, /data-demo-reset-catalog-link/);
  assert.match(html, /href="#scenario-catalog"/);
});

test("component prerequisites show degraded baseline status", () => {
  const html = renderDemoPrerequisites({ baselineStatus: degradedBaseline });

  assert.match(html, /data-demo-prerequisites-panel/);
  assert.match(html, /data-demo-baseline-overall="degraded"/);
  assert.match(html, /data-demo-baseline-check="mcp-server"/);
  assert.match(html, /data-demo-baseline-status="degraded"/);
  assert.match(html, /mcp_demo_refund/);
});

test("component run timeline updates step status", () => {
  const html = renderDemoRunTimeline({ run });

  assert.match(html, /data-demo-step-run-status="succeeded"/);
  assert.match(html, /data-demo-step-run-status="pending"/);
  assert.match(html, /Imported 2 active demo policies\./);
  assert.match(html, /data-demo-run-continue="demo_run_1"/);
  assert.match(html, /data-demo-run-cancel="demo_run_1"/);
});

test("component proof checklist marks completed steps", () => {
  const html = renderDemoProofChecklist({ stepRuns });

  assert.match(html, /data-demo-proof-checklist/);
  assert.match(html, /data-demo-proof-item="completed"/);
  assert.match(html, /Import refund policy pack/);
  assert.match(html, /Imported 2 active demo policies\./);
  assert.match(html, /href="\/policies\?policy_slug=refund-limit&amp;correlation_id=corr-demo"/);
  assert.match(html, /data-demo-proof-item="pending"/);
});

test("component proof checklist renders empty state", () => {
  const html = renderDemoProofChecklist({ stepRuns: [] });

  assert.match(html, /data-demo-proof-checklist/);
  assert.match(html, /No proof yet/);
});

test("api client cancels demo run with expected path", async () => {
  const calls = [];
  const api = createApiClient({
    baseUrl: "/api/v1",
    fetchImpl: async (url, options = {}) => {
      calls.push({ url, method: options.method ?? "GET" });
      return {
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => ({ id: "demo_run_1", status: "canceled" })
      };
    }
  });

  await api.cancelDemoRun("demo_run_1");

  assert.deepEqual(calls, [{ url: "/api/v1/demo/runs/demo_run_1/cancel", method: "POST" }]);
});

test("api client loads demo baseline with expected path", async () => {
  const calls = [];
  const api = createApiClient({
    baseUrl: "/api/v1",
    fetchImpl: async (url, options = {}) => {
      calls.push({ url, method: options.method ?? "GET" });
      return {
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => degradedBaseline
      };
    }
  });

  await api.getDemoBaselineStatus();

  assert.deepEqual(calls, [{ url: "/api/v1/demo/baseline-status", method: "GET" }]);
});

test("api client resets demo environment with expected path", async () => {
  const calls = [];
  const api = createApiClient({
    baseUrl: "/api/v1",
    fetchImpl: async (url, options = {}) => {
      calls.push({ url, method: options.method ?? "GET", body: options.body });
      return {
        ok: true,
        status: 201,
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => resetRun
      };
    }
  });

  await api.resetDemoEnvironment({ confirmation: "RESET" });

  assert.deepEqual(calls, [
    { url: "/api/v1/demo/reset", method: "POST", body: "{\"confirmation\":\"RESET\"}" }
  ]);
});

function fakeResetForm(value) {
  return {
    elements: {
      namedItem: (name) => (name === "confirmation" ? { value } : null)
    }
  };
}
