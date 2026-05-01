import assert from "node:assert/strict";
import test from "node:test";

import { createApiClient } from "../src/apiClient.js";
import {
  policyBindingPayloadFromValues,
  policyExceptionPayloadFromValues,
  policyPromotePayloadFromValues,
  renderPolicyBindingsPanel
} from "../src/policies.js";

const policy = {
  id: "policy_1",
  name: "Runtime Guardrails",
  active_version_id: "pver_1",
  versions: [
    {
      id: "pver_1",
      version_number: 1,
      status: "active"
    }
  ]
};

const binding = {
  id: "pbind_1",
  policy_id: "policy_1",
  policy_version_id: "pver_1",
  target_type: "agent",
  target_id: "agent_1",
  mode: "shadow",
  rollout_percentage: 25,
  priority: 10,
  status: "active"
};

const exception = {
  id: "pex_1",
  binding_id: "pbind_1",
  target_type: "agent",
  target_id: "agent_1",
  reason: "maintenance",
  expires_at: "2026-05-02T00:00:00+00:00"
};

test("component binding table renders target labels", () => {
  const html = renderPolicyBindingsPanel({
    bindings: [binding],
    exceptions: [exception],
    policies: [policy],
    selectedPolicy: policy,
    agents: [{ id: "agent_1", name: "Claims Agent" }],
    environments: [{ id: "env_default", name: "Development" }]
  });

  assert.match(html, /data-policy-binding-matrix/);
  assert.match(html, /data-policy-binding-row="pbind_1"/);
  assert.match(html, /Claims Agent/);
  assert.match(html, /Runtime Guardrails/);
  assert.match(html, /maintenance/);
});

test("component create wizard validates target selection", () => {
  const html = renderPolicyBindingsPanel({ policies: [policy], selectedPolicy: policy });

  assert.match(html, /data-policy-binding-create-form/);
  assert.match(html, /name="policy_id" required/);
  assert.match(html, /name="target_type" required/);
  assert.match(html, /name="target_id" list="policy-binding-target-options" required/);
});

test("component promote controls require reason", () => {
  const html = renderPolicyBindingsPanel({
    bindings: [binding],
    policies: [policy],
    selectedPolicy: policy
  });

  assert.match(html, /data-policy-binding-promote-form/);
  assert.match(html, /name="reason" required/);
});

test("policy binding payloads normalize numeric and optional values", () => {
  assert.deepEqual(
    policyBindingPayloadFromValues({
      policy_id: "policy_1",
      policy_version_id: "",
      target_type: "agent",
      target_id: "agent_1",
      mode: "shadow",
      rollout_percentage: "25",
      priority: "10"
    }),
    {
      policy_id: "policy_1",
      target_type: "agent",
      target_id: "agent_1",
      mode: "shadow",
      rollout_percentage: 25,
      priority: 10
    }
  );
  assert.deepEqual(policyPromotePayloadFromValues({ mode: "enforce", rollout_percentage: "100", reason: "approved" }), {
    mode: "enforce",
    rollout_percentage: 100,
    reason: "approved"
  });
  assert.deepEqual(
    policyExceptionPayloadFromValues({
      reason: "maintenance",
      expires_at: "2026-05-02T00:00",
      no_expiry_approved: "on"
    }),
    {
      reason: "maintenance",
      expires_at: "2026-05-02T00:00:00+00:00",
      no_expiry_approved: true
    }
  );
});

test("api client policy binding methods call expected endpoints", async () => {
  const calls = [];
  const client = createApiClient({
    fetchImpl: async (url, init = {}) => {
      calls.push([url, init.method ?? "GET", init.body ? JSON.parse(init.body) : null]);
      return {
        ok: true,
        status: init.method === "DELETE" ? 204 : 200,
        headers: new Map([["content-type", "application/json"]]),
        json: async () => ({ id: "ok" }),
        text: async () => ""
      };
    }
  });

  await client.listPolicyBindings({ policy_id: "policy_1", status: "active" });
  await client.createPolicyBinding({ policy_id: "policy_1", target_type: "agent" });
  await client.patchPolicyBinding("pbind_1", { mode: "audit-only" });
  await client.promotePolicyBinding("pbind_1", { mode: "enforce", reason: "approved" });
  await client.createPolicyException("pbind_1", { reason: "maintenance", expires_at: "2026-05-02T00:00:00+00:00" });
  await client.listPolicyExceptions({ binding_id: "pbind_1" });
  await client.deletePolicyBinding("pbind_1");

  assert.deepEqual(calls, [
    ["/api/v1/policy-bindings?policy_id=policy_1&status=active", "GET", null],
    ["/api/v1/policy-bindings", "POST", { policy_id: "policy_1", target_type: "agent" }],
    ["/api/v1/policy-bindings/pbind_1", "PATCH", { mode: "audit-only" }],
    ["/api/v1/policy-bindings/pbind_1/promote", "POST", { mode: "enforce", reason: "approved" }],
    [
      "/api/v1/policy-bindings/pbind_1/exceptions",
      "POST",
      { reason: "maintenance", expires_at: "2026-05-02T00:00:00+00:00" }
    ],
    ["/api/v1/policy-exceptions?binding_id=pbind_1", "GET", null],
    ["/api/v1/policy-bindings/pbind_1", "DELETE", null]
  ]);
});
