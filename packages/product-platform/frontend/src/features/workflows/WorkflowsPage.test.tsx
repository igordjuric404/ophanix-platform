import { fireEvent, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithQueryClient } from "../../test/test-utils";
import {
  WorkflowsPage,
  artifactAttestationPayloadFromValues,
  artifactUploadPayloadFromValues,
  workflowRunPayloadFromValues
} from "./WorkflowsPage";

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
  created_at: "2026-05-01T00:00:00Z",
  updated_at: "2026-05-01T00:00:00Z"
};

const run = {
  id: "wrun_1",
  organization_id: "org_default",
  environment_id: "env_default",
  workflow_definition_id: "policy_lint",
  workflow_type: "policy",
  command_ref: "python:policy.lint",
  status: "queued",
  inputs: { policy_format: "yaml" },
  started_by: "user_admin",
  started_at: "2026-05-01T00:00:01Z",
  finished_at: null,
  exit_code: null,
  summary: { passed: true, error_count: 0 },
  created_at: "2026-05-01T00:00:00Z",
  updated_at: "2026-05-01T00:00:02Z",
  logs: [
    {
      id: "wlog_1",
      workflow_run_id: "wrun_1",
      stream: "stdout",
      line_number: 1,
      message: "policy lint passed=True errors=0",
      created_at: "2026-05-01T00:00:02Z"
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
  created_at: "2026-05-01T00:00:03Z",
  links: [
    {
      id: "alink_1",
      artifact_id: "art_1",
      target_type: "workflow_run",
      target_id: "wrun_1",
      link_type: "output",
      created_at: "2026-05-01T00:00:03Z"
    }
  ],
  attestations: [
    {
      id: "aat_1",
      artifact_id: "art_1",
      attested_by: "user_admin",
      statement: "Checksum reviewed.",
      signature_ref: "sig-1",
      created_at: "2026-05-01T00:00:04Z"
    }
  ]
};

const download = {
  artifact,
  content_base64: "e30=",
  metadata: { checksum_verified: true }
};

describe("WorkflowsPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders workflow catalog, run detail, logs, artifact detail, and attestations", async () => {
    mockWorkflowsFetch();

    renderWithQueryClient(<WorkflowsPage />);

    expect(await screen.findByRole("heading", { name: "Workflow Catalog" })).toBeInTheDocument();
    expect(await screen.findByText("Policy Lint")).toBeInTheDocument();
    expect(await screen.findByText("policy lint passed=True errors=0")).toBeInTheDocument();
    expect((await screen.findAllByText("policy-lint-output.json")).length).toBeGreaterThan(0);
    expect(screen.getByText("Checksum reviewed.")).toBeInTheDocument();
  });

  it("submits workflow run, cancel, artifact upload, download, link, and attest actions", async () => {
    const requests = mockWorkflowsFetch();

    renderWithQueryClient(<WorkflowsPage />);
    await screen.findByText("Policy Lint");

    fireEvent.change(screen.getByLabelText("Policy Body"), { target: { value: "package demo" } });
    fireEvent.click(screen.getByRole("button", { name: /Run Workflow/ }));
    expect(await screen.findByText("Workflow run created")).toBeInTheDocument();

    const runRow = document.querySelector('[data-workflow-run-row="wrun_1"]');
    expect(runRow).not.toBeNull();
    fireEvent.click(within(runRow as HTMLElement).getByRole("button", { name: /Cancel/ }));
    expect(await screen.findByText("Workflow run cancelled")).toBeInTheDocument();

    const artifactDetail = document.querySelector('[data-workflow-artifact-detail="art_1"]');
    expect(artifactDetail).not.toBeNull();
    fireEvent.click(within(artifactDetail as HTMLElement).getByRole("button", { name: "Download" }));
    expect(await screen.findByText(/checksum verified/)).toBeInTheDocument();
    expect(within(artifactDetail as HTMLElement).queryByText("e30=")).not.toBeInTheDocument();

    fireEvent.change(within(artifactDetail as HTMLElement).getByLabelText("Link Target ID"), {
      target: { value: "wrun_1" }
    });
    fireEvent.click(within(artifactDetail as HTMLElement).getByRole("button", { name: "Link Artifact" }));
    expect(await screen.findByText("Artifact linked")).toBeInTheDocument();

    fireEvent.change(within(artifactDetail as HTMLElement).getByLabelText("Statement"), {
      target: { value: "Reviewed" }
    });
    fireEvent.click(within(artifactDetail as HTMLElement).getByRole("button", { name: "Attest" }));
    expect(await screen.findByText("Artifact attested")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Artifact Name"), { target: { value: "out.json" } });
    fireEvent.click(screen.getByRole("button", { name: "Upload Artifact" }));
    expect(await screen.findByText("Artifact uploaded")).toBeInTheDocument();

    expect(requests.some((request) => request.url.endsWith("/policy_lint/runs"))).toBe(true);
    expect(requests.some((request) => request.url.endsWith("/wrun_1/cancel"))).toBe(true);
    expect(requests.some((request) => request.url.endsWith("/artifacts"))).toBe(true);
    expect(requests.some((request) => request.url.endsWith("/art_1/download"))).toBe(true);
    expect(requests.some((request) => request.url.endsWith("/art_1/links"))).toBe(true);
    expect(requests.some((request) => request.url.endsWith("/art_1/attest"))).toBe(true);
  });

  it("normalizes workflow and artifact payloads", () => {
    expect(
      workflowRunPayloadFromValues(workflow, {
        policy_body: "package demo",
        policy_format: "",
        run_immediately: "true"
      })
    ).toEqual({
      inputs: { policy_body: "package demo", policy_format: "yaml" },
      run_immediately: true
    });

    expect(
      workflowRunPayloadFromValues(
        {
          ...workflow,
          input_schema: {
            type: "object",
            required: ["retries", "metadata"],
            properties: {
              retries: { type: "integer" },
              dry_run: { type: "boolean", default: false },
              metadata: { type: "object" },
              tags: { type: "array", default: ["policy"] }
            }
          }
        },
        {
          retries: "2",
          dry_run: "true",
          metadata: "{\"owner\":\"security\"}",
          tags: ""
        }
      )
    ).toEqual({
      inputs: {
        dry_run: true,
        metadata: { owner: "security" },
        retries: 2,
        tags: ["policy"]
      },
      run_immediately: true
    });

    expect(() =>
      workflowRunPayloadFromValues(
        {
          ...workflow,
          input_schema: {
            type: "object",
            properties: { retries: { type: "integer" } }
          }
        },
        { retries: "1.5" }
      )
    ).toThrow("Workflow input retries must be an integer.");

    expect(
      artifactUploadPayloadFromValues({
        name: "out.json",
        artifact_type: "workflow.output",
        content_type: "application/json",
        content: "{}"
      })
    ).toEqual({
      name: "out.json",
      artifact_type: "workflow.output",
      content_type: "application/json",
      content_base64: "e30="
    });

    expect(
      artifactAttestationPayloadFromValues({
        statement: " Reviewed ",
        signature_ref: " sig-1 "
      })
    ).toEqual({
      statement: "Reviewed",
      signature_ref: "sig-1"
    });
  });
});

function mockWorkflowsFetch() {
  const requests: Array<{ url: string; method: string; body?: unknown }> = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = input.toString();
      const path = new URL(url, "http://localhost").pathname;
      const method = init?.method ?? "GET";
      const body = init?.body ? JSON.parse(String(init.body)) : undefined;
      requests.push({ url: path, method, body });

      if (path === "/api/v1/workflows" && method === "GET") {
        return json([workflow]);
      }
      if (path === "/api/v1/workflow-runs" && method === "GET") {
        return json([run]);
      }
      if (path === "/api/v1/workflow-runs/wrun_1" && method === "GET") {
        return json(run);
      }
      if (path === "/api/v1/artifacts" && method === "GET") {
        return json([artifact]);
      }
      if (path === "/api/v1/artifacts/art_1" && method === "GET") {
        return json(artifact);
      }
      if (path === "/api/v1/workflows/policy_lint/runs" && method === "POST") {
        return json({ ...run, id: "wrun_2", status: "succeeded" }, 201);
      }
      if (path === "/api/v1/workflow-runs/wrun_1/cancel" && method === "POST") {
        return json({ ...run, status: "cancelled" });
      }
      if (path === "/api/v1/artifacts" && method === "POST") {
        return json({ ...artifact, id: "art_2", name: "out.json" }, 201);
      }
      if (path === "/api/v1/artifacts/art_1/download" && method === "GET") {
        return json(download);
      }
      if (path === "/api/v1/artifacts/art_1/links" && method === "POST") {
        return json({ ...artifact.links[0], id: "alink_2" }, 201);
      }
      if (path === "/api/v1/artifacts/art_1/attest" && method === "POST") {
        return json({ ...artifact.attestations[0], id: "aat_2", statement: "Reviewed" }, 201);
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
