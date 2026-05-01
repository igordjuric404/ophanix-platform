import { escapeHtml } from "./html.js";

export function renderDemoLabPage(state = {}) {
  const scenarios = state.demoScenarios ?? [];
  const selectedScenario = state.selectedDemoScenario ?? scenarios[0] ?? null;
  const selectedRun = state.selectedDemoRun ?? null;
  const baselineStatus = state.demoBaselineStatus ?? null;
  const resetRuns = state.demoResetRuns ?? [];
  return `
    <section class="page-heading" data-route-page="/demo-lab">
      <p class="section-label">Automation</p>
      <h1>Demo Lab</h1>
      <p>Run governed scenarios and inspect live proof across the product workspace.</p>
    </section>
    <section class="demo-lab-workspace" aria-label="Demo Lab workspace">
      ${renderDemoPrerequisites({ baselineStatus })}
      ${renderDemoResetPanel({ resetRuns })}
      ${renderDemoScenarioCatalog({ scenarios, selectedScenario })}
      ${renderDemoScenarioDetail({ scenario: selectedScenario })}
      ${renderDemoRunTimeline({ run: selectedRun })}
      ${renderDemoProofChecklist({ stepRuns: selectedRun?.step_runs ?? [] })}
    </section>
  `;
}

export function renderDemoResetPanel({ resetRuns = [] } = {}) {
  const latestReset = resetRuns[0] ?? null;
  return `
    <article class="workspace-panel demo-reset-panel" data-demo-reset-panel>
      <header class="panel-header">
        <div>
          <p class="section-label">Reset</p>
          <h2>Environment Reset</h2>
        </div>
      </header>
      <dl class="metadata-grid" data-demo-reset-scope>
        <dt>Clears</dt><dd>demo_step_runs, demo_runs, demo-lab audit events</dd>
        <dt>Preserves</dt><dd>users, organizations, environments, provider credentials</dd>
      </dl>
      <form class="inline-form" data-demo-reset-form>
        <label>
          <span>Confirmation</span>
          <input name="confirmation" data-demo-reset-confirmation autocomplete="off" pattern="RESET" required />
        </label>
        <button type="submit" data-demo-reset-submit>Reset</button>
      </form>
      ${renderDemoResetResult({ resetRun: latestReset })}
    </article>
  `;
}

export function renderDemoResetResult({ resetRun = null } = {}) {
  if (!resetRun) {
    return `
      <div class="empty-state" data-demo-reset-result>
        <strong>No reset run</strong><span>Baseline fixtures are ready for the first reset</span>
      </div>
    `;
  }
  const summary = resetRun.summary ?? {};
  const cleared = summary.cleared ?? {};
  const seeded = summary.seeded ?? {};
  return `
    <div class="result-summary" data-demo-reset-result="${escapeHtml(resetRun.id)}" data-demo-reset-progress="${escapeHtml(resetRun.status)}">
      <dl class="metadata-grid">
        <dt>Status</dt><dd>${escapeHtml(resetRun.status)}</dd>
        <dt>Started</dt><dd>${escapeHtml(resetRun.started_at)}</dd>
        <dt>Finished</dt><dd>${escapeHtml(resetRun.finished_at ?? "running")}</dd>
      </dl>
      <table class="data-table">
        <thead><tr><th>Area</th><th>Count</th></tr></thead>
        <tbody>
          ${resetSummaryRow("Cleared demo runs", cleared.demo_runs)}
          ${resetSummaryRow("Cleared step runs", cleared.demo_step_runs)}
          ${resetSummaryRow("Cleared audit events", cleared.demo_lab_audit_events)}
          ${resetSummaryRow("Seed policies", seeded.policy_placeholders)}
          ${resetSummaryRow("Seed scenarios", seeded.demo_scenarios)}
          ${resetSummaryRow("Seed steps", seeded.demo_steps)}
        </tbody>
      </table>
      <a href="#scenario-catalog" data-demo-reset-catalog-link>Scenario Catalog</a>
    </div>
  `;
}

export function demoResetPayloadFromForm(form) {
  const confirmation = String(form.elements.namedItem("confirmation")?.value ?? "").trim();
  if (confirmation !== "RESET") {
    throw new Error("Type RESET to confirm demo reset.");
  }
  return { confirmation };
}

function resetSummaryRow(label, value) {
  return `
    <tr data-demo-reset-summary-row="${escapeHtml(label.toLowerCase().replaceAll(" ", "-"))}">
      <td>${escapeHtml(label)}</td>
      <td>${escapeHtml(String(value ?? 0))}</td>
    </tr>
  `;
}

export function renderDemoPrerequisites({ baselineStatus = null } = {}) {
  const checks = baselineStatus?.checks ?? [];
  const rows = checks
    .map(
      (check) => `
        <tr data-demo-baseline-check="${escapeHtml(check.key)}" data-demo-baseline-status="${escapeHtml(check.status)}">
          <td><strong>${escapeHtml(check.label)}</strong><small>${escapeHtml(check.required ? "required" : "optional")}</small></td>
          <td><span class="status-pill">${escapeHtml(check.status)}</span></td>
          <td>${escapeHtml(String(check.count ?? 0))}${check.expected_count ? `/${escapeHtml(String(check.expected_count))}` : ""}</td>
          <td>${escapeHtml(check.detail)}</td>
          <td>${escapeHtml((check.missing ?? []).join(", "))}</td>
        </tr>
      `
    )
    .join("");
  return `
    <article class="workspace-panel demo-prerequisites" data-demo-prerequisites-panel>
      <header class="panel-header">
        <div>
          <p class="section-label">Prerequisites</p>
          <h2>Baseline</h2>
        </div>
        <span class="status-pill" data-demo-baseline-overall="${escapeHtml(baselineStatus?.overall_status ?? "unknown")}">${escapeHtml(baselineStatus?.overall_status ?? "unknown")}</span>
      </header>
      ${
        rows
          ? `<table class="data-table">
              <thead><tr><th>Check</th><th>Status</th><th>Count</th><th>Detail</th><th>Missing</th></tr></thead>
              <tbody>${rows}</tbody>
            </table>`
          : '<div class="empty-state"><strong>No baseline status</strong><span>Refresh Demo Lab after seeding the environment</span></div>'
      }
    </article>
  `;
}

export function renderDemoScenarioCatalog({ scenarios = [], selectedScenario = null } = {}) {
  const rows = scenarios
    .map(
      (scenario) => `
        <tr data-demo-scenario-row="${escapeHtml(scenario.id)}">
          <td><strong>${escapeHtml(scenario.name)}</strong><small>${escapeHtml(scenario.slug)}</small></td>
          <td><span class="status-pill">${escapeHtml(scenario.status)}</span></td>
          <td>${escapeHtml(String(scenario.required_services?.length ?? 0))}</td>
          <td><button type="button" data-demo-scenario-open="${escapeHtml(scenario.id)}" ${selectedScenario?.id === scenario.id ? "disabled" : ""}>Open</button></td>
        </tr>
      `
    )
    .join("");
  return `
    <article id="scenario-catalog" class="workspace-panel demo-scenario-catalog" data-demo-scenario-catalog>
      <header class="panel-header">
        <div>
          <p class="section-label">Catalog</p>
          <h2>Scenario Catalog</h2>
        </div>
      </header>
      ${
        scenarios.length
          ? `<table class="data-table">
              <thead><tr><th>Scenario</th><th>Status</th><th>Services</th><th></th></tr></thead>
              <tbody>${rows}</tbody>
            </table>`
          : '<div class="empty-state"><strong>No scenarios</strong><span>Seed Demo Lab scenarios to begin</span></div>'
      }
    </article>
  `;
}

export function renderDemoScenarioDetail({ scenario = null } = {}) {
  if (!scenario) {
    return `
      <article class="workspace-panel demo-scenario-detail" data-demo-scenario-detail>
        <header class="panel-header">
          <div>
            <p class="section-label">Scenario</p>
            <h2>Details</h2>
          </div>
        </header>
        <div class="empty-state"><strong>No scenario selected</strong><span>Open a scenario from the catalog</span></div>
      </article>
    `;
  }
  const serviceItems = (scenario.required_services ?? [])
    .map(
      (service) => `
        <li data-demo-required-service="${escapeHtml(service.key)}">
          <span>${escapeHtml(service.label)}</span>
          <strong>${escapeHtml(service.required ? "required" : "optional")}</strong>
        </li>
      `
    )
    .join("");
  const stepRows = (scenario.steps ?? [])
    .map(
      (step) => `
        <tr data-demo-step-row="${escapeHtml(step.id)}">
          <td>${escapeHtml(String(step.step_order))}</td>
          <td><strong>${escapeHtml(step.title)}</strong><small>${escapeHtml(step.action_type)}</small></td>
          <td>${escapeHtml(step.expected_result)}</td>
        </tr>
      `
    )
    .join("");
  return `
    <article class="workspace-panel demo-scenario-detail" data-demo-scenario-detail="${escapeHtml(scenario.id)}">
      <header class="panel-header">
        <div>
          <p class="section-label">Scenario</p>
          <h2>${escapeHtml(scenario.name)}</h2>
        </div>
        <button type="button" data-demo-run-start="${escapeHtml(scenario.id)}">Start</button>
      </header>
      <p>${escapeHtml(scenario.description)}</p>
      <dl class="metadata-grid">
        <dt>Value Proof</dt><dd>${escapeHtml(scenario.value_proof)}</dd>
      </dl>
      <ul class="status-list" data-demo-prerequisites>${serviceItems}</ul>
      ${
        stepRows
          ? `<table class="data-table">
              <thead><tr><th>#</th><th>Step</th><th>Expected</th></tr></thead>
              <tbody>${stepRows}</tbody>
            </table>`
          : '<div class="empty-state"><strong>No steps</strong><span>Scenario definition is incomplete</span></div>'
      }
    </article>
  `;
}

export function renderDemoRunTimeline({ run = null } = {}) {
  if (!run) {
    return `
      <article class="workspace-panel demo-run-timeline" data-demo-run-timeline>
        <header class="panel-header">
          <div>
            <p class="section-label">Runner</p>
            <h2>Run Timeline</h2>
          </div>
        </header>
        <div class="empty-state"><strong>No active run</strong><span>Start a scenario to execute steps</span></div>
      </article>
    `;
  }
  const terminal = ["succeeded", "failed", "canceled"].includes(run.status);
  const rows = (run.step_runs ?? [])
    .map((stepRun) => {
      const proof = stepRun.proof_checklist?.[0] ?? {};
      const expected = stepRun.step?.expected_result ?? proof.expected_result ?? "";
      const actual = stepRun.actual_result ?? proof.actual_result ?? "pending";
      return `
        <tr data-demo-step-run-row="${escapeHtml(stepRun.id)}" data-demo-step-run-status="${escapeHtml(stepRun.status)}">
          <td><strong>${escapeHtml(stepRun.step?.title ?? stepRun.demo_step_id)}</strong><small>${escapeHtml(stepRun.step?.action_type ?? stepRun.demo_step_id)}</small></td>
          <td><span class="status-pill">${escapeHtml(stepRun.status)}</span></td>
          <td>${escapeHtml(expected)}</td>
          <td>${escapeHtml(actual)}</td>
        </tr>
      `;
    })
    .join("");
  return `
    <article class="workspace-panel demo-run-timeline" data-demo-run-timeline="${escapeHtml(run.id)}">
      <header class="panel-header">
        <div>
          <p class="section-label">Runner</p>
          <h2>Run Timeline</h2>
        </div>
        <div class="button-row">
          <button type="button" data-demo-run-continue="${escapeHtml(run.id)}" ${terminal ? "disabled" : ""}>Continue</button>
          <button type="button" data-demo-run-cancel="${escapeHtml(run.id)}" ${terminal ? "disabled" : ""}>Cancel</button>
        </div>
      </header>
      <dl class="metadata-grid">
        <dt>Status</dt><dd>${escapeHtml(run.status)}</dd>
        <dt>Started</dt><dd>${escapeHtml(run.started_at)}</dd>
        <dt>Completed</dt><dd>${escapeHtml(String(run.summary?.completed_steps ?? 0))}/${escapeHtml(String(run.summary?.total_steps ?? 0))}</dd>
      </dl>
      <table class="data-table">
        <thead><tr><th>Step</th><th>Status</th><th>Expected</th><th>Actual</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </article>
  `;
}

export function renderDemoProofChecklist({ stepRuns = [] } = {}) {
  const items = stepRuns.flatMap((stepRun) =>
    (stepRun.proof_checklist ?? []).map((item) => ({
      ...item,
      step_title: stepRun.step?.title ?? stepRun.demo_step_id,
      step_status: stepRun.status
    }))
  );
  if (!items.length) {
    return `
      <article class="workspace-panel demo-proof-checklist" data-demo-proof-checklist>
        <header class="panel-header">
          <div>
            <p class="section-label">Evidence</p>
            <h2>Proof Checklist</h2>
          </div>
        </header>
        <div class="empty-state"><strong>No proof yet</strong><span>Run scenario steps to collect evidence</span></div>
      </article>
    `;
  }
  const rows = items
    .map(
      (item) => `
        <tr data-demo-proof-item="${escapeHtml(item.status)}">
          <td><strong>${escapeHtml(item.step_title)}</strong><small>${escapeHtml(item.area)}</small></td>
          <td><span class="status-pill">${escapeHtml(proofStatusLabel(item.status))}</span></td>
          <td>${escapeHtml(item.expected_result)}</td>
          <td>${escapeHtml(item.actual_result ?? "pending")}</td>
          <td><a href="${escapeHtml(item.route)}">${escapeHtml(item.label)}</a></td>
        </tr>
      `
    )
    .join("");
  return `
    <article class="workspace-panel demo-proof-checklist" data-demo-proof-checklist>
      <header class="panel-header">
        <div>
          <p class="section-label">Evidence</p>
          <h2>Proof Checklist</h2>
        </div>
      </header>
      <table class="data-table">
        <thead><tr><th>Step</th><th>Status</th><th>Expected</th><th>Actual</th><th>Evidence</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </article>
  `;
}

export function proofStatusLabel(status) {
  return {
    completed: "completed",
    failed: "failed",
    canceled: "canceled",
    pending: "pending"
  }[status] ?? "pending";
}
