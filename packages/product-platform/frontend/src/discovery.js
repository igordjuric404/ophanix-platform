import { escapeHtml } from "./html.js";

export function renderDiscoveryPage(state = {}) {
  const scanners = state.discoveryScanners ?? [];
  const targets = state.discoveryTargets ?? [];
  const runs = state.discoveryRuns ?? [];
  const findings = state.discoveryFindings ?? [];
  const selectedRun = state.selectedDiscoveryRun ?? runs[0] ?? null;
  const selectedFinding = state.selectedDiscoveryFinding ?? findings.find((finding) => finding.status !== "suppressed") ?? findings[0] ?? null;
  return `
    <section class="page-heading" data-route-page="/discovery">
      <p class="section-label">Operations</p>
      <h1>Discovery</h1>
      <p>Scanner targets, schedules, run history, and raw findings.</p>
    </section>
    <section class="discovery-workspace" data-discovery-workspace>
      ${renderScannerCards(scanners)}
      ${renderDiscoveryTargets(targets)}
      ${renderDiscoveryRunTable(runs)}
      ${renderDiscoveryRunDetail(selectedRun)}
      ${renderDiscoveryFindingsTable(findings)}
      ${renderDiscoveryFindingDetail(selectedFinding)}
    </section>
  `;
}

export function renderScannerCards(scanners = []) {
  return `
    <section class="workspace-panel discovery-scanners" data-discovery-scanners>
      <header class="panel-header">
        <div>
          <p class="section-label">Scanners</p>
          <h2>Scanner Registry</h2>
        </div>
      </header>
      <div class="scanner-grid">
        ${
          scanners.length
            ? scanners.map(renderScannerCard).join("")
            : '<div class="empty-state"><strong>No scanners</strong><span>Unavailable</span></div>'
        }
      </div>
    </section>
  `;
}

function renderScannerCard(scanner) {
  return `
    <article class="scanner-card" data-discovery-scanner="${escapeHtml(scanner.scanner_type)}">
      <div>
        <h3>${escapeHtml(scanner.name)}</h3>
        <p>${escapeHtml(scanner.description ?? "")}</p>
      </div>
      <span class="status-pill">${escapeHtml(scanner.status ?? "unknown")}</span>
      <small>${escapeHtml((scanner.required_config ?? []).join(", ") || "no required config")}</small>
    </article>
  `;
}

export function renderDiscoveryTargets(targets = []) {
  return `
    <section class="workspace-panel discovery-targets" data-discovery-targets>
      <header class="panel-header">
        <div>
          <p class="section-label">Targets</p>
          <h2>Scanner Settings</h2>
        </div>
      </header>
      ${
        targets.length
          ? `<table class="data-table" data-discovery-target-table>
              <thead>
                <tr>
                  <th>Target</th>
                  <th>Scanner</th>
                  <th>Schedule</th>
                  <th>Next Run</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>${targets.map(renderTargetRow).join("")}</tbody>
            </table>`
          : '<div class="empty-state" data-discovery-target-empty><strong>No targets</strong><span>Add scanner target</span></div>'
      }
    </section>
  `;
}

function renderTargetRow(target) {
  return `
    <tr data-discovery-target-row="${escapeHtml(target.id)}">
      <td><strong>${escapeHtml(target.target_value ?? target.id)}</strong><small>${escapeHtml(target.target_type ?? "")}</small></td>
      <td>${escapeHtml(target.scanner_type)}</td>
      <td>
        <form class="inline-controls" data-discovery-schedule-form data-target-id="${escapeHtml(target.id)}">
          <label>
            <span class="visually-hidden">Schedule mode</span>
            <select name="mode">
              ${["manual", "hourly", "daily"]
                .map(
                  (mode) => `
                    <option value="${mode}" ${target.schedule_mode === mode ? "selected" : ""}>${mode}</option>
                  `
                )
                .join("")}
            </select>
          </label>
          <button type="submit">Update</button>
        </form>
      </td>
      <td>${escapeHtml(target.next_run_at ?? "manual")}</td>
      <td class="row-actions">
        <button type="button" data-discovery-run-now="${escapeHtml(target.id)}">Run</button>
      </td>
    </tr>
  `;
}

export function renderDiscoveryRunTable(runs = []) {
  const rows = runs.map(renderRunRow).join("");
  return `
    <section class="workspace-panel discovery-runs" data-discovery-runs>
      <header class="panel-header">
        <div>
          <p class="section-label">Runs</p>
          <h2>Scan Run History</h2>
        </div>
      </header>
      ${
        runs.length
          ? `<table class="data-table" data-discovery-run-table>
              <thead>
                <tr>
                  <th>Run</th>
                  <th>Status</th>
                  <th>Findings</th>
                  <th>Duration</th>
                  <th>Error</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>${rows}</tbody>
            </table>`
          : '<div class="empty-state" data-discovery-run-empty><strong>No runs</strong><span>Run a target</span></div>'
      }
    </section>
  `;
}

function renderRunRow(run) {
  const rawCount = run.raw_finding_count ?? run.summary_json?.raw_finding_count ?? 0;
  return `
    <tr data-discovery-run-row="${escapeHtml(run.id)}">
      <td><strong>${escapeHtml(run.id)}</strong><small>${escapeHtml(run.target_id ?? "")}</small></td>
      <td><span class="status-pill">${escapeHtml(run.status)}</span></td>
      <td><strong>${escapeHtml(String(rawCount))} raw</strong><small>0 high</small></td>
      <td>${escapeHtml(durationLabel(run))}</td>
      <td>${run.error_message ? `<span data-discovery-run-error>${escapeHtml(run.error_message)}</span>` : "none"}</td>
      <td class="row-actions">
        <button type="button" data-discovery-run-open="${escapeHtml(run.id)}">Open</button>
      </td>
    </tr>
  `;
}

export function renderDiscoveryRunDetail(run) {
  if (!run) {
    return `
      <section class="workspace-panel discovery-run-detail" data-discovery-run-detail-empty>
        <header class="panel-header">
          <div>
            <p class="section-label">Detail</p>
            <h2>Run Detail</h2>
          </div>
        </header>
        <div class="empty-state"><strong>No selected run</strong><span>Open a run</span></div>
      </section>
    `;
  }
  const findings = run.raw_findings ?? [];
  return `
    <section class="workspace-panel discovery-run-detail" data-discovery-run-detail="${escapeHtml(run.id)}">
      <header class="panel-header">
        <div>
          <p class="section-label">Detail</p>
          <h2>${escapeHtml(run.id)}</h2>
        </div>
        <span class="status-pill">${escapeHtml(run.status)}</span>
      </header>
      ${run.error_message ? `<div class="drawer-state is-error" data-discovery-run-error>${escapeHtml(run.error_message)}</div>` : ""}
      <ul class="compact-list">
        <li><span>Raw findings</span><strong>${escapeHtml(String(run.raw_finding_count ?? findings.length))}</strong></li>
        <li><span>High risk</span><strong>0 high</strong></li>
        <li><span>Duration</span><strong>${escapeHtml(durationLabel(run))}</strong></li>
        <li><span>Reconciliation</span><strong>Pending</strong></li>
      </ul>
      <div class="raw-finding-list" data-discovery-raw-findings>
        ${
          findings.length
            ? findings.map(renderRawFinding).join("")
            : '<div class="empty-state"><strong>No raw findings</strong><span>0</span></div>'
        }
      </div>
    </section>
  `;
}

export function renderDiscoveryFindingsTable(findings = [], { includeSuppressed = false } = {}) {
  const visibleFindings = includeSuppressed
    ? findings
    : findings.filter((finding) => finding.status !== "suppressed");
  return `
    <section class="workspace-panel discovery-findings" data-discovery-findings>
      <header class="panel-header">
        <div>
          <p class="section-label">Findings</p>
          <h2>Discovery Findings</h2>
        </div>
      </header>
      <form class="filter-bar" data-discovery-finding-filter>
        <label>
          <span>Risk</span>
          <select name="risk_level">
            <option value="">Any</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
          </select>
        </label>
        <label>
          <span>Status</span>
          <select name="status">
            <option value="">Open</option>
            <option value="shadow_candidate">Shadow</option>
            <option value="manual_review">Review</option>
            <option value="registered">Registered</option>
            <option value="suppressed">Suppressed</option>
          </select>
        </label>
        <label>
          <span>Owner</span>
          <input name="owner" placeholder="owner">
        </label>
        <label>
          <span>Source</span>
          <input name="source" placeholder="config, repo, process">
        </label>
        <label>
          <span>Registry</span>
          <select name="registry_match">
            <option value="">Any</option>
            <option value="matched">Matched</option>
            <option value="unmatched">Unmatched</option>
          </select>
        </label>
        <button type="submit">Filter</button>
      </form>
      ${
        visibleFindings.length
          ? `<table class="data-table" data-discovery-finding-table>
              <thead>
                <tr>
                  <th>Finding</th>
                  <th>Risk</th>
                  <th>Status</th>
                  <th>Owner</th>
                  <th>Source</th>
                  <th>Registry</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>${visibleFindings.map(renderFindingRow).join("")}</tbody>
            </table>`
          : '<div class="empty-state" data-discovery-finding-empty><strong>No findings</strong><span>Run reconciliation</span></div>'
      }
    </section>
  `;
}

export function discoveryFindingParamsFromForm(form) {
  return discoveryFindingParamsFromValues(Object.fromEntries(new FormData(form)));
}

export function discoveryFindingParamsFromValues(values = {}) {
  const params = {};
  for (const key of ["risk_level", "status", "source", "owner", "registry_match"]) {
    const value = String(values[key] ?? "").trim();
    if (value) {
      params[key] = value;
    }
  }
  if (params.status === "suppressed") {
    params.include_suppressed = true;
  }
  return params;
}

function renderFindingRow(finding) {
  return `
    <tr data-discovery-finding-row="${escapeHtml(finding.id)}">
      <td><strong>${escapeHtml(finding.detected_name)}</strong><small>${escapeHtml(finding.fingerprint)}</small></td>
      <td><span class="status-pill">${escapeHtml(finding.risk_level)}</span><small>${escapeHtml(String(finding.risk_score))}</small></td>
      <td>${escapeHtml(finding.status)}</td>
      <td>${escapeHtml(finding.owner_hint ?? "unassigned")}</td>
      <td>${escapeHtml(finding.source ?? "unknown")}</td>
      <td>${escapeHtml(finding.registry_agent_id ?? "none")}</td>
      <td class="row-actions">
        <button type="button" data-discovery-finding-open="${escapeHtml(finding.id)}">Open</button>
      </td>
    </tr>
  `;
}

export function renderDiscoveryFindingDetail(finding) {
  if (!finding) {
    return `
      <section class="workspace-panel discovery-finding-detail" data-discovery-finding-detail-empty>
        <header class="panel-header">
          <div>
            <p class="section-label">Triage</p>
            <h2>Finding Detail</h2>
          </div>
        </header>
        <div class="empty-state"><strong>No selected finding</strong><span>Open a finding</span></div>
      </section>
    `;
  }
  return `
    <section class="workspace-panel discovery-finding-detail" data-discovery-finding-detail="${escapeHtml(finding.id)}">
      <header class="panel-header">
        <div>
          <p class="section-label">Triage</p>
          <h2>${escapeHtml(finding.detected_name)}</h2>
        </div>
        <span class="status-pill">${escapeHtml(finding.risk_level)}</span>
      </header>
      <div class="finding-detail-grid">
        <article>
          <h3>Risk Factors</h3>
          ${renderStringList(finding.risk_factors ?? [], "No risk factors")}
        </article>
        <article>
          <h3>Evidence</h3>
          ${renderEvidenceList(finding.evidence ?? [])}
        </article>
        <article class="suppression-review">
          <h3>Suppression Review</h3>
          <p>${escapeHtml(finding.status === "suppressed" ? "Suppressed" : "Open")}</p>
        </article>
      </div>
      ${renderFindingActions(finding)}
    </section>
  `;
}

function renderStringList(items, emptyLabel) {
  return items.length
    ? `<ul class="compact-list">${items
        .map((item) => `<li><span>${escapeHtml(item)}</span><strong>risk</strong></li>`)
        .join("")}</ul>`
    : `<div class="empty-state"><strong>${escapeHtml(emptyLabel)}</strong><span>0</span></div>`;
}

function renderEvidenceList(evidence = []) {
  return evidence.length
    ? `<ul class="compact-list">${evidence
        .map(
          (item) => `
            <li>
              <span>${escapeHtml(item.evidence_type)}</span>
              <strong>${escapeHtml(item.evidence_value)}</strong>
            </li>
          `
        )
        .join("")}</ul>`
    : '<div class="empty-state"><strong>No evidence</strong><span>0</span></div>';
}

function renderFindingActions(finding) {
  return `
    <div class="finding-actions" data-discovery-finding-actions="${escapeHtml(finding.id)}">
      <form data-discovery-action="assign-owner" data-finding-id="${escapeHtml(finding.id)}">
        <input name="owner_user_id" placeholder="owner_user_id" required>
        <button type="submit">Assign</button>
      </form>
      <form data-discovery-action="register-agent" data-finding-id="${escapeHtml(finding.id)}">
        <input name="owner_user_id" placeholder="owner_user_id" required>
        <input name="sponsor_user_id" placeholder="sponsor_user_id" required>
        <label><input type="checkbox" name="confirm" required> Confirm</label>
        <button type="submit">Register</button>
      </form>
      <form data-discovery-action="suppress" data-finding-id="${escapeHtml(finding.id)}">
        <input name="reason" placeholder="reason" required>
        <label><input type="checkbox" name="confirm" required> Confirm</label>
        <button type="submit">Suppress</button>
      </form>
      <form data-discovery-action="mark-decommissioned" data-finding-id="${escapeHtml(finding.id)}">
        <label><input type="checkbox" name="confirm" required> Confirm</label>
        <button type="submit">Decommissioned</button>
      </form>
    </div>
  `;
}

function renderRawFinding(finding) {
  const payload = finding.raw_payload_json ?? {};
  return `
    <article class="raw-finding" data-discovery-raw-finding="${escapeHtml(finding.id)}">
      <h3>${escapeHtml(payload.name ?? finding.fingerprint)}</h3>
      <dl>
        <dt>Fingerprint</dt>
        <dd>${escapeHtml(finding.fingerprint)}</dd>
        <dt>Type</dt>
        <dd>${escapeHtml(payload.agent_type ?? "unknown")}</dd>
        <dt>Confidence</dt>
        <dd>${escapeHtml(String(payload.confidence ?? "n/a"))}</dd>
      </dl>
    </article>
  `;
}

export function durationLabel(run) {
  if (!run?.started_at || !run?.finished_at) {
    return "pending";
  }
  const started = Date.parse(run.started_at);
  const finished = Date.parse(run.finished_at);
  if (!Number.isFinite(started) || !Number.isFinite(finished) || finished < started) {
    return "pending";
  }
  const seconds = Math.round((finished - started) / 1000);
  return `${seconds}s`;
}
