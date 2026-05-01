import assert from "node:assert/strict";
import test from "node:test";

import { createApiClient } from "../src/apiClient.js";
import {
  backendHint,
  policyEditorPayloadFromValues,
  renderPolicyAffectedResourcesPanel,
  renderPolicyEditor,
  renderPolicyLintPanel
} from "../src/policies.js";

const policy = {
  id: "policy_1",
  name: "Runtime Guardrails",
  description: "Blocks risky runtime actions.",
  scope: "runtime-action",
  status: "active",
  tags: ["runtime"],
  versions: [
    {
      id: "pver_1",
      version_number: 1,
      body_format: "yaml",
      body_text: "version: '1.0'\nname: runtime\nrules: []\n",
      backend: "native",
      status: "active"
    }
  ]
};

const lintError = {
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
};

test("component lint errors render", () => {
  const html = renderPolicyLintPanel(lintError);

  assert.match(html, /data-policy-lint-panel/);
  assert.match(html, /schema.unknown_operator/);
  assert.match(html, /line 7/);
  assert.match(html, /unknown operator/);
});

test("component save button disabled when fatal validation errors exist", () => {
  const html = renderPolicyEditor(policy, { lintResult: lintError });

  assert.match(html, /data-policy-save-version disabled/);
});

test("component backend selector changes editor hints", () => {
  const opaHtml = renderPolicyEditor(policy, { backend: "opa" });
  const cedarHtml = renderPolicyEditor(policy, { backend: "cedar" });

  assert.match(opaHtml, /OPA\/Rego backend selected/);
  assert.match(cedarHtml, /Cedar authorization backend selected/);
  assert.equal(backendHint("native"), "Native YAML/JSON evaluator selected.");
});

test("component affected resources list renders", () => {
  const html = renderPolicyAffectedResourcesPanel({
    policy_id: "policy_1",
    active_binding_count: 0,
    resources: [
      {
        target_type: "agent",
        target_id: "agent_1",
        label: "Claims Agent",
        status: "active",
        mode: "policy_binding",
        environment_id: "env_default"
      }
    ]
  });

  assert.match(html, /data-policy-affected-resources/);
  assert.match(html, /Claims Agent/);
  assert.match(html, /policy_binding/);
});

test("component active binding warning renders", () => {
  const html = renderPolicyAffectedResourcesPanel({
    policy_id: "policy_1",
    active_binding_count: 2,
    resources: []
  });

  assert.match(html, /data-policy-active-binding-warning/);
  assert.match(html, /2 active bindings/);
});

test("editor payload keeps body format, backend, and body", () => {
  assert.deepEqual(
    policyEditorPayloadFromValues({
      body_format: "rego",
      backend: "opa",
      body_text: "package agentos\nallow := true"
    }),
    {
      body_format: "rego",
      backend: "opa",
      body_text: "package agentos\nallow := true"
    }
  );
});

test("api client editor methods call expected endpoints", async () => {
  const calls = [];
  const client = createApiClient({
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

  await client.lintPolicy({ body_text: "rules: []", body_format: "yaml" });
  await client.savePolicyDraftVersion("policy_1", { body_text: "rules: []" });
  await client.lintPolicyVersion("policy_1", "pver_1");
  await client.listPolicyLintResults("policy_1", "pver_1");
  await client.getPolicyAffectedResources("policy_1");

  assert.deepEqual(calls, [
    ["/api/v1/policies/lint", "POST", { body_text: "rules: []", body_format: "yaml" }],
    ["/api/v1/policies/policy_1/versions/draft", "POST", { body_text: "rules: []" }],
    ["/api/v1/policies/policy_1/versions/pver_1/lint", "POST", null],
    ["/api/v1/policies/policy_1/versions/pver_1/lint-results", "GET", null],
    ["/api/v1/policies/policy_1/affected-resources", "GET", null]
  ]);
});
