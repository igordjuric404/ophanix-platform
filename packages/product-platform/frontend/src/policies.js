import { escapeHtml } from "./html.js";

export function renderPoliciesPage(state = {}) {
  const policies = state.policies ?? [];
  const selectedPolicy = state.selectedPolicy ?? policies[0] ?? null;
  const versions = selectedPolicy?.versions ?? state.policyVersions ?? [];
  const policyBindingTargets = state.policyBindingTargets ?? {};
  return `
    <section class="page-heading" data-route-page="/policies">
      <p class="section-label">Governance</p>
      <h1>Policies</h1>
      <p>Policy library, editor, bindings, simulator, approvals, and packs.</p>
    </section>
    <section class="policy-workspace" data-policy-workspace>
      ${renderPolicyLibrary(policies)}
      ${renderPolicyVersionDrawer(selectedPolicy, versions)}
      ${renderPolicyEditor(selectedPolicy, {
        lintResult: state.policyEditorLint ?? null,
        backend: state.policyEditorBackend ?? selectedPolicy?.versions?.[0]?.backend ?? "native",
        bodyFormat: state.policyEditorBodyFormat ?? selectedPolicy?.versions?.[0]?.body_format ?? "yaml",
        bodyText: state.policyEditorBody ?? selectedPolicy?.versions?.[0]?.body_text ?? ""
      })}
      ${renderPolicyBindingsPanel({
        bindings: state.policyBindings ?? [],
        exceptions: state.policyExceptions ?? [],
        policies,
        selectedPolicy,
        agents: policyBindingTargets.agents ?? state.agents ?? [],
        environments: state.environments ?? []
      })}
      ${renderPolicySimulatorPanel({
        policies,
        selectedPolicy,
        result: state.policyEvaluationResult ?? null,
        error: state.policyEvaluationError ?? null
      })}
      ${renderPolicyEvaluationFeed({
        evaluations: state.policyEvaluations ?? [],
        summary: state.policyEvaluationSummary ?? null,
        filters: state.policyEvaluationFilter ?? {},
        selectedEvaluation: state.selectedPolicyEvaluation ?? null
      })}
      ${renderPolicyAffectedResourcesPanel(state.policyAffectedResources ?? null)}
      ${renderPolicyImportDialog()}
      ${renderPolicyExportPanel(state.policyExport ?? null)}
    </section>
  `;
}

export function renderPolicyLibrary(policies = []) {
  return `
    <section class="workspace-panel policy-library" data-policy-library>
      <header class="panel-header">
        <div>
          <p class="section-label">Library</p>
          <h2>Policy Library</h2>
        </div>
      </header>
      ${renderPolicyFilterBar()}
      ${
        policies.length
          ? renderPolicyTable(policies)
          : '<div class="empty-state" data-policy-empty><strong>No policies</strong><span>Import policy</span></div>'
      }
    </section>
  `;
}

export function renderPolicyFilterBar() {
  return `
    <form class="filter-bar" data-policy-filter>
      <label>
        <span>Scope</span>
        <select name="scope">
          <option value="">Any</option>
          <option value="agent">Agent</option>
          <option value="mcp-tool">MCP Tool</option>
          <option value="runtime-action">Runtime Action</option>
          <option value="environment">Environment</option>
        </select>
      </label>
      <label>
        <span>Status</span>
        <select name="status">
          <option value="">Any</option>
          <option value="draft">Draft</option>
          <option value="active">Active</option>
          <option value="archived">Archived</option>
        </select>
      </label>
      <label>
        <span>Backend</span>
        <select name="backend">
          <option value="">Any</option>
          <option value="native">Native</option>
          <option value="opa">OPA</option>
          <option value="cedar">Cedar</option>
        </select>
      </label>
      <label>
        <span>Owner</span>
        <input name="owner_user_id" placeholder="user id">
      </label>
      <label>
        <span>Tag</span>
        <input name="tag" placeholder="safety">
      </label>
      <button type="submit">Filter</button>
    </form>
  `;
}

export function renderPolicyTable(policies = []) {
  const rows = policies
    .map(
      (policy) => `
        <tr data-policy-row="${escapeHtml(policy.id)}">
          <td>
            <strong>${escapeHtml(policy.name)}</strong>
            <small>${escapeHtml(policy.slug)}</small>
          </td>
          <td>${escapeHtml(policy.scope)}</td>
          <td><span class="status-pill">${escapeHtml(policy.status)}</span></td>
          <td>${escapeHtml(policy.owner_user_id)}</td>
          <td>${escapeHtml((policy.tags ?? []).join(", ") || "none")}</td>
          <td>${escapeHtml(policy.active_version_number ? `v${policy.active_version_number}` : "none")}</td>
          <td>${escapeHtml(String(policy.version_count ?? 0))}</td>
          <td class="row-actions">
            <button type="button" data-policy-open="${escapeHtml(policy.id)}">Open</button>
            <button type="button" data-policy-export="${escapeHtml(policy.id)}">Export</button>
          </td>
        </tr>
      `
    )
    .join("");
  return `
    <table class="data-table" data-policy-table>
      <thead>
        <tr>
          <th>Name</th>
          <th>Scope</th>
          <th>Status</th>
          <th>Owner</th>
          <th>Tags</th>
          <th>Active</th>
          <th>Versions</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

export function renderPolicyVersionDrawer(policy = null, versions = []) {
  if (!policy) {
    return `
      <section class="workspace-panel policy-version-drawer" data-policy-version-drawer-empty>
        <header class="panel-header">
          <div>
            <p class="section-label">Versions</p>
            <h2>Version History</h2>
          </div>
        </header>
        <div class="empty-state"><strong>No selected policy</strong><span>Open policy</span></div>
      </section>
    `;
  }
  const versionRows = versions
    .map(
      (version) => `
        <tr data-policy-version-row="${escapeHtml(version.id)}">
          <td><strong>v${escapeHtml(String(version.version_number))}</strong><small>${escapeHtml(version.checksum)}</small></td>
          <td>${escapeHtml(version.body_format)}</td>
          <td>${escapeHtml(version.backend)}</td>
          <td><span class="status-pill">${escapeHtml(version.status)}</span></td>
          <td>${escapeHtml(version.created_by)}</td>
          <td>${escapeHtml(version.activated_at ?? "not active")}</td>
          <td class="row-actions">
            <button type="button" data-policy-activate="${escapeHtml(policy.id)}:${escapeHtml(version.id)}">Activate</button>
            <button type="button" data-policy-rollback="${escapeHtml(policy.id)}:${escapeHtml(version.id)}">Rollback</button>
            <button type="button" data-policy-archive="${escapeHtml(policy.id)}:${escapeHtml(version.id)}">Archive</button>
          </td>
        </tr>
      `
    )
    .join("");
  return `
    <section class="workspace-panel policy-version-drawer" data-policy-version-drawer="${escapeHtml(policy.id)}">
      <header class="panel-header">
        <div>
          <p class="section-label">Versions</p>
          <h2>${escapeHtml(policy.name)}</h2>
        </div>
        <span class="status-pill">${escapeHtml(policy.status)}</span>
      </header>
      ${
        versions.length
          ? `<table class="data-table" data-policy-version-table>
              <thead>
                <tr>
                  <th>Version</th>
                  <th>Format</th>
                  <th>Backend</th>
                  <th>Status</th>
                  <th>Author</th>
                  <th>Activated</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>${versionRows}</tbody>
            </table>`
          : '<div class="empty-state" data-policy-version-empty><strong>No versions</strong><span>Create version</span></div>'
      }
    </section>
  `;
}

export function renderPolicyImportDialog() {
  return `
    <section class="workspace-panel policy-import" data-policy-import>
      <header class="panel-header">
        <div>
          <p class="section-label">Import</p>
          <h2>Import Policy</h2>
        </div>
      </header>
      <form class="policy-import-form" data-policy-import-form>
        <label>
          <span>Name</span>
          <input name="name" placeholder="Optional imported policy name">
        </label>
        <label>
          <span>Source Path</span>
          <input name="source_path" placeholder="packages/agent-os/examples/policies/default.yaml">
        </label>
        <label>
          <span>Format</span>
          <select name="body_format">
            <option value="yaml">YAML</option>
            <option value="json">JSON</option>
            <option value="rego">Rego</option>
            <option value="cedar">Cedar</option>
          </select>
        </label>
        <label>
          <span>Scope</span>
          <select name="scope">
            <option value="agent">Agent</option>
            <option value="mcp-tool">MCP Tool</option>
            <option value="runtime-action">Runtime Action</option>
            <option value="environment">Environment</option>
          </select>
        </label>
        <label>
          <span>Backend</span>
          <select name="backend">
            <option value="native">Native</option>
            <option value="opa">OPA</option>
            <option value="cedar">Cedar</option>
          </select>
        </label>
        <label>
          <span>Tags</span>
          <input name="tags" placeholder="safety, runtime">
        </label>
        <label class="full-width">
          <span>Body</span>
          <textarea name="body_text" rows="10" spellcheck="false"></textarea>
        </label>
        <button type="submit">Import</button>
        <output data-policy-import-result></output>
      </form>
    </section>
  `;
}

export function renderPolicyEditor(policy = null, editor = {}) {
  if (!policy) {
    return `
      <section class="workspace-panel policy-editor" data-policy-editor-empty>
        <header class="panel-header">
          <div>
            <p class="section-label">Editor</p>
            <h2>Policy Editor</h2>
          </div>
        </header>
        <div class="empty-state"><strong>No selected policy</strong><span>Open policy</span></div>
      </section>
    `;
  }
  const backend = editor.backend ?? "native";
  const bodyFormat = editor.bodyFormat ?? "yaml";
  const bodyText = editor.bodyText ?? "";
  const lintResult = editor.lintResult ?? null;
  const hasFatal = (lintResult?.issues ?? []).some((issue) => issue.fatal || issue.severity === "error");
  return `
    <section class="workspace-panel policy-editor" data-policy-editor="${escapeHtml(policy.id)}">
      <header class="panel-header">
        <div>
          <p class="section-label">Editor</p>
          <h2>${escapeHtml(policy.name)}</h2>
        </div>
        <button type="button" data-policy-editor-lint="${escapeHtml(policy.id)}">Lint</button>
      </header>
      <form class="policy-editor-form" data-policy-editor-form data-policy-id="${escapeHtml(policy.id)}">
        <div class="editor-metadata" data-policy-editor-metadata>
          <label>
            <span>Description</span>
            <input name="description" value="${escapeHtml(policy.description ?? "")}">
          </label>
          <label>
            <span>Tags</span>
            <input name="tags" value="${escapeHtml((policy.tags ?? []).join(", "))}">
          </label>
          <label>
            <span>Scope</span>
            <select name="scope">
              ${["agent", "mcp-tool", "runtime-action", "environment"]
                .map(
                  (scope) => `
                    <option value="${scope}" ${policy.scope === scope ? "selected" : ""}>${scope}</option>
                  `
                )
                .join("")}
            </select>
          </label>
          <label>
            <span>Backend</span>
            <select name="backend" data-policy-backend-selector>
              ${["native", "opa", "cedar"]
                .map(
                  (option) => `
                    <option value="${option}" ${backend === option ? "selected" : ""}>${option}</option>
                  `
                )
                .join("")}
            </select>
          </label>
          <label>
            <span>Format</span>
            <select name="body_format">
              ${["yaml", "json", "rego", "cedar"]
                .map(
                  (format) => `
                    <option value="${format}" ${bodyFormat === format ? "selected" : ""}>${format}</option>
                  `
                )
                .join("")}
            </select>
          </label>
        </div>
        <p class="drawer-state" data-policy-backend-hint>${escapeHtml(backendHint(backend))}</p>
        <label class="full-width code-editor">
          <span>Body</span>
          <textarea name="body_text" rows="16" spellcheck="false" data-policy-code-editor>${escapeHtml(bodyText)}</textarea>
        </label>
        ${renderPolicyLintPanel(lintResult)}
        <button type="submit" data-policy-save-version ${hasFatal ? "disabled" : ""}>Save Version</button>
      </form>
    </section>
  `;
}

export function renderPolicyLintPanel(lintResult = null) {
  if (!lintResult) {
    return `
      <section class="lint-panel" data-policy-lint-panel>
        <h3>Lint Results</h3>
        <div class="empty-state"><strong>No lint run</strong><span>Pending</span></div>
      </section>
    `;
  }
  const issues = lintResult.issues ?? [];
  return `
    <section class="lint-panel" data-policy-lint-panel>
      <h3>Lint Results</h3>
      <ul class="compact-list">
        <li><span>Errors</span><strong>${escapeHtml(String(lintResult.error_count ?? 0))}</strong></li>
        <li><span>Warnings</span><strong>${escapeHtml(String(lintResult.warning_count ?? 0))}</strong></li>
      </ul>
      ${
        issues.length
          ? `<ol class="related-event-timeline" data-policy-lint-issues>
              ${issues
                .map(
                  (issue) => `
                    <li data-policy-lint-issue="${escapeHtml(issue.code)}">
                      <button type="button" data-policy-lint-path="${escapeHtml(issue.path)}">
                        <span>${escapeHtml(issue.severity)}</span>
                        <strong>${escapeHtml(issue.code)}</strong>
                        <small>${escapeHtml(issue.path)} ${escapeHtml(issue.line ? `line ${issue.line}` : "")}</small>
                        <em>${escapeHtml(issue.message)}</em>
                      </button>
                    </li>
                  `
                )
                .join("")}
            </ol>`
          : '<div class="empty-state"><strong>No issues</strong><span>Passed</span></div>'
      }
    </section>
  `;
}

export function renderPolicyAffectedResourcesPanel(affected = null) {
  const resources = affected?.resources ?? [];
  const activeCount = affected?.active_binding_count ?? 0;
  return `
    <section class="workspace-panel policy-affected-resources" data-policy-affected-resources>
      <header class="panel-header">
        <div>
          <p class="section-label">Impact</p>
          <h2>Affected Resources</h2>
        </div>
        <a href="/policies?tab=bindings" data-route="/policies">Bindings</a>
      </header>
      ${
        activeCount > 0
          ? `<div class="drawer-state is-warning" data-policy-active-binding-warning>${escapeHtml(String(activeCount))} active bindings</div>`
          : ""
      }
      ${
        resources.length
          ? `<table class="data-table" data-policy-affected-table>
              <thead>
                <tr>
                  <th>Resource</th>
                  <th>Type</th>
                  <th>Status</th>
                  <th>Mode</th>
                  <th>Environment</th>
                </tr>
              </thead>
              <tbody>
                ${resources
                  .map(
                    (resource) => `
                      <tr data-policy-affected-resource="${escapeHtml(resource.target_id)}">
                        <td><strong>${escapeHtml(resource.label)}</strong><small>${escapeHtml(resource.target_id)}</small></td>
                        <td>${escapeHtml(resource.target_type)}</td>
                        <td>${escapeHtml(resource.status)}</td>
                        <td>${escapeHtml(resource.mode ?? "reference")}</td>
                        <td>${escapeHtml(resource.environment_id ?? "any")}</td>
                      </tr>
                    `
                  )
                  .join("")}
              </tbody>
            </table>`
          : '<div class="empty-state" data-policy-affected-empty><strong>No affected resources</strong><span>Unbound</span></div>'
      }
    </section>
  `;
}

export function renderPolicyBindingsPanel({
  bindings = [],
  exceptions = [],
  policies = [],
  selectedPolicy = null,
  agents = [],
  environments = []
} = {}) {
  const activePolicyId = selectedPolicy?.id ?? policies[0]?.id ?? "";
  const targetOptions = bindingTargetOptions({ agents, environments });
  return `
    <section class="workspace-panel policy-bindings" data-policy-bindings-panel>
      <header class="panel-header">
        <div>
          <p class="section-label">Bindings</p>
          <h2>Policy Bindings</h2>
        </div>
      </header>
      ${renderPolicyBindingCreateForm({ policies, selectedPolicy, targetOptions })}
      ${
        bindings.length
          ? renderPolicyBindingMatrix({ bindings, exceptions, policies, agents, environments })
          : '<div class="empty-state" data-policy-bindings-empty><strong>No bindings</strong><span>Create binding</span></div>'
      }
      ${renderPolicyExceptionDialogs({ bindings, agents, environments })}
      <input type="hidden" data-policy-bindings-selected-policy value="${escapeHtml(activePolicyId)}">
    </section>
  `;
}

export function renderPolicyBindingMatrix({
  bindings = [],
  exceptions = [],
  policies = [],
  agents = [],
  environments = []
} = {}) {
  const policyById = new Map(policies.map((policy) => [policy.id, policy]));
  const rows = bindings
    .map((binding) => {
      const policy = policyById.get(binding.policy_id);
      const bindingExceptions = exceptions.filter((exception) => exception.binding_id === binding.id);
      return `
        <tr data-policy-binding-row="${escapeHtml(binding.id)}">
          <td>
            <strong>${escapeHtml(targetLabel(binding, { agents, environments }))}</strong>
            <small>${escapeHtml(binding.target_type)} - ${escapeHtml(binding.target_id)}</small>
          </td>
          <td>
            <strong>${escapeHtml(policy?.name ?? binding.policy_id)}</strong>
            <small>${escapeHtml(binding.policy_version_id)}</small>
          </td>
          <td><span class="status-pill">${escapeHtml(binding.mode)}</span></td>
          <td>${escapeHtml(String(binding.rollout_percentage))}%</td>
          <td>${escapeHtml(String(binding.priority ?? 0))}</td>
          <td><span class="status-pill">${escapeHtml(binding.status)}</span></td>
          <td>
            ${
              bindingExceptions.length
                ? `<ul class="compact-list" data-policy-binding-exceptions="${escapeHtml(binding.id)}">
                    ${bindingExceptions
                      .map(
                        (exception) => `
                          <li>
                            <span>${escapeHtml(exception.reason)}</span>
                            <strong>${escapeHtml(exception.expires_at ?? "no expiry")}</strong>
                          </li>
                        `
                      )
                      .join("")}
                  </ul>`
                : '<small>none</small>'
            }
          </td>
          <td class="row-actions policy-binding-actions">
            <form data-policy-binding-promote-form data-binding-id="${escapeHtml(binding.id)}">
              <select name="mode" aria-label="Mode">
                ${["shadow", "audit-only", "enforce", "disabled"]
                  .map(
                    (mode) => `
                      <option value="${mode}" ${binding.mode === mode ? "selected" : ""}>${mode}</option>
                    `
                  )
                  .join("")}
              </select>
              <input name="rollout_percentage" type="number" min="0" max="100" value="${escapeHtml(String(binding.rollout_percentage))}" aria-label="Rollout percentage">
              <input name="reason" required placeholder="Reason" aria-label="Promotion reason">
              <button type="submit">Promote</button>
            </form>
            <button type="button" data-policy-exception-open="${escapeHtml(binding.id)}">Exception</button>
            <button type="button" data-policy-binding-delete="${escapeHtml(binding.id)}">Delete</button>
          </td>
        </tr>
      `;
    })
    .join("");
  return `
    <table class="data-table policy-binding-matrix" data-policy-binding-matrix>
      <thead>
        <tr>
          <th>Target</th>
          <th>Policy</th>
          <th>Mode</th>
          <th>Rollout</th>
          <th>Priority</th>
          <th>Status</th>
          <th>Exceptions</th>
          <th>Controls</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

export function renderPolicyBindingCreateForm({
  policies = [],
  selectedPolicy = null,
  targetOptions = []
} = {}) {
  const policyOptions = policies
    .map(
      (policy) => `
        <option value="${escapeHtml(policy.id)}" ${policy.id === selectedPolicy?.id ? "selected" : ""}>
          ${escapeHtml(policy.name)}
        </option>
      `
    )
    .join("");
  const versionOptions = (selectedPolicy?.versions ?? [])
    .map(
      (version) => `
        <option value="${escapeHtml(version.id)}" ${version.id === selectedPolicy?.active_version_id ? "selected" : ""}>
          v${escapeHtml(String(version.version_number))} - ${escapeHtml(version.status)}
        </option>
      `
    )
    .join("");
  return `
    <form class="policy-binding-create" data-policy-binding-create-form>
      <label>
        <span>Policy</span>
        <select name="policy_id" required>
          ${policyOptions || '<option value="">No policies</option>'}
        </select>
      </label>
      <label>
        <span>Version</span>
        <select name="policy_version_id">
          <option value="">Latest active</option>
          ${versionOptions}
        </select>
      </label>
      <label>
        <span>Target Type</span>
        <select name="target_type" required>
          ${["agent", "environment", "mcp-server", "mcp-tool", "runtime-action", "framework-connector", "discovery", "agent-group"]
            .map((targetType) => `<option value="${targetType}">${targetType}</option>`)
            .join("")}
        </select>
      </label>
      <label>
        <span>Target</span>
        <input name="target_id" list="policy-binding-target-options" required placeholder="agent id or resource key">
      </label>
      <label>
        <span>Mode</span>
        <select name="mode">
          <option value="shadow">shadow</option>
          <option value="audit-only">audit-only</option>
          <option value="enforce">enforce</option>
          <option value="disabled">disabled</option>
        </select>
      </label>
      <label>
        <span>Rollout</span>
        <input name="rollout_percentage" type="number" min="0" max="100" value="100">
      </label>
      <label>
        <span>Priority</span>
        <input name="priority" type="number" value="0">
      </label>
      <button type="submit">Create Binding</button>
      <datalist id="policy-binding-target-options">
        ${targetOptions
          .map(
            (option) => `
              <option value="${escapeHtml(option.id)}" label="${escapeHtml(option.label)}"></option>
            `
          )
          .join("")}
      </datalist>
    </form>
  `;
}

export function renderPolicyExceptionDialogs({ bindings = [], agents = [], environments = [] } = {}) {
  return bindings
    .map(
      (binding) => `
        <dialog class="policy-exception-dialog" data-policy-exception-modal="${escapeHtml(binding.id)}">
          <form method="dialog" class="dialog-close-row">
            <button type="submit" data-policy-exception-close="${escapeHtml(binding.id)}">Close</button>
          </form>
          <form data-policy-exception-form data-binding-id="${escapeHtml(binding.id)}">
            <h3>${escapeHtml(targetLabel(binding, { agents, environments }))}</h3>
            <label>
              <span>Reason</span>
              <input name="reason" required placeholder="Temporary business exception">
            </label>
            <label>
              <span>Expires At</span>
              <input name="expires_at" type="datetime-local">
            </label>
            <label>
              <span>Target Override</span>
              <input name="target_id" placeholder="${escapeHtml(binding.target_id)}">
            </label>
            <label>
              <span>Target Type</span>
              <select name="target_type">
                <option value="">Binding target</option>
                <option value="agent">agent</option>
                <option value="environment">environment</option>
                <option value="mcp-server">mcp-server</option>
                <option value="mcp-tool">mcp-tool</option>
                <option value="runtime-action">runtime-action</option>
                <option value="framework-connector">framework-connector</option>
                <option value="discovery">discovery</option>
                <option value="agent-group">agent-group</option>
              </select>
            </label>
            <label class="checkbox-row">
              <input name="no_expiry_approved" type="checkbox">
              <span>No Expiry Approved</span>
            </label>
            <button type="submit">Create Exception</button>
          </form>
        </dialog>
      `
    )
    .join("");
}

export function renderPolicyExportPanel(exported = null) {
  if (!exported) {
    return "";
  }
  return `
    <section class="workspace-panel policy-export" data-policy-export-panel>
      <header class="panel-header">
        <div>
          <p class="section-label">Export</p>
          <h2>${escapeHtml(exported.filename)}</h2>
        </div>
      </header>
      <pre><code>${escapeHtml(exported.body_text)}</code></pre>
    </section>
  `;
}

export function renderPolicySimulatorPanel({
  policies = [],
  selectedPolicy = null,
  result = null,
  error = null
} = {}) {
  const activePolicyId = selectedPolicy?.id ?? policies[0]?.id ?? "";
  const versions = selectedPolicy?.versions ?? [];
  return `
    <section class="workspace-panel policy-simulator" data-policy-simulator>
      <header class="panel-header">
        <div>
          <p class="section-label">Simulator</p>
          <h2>Policy Simulator</h2>
        </div>
      </header>
      <form class="policy-simulator-form" data-policy-simulator-form>
        <label>
          <span>Policy</span>
          <select name="policy_id">
            <option value="">Active binding</option>
            ${policies
              .map(
                (policy) => `
                  <option value="${escapeHtml(policy.id)}" ${policy.id === activePolicyId ? "selected" : ""}>${escapeHtml(policy.name)}</option>
                `
              )
              .join("")}
          </select>
        </label>
        <label>
          <span>Version</span>
          <select name="policy_version_id">
            <option value="">Latest active</option>
            ${versions
              .map(
                (version) => `
                  <option value="${escapeHtml(version.id)}" ${version.id === selectedPolicy?.active_version_id ? "selected" : ""}>v${escapeHtml(String(version.version_number))} - ${escapeHtml(version.status)}</option>
                `
              )
              .join("")}
          </select>
        </label>
        <label>
          <span>Target Type</span>
          <select name="target_type">
            <option value="">Policy version</option>
            <option value="agent">agent</option>
            <option value="environment">environment</option>
            <option value="mcp-tool">mcp-tool</option>
            <option value="runtime-action">runtime-action</option>
            <option value="framework-connector">framework-connector</option>
          </select>
        </label>
        <label>
          <span>Target</span>
          <input name="target_id" placeholder="target id">
        </label>
        <label>
          <span>Agent</span>
          <input name="agent_id" placeholder="agent id">
        </label>
        <label>
          <span>Action</span>
          <input name="action" required value="mcp.tool_call">
        </label>
        <label>
          <span>Resource Type</span>
          <input name="resource_type" placeholder="mcp-tool">
        </label>
        <label>
          <span>Resource</span>
          <input name="resource_id" placeholder="resource id">
        </label>
        <label class="full-width code-editor">
          <span>Context JSON</span>
          <textarea name="context_json" rows="7" spellcheck="false" data-policy-simulator-context>{}</textarea>
        </label>
        <button type="submit">Simulate</button>
        <output data-policy-simulator-error>${error ? escapeHtml(error) : ""}</output>
      </form>
      ${renderPolicyEvaluationResult(result)}
    </section>
  `;
}

export function renderPolicyEvaluationResult(evaluation = null) {
  if (!evaluation) {
    return `
      <section class="lint-panel" data-policy-simulator-result>
        <h3>Decision Result</h3>
        <div class="empty-state"><strong>No simulation</strong><span>Pending</span></div>
      </section>
    `;
  }
  return `
    <section class="lint-panel" data-policy-simulator-result="${escapeHtml(evaluation.id ?? "transient")}">
      <h3>Decision Result</h3>
      <ul class="compact-list">
        <li><span>Decision</span><strong>${escapeHtml(evaluation.decision)}</strong></li>
        <li><span>Mode</span><strong>${escapeHtml(evaluation.mode)}</strong></li>
        <li><span>Matched Rule</span><strong>${escapeHtml(evaluation.matched_rule ?? "default")}</strong></li>
        <li><span>Latency</span><strong>${escapeHtml(String(evaluation.latency_ms ?? 0))}ms</strong></li>
      </ul>
      <p class="drawer-state ${evaluation.decision === "deny" ? "is-warning" : ""}">${escapeHtml(evaluation.reason ?? "")}</p>
    </section>
  `;
}

export function renderPolicyEvaluationFeed({
  evaluations = [],
  summary = null,
  filters = {},
  selectedEvaluation = null
} = {}) {
  return `
    <section class="workspace-panel policy-evaluation-feed" data-policy-evaluation-feed>
      <header class="panel-header">
        <div>
          <p class="section-label">Evaluation Feed</p>
          <h2>Policy Decisions</h2>
        </div>
      </header>
      ${renderPolicyEvaluationSummary(summary)}
      ${renderPolicyEvaluationFilter(filters)}
      ${
        evaluations.length
          ? renderPolicyEvaluationTable(evaluations)
          : '<div class="empty-state" data-policy-evaluation-empty><strong>No decisions</strong><span>Run simulator</span></div>'
      }
      ${renderPolicyEvaluationDetail(selectedEvaluation)}
    </section>
  `;
}

export function renderPolicyEvaluationSummary(summary = null) {
  if (!summary) {
    return `
      <section class="lint-panel" data-policy-evaluation-summary>
        <h3>Decision Trends</h3>
        <div class="empty-state"><strong>No summary</strong><span>Pending</span></div>
      </section>
    `;
  }
  const buckets = summary.time_buckets ?? [];
  return `
    <section class="lint-panel policy-evaluation-summary" data-policy-evaluation-summary>
      <h3>Decision Trends</h3>
      <ul class="compact-list">
        <li><span>Total</span><strong>${escapeHtml(String(summary.total_count ?? 0))}</strong></li>
        <li><span>Decisions</span><strong>${renderInlineCountMap(summary.decision_counts)}</strong></li>
        <li><span>Modes</span><strong>${renderInlineCountMap(summary.mode_counts)}</strong></li>
        <li><span>Actions</span><strong>${renderInlineCountMap(summary.action_counts)}</strong></li>
      </ul>
      <div class="summary-grid" data-policy-evaluation-trends>
        ${
          buckets.length
            ? buckets
                .map(
                  (bucket) => `
                    <div class="summary-metric" data-policy-evaluation-trend="${escapeHtml(bucket.bucket)}">
                      <strong>${escapeHtml(bucket.bucket)}</strong>
                      <span>${escapeHtml(String(bucket.total_count ?? 0))} decisions</span>
                      <small>${renderInlineCountMap(bucket.decision_counts)}</small>
                    </div>
                  `
                )
                .join("")
            : '<div class="empty-state"><strong>No trend data</strong><span>Run simulator</span></div>'
        }
      </div>
    </section>
  `;
}

export function renderPolicyEvaluationFilter(filters = {}) {
  return `
    <form class="filter-bar" data-policy-evaluation-filter>
      <label>
        <span>Decision</span>
        <select name="decision">
          <option value="">Any</option>
          <option value="allow" ${filters.decision === "allow" ? "selected" : ""}>allow</option>
          <option value="deny" ${filters.decision === "deny" ? "selected" : ""}>deny</option>
        </select>
      </label>
      <label>
        <span>Mode</span>
        <select name="mode">
          <option value="">Any</option>
          <option value="simulate" ${filters.mode === "simulate" ? "selected" : ""}>simulate</option>
          <option value="live" ${filters.mode === "live" ? "selected" : ""}>live</option>
        </select>
      </label>
      <label>
        <span>Agent</span>
        <input name="agent_id" value="${escapeHtml(filters.agent_id ?? "")}" placeholder="agent id">
      </label>
      <label>
        <span>Action</span>
        <input name="action" value="${escapeHtml(filters.action ?? "")}" placeholder="mcp.tool_call">
      </label>
      <label>
        <span>Policy</span>
        <input name="policy_id" value="${escapeHtml(filters.policy_id ?? "")}" placeholder="policy id">
      </label>
      <label>
        <span>Correlation</span>
        <input name="correlation_id" value="${escapeHtml(filters.correlation_id ?? "")}" placeholder="correlation id">
      </label>
      <button type="submit">Filter</button>
    </form>
  `;
}

export function renderPolicyEvaluationTable(evaluations = []) {
  const rows = evaluations
    .map(
      (evaluation) => `
        <tr data-policy-evaluation-row="${escapeHtml(evaluation.id)}">
          <td><span class="status-pill">${escapeHtml(evaluation.decision)}</span><small>${escapeHtml(evaluation.mode)}</small></td>
          <td><strong>${escapeHtml(evaluation.action)}</strong><small>${escapeHtml(evaluation.agent_id ?? "no agent")}</small></td>
          <td>${escapeHtml(evaluation.policy_id ?? evaluation.backend ?? "unbound")}</td>
          <td>${escapeHtml(evaluation.matched_rule ?? "default")}</td>
          <td>${escapeHtml(String(evaluation.latency_ms ?? 0))}ms</td>
          <td>${escapeHtml(evaluation.correlation_id ?? "none")}</td>
          <td class="row-actions">
            <button type="button" data-policy-evaluation-open="${escapeHtml(evaluation.id)}">Open</button>
          </td>
        </tr>
      `
    )
    .join("");
  return `
    <table class="data-table" data-policy-evaluation-table>
      <thead>
        <tr>
          <th>Decision</th>
          <th>Action</th>
          <th>Policy</th>
          <th>Rule</th>
          <th>Latency</th>
          <th>Correlation</th>
          <th>Detail</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

export function renderPolicyEvaluationDetail(evaluation = null) {
  if (!evaluation) {
    return "";
  }
  return `
    <section class="drawer-panel" data-policy-evaluation-detail="${escapeHtml(evaluation.id)}">
      <header class="panel-header">
        <div>
          <p class="section-label">Decision Detail</p>
          <h3>${escapeHtml(evaluation.decision)} - ${escapeHtml(evaluation.action)}</h3>
        </div>
        <span class="status-pill">${escapeHtml(evaluation.backend)}</span>
      </header>
      <ul class="compact-list">
        <li><span>Reason</span><strong>${escapeHtml(evaluation.reason)}</strong></li>
        <li><span>Policy</span><strong>${escapeHtml(evaluation.policy_id ?? "unbound")}</strong></li>
        <li><span>Version</span><strong>${escapeHtml(evaluation.policy_version_id ?? "n/a")}</strong></li>
        <li><span>Resource</span><strong>${escapeHtml(evaluation.resource_type ?? "n/a")} / ${escapeHtml(evaluation.resource_id ?? "n/a")}</strong></li>
      </ul>
      <pre><code>${escapeHtml(JSON.stringify(evaluation.context ?? {}, null, 2))}</code></pre>
    </section>
  `;
}

export function policyFilterParamsFromValues(values = {}) {
  return cleanParams({
    scope: values.scope,
    owner_user_id: values.owner_user_id,
    backend: values.backend,
    status: values.status,
    tag: values.tag
  });
}

export function policyFilterParamsFromForm(form) {
  return policyFilterParamsFromValues(Object.fromEntries(new FormData(form)));
}

export function policyImportPayloadFromValues(values = {}) {
  const tags = String(values.tags ?? "")
    .split(",")
    .map((tag) => tag.trim())
    .filter(Boolean);
  return cleanParams({
    name: values.name,
    source_path: values.source_path,
    body_format: values.body_format || "yaml",
    body_text: values.body_text,
    scope: values.scope || "agent",
    backend: values.backend || "native",
    tags
  });
}

export function policyImportPayloadFromForm(form) {
  return policyImportPayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function policyEditorPayloadFromValues(values = {}) {
  return cleanParams({
    body_format: values.body_format || "yaml",
    body_text: values.body_text,
    backend: values.backend || "native"
  });
}

export function policyEditorPayloadFromForm(form) {
  return policyEditorPayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function policyBindingPayloadFromValues(values = {}) {
  return cleanParams({
    policy_id: values.policy_id,
    policy_version_id: values.policy_version_id,
    target_type: values.target_type || "agent",
    target_id: values.target_id,
    mode: values.mode || "shadow",
    rollout_percentage: numericValue(values.rollout_percentage, 100),
    priority: numericValue(values.priority, 0)
  });
}

export function policyBindingPayloadFromForm(form) {
  return policyBindingPayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function policyPromotePayloadFromValues(values = {}) {
  return cleanParams({
    mode: values.mode,
    rollout_percentage: numericValue(values.rollout_percentage, null),
    reason: values.reason
  });
}

export function policyPromotePayloadFromForm(form) {
  return policyPromotePayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function policyExceptionPayloadFromValues(values = {}) {
  return cleanParams({
    target_type: values.target_type,
    target_id: values.target_id,
    reason: values.reason,
    expires_at: datetimeLocalToIso(values.expires_at),
    approved_by: values.approved_by,
    no_expiry_approved: values.no_expiry_approved === true || values.no_expiry_approved === "on"
  });
}

export function policyExceptionPayloadFromForm(form) {
  return policyExceptionPayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function policyEvaluationPayloadFromValues(values = {}) {
  return cleanParams({
    policy_id: values.policy_id,
    policy_version_id: values.policy_version_id,
    target_type: values.target_type,
    target_id: values.target_id,
    agent_id: values.agent_id,
    action: values.action,
    resource_type: values.resource_type,
    resource_id: values.resource_id,
    context: parseContextJson(values.context_json)
  });
}

export function policyEvaluationPayloadFromForm(form) {
  return policyEvaluationPayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function policyEvaluationFilterParamsFromValues(values = {}) {
  return cleanParams({
    decision: values.decision,
    mode: values.mode,
    agent_id: values.agent_id,
    action: values.action,
    policy_id: values.policy_id,
    correlation_id: values.correlation_id
  });
}

export function policyEvaluationFilterParamsFromForm(form) {
  return policyEvaluationFilterParamsFromValues(Object.fromEntries(new FormData(form)));
}

export function policyEvaluationMatchesFilters(evaluation = {}, filters = {}) {
  return ["decision", "mode", "agent_id", "action", "policy_id", "correlation_id"].every((key) => {
    if (!filters[key]) {
      return true;
    }
    return evaluation[key] === filters[key];
  });
}

export function upsertPolicyEvaluationFeed(evaluations = [], evaluation = null, limit = 50) {
  if (!evaluation?.id) {
    return evaluations;
  }
  return [
    evaluation,
    ...evaluations.filter((existing) => existing.id !== evaluation.id)
  ].slice(0, limit);
}

export function backendHint(backend) {
  if (backend === "opa") {
    return "OPA/Rego backend selected.";
  }
  if (backend === "cedar") {
    return "Cedar authorization backend selected.";
  }
  return "Native YAML/JSON evaluator selected.";
}

function renderInlineCountMap(counts = {}) {
  const entries = Object.entries(counts ?? {});
  if (!entries.length) {
    return "none";
  }
  return entries
    .map(([key, value]) => `${escapeHtml(key)}: ${escapeHtml(String(value))}`)
    .join(", ");
}

function cleanParams(values) {
  return Object.fromEntries(
    Object.entries(values).filter(([, value]) => {
      if (Array.isArray(value)) {
        return value.length > 0;
      }
      return value !== undefined && value !== null && value !== "";
    })
  );
}

function numericValue(value, fallback) {
  if (value === undefined || value === null || value === "") {
    return fallback;
  }
  return Number(value);
}

function datetimeLocalToIso(value) {
  if (!value) {
    return null;
  }
  const text = String(value);
  if (text.endsWith("Z") || /[+-]\d\d:\d\d$/.test(text)) {
    return text;
  }
  return `${text}:00+00:00`;
}

function parseContextJson(value) {
  const text = String(value ?? "{}").trim() || "{}";
  try {
    const parsed = JSON.parse(text);
    if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
      throw new Error("Context JSON must be an object.");
    }
    return parsed;
  } catch (error) {
    throw new Error(error?.message ?? "Context JSON is invalid.");
  }
}

function bindingTargetOptions({ agents = [], environments = [] } = {}) {
  return [
    ...agents.map((agent) => ({
      id: agent.id,
      label: `${agent.name ?? agent.id} - agent`
    })),
    ...environments.map((environment) => ({
      id: environment.id,
      label: `${environment.name ?? environment.id} - environment`
    }))
  ];
}

function targetLabel(binding, { agents = [], environments = [] } = {}) {
  if (binding.target_type === "agent") {
    return agents.find((agent) => agent.id === binding.target_id)?.name ?? binding.target_id;
  }
  if (binding.target_type === "environment") {
    return environments.find((environment) => environment.id === binding.target_id)?.name ?? binding.target_id;
  }
  return binding.target_id;
}
