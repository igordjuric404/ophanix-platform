import { escapeHtml } from "./html.js";

export function renderObservabilityPage(state) {
  const slos = state?.observabilitySlos ?? [];
  const costs = state?.observabilityCosts ?? { budgets: [], events: [], total_amount: 0, by_target: {}, by_provider: {}, by_model: {} };
  const incidents = state?.observabilityIncidents ?? [];
  const chaosExperiments = state?.observabilityChaosExperiments ?? [];
  const chaosRuns = state?.observabilityChaosRuns ?? [];
  const rollouts = state?.observabilityRollouts ?? [];
  return `
    <section class="page-heading" data-route-page="/observability">
      <p class="section-label">Operations</p>
      <h1>Observability</h1>
      <p>SLOs, costs, incidents, telemetry, and operational health.</p>
    </section>
    <section class="observability-workspace" aria-label="Observability workspace">
      ${renderObservabilityOverview({ slos, costs, incidents })}
      ${renderSloPanel({ slos })}
      ${renderCostPanel({ costs })}
      ${renderIncidentPanel({ incidents })}
      ${renderChaosPanel({ experiments: chaosExperiments, runs: chaosRuns })}
      ${renderRolloutPanel({ rollouts })}
    </section>
  `;
}

export function renderObservabilityOverview({ slos = [], costs = {}, incidents = [] } = {}) {
  const unhealthySlos = slos.filter((slo) => !["healthy", "unknown"].includes(slo.status)).length;
  const breachedBudgets = (costs.budgets ?? []).filter((budget) => budget.status === "breached").length;
  const openIncidents = incidents.filter((incident) => incident.status !== "resolved").length;
  return `
    <article class="workspace-panel observability-overview" data-observability-overview>
      <div class="metric-grid">
        <div><span>SLOs at risk</span><strong>${escapeHtml(String(unhealthySlos))}</strong></div>
        <div><span>Cost total</span><strong>${escapeHtml(formatMoney(costs.total_amount ?? 0))}</strong></div>
        <div><span>Budget breaches</span><strong>${escapeHtml(String(breachedBudgets))}</strong></div>
        <div><span>Open incidents</span><strong>${escapeHtml(String(openIncidents))}</strong></div>
      </div>
    </article>
  `;
}

export function renderSloPanel({ slos = [] } = {}) {
  const rows = slos
    .map((slo) => {
      const latest = slo.measurements?.[0] ?? null;
      return `
        <tr data-observability-slo-row="${escapeHtml(slo.id)}">
          <td><strong>${escapeHtml(slo.name)}</strong><small>${escapeHtml(`${slo.target_type}:${slo.target_id}`)}</small></td>
          <td>${escapeHtml(slo.sli)}</td>
          <td>${escapeHtml(String(slo.target_value))}</td>
          <td><span class="status-pill">${escapeHtml(slo.status)}</span></td>
          <td>${escapeHtml(String(latest?.burn_rate ?? 0))}</td>
          <td>${escapeHtml(String(latest?.error_budget_remaining ?? 0))}</td>
        </tr>
      `;
    })
    .join("");
  return `
    <article class="workspace-panel observability-slos" data-observability-slos>
      <header class="panel-header">
        <div>
          <p class="section-label">SLOs</p>
          <h2>SLO Objectives</h2>
        </div>
      </header>
      <form class="bridge-form-grid" data-observability-slo-form>
        <label><span>Name</span><input name="name" required></label>
        <label><span>Target Type</span><input name="target_type" value="agent" required></label>
        <label><span>Target ID</span><input name="target_id" required></label>
        <label><span>SLI</span><input name="sli" value="task_success_rate" required></label>
        <label><span>Target</span><input name="target_value" type="number" step="0.001" value="0.99" required></label>
        <label><span>Window</span><input name="window" value="30d" required></label>
        <button type="submit">Create SLO</button>
      </form>
      ${
        slos.length
          ? `<table class="data-table" data-observability-slo-chart>
              <thead><tr><th>SLO</th><th>SLI</th><th>Target</th><th>Status</th><th>Burn Rate</th><th>Budget</th></tr></thead>
              <tbody>${rows}</tbody>
            </table>`
          : '<div class="empty-state" data-observability-slo-empty><strong>No SLOs</strong><span>Create an objective</span></div>'
      }
    </article>
  `;
}

export function renderCostPanel({ costs = {} } = {}) {
  const budgets = costs.budgets ?? [];
  const events = costs.events ?? [];
  const budgetRows = budgets
    .map(
      (budget) => `
        <tr data-observability-cost-budget-row="${escapeHtml(budget.id)}">
          <td><strong>${escapeHtml(`${budget.target_type}:${budget.target_id}`)}</strong><small>${escapeHtml(budget.period)}</small></td>
          <td>${escapeHtml(formatMoney(budget.used_amount))} / ${escapeHtml(formatMoney(budget.amount_limit))}</td>
          <td><span class="status-pill">${escapeHtml(budget.status)}</span></td>
          <td>${escapeHtml(budget.breach_action)}</td>
        </tr>
      `
    )
    .join("");
  return `
    <article class="workspace-panel observability-costs" data-observability-costs>
      <header class="panel-header">
        <div>
          <p class="section-label">Costs</p>
          <h2>Cost Budgets</h2>
        </div>
      </header>
      <form class="bridge-form-grid" data-observability-cost-budget-form>
        <label><span>Target Type</span><input name="target_type" value="agent" required></label>
        <label><span>Target ID</span><input name="target_id" required></label>
        <label><span>Period</span><input name="period" value="monthly" required></label>
        <label><span>Limit</span><input name="amount_limit" type="number" step="0.01" value="100" required></label>
        <label><span>Breach Action</span><select name="action_on_breach"><option>warn</option><option>throttle</option><option>kill_switch</option></select></label>
        <button type="submit">Create Budget</button>
      </form>
      <form class="bridge-form-grid" data-observability-cost-event-form>
        <label><span>Target Type</span><input name="target_type" value="agent" required></label>
        <label><span>Target ID</span><input name="target_id" required></label>
        <label><span>Provider</span><input name="provider" required></label>
        <label><span>Model</span><input name="model" required></label>
        <label><span>Amount</span><input name="amount" type="number" step="0.0001" required></label>
        <label><span>Units</span><input name="units" type="number" step="1" value="1" required></label>
        <label><span>Correlation</span><input name="correlation_id"></label>
        <button type="submit">Record Cost</button>
      </form>
      ${renderCostRollups(costs)}
      ${
        budgets.length
          ? `<table class="data-table">
              <thead><tr><th>Budget</th><th>Used</th><th>Status</th><th>Action</th></tr></thead>
              <tbody>${budgetRows}</tbody>
            </table>`
          : '<div class="empty-state" data-observability-cost-budget-empty><strong>No budgets</strong><span>Create a budget</span></div>'
      }
      ${
        events.length
          ? `<p data-observability-cost-events-count>${escapeHtml(String(events.length))} recent cost events</p>`
          : '<div class="empty-state" data-observability-cost-empty><strong>No cost events</strong><span>Record model or tool usage</span></div>'
      }
    </article>
  `;
}

export function renderCostRollups(costs = {}) {
  const providerRows = Object.entries(costs.by_provider ?? {});
  const modelRows = Object.entries(costs.by_model ?? {});
  if (!providerRows.length && !modelRows.length) {
    return '<div class="empty-state" data-observability-cost-chart-empty><strong>No cost chart</strong><span>Cost events will populate rollups</span></div>';
  }
  return `
    <div class="observability-rollups" data-observability-cost-chart>
      <section>
        <h3>By Provider</h3>
        ${renderRollupBars(providerRows)}
      </section>
      <section>
        <h3>By Model</h3>
        ${renderRollupBars(modelRows)}
      </section>
    </div>
  `;
}

export function renderIncidentPanel({ incidents = [] } = {}) {
  const rows = incidents
    .map(
      (incident) => `
        <tr data-observability-incident-row="${escapeHtml(incident.id)}">
          <td><strong>${escapeHtml(incident.title)}</strong><small>${escapeHtml(incident.summary)}</small></td>
          <td><span class="status-pill">${escapeHtml(incident.severity)}</span></td>
          <td><span class="status-pill">${escapeHtml(incident.status)}</span></td>
          <td>${escapeHtml(incident.correlation_id ?? "none")}</td>
          <td>
            <button type="button" data-observability-incident-open="${escapeHtml(incident.id)}">Open</button>
            <button type="button" data-observability-incident-ack="${escapeHtml(incident.id)}" ${incident.status === "resolved" ? "disabled" : ""}>Ack</button>
            <form class="inline-actions" data-observability-incident-resolve-form data-incident-id="${escapeHtml(incident.id)}">
              <input name="resolution_note" placeholder="Resolution note" required>
              <button type="submit" ${incident.status === "resolved" ? "disabled" : ""}>Resolve</button>
            </form>
          </td>
        </tr>
      `
    )
    .join("");
  return `
    <article class="workspace-panel observability-incidents" data-observability-incidents>
      <header class="panel-header">
        <div>
          <p class="section-label">Incidents</p>
          <h2>Incident Queue</h2>
        </div>
      </header>
      <form class="bridge-form-grid" data-observability-incident-form>
        <label><span>Severity</span><select name="severity"><option>warning</option><option>critical</option><option>info</option></select></label>
        <label><span>Title</span><input name="title" required></label>
        <label><span>Summary</span><input name="summary" required></label>
        <label><span>Correlation</span><input name="correlation_id"></label>
        <button type="submit">Create Incident</button>
      </form>
      ${
        incidents.length
          ? `<table class="data-table">
              <thead><tr><th>Incident</th><th>Severity</th><th>Status</th><th>Correlation</th><th>Actions</th></tr></thead>
              <tbody>${rows}</tbody>
            </table>`
          : '<div class="empty-state" data-observability-incidents-empty><strong>No incidents</strong><span>Create or link incidents</span></div>'
      }
    </article>
  `;
}

export function renderIncidentDetail(incident = null) {
  if (!incident) {
    return "<p>No incident selected.</p>";
  }
  return `
    <dl class="detail-list" data-observability-incident-detail="${escapeHtml(incident.id)}">
      <div><dt>Severity</dt><dd>${escapeHtml(incident.severity)}</dd></div>
      <div><dt>Status</dt><dd>${escapeHtml(incident.status)}</dd></div>
      <div><dt>Owner</dt><dd>${escapeHtml(incident.owner_user_id ?? "unassigned")}</dd></div>
      <div><dt>Correlation</dt><dd>${escapeHtml(incident.correlation_id ?? "none")}</dd></div>
      <div><dt>Resolution</dt><dd>${escapeHtml(incident.resolution_note ?? "open")}</dd></div>
    </dl>
    ${renderTagList(incident.related_event_ids ?? [], "No related audit events")}
  `;
}

export function renderChaosPanel({ experiments = [], runs = [] } = {}) {
  const experimentRows = experiments
    .map(
      (experiment) => `
        <tr data-observability-chaos-row="${escapeHtml(experiment.id)}">
          <td><strong>${escapeHtml(experiment.name)}</strong><small>${escapeHtml(`${experiment.target_type}:${experiment.target_id}`)}</small></td>
          <td>${escapeHtml(experiment.fault_type)}</td>
          <td>${renderJsonSummary(experiment.blast_radius ?? {})}</td>
          <td>${renderJsonSummary(experiment.guardrails ?? {})}</td>
          <td><span class="status-pill">${escapeHtml(experiment.status)}</span></td>
          <td>
            <button type="button" data-observability-chaos-run-open="${escapeHtml(experiment.id)}">Run</button>
            ${renderChaosRunDialog(experiment)}
          </td>
        </tr>
      `
    )
    .join("");
  return `
    <article class="workspace-panel observability-chaos" data-observability-chaos>
      <header class="panel-header">
        <div>
          <p class="section-label">Chaos</p>
          <h2>Experiments</h2>
        </div>
      </header>
      <form class="bridge-form-grid" data-observability-chaos-experiment-form>
        <label><span>Name</span><input name="name" required></label>
        <label><span>Fault Type</span><select name="fault_type"><option>latency</option><option>error</option><option>timeout</option><option>trust_perturbation</option><option>policy_denial</option></select></label>
        <label><span>Target Type</span><input name="target_type" value="agent" required></label>
        <label><span>Target ID</span><input name="target_id" required></label>
        <label><span>Blast Radius JSON</span><textarea name="blast_radius_json" required>{"max_agents":1,"environment":"demo"}</textarea></label>
        <label><span>Guardrails JSON</span><textarea name="guardrails_json" required>{"max_error_rate":0.05,"max_duration_seconds":60}</textarea></label>
        <button type="submit">Create Experiment</button>
      </form>
      ${
        experiments.length
          ? `<table class="data-table">
              <thead><tr><th>Experiment</th><th>Fault</th><th>Blast Radius</th><th>Guardrails</th><th>Status</th><th>Actions</th></tr></thead>
              <tbody>${experimentRows}</tbody>
            </table>`
          : '<div class="empty-state" data-observability-chaos-empty><strong>No chaos experiments</strong><span>Create a guarded experiment</span></div>'
      }
      ${renderChaosRunDetail(runs[0] ?? null)}
    </article>
  `;
}

export function renderChaosRunDetail(run = null) {
  if (!run) {
    return '<div class="empty-state" data-observability-chaos-run-empty><strong>No recent run</strong><span>Run an experiment to inspect the result</span></div>';
  }
  const result = run.result ?? {};
  return `
    <section class="chaos-run-detail" data-observability-chaos-run-detail="${escapeHtml(run.id)}">
      <h3>Latest Run</h3>
      <dl class="detail-list">
        <div><dt>Status</dt><dd>${escapeHtml(run.status)}</dd></div>
        <div><dt>Experiment</dt><dd>${escapeHtml(run.experiment_id)}</dd></div>
        <div><dt>Guardrail</dt><dd>${escapeHtml(result.guardrail_breached ? "breached" : "clear")}</dd></div>
        <div><dt>Fault</dt><dd>${escapeHtml(result.fault_type ?? "unknown")}</dd></div>
      </dl>
      ${renderTagList(result.breached_guardrails ?? [], "No breached guardrails")}
    </section>
  `;
}

export function renderRolloutPanel({ rollouts = [] } = {}) {
  const rows = rollouts
    .map(
      (rollout) => `
        <tr data-observability-rollout-row="${escapeHtml(rollout.id)}">
          <td><strong>${escapeHtml(rollout.name)}</strong><small>${escapeHtml(`${rollout.target_type}:${rollout.target_id}`)}</small></td>
          <td>${escapeHtml(rollout.strategy)}</td>
          <td><span class="status-pill">${escapeHtml(rollout.status)}</span></td>
          <td>${renderRolloutTimeline(rollout)}</td>
          <td>${escapeHtml(rollout.events?.[0]?.decision ?? "created")}</td>
          <td>
            <button type="button" data-observability-rollout-advance-open="${escapeHtml(rollout.id)}">Advance</button>
            <button type="button" data-observability-rollout-rollback-open="${escapeHtml(rollout.id)}">Rollback</button>
            ${renderRolloutActionDialogs(rollout)}
          </td>
        </tr>
      `
    )
    .join("");
  return `
    <article class="workspace-panel observability-rollouts" data-observability-rollouts>
      <header class="panel-header">
        <div>
          <p class="section-label">Rollouts</p>
          <h2>Staged Rollouts</h2>
        </div>
      </header>
      <form class="bridge-form-grid" data-observability-rollout-form>
        <label><span>Name</span><input name="name" required></label>
        <label><span>Target Type</span><input name="target_type" value="agent" required></label>
        <label><span>Target ID</span><input name="target_id" required></label>
        <label><span>Strategy</span><select name="strategy"><option>canary</option><option>percentage</option></select></label>
        <label><span>Stages</span><input name="stages" value="5,25,100" required></label>
        <label><span>Gates JSON</span><textarea name="gates_json" required>{"require_slo_healthy":true,"block_on_open_incident":true}</textarea></label>
        <button type="submit">Create Rollout</button>
      </form>
      ${
        rollouts.length
          ? `<table class="data-table">
              <thead><tr><th>Rollout</th><th>Strategy</th><th>Status</th><th>Timeline</th><th>Latest Event</th><th>Actions</th></tr></thead>
              <tbody>${rows}</tbody>
            </table>`
          : '<div class="empty-state" data-observability-rollout-empty><strong>No rollouts</strong><span>Create a staged rollout</span></div>'
      }
    </article>
  `;
}

export function renderRolloutTimeline(rollout) {
  const stages = rolloutStages(rollout?.config ?? {}, rollout?.strategy ?? "canary");
  const currentStage = Number(rollout?.current_stage ?? 0);
  return `
    <ol class="rollout-timeline" data-observability-rollout-timeline="${escapeHtml(rollout?.id ?? "new")}">
      ${stages
        .map((stage) => {
          const state = stage <= currentStage ? "is-complete" : "is-pending";
          return `<li class="${state}" data-stage="${escapeHtml(String(stage))}"><span>${escapeHtml(String(stage))}%</span></li>`;
        })
        .join("")}
    </ol>
  `;
}

export function observabilitySloPayloadFromValues(values) {
  return {
    name: String(values.name ?? "").trim(),
    target_type: String(values.target_type ?? "agent").trim(),
    target_id: String(values.target_id ?? "").trim(),
    sli: String(values.sli ?? "task_success_rate").trim(),
    target_value: numberValue(values.target_value),
    window: String(values.window ?? "30d").trim()
  };
}

export function observabilitySloPayloadFromForm(form) {
  return observabilitySloPayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function observabilityCostBudgetPayloadFromValues(values) {
  return {
    target_type: String(values.target_type ?? "agent").trim(),
    target_id: String(values.target_id ?? "").trim(),
    period: String(values.period ?? "monthly").trim(),
    amount_limit: numberValue(values.amount_limit),
    action_on_breach: String(values.action_on_breach ?? "warn").trim()
  };
}

export function observabilityCostBudgetPayloadFromForm(form) {
  return observabilityCostBudgetPayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function observabilityCostEventPayloadFromValues(values) {
  return {
    target_type: String(values.target_type ?? "agent").trim(),
    target_id: String(values.target_id ?? "").trim(),
    provider: String(values.provider ?? "").trim(),
    model: String(values.model ?? "").trim(),
    amount: numberValue(values.amount),
    units: numberValue(values.units),
    correlation_id: optionalString(values.correlation_id)
  };
}

export function observabilityCostEventPayloadFromForm(form) {
  return observabilityCostEventPayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function observabilityIncidentPayloadFromValues(values) {
  return {
    severity: String(values.severity ?? "warning").trim(),
    title: String(values.title ?? "").trim(),
    summary: String(values.summary ?? "").trim(),
    correlation_id: optionalString(values.correlation_id)
  };
}

export function observabilityIncidentPayloadFromForm(form) {
  return observabilityIncidentPayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function observabilityIncidentResolvePayloadFromValues(values) {
  return {
    resolution_note: String(values.resolution_note ?? "").trim()
  };
}

export function observabilityIncidentResolvePayloadFromForm(form) {
  return observabilityIncidentResolvePayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function observabilityChaosExperimentPayloadFromValues(values) {
  return {
    name: String(values.name ?? "").trim(),
    fault_type: String(values.fault_type ?? "latency").trim(),
    target_type: String(values.target_type ?? "agent").trim(),
    target_id: String(values.target_id ?? "").trim(),
    blast_radius: parseJsonObject(values.blast_radius_json, { max_agents: 1, environment: "demo" }),
    guardrails: parseJsonObject(values.guardrails_json, { max_error_rate: 0.05 })
  };
}

export function observabilityChaosExperimentPayloadFromForm(form) {
  return observabilityChaosExperimentPayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function observabilityChaosRunPayloadFromValues(values) {
  const observedMetrics = {};
  for (const key of ["error_rate", "duration_seconds", "latency_ms", "trust_score"]) {
    if (optionalString(values[key]) !== null) {
      observedMetrics[key] = numberValue(values[key]);
    }
  }
  return {
    observed_metrics: observedMetrics,
    acknowledgement: values.acknowledge_blast_radius ? "blast-radius-acknowledged" : null
  };
}

export function observabilityChaosRunPayloadFromForm(form) {
  return observabilityChaosRunPayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function observabilityRolloutPayloadFromValues(values) {
  const strategy = String(values.strategy ?? "canary").trim();
  return {
    name: String(values.name ?? "").trim(),
    target_type: String(values.target_type ?? "agent").trim(),
    target_id: String(values.target_id ?? "").trim(),
    strategy,
    config: {
      stages: String(values.stages ?? "5,25,100")
        .split(",")
        .map((stage) => Number.parseInt(stage.trim(), 10))
        .filter((stage) => Number.isFinite(stage)),
      gates: parseJsonObject(values.gates_json, {})
    }
  };
}

export function observabilityRolloutPayloadFromForm(form) {
  return observabilityRolloutPayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function observabilityRolloutAdvancePayloadFromValues(values) {
  const metrics = {};
  if (optionalString(values.slo_status) !== null) {
    metrics.slo_status = String(values.slo_status).trim();
  }
  for (const key of ["policy_deny_rate", "trust_score", "open_incidents"]) {
    if (optionalString(values[key]) !== null) {
      metrics[key] = numberValue(values[key]);
    }
  }
  return { metrics };
}

export function observabilityRolloutAdvancePayloadFromForm(form) {
  return observabilityRolloutAdvancePayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function observabilityRolloutRollbackPayloadFromValues(values) {
  return {
    reason: String(values.reason ?? "").trim()
  };
}

export function observabilityRolloutRollbackPayloadFromForm(form) {
  return observabilityRolloutRollbackPayloadFromValues(Object.fromEntries(new FormData(form)));
}

function renderChaosRunDialog(experiment) {
  return `
    <dialog class="policy-exception-dialog mcp-action-dialog" data-observability-chaos-run-modal="${escapeHtml(experiment.id)}">
      <form method="dialog" class="dialog-close-row"><button type="submit">Close</button></form>
      <form data-observability-chaos-run-form data-experiment-id="${escapeHtml(experiment.id)}">
        <h3>${escapeHtml(experiment.name)}</h3>
        <label><span>Error Rate</span><input name="error_rate" type="number" step="0.001" value="0.01"></label>
        <label><span>Duration Seconds</span><input name="duration_seconds" type="number" step="1" value="10"></label>
        <label class="checkbox-row"><input type="checkbox" name="acknowledge_blast_radius" value="yes" required> Acknowledge blast radius</label>
        <button type="submit">Run Experiment</button>
      </form>
    </dialog>
  `;
}

function renderRolloutActionDialogs(rollout) {
  return `
    <dialog class="policy-exception-dialog mcp-action-dialog" data-observability-rollout-advance-modal="${escapeHtml(rollout.id)}">
      <form method="dialog" class="dialog-close-row"><button type="submit">Close</button></form>
      <form data-observability-rollout-advance-form data-rollout-id="${escapeHtml(rollout.id)}">
        <h3>${escapeHtml(rollout.name)}</h3>
        <label><span>SLO Status</span><input name="slo_status" value="healthy"></label>
        <label><span>Policy Deny Rate</span><input name="policy_deny_rate" type="number" step="0.001" value="0"></label>
        <label><span>Trust Score</span><input name="trust_score" type="number" step="1" value="1000"></label>
        <label><span>Open Incidents</span><input name="open_incidents" type="number" step="1" value="0"></label>
        <label class="checkbox-row"><input type="checkbox" name="confirm" value="yes" required> Confirm gate evaluation</label>
        <button type="submit">Advance</button>
      </form>
    </dialog>
    <dialog class="policy-exception-dialog mcp-action-dialog" data-observability-rollout-rollback-modal="${escapeHtml(rollout.id)}">
      <form method="dialog" class="dialog-close-row"><button type="submit">Close</button></form>
      <form data-observability-rollout-rollback-form data-rollout-id="${escapeHtml(rollout.id)}">
        <h3>${escapeHtml(rollout.name)}</h3>
        <label><span>Reason</span><textarea name="reason" required placeholder="Rollback reason"></textarea></label>
        <button type="submit">Rollback</button>
      </form>
    </dialog>
  `;
}

function renderRollupBars(entries) {
  const max = Math.max(...entries.map(([, value]) => Number(value)), 0.000001);
  return `
    <ul class="observability-bars">
      ${entries
        .map(([label, value]) => {
          const width = Math.max(4, Math.round((Number(value) / max) * 100));
          return `<li><span>${escapeHtml(label)}</span><meter min="0" max="100" value="${escapeHtml(String(width))}"></meter><strong>${escapeHtml(formatMoney(value))}</strong></li>`;
        })
        .join("")}
    </ul>
  `;
}

function renderTagList(items, emptyText) {
  if (!items.length) {
    return `<p>${escapeHtml(emptyText)}</p>`;
  }
  return `<div class="tag-list">${items.map((item) => `<span>${escapeHtml(item)}</span>`).join("")}</div>`;
}

function formatMoney(value) {
  return `$${Number(value ?? 0).toFixed(2)}`;
}

function numberValue(value) {
  const parsed = Number.parseFloat(String(value ?? "0"));
  return Number.isFinite(parsed) ? parsed : 0;
}

function optionalString(value) {
  const normalized = String(value ?? "").trim();
  return normalized || null;
}

function parseJsonObject(value, fallback) {
  try {
    const parsed = JSON.parse(String(value ?? ""));
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : fallback;
  } catch {
    return fallback;
  }
}

function renderJsonSummary(value) {
  return `<code>${escapeHtml(JSON.stringify(value ?? {}))}</code>`;
}

function rolloutStages(config, strategy) {
  if (Array.isArray(config?.stages) && config.stages.length) {
    return config.stages
      .map((stage) => Number.parseInt(String(stage), 10))
      .filter((stage) => Number.isFinite(stage));
  }
  if (strategy === "percentage") {
    return [Number.parseInt(String(config?.percentage ?? 100), 10)].filter((stage) =>
      Number.isFinite(stage)
    );
  }
  return [5, 25, 50, 100];
}
