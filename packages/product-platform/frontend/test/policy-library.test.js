import assert from "node:assert/strict";
import test from "node:test";

import { createApiClient } from "../src/apiClient.js";
import {
  policyFilterParamsFromValues,
  policyImportPayloadFromValues,
  renderPoliciesPage,
  renderPolicyTable,
  renderPolicyVersionDrawer
} from "../src/policies.js";

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
  created_at: "2026-05-01T00:00:00+00:00",
  updated_at: "2026-05-01T00:00:00+00:00",
  active_version_id: "pver_2",
  active_version_number: 2,
  version_count: 2
};

const versions = [
  {
    id: "pver_2",
    policy_id: "policy_1",
    version_number: 2,
    body_format: "yaml",
    body_text: "version: '1.0'",
    backend: "native",
    checksum: "sha256:def",
    status: "active",
    created_by: "user_admin",
    created_at: "2026-05-01T00:01:00+00:00",
    activated_at: "2026-05-01T00:02:00+00:00",
    archived_at: null
  },
  {
    id: "pver_1",
    policy_id: "policy_1",
    version_number: 1,
    body_format: "yaml",
    body_text: "version: '1.0'",
    backend: "native",
    checksum: "sha256:abc",
    status: "inactive",
    created_by: "user_admin",
    created_at: "2026-05-01T00:00:00+00:00",
    activated_at: "2026-05-01T00:00:30+00:00",
    archived_at: null
  }
];

test("component policy table renders policy rows", () => {
  const html = renderPolicyTable([policy]);

  assert.match(html, /data-policy-table/);
  assert.match(html, /data-policy-row="policy_1"/);
  assert.match(html, /Runtime Guardrails/);
  assert.match(html, /runtime-action/);
  assert.match(html, /v2/);
});

test("component import dialog submits body payload", () => {
  const payload = policyImportPayloadFromValues({
    name: "Inline Policy",
    body_format: "yaml",
    body_text: "version: '1.0'\nname: inline\nrules: []\n",
    source_path: "",
    scope: "agent",
    backend: "native",
    tags: "safety, runtime"
  });

  assert.deepEqual(payload, {
    name: "Inline Policy",
    body_format: "yaml",
    body_text: "version: '1.0'\nname: inline\nrules: []\n",
    scope: "agent",
    backend: "native",
    tags: ["safety", "runtime"]
  });
});

test("component version drawer shows active version", () => {
  const html = renderPolicyVersionDrawer(policy, versions);

  assert.match(html, /data-policy-version-drawer="policy_1"/);
  assert.match(html, /v2/);
  assert.match(html, /active/);
  assert.match(html, /data-policy-rollback="policy_1:pver_1"/);
});

test("component policies page renders library, versions, and import form", () => {
  const html = renderPoliciesPage({ policies: [policy], selectedPolicy: { ...policy, versions } });

  assert.match(html, /data-policy-workspace/);
  assert.match(html, /data-policy-library/);
  assert.match(html, /data-policy-version-table/);
  assert.match(html, /data-policy-import-form/);
});

test("policy filter params omit empty values", () => {
  assert.deepEqual(
    policyFilterParamsFromValues({
      scope: "agent",
      status: "",
      backend: "native",
      owner_user_id: "",
      tag: "safety"
    }),
    { scope: "agent", backend: "native", tag: "safety" }
  );
});

test("api client policy methods call expected endpoints", async () => {
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

  await client.listPolicies({ scope: "agent" });
  await client.getPolicy("policy_1");
  await client.importPolicy({ body_text: "version: '1.0'", body_format: "yaml" });
  await client.createPolicyVersion("policy_1", { body_text: "rules: []" });
  await client.activatePolicyVersion("policy_1", "pver_1");
  await client.rollbackPolicyVersion("policy_1", "pver_1");
  await client.archivePolicyVersion("policy_1", "pver_1");
  await client.exportPolicy("policy_1", "pver_1");

  assert.deepEqual(calls, [
    ["/api/v1/policies?scope=agent", "GET", null],
    ["/api/v1/policies/policy_1", "GET", null],
    ["/api/v1/policies/import", "POST", { body_text: "version: '1.0'", body_format: "yaml" }],
    ["/api/v1/policies/policy_1/versions", "POST", { body_text: "rules: []" }],
    ["/api/v1/policies/policy_1/versions/pver_1/activate", "POST", null],
    ["/api/v1/policies/policy_1/versions/pver_1/rollback", "POST", null],
    ["/api/v1/policies/policy_1/versions/pver_1/archive", "POST", null],
    ["/api/v1/policies/policy_1/export?version_id=pver_1", "GET", null]
  ]);
});
