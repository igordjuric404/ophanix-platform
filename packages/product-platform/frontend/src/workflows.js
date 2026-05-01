import { escapeHtml } from "./html.js";

export function renderWorkflowsPage(state = {}) {
  const workflows = state.workflowDefinitions ?? [];
  const runs = state.workflowRuns ?? [];
  const artifacts = state.workflowArtifacts ?? [];
  const selectedWorkflow =
    state.selectedWorkflowDefinition ??
    workflows.find((workflow) => workflow.id === state.selectedWorkflowId) ??
    workflows[0] ??
    null;
  const selectedRun =
    state.selectedWorkflowRun ??
    runs.find((run) => run.id === state.selectedWorkflowRunId) ??
    runs[0] ??
    null;
  const selectedArtifact =
    state.selectedArtifact ??
    artifacts.find((artifact) => artifact.id === state.selectedArtifactId) ??
    artifacts[0] ??
    null;

  return `
    <section class="page-heading" data-route-page="/workflows">
      <p class="section-label">Automation</p>
      <h1>Workflows</h1>
      <p>Catalog, runs, logs, artifacts, and attestations.</p>
    </section>
    <section class="policy-workspace workflow-workspace" data-workflow-workspace>
      ${renderWorkflowCatalog({ workflows, selectedWorkflow })}
      ${renderWorkflowRunForm({
        workflow: selectedWorkflow,
        runResult: state.workflowRunResult ?? null,
        error: state.workflowRunError ?? null
      })}
      ${renderWorkflowRuns({ runs, selectedRun })}
      ${renderWorkflowArtifacts({
        artifacts,
        selectedArtifact,
        downloadResult: state.workflowArtifactDownload ?? null,
        uploadResult: state.workflowArtifactUpload ?? null,
        attestationResult: state.workflowArtifactAttestation ?? null,
        attestationError: state.workflowArtifactAttestationError ?? null
      })}
    </section>
  `;
}

export function renderWorkflowCatalog({ workflows = [], selectedWorkflow = null } = {}) {
  return `
    <section class="workspace-panel workflow-catalog" data-workflow-catalog>
      <h2>Catalog</h2>
      ${
        workflows.length
          ? `<table class="data-table" data-workflow-catalog-table>
              <thead>
                <tr><th>Name</th><th>Type</th><th>Command</th><th>Status</th><th></th></tr>
              </thead>
              <tbody>
                ${workflows
                  .map(
                    (workflow) => `
                      <tr data-workflow-row="${escapeHtml(workflow.id)}">
                        <td>
                          <strong>${escapeHtml(workflow.name)}</strong>
                          <small>${escapeHtml(workflow.id)}</small>
                        </td>
                        <td>${escapeHtml(workflow.workflow_type)}</td>
                        <td><code>${escapeHtml(workflow.command_ref)}</code></td>
                        <td><span class="status-pill">${workflow.enabled ? "enabled" : "disabled"}</span></td>
                        <td>
                          <button type="button" data-workflow-open="${escapeHtml(workflow.id)}" ${
                            selectedWorkflow?.id === workflow.id ? "disabled" : ""
                          }>Open</button>
                        </td>
                      </tr>
                    `
                  )
                  .join("")}
              </tbody>
            </table>`
          : '<div class="empty-state" data-workflow-catalog-empty><strong>No workflows</strong><span>Catalog is empty</span></div>'
      }
    </section>
  `;
}

export function renderWorkflowRunForm({ workflow = null, runResult = null, error = null } = {}) {
  if (!workflow) {
    return `
      <section class="workspace-panel workflow-runner" data-workflow-runner>
        <h2>Run</h2>
        <div class="empty-state" data-workflow-run-form-empty><strong>No workflow selected</strong><span>Select a workflow</span></div>
      </section>
    `;
  }
  const properties = workflow.input_schema?.properties ?? {};
  const required = new Set(workflow.input_schema?.required ?? []);
  const fields = Object.entries(properties)
    .map(([name, schema]) => renderWorkflowInput(name, schema, required.has(name)))
    .join("");

  return `
    <section class="workspace-panel workflow-runner" data-workflow-runner>
      <h2>Run ${escapeHtml(workflow.name)}</h2>
      <form class="workflow-run-form" data-workflow-run-form data-workflow-id="${escapeHtml(workflow.id)}">
        ${fields}
        <input type="hidden" name="run_immediately" value="false">
        <label class="checkbox-row">
          <input type="checkbox" name="run_immediately" value="true" checked>
          Run immediately
        </label>
        <button type="submit">Run</button>
      </form>
      ${
        error
          ? `<output class="form-error" data-workflow-run-error>${escapeHtml(error)}</output>`
          : ""
      }
      ${
        runResult
          ? `<output data-workflow-run-result>${escapeHtml(runResult.id)} ${escapeHtml(runResult.status)}</output>`
          : ""
      }
    </section>
  `;
}

function renderWorkflowInput(name, schema = {}, required = false) {
  const label = schema.title ?? name;
  const defaultValue = schema.default ?? "";
  const common = `name="${escapeHtml(name)}" ${required ? "required" : ""}`;
  if (name.includes("body") || name.includes("json") || name.includes("manifest")) {
    return `
      <label>
        ${escapeHtml(label)}
        <textarea ${common} rows="5">${escapeHtml(defaultValue)}</textarea>
      </label>
    `;
  }
  return `
    <label>
      ${escapeHtml(label)}
      <input ${common} value="${escapeHtml(defaultValue)}">
    </label>
  `;
}

export function renderWorkflowRuns({ runs = [], selectedRun = null } = {}) {
  return `
    <section class="workspace-panel workflow-runs" data-workflow-runs>
      <h2>Runs</h2>
      ${
        runs.length
          ? `<table class="data-table" data-workflow-run-table>
              <thead>
                <tr><th>Run</th><th>Workflow</th><th>Status</th><th>Exit</th><th></th></tr>
              </thead>
              <tbody>
                ${runs
                  .map(
                    (run) => `
                      <tr data-workflow-run-row="${escapeHtml(run.id)}">
                        <td><strong>${escapeHtml(run.id)}</strong><small>${escapeHtml(run.created_at ?? "")}</small></td>
                        <td>${escapeHtml(run.workflow_definition_id ?? run.workflow_type)}</td>
                        <td><span class="status-pill">${escapeHtml(run.status)}</span></td>
                        <td>${run.exit_code ?? "n/a"}</td>
                        <td class="row-actions">
                          <button type="button" data-workflow-run-open="${escapeHtml(run.id)}">Open</button>
                          <button type="button" data-workflow-run-cancel="${escapeHtml(run.id)}" ${
                            ["queued", "running"].includes(run.status) ? "" : "disabled"
                          }>Cancel</button>
                        </td>
                      </tr>
                    `
                  )
                  .join("")}
              </tbody>
            </table>`
          : '<div class="empty-state" data-workflow-run-empty><strong>No runs</strong><span>Run a workflow</span></div>'
      }
      ${selectedRun ? renderWorkflowRunDetail(selectedRun) : ""}
    </section>
  `;
}

export function renderWorkflowRunDetail(run) {
  const logs = run.logs ?? [];
  return `
    <section class="lint-panel" data-workflow-run-detail="${escapeHtml(run.id)}">
      <h3>${escapeHtml(run.id)}</h3>
      <dl class="metadata-grid">
        <dt>Status</dt><dd>${escapeHtml(run.status)}</dd>
        <dt>Command</dt><dd>${escapeHtml(run.command_ref ?? "n/a")}</dd>
        <dt>Started</dt><dd>${escapeHtml(run.started_at ?? "n/a")}</dd>
        <dt>Finished</dt><dd>${escapeHtml(run.finished_at ?? "n/a")}</dd>
      </dl>
      <pre data-workflow-run-summary="${escapeHtml(run.id)}">${escapeHtml(JSON.stringify(run.summary ?? {}, null, 2))}</pre>
      ${
        logs.length
          ? `<table class="data-table" data-workflow-run-logs="${escapeHtml(run.id)}">
              <thead><tr><th>#</th><th>Stream</th><th>Message</th></tr></thead>
              <tbody>
                ${logs
                  .map(
                    (log) => `
                      <tr data-workflow-log-row="${escapeHtml(log.id)}">
                        <td>${log.line_number}</td>
                        <td>${escapeHtml(log.stream)}</td>
                        <td>${escapeHtml(log.message)}</td>
                      </tr>
                    `
                  )
                  .join("")}
              </tbody>
            </table>`
          : '<div class="empty-state" data-workflow-run-logs-empty><strong>No logs</strong><span>Run has not emitted logs</span></div>'
      }
    </section>
  `;
}

export function renderWorkflowArtifacts({
  artifacts = [],
  selectedArtifact = null,
  downloadResult = null,
  uploadResult = null,
  attestationResult = null,
  attestationError = null
} = {}) {
  return `
    <section class="workspace-panel workflow-artifacts" data-workflow-artifacts>
      <h2>Artifacts</h2>
      <form class="filter-bar" data-artifact-upload-form>
        <label>Name<input name="name" value="workflow-output.json" required></label>
        <label>Type<input name="artifact_type" value="workflow.output" required></label>
        <label>Content type<input name="content_type" value="application/json" required></label>
        <label>Content<textarea name="content" rows="2" required>{}</textarea></label>
        <button type="submit">Upload</button>
      </form>
      ${uploadResult ? `<output data-artifact-upload-result>${escapeHtml(uploadResult.id)}</output>` : ""}
      ${
        artifacts.length
          ? `<table class="data-table" data-workflow-artifact-table>
              <thead><tr><th>Name</th><th>Type</th><th>Checksum</th><th>Size</th><th></th></tr></thead>
              <tbody>
                ${artifacts
                  .map(
                    (artifact) => `
                      <tr data-workflow-artifact-row="${escapeHtml(artifact.id)}">
                        <td><strong>${escapeHtml(artifact.name)}</strong><small>${escapeHtml(artifact.id)}</small></td>
                        <td>${escapeHtml(artifact.artifact_type)}</td>
                        <td><code>${escapeHtml(shortChecksum(artifact.checksum))}</code></td>
                        <td>${artifact.size_bytes ?? 0}</td>
                        <td><button type="button" data-workflow-artifact-open="${escapeHtml(artifact.id)}">Open</button></td>
                      </tr>
                    `
                  )
                  .join("")}
              </tbody>
            </table>`
          : '<div class="empty-state" data-workflow-artifact-empty><strong>No artifacts</strong><span>Upload an artifact</span></div>'
      }
      ${
        selectedArtifact
          ? renderWorkflowArtifactDetail({
              artifact: selectedArtifact,
              downloadResult,
              attestationResult,
              attestationError
            })
          : ""
      }
    </section>
  `;
}

export function renderWorkflowArtifactDetail({
  artifact,
  downloadResult = null,
  attestationResult = null,
  attestationError = null
}) {
  const links = artifact.links ?? [];
  const attestations = artifact.attestations ?? [];
  return `
    <section class="lint-panel" data-workflow-artifact-detail="${escapeHtml(artifact.id)}">
      <h3>${escapeHtml(artifact.name)}</h3>
      <dl class="metadata-grid">
        <dt>Checksum</dt><dd><code>${escapeHtml(artifact.checksum)}</code></dd>
        <dt>Content type</dt><dd>${escapeHtml(artifact.content_type)}</dd>
        <dt>Storage</dt><dd>${escapeHtml(artifact.storage_uri)}</dd>
        <dt>Created by</dt><dd>${escapeHtml(artifact.created_by)}</dd>
      </dl>
      <div class="row-actions">
        <button type="button" data-workflow-artifact-download="${escapeHtml(artifact.id)}">Download</button>
      </div>
      ${
        downloadResult?.artifact?.id === artifact.id
          ? `<output data-workflow-artifact-download-result="${escapeHtml(artifact.id)}">
              checksum ${downloadResult.metadata?.checksum_verified ? "verified" : "unverified"}
            </output>`
          : ""
      }
      <h4>Links</h4>
      ${
        links.length
          ? `<ul data-workflow-artifact-links="${escapeHtml(artifact.id)}">
              ${links
                .map(
                  (link) => `
                    <li>${escapeHtml(link.link_type)} ${escapeHtml(link.target_type)} ${escapeHtml(link.target_id)}</li>
                  `
                )
                .join("")}
            </ul>`
          : '<div class="empty-state" data-workflow-artifact-links-empty><strong>No links</strong><span>Unlinked artifact</span></div>'
      }
      <h4>Attestations</h4>
      ${
        attestations.length
          ? `<ul data-workflow-artifact-attestations="${escapeHtml(artifact.id)}">
              ${attestations
                .map(
                  (attestation) => `
                    <li data-workflow-artifact-attestation-row="${escapeHtml(attestation.id)}">
                      <strong>${escapeHtml(attestation.attested_by)}</strong>
                      <span>${escapeHtml(attestation.statement)}</span>
                      <small>${escapeHtml(attestation.signature_ref ?? "unsigned")}</small>
                    </li>
                  `
                )
                .join("")}
            </ul>`
          : '<div class="empty-state" data-workflow-artifact-attestations-empty><strong>No attestations</strong><span>Awaiting review</span></div>'
      }
      <form class="filter-bar" data-artifact-attest-form data-artifact-id="${escapeHtml(artifact.id)}">
        <label>Statement<textarea name="statement" rows="2" required></textarea></label>
        <label>Signature ref<input name="signature_ref"></label>
        <button type="submit">Attest</button>
      </form>
      ${
        attestationError
          ? `<output class="form-error" data-artifact-attestation-error>${escapeHtml(attestationError)}</output>`
          : ""
      }
      ${
        attestationResult?.artifact_id === artifact.id
          ? `<output data-artifact-attestation-result>${escapeHtml(attestationResult.id)}</output>`
          : ""
      }
    </section>
  `;
}

export function workflowRunPayloadFromValues(workflow, values = {}) {
  const schema = workflow?.input_schema ?? {};
  const properties = schema.properties ?? {};
  const required = new Set(schema.required ?? []);
  const missing = [];
  const inputs = {};

  for (const [name, propertySchema] of Object.entries(properties)) {
    const submittedValue = values[name];
    const rawValue =
      submittedValue === undefined || submittedValue === null || String(submittedValue).trim() === ""
        ? propertySchema.default ?? ""
        : submittedValue;
    const value = String(rawValue).trim();
    if (value || required.has(name)) {
      inputs[name] = value;
    }
    if (required.has(name) && !value) {
      missing.push(name);
    }
  }

  if (missing.length > 0) {
    throw new Error(`Missing required workflow input: ${missing.join(", ")}`);
  }

  return {
    inputs,
    run_immediately: values.run_immediately !== "false" && values.run_immediately !== false
  };
}

export function workflowRunPayloadFromForm(form, workflow) {
  return workflowRunPayloadFromValues(workflow, Object.fromEntries(new FormData(form)));
}

export function artifactUploadPayloadFromValues(values = {}) {
  const content = String(values.content ?? "").trim();
  if (!content) {
    throw new Error("Artifact content is required.");
  }
  return {
    name: String(values.name ?? "").trim(),
    artifact_type: String(values.artifact_type ?? "workflow.output").trim(),
    content_type: String(values.content_type ?? "application/octet-stream").trim(),
    content_base64: encodeUtf8Base64(content)
  };
}

export function artifactUploadPayloadFromForm(form) {
  return artifactUploadPayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function artifactAttestationPayloadFromValues(values = {}) {
  const statement = String(values.statement ?? "").trim();
  if (!statement) {
    throw new Error("Attestation statement is required.");
  }
  const signatureRef = String(values.signature_ref ?? "").trim();
  return {
    statement,
    signature_ref: signatureRef || null
  };
}

export function artifactAttestationPayloadFromForm(form) {
  return artifactAttestationPayloadFromValues(Object.fromEntries(new FormData(form)));
}

function shortChecksum(checksum = "") {
  return checksum.length > 12 ? `${checksum.slice(0, 12)}...` : checksum;
}

function encodeUtf8Base64(value) {
  if (typeof Buffer !== "undefined") {
    return Buffer.from(value, "utf8").toString("base64");
  }
  const bytes = new TextEncoder().encode(value);
  let binary = "";
  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }
  return btoa(binary);
}
