import assert from "node:assert/strict";
import test from "node:test";

import { createApiClient } from "../src/apiClient.js";
import {
  policyEvaluationMatchesFilters,
  policyEvaluationFilterParamsFromValues,
  policyEvaluationPayloadFromValues,
  renderPoliciesPage,
  renderPolicyEvaluationFeed,
  renderPolicyEvaluationResult,
  renderPolicyEvaluationSummary,
  renderPolicySimulatorPanel,
  upsertPolicyEvaluationFeed
} from "../src/policies.js";

const policy = {
  id: "policy_1",
  name: "MCP Guard",
  slug: "mcp-guard",
  description: "Blocks risky tools.",
  scope: "mcp-tool",
  owner_user_id: "user_admin",
  status: "active",
  tags: ["mcp"],
  active_version_id: "pver_1",
  active_version_number: 1,
  version_count: 1,
  versions: [
    {
      id: "pver_1",
      version_number: 1,
      body_format: "yaml",
      body_text: "version: '1.0'",
      backend: "native",
      checksum: "sha256:abc",
      status: "active"
    }
  ]
};

const deniedEvaluation = {
  id: "peval_1",
  organization_id: "org_default",
  environment_id: "env_default",
  policy_id: "policy_1",
  policy_version_id: "pver_1",
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

const evaluationSummary = {
  total_count: 3,
  decision_counts: { allow: 2, deny: 1 },
  mode_counts: { live: 1, simulate: 2 },
  action_counts: { "mcp.tool_call": 2, "runtime.action": 1 },
  time_buckets: [
    {
      bucket: "2026-05-01",
      total_count: 3,
      decision_counts: { allow: 2, deny: 1 }
    }
  ]
};

test("component simulator renders form and blocks invalid context JSON in payload helper", () => {
  const html = renderPolicySimulatorPanel({ policies: [policy], selectedPolicy: policy });

  assert.match(html, /data-policy-simulator-form/);
  assert.match(html, /data-policy-simulator-context/);
  assert.throws(
    () =>
      policyEvaluationPayloadFromValues({
        policy_id: "policy_1",
        action: "mcp.tool_call",
        context_json: "{"
      }),
    /JSON/
  );
});

test("component deny result renders matched rule and reason", () => {
  const html = renderPolicyEvaluationResult(deniedEvaluation);

  assert.match(html, /data-policy-simulator-result="peval_1"/);
  assert.match(html, /deny_delete_customer/);
  assert.match(html, /Customer deletion requires approval/);
});

test("component feed renders filters, rows, and detail", () => {
  const html = renderPolicyEvaluationFeed({
    evaluations: [deniedEvaluation],
    summary: evaluationSummary,
    filters: { decision: "deny", mode: "simulate" },
    selectedEvaluation: deniedEvaluation
  });

  assert.match(html, /data-policy-evaluation-filter/);
  assert.match(html, /data-policy-evaluation-summary/);
  assert.match(html, /data-policy-evaluation-row="peval_1"/);
  assert.match(html, /data-policy-evaluation-detail="peval_1"/);
  assert.match(html, /corr-policy-eval/);
});

test("component summary renders decision counts and trend buckets", () => {
  const html = renderPolicyEvaluationSummary(evaluationSummary);

  assert.match(html, /data-policy-evaluation-summary/);
  assert.match(html, /data-policy-evaluation-trend="2026-05-01"/);
  assert.match(html, /allow: 2/);
  assert.match(html, /deny: 1/);
});

test("component policy page includes simulator and evaluation feed", () => {
  const html = renderPoliciesPage({
    policies: [policy],
    selectedPolicy: policy,
    policyEvaluations: [deniedEvaluation],
    policyEvaluationSummary: evaluationSummary,
    policyEvaluationResult: deniedEvaluation
  });

  assert.match(html, /data-policy-simulator/);
  assert.match(html, /data-policy-evaluation-feed/);
  assert.match(html, /data-policy-evaluation-summary/);
  assert.match(html, /data-policy-evaluation-table/);
});

test("payload helpers normalize evaluation request and filters", () => {
  assert.deepEqual(
    policyEvaluationPayloadFromValues({
      policy_id: "policy_1",
      policy_version_id: "",
      target_type: "",
      target_id: "",
      agent_id: "agent_1",
      action: "mcp.tool_call",
      resource_type: "mcp-tool",
      resource_id: "demo.delete_customer",
      context_json: '{"tool_name":"delete_customer"}'
    }),
    {
      policy_id: "policy_1",
      agent_id: "agent_1",
      action: "mcp.tool_call",
      resource_type: "mcp-tool",
      resource_id: "demo.delete_customer",
      context: { tool_name: "delete_customer" }
    }
  );
  assert.deepEqual(
    policyEvaluationFilterParamsFromValues({
      decision: "deny",
      mode: "simulate",
      agent_id: "",
      action: "mcp.tool_call",
      policy_id: "",
      correlation_id: "corr-1"
    }),
    { decision: "deny", mode: "simulate", action: "mcp.tool_call", correlation_id: "corr-1" }
  );
});

test("stream helpers match active filters and upsert new feed rows", () => {
  const streamedEvaluation = {
    ...deniedEvaluation,
    id: "peval_2",
    correlation_id: "corr-streamed"
  };

  assert.equal(
    policyEvaluationMatchesFilters(streamedEvaluation, { decision: "deny", mode: "simulate" }),
    true
  );
  assert.equal(
    policyEvaluationMatchesFilters(streamedEvaluation, { decision: "allow" }),
    false
  );
  assert.deepEqual(
    upsertPolicyEvaluationFeed([deniedEvaluation], streamedEvaluation).map((row) => row.id),
    ["peval_2", "peval_1"]
  );
  assert.deepEqual(
    upsertPolicyEvaluationFeed([deniedEvaluation, streamedEvaluation], {
      ...streamedEvaluation,
      reason: "Updated reason"
    }).map((row) => row.id),
    ["peval_2", "peval_1"]
  );
});

test("api client policy evaluation methods call expected endpoints", async () => {
  const calls = [];
  const client = createApiClient({
    getTenantContext: () => ({ organizationId: "org_default", environmentId: "env_default" }),
    fetchImpl: async (url, init = {}) => {
      calls.push([url, init.method ?? "GET", init.body ? JSON.parse(init.body) : null]);
      return {
        ok: true,
        status: 200,
        headers: new Map([["content-type", "application/json"]]),
        json: async () => ({ id: "ok" })
      };
    }
  });

  await client.simulatePolicyEvaluation({ action: "mcp.tool_call" });
  await client.evaluatePolicy({ action: "mcp.tool_call" });
  await client.listPolicyEvaluations({ decision: "deny", mode: "simulate", agent_id: "agent_1" });
  await client.getPolicyEvaluationSummary({ decision: "deny" });
  await client.getPolicyEvaluation("peval_1");
  const streamUrl = client.policyEvaluationStreamUrl({ decision: "deny" });

  assert.deepEqual(calls, [
    ["/api/v1/policy-evaluations/simulate", "POST", { action: "mcp.tool_call" }],
    ["/api/v1/policy-evaluations/evaluate", "POST", { action: "mcp.tool_call" }],
    ["/api/v1/policy-evaluations?decision=deny&mode=simulate&agent_id=agent_1", "GET", null],
    ["/api/v1/policy-evaluations/summary?decision=deny", "GET", null],
    ["/api/v1/policy-evaluations/peval_1", "GET", null]
  ]);
  assert.equal(streamUrl, "/api/v1/policy-evaluations/stream?decision=deny&environment_id=env_default");
});
