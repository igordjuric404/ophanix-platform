import assert from "node:assert/strict";
import test from "node:test";

import { createApiClient } from "../src/apiClient.js";
import { renderShell } from "../src/render.js";
import { createInitialAppState } from "../src/state.js";
import {
  artifactAttestationPayloadFromValues,
  artifactUploadPayloadFromValues,
  renderWorkflowArtifactDetail,
  renderWorkflowRunDetail,
  renderWorkflowsPage,
  workflowRunPayloadFromValues
} from "../src/workflows.js";

const workflow = {
  id: "policy_lint",
  organization_id: "org_default",
  name: "Policy Lint",
  workflow_type: "policy",
  command_ref: "python:policy.lint",
  input_schema: {
    type: "object",
    required: ["policy_body"],
    properties: {
      policy_body: { type: "string", title: "Policy Body" },
      policy_format: { type: "string", title: "Policy Format", default: "yaml" }
    }
  },
  enabled: true,
  created_at: "2026-05-01T00:00:00+00:00",
  updated_at: "2026-05-01T00:00:00+00:00"
};

const run = {
  id: "wrun_1",
  organization_id: "org_default",
  environment_id: "env_default",
  workflow_definition_id: "policy_lint",
  workflow_type: "policy",
  command_ref: "python:policy.lint",
  status: "succeeded",
  inputs: { policy_format: "yaml" },
  started_by: "user_admin",
  started_at: "2026-05-01T00:00:01+00:00",
  finished_at: "2026-05-01T00:00:02+00:00",
  exit_code: 0,
  summary: { passed: true, error_count: 0 },
  created_at: "2026-05-01T00:00:00+00:00",
  updated_at: "2026-05-01T00:00:02+00:00",
  logs: [
    {
      id: "wlog_1",
      workflow_run_id: "wrun_1",
      stream: "stdout",
      line_number: 1,
      message: "policy lint passed=True errors=0",
      created_at: "2026-05-01T00:00:02+00:00"
    }
  ]
};

const artifact = {
  id: "art_1",
  organization_id: "org_default",
  environment_id: "env_default",
  artifact_type: "workflow.output",
  name: "policy-lint-output.json",
  content_type: "application/json",
  storage_uri: "local-artifact://org_default/env_default/art_1/policy-lint-output.json",
  checksum: "1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
  size_bytes: 33,
  created_by: "user_admin",
  created_at: "2026-05-01T00:00:03+00:00",
  links: [
    {
      id: "alink_1",
      artifact_id: "art_1",
      target_type: "workflow_run",
      target_id: "wrun_1",
      link_type: "output",
      created_at: "2026-05-01T00:00:03+00:00"
    }
  ],
  attestations: [
    {
      id: "aat_1",
      artifact_id: "art_1",
      attested_by: "user_admin",
      statement: "Checksum reviewed.",
      signature_ref: "sig-1",
      created_at: "2026-05-01T00:00:04+00:00"
    }
  ]
};

test("workflows route renders product workspace instead of placeholder", () => {
  const state = createInitialAppState({
    workflowDefinitions: [workflow],
    workflowRuns: [run],
    selectedWorkflowRun: run,
    workflowArtifacts: [artifact],
    selectedArtifact: artifact
  });
  const html = renderShell({ currentPath: "/workflows", state });

  assert.match(html, /data-route-page="\/workflows"/);
  assert.match(html, /data-workflow-workspace/);
  assert.match(html, /data-workflow-catalog/);
  assert.match(html, /data-workflow-run-form/);
  assert.match(html, /data-workflow-runs/);
  assert.match(html, /data-workflow-artifacts/);
  assert.doesNotMatch(html, /Primary Workspace/);
});

test("workflow page renders catalog run logs artifact detail and attestation form", () => {
  const html = renderWorkflowsPage({
    workflowDefinitions: [workflow],
    workflowRuns: [run],
    selectedWorkflowRun: run,
    workflowArtifacts: [artifact],
    selectedArtifact: artifact,
    workflowArtifactDownload: {
      artifact,
      content_base64: "e30=",
      metadata: { checksum_verified: true }
    },
    workflowArtifactAttestation: { id: "aat_2", artifact_id: "art_1" }
  });

  assert.match(html, /data-workflow-row="policy_lint"/);
  assert.match(html, /name="policy_body" required/);
  assert.match(html, /data-workflow-run-logs="wrun_1"/);
  assert.match(html, /policy lint passed=True/);
  assert.match(html, /data-workflow-artifact-detail="art_1"/);
  assert.match(html, /data-workflow-artifact-download="art_1"/);
  assert.match(html, /checksum verified/);
  assert.match(html, /data-artifact-attest-form/);
  assert.match(html, /data-workflow-artifact-attestation-row="aat_1"/);
  assert.match(html, /aat_2/);
});

test("workflow run detail renders ordered logs", () => {
  const html = renderWorkflowRunDetail(run);

  assert.match(html, /data-workflow-run-summary="wrun_1"/);
  assert.match(html, /data-workflow-log-row="wlog_1"/);
  assert.match(html, /stdout/);
});

test("artifact detail renders download links and attestation history", () => {
  const html = renderWorkflowArtifactDetail({ artifact });

  assert.match(html, /data-workflow-artifact-download="art_1"/);
  assert.match(html, /local-artifact:\/\/org_default/);
  assert.match(html, /data-workflow-artifact-links="art_1"/);
  assert.match(html, /data-workflow-artifact-attestations="art_1"/);
  assert.match(html, /Checksum reviewed/);
});

test("workflow run payload validates required schema fields", () => {
  assert.throws(
    () => workflowRunPayloadFromValues(workflow, { policy_body: "", policy_format: "yaml" }),
    /policy_body/
  );

  assert.deepEqual(
    workflowRunPayloadFromValues(workflow, {
      policy_body: "package demo",
      policy_format: "",
      run_immediately: "true"
    }),
    {
      inputs: { policy_body: "package demo", policy_format: "yaml" },
      run_immediately: true
    }
  );
});

test("artifact upload and attestation payload helpers validate content", () => {
  assert.deepEqual(artifactUploadPayloadFromValues({
    name: "out.json",
    artifact_type: "workflow.output",
    content_type: "application/json",
    content: "{}"
  }), {
    name: "out.json",
    artifact_type: "workflow.output",
    content_type: "application/json",
    content_base64: "e30="
  });

  assert.throws(() => artifactUploadPayloadFromValues({ content: " " }), /content is required/);
  assert.throws(() => artifactAttestationPayloadFromValues({ statement: " " }), /statement is required/);
  assert.deepEqual(artifactAttestationPayloadFromValues({
    statement: " Reviewed ",
    signature_ref: " sig-1 "
  }), {
    statement: "Reviewed",
    signature_ref: "sig-1"
  });
});

test("api client workflow and artifact methods call expected endpoints", async () => {
  const calls = [];
  const client = createApiClient({
    baseUrl: "/api/v1",
    fetchImpl: async (url, options = {}) => {
      calls.push([
        url,
        options.method ?? "GET",
        options.body ? JSON.parse(options.body) : null
      ]);
      return {
        ok: true,
        status: 200,
        headers: new Map([["content-type", "application/json"]]),
        json: async () => ({ id: "ok" })
      };
    }
  });

  await client.listWorkflows({ workflow_type: "policy" });
  await client.createWorkflowRun("policy lint", { inputs: { policy_body: "package demo" } });
  await client.listWorkflowRuns({ status: "succeeded" });
  await client.getWorkflowRun("wrun 1");
  await client.cancelWorkflowRun("wrun 1");
  await client.createArtifact({ name: "out.json" });
  await client.listArtifacts({ artifact_type: "workflow.output" });
  await client.getArtifact("art 1");
  await client.downloadArtifact("art 1");
  await client.createArtifactLink("art 1", { target_type: "workflow_run", target_id: "wrun 1" });
  await client.attestArtifact("art 1", { statement: "I attest" });

  assert.deepEqual(calls, [
    ["/api/v1/workflows?workflow_type=policy", "GET", null],
    ["/api/v1/workflows/policy%20lint/runs", "POST", { inputs: { policy_body: "package demo" } }],
    ["/api/v1/workflow-runs?status=succeeded", "GET", null],
    ["/api/v1/workflow-runs/wrun%201", "GET", null],
    ["/api/v1/workflow-runs/wrun%201/cancel", "POST", null],
    ["/api/v1/artifacts", "POST", { name: "out.json" }],
    ["/api/v1/artifacts?artifact_type=workflow.output", "GET", null],
    ["/api/v1/artifacts/art%201", "GET", null],
    ["/api/v1/artifacts/art%201/download", "GET", null],
    ["/api/v1/artifacts/art%201/links", "POST", { target_type: "workflow_run", target_id: "wrun 1" }],
    ["/api/v1/artifacts/art%201/attest", "POST", { statement: "I attest" }]
  ]);
});
