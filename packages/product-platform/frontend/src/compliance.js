import { escapeHtml } from "./html.js";

export function renderCompliancePage(state = {}) {
  return `
    <section class="page-heading" data-route-page="/compliance">
      <p class="section-label">Assurance</p>
      <h1>Compliance</h1>
      <p>Audit explorer, controls, evidence, reports, violations, and governance attestations.</p>
    </section>
    <section class="policy-workspace" data-compliance-workspace>
      ${renderAuditExplorer({
        events: state.complianceAuditEvents ?? [],
        filters: state.complianceAuditFilters ?? {},
        selectedEvent: state.selectedComplianceAuditEvent ?? null,
        verification: state.complianceAuditVerification ?? null,
        relatedEvents: state.complianceRelatedAuditEvents ?? [],
        exportResult: state.complianceAuditExport ?? null
      })}
      ${renderControlMap({
        frameworks: state.complianceFrameworks ?? [],
        controls: state.complianceControls ?? [],
        evidence: state.complianceEvidence ?? []
      })}
      ${renderEvidenceLibrary({
        controls: state.complianceControls ?? [],
        evidence: state.complianceEvidence ?? [],
        filters: state.complianceEvidenceFilters ?? {},
        recomputeResult: state.complianceEvidenceRecompute ?? null
      })}
      ${renderViolationQueue({
        violations: state.complianceViolations ?? [],
        filters: state.complianceViolationFilters ?? {}
      })}
      ${renderReportBuilder({
        frameworks: state.complianceFrameworks ?? [],
        reports: state.complianceReports ?? [],
        selectedReport: state.selectedComplianceReport ?? null,
        attestationResult: state.complianceReportAttestation ?? null
      })}
    </section>
  `;
}

export function renderAuditExplorer({
  events = [],
  filters = {},
  selectedEvent = null,
  verification = null,
  relatedEvents = [],
  exportResult = null
} = {}) {
  const activeEvent = selectedEvent ?? events[0] ?? null;
  return `
    <section class="workspace-panel compliance-audit-explorer" data-compliance-audit-explorer>
      <header class="panel-header">
        <div>
          <p class="section-label">Audit Explorer</p>
          <h2>Audit Events</h2>
        </div>
      </header>
      ${renderAuditExplorerFilter(filters)}
      ${renderAuditExportForm(filters, exportResult)}
      ${events.length ? renderAuditEventTable(events) : '<div class="empty-state" data-compliance-audit-empty><strong>No events</strong><span>Adjust filters</span></div>'}
      ${renderAuditVerification(activeEvent, verification)}
      ${renderCorrelationTimeline(activeEvent, relatedEvents.length ? relatedEvents : events)}
    </section>
  `;
}

export function renderAuditExplorerFilter(filters = {}) {
  return `
    <form class="filter-bar" data-compliance-audit-filter>
      ${filterInput("event_type", "Event", filters.event_type, "policy.decision")}
      ${filterInput("source_component", "Source", filters.source_component, "policy-engine")}
      ${filterInput("actor_id", "Actor", filters.actor_id, "user id")}
      ${filterInput("resource_type", "Resource Type", filters.resource_type, "policy_evaluation")}
      ${filterInput("resource_id", "Resource", filters.resource_id, "resource id")}
      <label>
        <span>Decision</span>
        <select name="decision">
          <option value="">Any</option>
          <option value="allow" ${filters.decision === "allow" ? "selected" : ""}>allow</option>
          <option value="deny" ${filters.decision === "deny" ? "selected" : ""}>deny</option>
          <option value="allowed" ${filters.decision === "allowed" ? "selected" : ""}>allowed</option>
          <option value="denied" ${filters.decision === "denied" ? "selected" : ""}>denied</option>
        </select>
      </label>
      ${filterInput("severity", "Severity", filters.severity, "warning")}
      ${filterInput("correlation_id", "Correlation", filters.correlation_id, "correlation id")}
      <button type="submit">Filter</button>
    </form>
  `;
}

export function renderAuditExportForm(filters = {}, exportResult = null) {
  return `
    <form class="filter-bar" data-audit-export-form>
      ${Object.entries(auditEventFilterParamsFromValues(filters))
        .map(
          ([key, value]) => `<input type="hidden" name="${escapeHtml(key)}" value="${escapeHtml(value)}">`
        )
        .join("")}
      <label>
        <span>Format</span>
        <select name="format">
          <option value="json">json</option>
          <option value="csv">csv</option>
          <option value="markdown">markdown</option>
        </select>
      </label>
      <button type="submit">Export</button>
      <output data-audit-export-result>${exportResult ? escapeHtml(exportResult.artifact_uri) : ""}</output>
    </form>
  `;
}

export function renderAuditEventTable(events = []) {
  return `
    <table class="data-table" data-compliance-audit-table>
      <thead>
        <tr>
          <th>Event</th>
          <th>Source</th>
          <th>Actor</th>
          <th>Resource</th>
          <th>Decision</th>
          <th>Severity</th>
          <th>Created</th>
          <th>Detail</th>
        </tr>
      </thead>
      <tbody>
        ${events
          .map(
            (event) => `
              <tr data-compliance-audit-row="${escapeHtml(event.id)}">
                <td><strong>${escapeHtml(event.event_type)}</strong><small>${escapeHtml(event.id)}</small></td>
                <td>${escapeHtml(event.source_component)}</td>
                <td>${escapeHtml([event.actor_type, event.actor_id].filter(Boolean).join(" / ") || "n/a")}</td>
                <td>${escapeHtml([event.resource_type, event.resource_id].filter(Boolean).join(" / ") || "n/a")}</td>
                <td>${escapeHtml(event.decision ?? "n/a")}</td>
                <td><span class="status-pill">${escapeHtml(event.severity)}</span></td>
                <td>${escapeHtml(event.created_at)}</td>
                <td><button type="button" data-compliance-audit-open="${escapeHtml(event.id)}">Open</button></td>
              </tr>
            `
          )
          .join("")}
      </tbody>
    </table>
  `;
}

export function renderAuditVerification(event = null, verification = null) {
  if (!event) {
    return "";
  }
  const label = verification?.valid ? "verified" : verification ? "failed" : "pending";
  return `
    <section class="lint-panel" data-compliance-hash-verification="${escapeHtml(event.id)}">
      <h3>Hash Verification</h3>
      <p>${escapeHtml(label)}</p>
      <small>${escapeHtml(verification?.reason ?? `${verification?.checked_count ?? 0} event(s) checked`)}</small>
    </section>
  `;
}

export function renderCorrelationTimeline(currentEvent = null, events = []) {
  if (!currentEvent) {
    return "";
  }
  const related = events
    .filter((event) => event.correlation_id && event.correlation_id === currentEvent.correlation_id)
    .sort((left, right) => String(left.created_at).localeCompare(String(right.created_at)));
  return `
    <section class="lint-panel" data-compliance-correlation-timeline="${escapeHtml(currentEvent.correlation_id ?? "")}">
      <h3>Correlation Timeline</h3>
      ${
        related.length
          ? `<ol class="related-event-timeline">
              ${related
                .map(
                  (event) => `
                    <li>
                      <button type="button" data-compliance-audit-open="${escapeHtml(event.id)}">
                        <span>${escapeHtml(event.event_type)}</span>
                        <strong>${escapeHtml(event.id)}</strong>
                        <small>${escapeHtml(event.created_at)}</small>
                      </button>
                    </li>
                  `
                )
                .join("")}
            </ol>`
          : '<div class="empty-state"><strong>No related events</strong><span>Single event</span></div>'
      }
    </section>
  `;
}

export function renderControlMap({ frameworks = [], controls = [], evidence = [] } = {}) {
  const evidenceByControl = evidenceByControlId(evidence);
  return `
    <section class="workspace-panel compliance-control-map" data-compliance-control-map>
      <header class="panel-header">
        <div>
          <p class="section-label">Control Map</p>
          <h2>Framework Controls</h2>
        </div>
      </header>
      ${
        frameworks.length
          ? `<div class="tabs" data-compliance-framework-tabs>
              ${frameworks
                .map(
                  (framework) => `
                    <button type="button" data-compliance-framework-id="${escapeHtml(framework.id)}">
                      ${escapeHtml(framework.name)}
                    </button>
                  `
                )
                .join("")}
            </div>`
          : ""
      }
      ${
        controls.length
          ? `<table class="data-table" data-compliance-control-table>
              <thead>
                <tr>
                  <th>Framework</th>
                  <th>Control</th>
                  <th>Required Evidence</th>
                  <th>Fresh Evidence</th>
                  <th>Latest</th>
                </tr>
              </thead>
              <tbody>
                ${controls
                  .map((control) => {
                    const linkedEvidence = evidenceByControl.get(control.id) ?? [];
                    const latest = latestEvidence(linkedEvidence);
                    return `
                      <tr data-compliance-control-row="${escapeHtml(control.id)}">
                        <td>${escapeHtml(control.framework_name ?? "n/a")}</td>
                        <td><strong>${escapeHtml(control.control_code)}</strong><small>${escapeHtml(control.title)}</small></td>
                        <td>${escapeHtml((control.required_evidence_types ?? []).join(", ") || "n/a")}</td>
                        <td><span class="status-pill">${escapeHtml(String(linkedEvidence.length))}</span></td>
                        <td>${latest ? escapeHtml(latest.freshness_at) : "n/a"}</td>
                      </tr>
                    `;
                  })
                  .join("")}
              </tbody>
            </table>`
          : '<div class="empty-state" data-compliance-control-empty><strong>No controls</strong><span>Seed frameworks first</span></div>'
      }
    </section>
  `;
}

export function renderEvidenceLibrary({
  controls = [],
  evidence = [],
  filters = {},
  recomputeResult = null
} = {}) {
  return `
    <section class="workspace-panel compliance-evidence-library" data-compliance-evidence-library>
      <header class="panel-header">
        <div>
          <p class="section-label">Evidence Library</p>
          <h2>Mapped Evidence</h2>
        </div>
      </header>
      <form class="filter-bar" data-compliance-evidence-filter>
        <label>
          <span>Control</span>
          <select name="control_id">
            <option value="">Any</option>
            ${controls
              .map(
                (control) => `
                  <option value="${escapeHtml(control.id)}" ${
                    filters.control_id === control.id ? "selected" : ""
                  }>
                    ${escapeHtml(control.control_code)}
                  </option>
                `
              )
              .join("")}
          </select>
        </label>
        <label>
          <span>Status</span>
          <select name="status">
            <option value="">Any</option>
            <option value="fresh" ${filters.status === "fresh" ? "selected" : ""}>fresh</option>
            <option value="stale" ${filters.status === "stale" ? "selected" : ""}>stale</option>
            <option value="missing" ${filters.status === "missing" ? "selected" : ""}>missing</option>
          </select>
        </label>
        <button type="submit">Filter</button>
      </form>
      <form class="filter-bar" data-compliance-evidence-recompute>
        <button type="submit">Recompute Evidence</button>
        <output data-compliance-evidence-recompute-result>
          ${
            recomputeResult
              ? escapeHtml(
                  `${recomputeResult.evidence_count} mapped / ${recomputeResult.refreshed_count} refreshed`
                )
              : ""
          }
        </output>
      </form>
      ${
        evidence.length
          ? `<table class="data-table" data-compliance-evidence-table>
              <thead>
                <tr>
                  <th>Control</th>
                  <th>Evidence</th>
                  <th>Source</th>
                  <th>Status</th>
                  <th>Freshness</th>
                </tr>
              </thead>
              <tbody>
                ${evidence
                  .map(
                    (item) => `
                      <tr data-compliance-evidence-row="${escapeHtml(item.id)}">
                        <td>${escapeHtml(item.control_code ?? item.control_id)}</td>
                        <td><strong>${escapeHtml(item.title)}</strong><small>${escapeHtml(item.summary)}</small></td>
                        <td>${escapeHtml(`${item.source_type}:${item.source_id}`)}</td>
                        <td><span class="status-pill">${escapeHtml(item.status)}</span></td>
                        <td>${escapeHtml(item.freshness_at)}</td>
                      </tr>
                    `
                  )
                  .join("")}
              </tbody>
            </table>`
          : '<div class="empty-state" data-compliance-evidence-empty><strong>No evidence</strong><span>Recompute evidence</span></div>'
      }
    </section>
  `;
}

export function renderViolationQueue({ violations = [], filters = {} } = {}) {
  return `
    <section class="workspace-panel compliance-violations" data-compliance-violations>
      <header class="panel-header">
        <div>
          <p class="section-label">Violations</p>
          <h2>Violation Queue</h2>
        </div>
      </header>
      <form class="filter-bar" data-compliance-violation-filter>
        <label>
          <span>Status</span>
          <select name="status">
            <option value="">Any</option>
            <option value="open" ${filters.status === "open" ? "selected" : ""}>open</option>
            <option value="acknowledged" ${filters.status === "acknowledged" ? "selected" : ""}>acknowledged</option>
            <option value="resolved" ${filters.status === "resolved" ? "selected" : ""}>resolved</option>
          </select>
        </label>
        <label>
          <span>Severity</span>
          <select name="severity">
            <option value="">Any</option>
            <option value="warning" ${filters.severity === "warning" ? "selected" : ""}>warning</option>
            <option value="high" ${filters.severity === "high" ? "selected" : ""}>high</option>
            <option value="critical" ${filters.severity === "critical" ? "selected" : ""}>critical</option>
          </select>
        </label>
        <button type="submit">Filter</button>
      </form>
      ${
        violations.length
          ? `<table class="data-table" data-compliance-violation-table>
              <thead>
                <tr>
                  <th>Control</th>
                  <th>Severity</th>
                  <th>Status</th>
                  <th>Reason</th>
                  <th>Source</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                ${violations
                  .map(
                    (violation) => `
                      <tr data-compliance-violation-row="${escapeHtml(violation.id)}">
                        <td>${escapeHtml(violation.control_code ?? violation.control_id)}</td>
                        <td><span class="status-pill">${escapeHtml(violation.severity)}</span></td>
                        <td><span class="status-pill">${escapeHtml(violation.status)}</span></td>
                        <td><strong>${escapeHtml(violation.reason)}</strong><small>${escapeHtml(violation.resolution_reason ?? "")}</small></td>
                        <td>${escapeHtml(`${violation.source_type}:${violation.source_id}`)}</td>
                        <td>
                          <button type="button" data-compliance-violation-ack="${escapeHtml(violation.id)}" ${violation.status === "resolved" ? "disabled" : ""}>Acknowledge</button>
                          <form class="inline-actions" data-compliance-violation-resolve-form data-violation-id="${escapeHtml(violation.id)}">
                            <input name="reason" placeholder="Resolution reason" required>
                            <button type="submit" ${violation.status === "resolved" ? "disabled" : ""}>Resolve</button>
                          </form>
                        </td>
                      </tr>
                    `
                  )
                  .join("")}
              </tbody>
            </table>`
          : '<div class="empty-state" data-compliance-violation-empty><strong>No violations</strong><span>Queue is clear</span></div>'
      }
    </section>
  `;
}

export function renderReportBuilder({
  frameworks = [],
  reports = [],
  selectedReport = null,
  attestationResult = null
} = {}) {
  const activeReport = selectedReport ?? reports[0] ?? null;
  return `
    <section class="workspace-panel compliance-reports" data-compliance-reports>
      <header class="panel-header">
        <div>
          <p class="section-label">Reports</p>
          <h2>Report Builder</h2>
        </div>
      </header>
      <form class="filter-bar" data-compliance-report-create-form>
        <label>
          <span>Framework</span>
          <select name="framework_id" required>
            ${frameworks
              .map(
                (framework) => `
                  <option value="${escapeHtml(framework.id)}">${escapeHtml(framework.name)}</option>
                `
              )
              .join("")}
          </select>
        </label>
        ${filterInput("name", "Name", "", "SOC 2 Evidence Report")}
        ${filterInput("date_from", "From", "", "2026-01-01")}
        ${filterInput("date_to", "To", "", "2026-12-31")}
        <button type="submit">Create Draft</button>
      </form>
      ${
        reports.length
          ? `<table class="data-table" data-compliance-report-table>
              <thead>
                <tr>
                  <th>Report</th>
                  <th>Framework</th>
                  <th>Status</th>
                  <th>Evidence</th>
                  <th>Attestations</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                ${reports
                  .map(
                    (report) => `
                      <tr data-compliance-report-row="${escapeHtml(report.id)}">
                        <td><strong>${escapeHtml(report.name)}</strong><small>${escapeHtml(`${report.date_from} to ${report.date_to}`)}</small></td>
                        <td>${escapeHtml(report.framework_name ?? report.framework_id)}</td>
                        <td><span class="status-pill">${escapeHtml(report.status)}</span></td>
                        <td>${escapeHtml(String((report.evidence_item_ids ?? []).length))}</td>
                        <td>${escapeHtml(String(report.attestation_count ?? 0))}</td>
                        <td>
                          <button type="button" data-compliance-report-open="${escapeHtml(report.id)}">Open</button>
                          <button type="button" data-compliance-report-generate="${escapeHtml(report.id)}">Generate</button>
                          ${
                            report.artifact_uri
                              ? `<a href="/api/v1/compliance/reports/${encodeURIComponent(report.id)}/download" data-compliance-report-download="${escapeHtml(report.id)}">Download</a>`
                              : ""
                          }
                        </td>
                      </tr>
                    `
                  )
                  .join("")}
              </tbody>
            </table>`
          : '<div class="empty-state" data-compliance-report-empty><strong>No reports</strong><span>Create a draft</span></div>'
      }
      ${
        activeReport
          ? `<section class="lint-panel" data-compliance-report-preview="${escapeHtml(activeReport.id)}">
              <h3>${escapeHtml(activeReport.name)}</h3>
              <p>${escapeHtml(activeReport.artifact_uri ?? "draft")}</p>
              <pre>${escapeHtml(activeReport.rendered_markdown ?? "Generate report")}</pre>
              <form class="filter-bar" data-compliance-report-attest-form data-report-id="${escapeHtml(activeReport.id)}">
                ${filterInput("statement", "Statement", "", "I attest this report")}
                ${filterInput("signature_ref", "Signature", "", "optional")}
                <button type="submit" ${activeReport.artifact_uri ? "" : "disabled"}>Attest</button>
                <output data-compliance-report-attestation-result>${attestationResult ? escapeHtml(attestationResult.id) : ""}</output>
              </form>
            </section>`
          : ""
      }
    </section>
  `;
}

export function auditEventFilterParamsFromValues(values = {}) {
  return cleanParams({
    event_type: values.event_type,
    source_component: values.source_component,
    actor_type: values.actor_type,
    actor_id: values.actor_id,
    agent_id: values.agent_id,
    decision: values.decision,
    severity: values.severity,
    policy_id: values.policy_id,
    resource_type: values.resource_type,
    resource_id: values.resource_id,
    correlation_id: values.correlation_id,
    created_from: values.created_from,
    created_to: values.created_to
  });
}

export function auditEventFilterParamsFromForm(form) {
  return auditEventFilterParamsFromValues(Object.fromEntries(new FormData(form)));
}

export function auditExportPayloadFromValues(values = {}) {
  const { format = "json", ...filters } = values;
  return {
    format: format || "json",
    filters: auditEventFilterParamsFromValues(filters)
  };
}

export function auditExportPayloadFromForm(form) {
  return auditExportPayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function complianceEvidenceFilterParamsFromValues(values = {}) {
  return cleanParams({
    control_id: values.control_id,
    status: values.status
  });
}

export function complianceEvidenceFilterParamsFromForm(form) {
  return complianceEvidenceFilterParamsFromValues(Object.fromEntries(new FormData(form)));
}

export function complianceViolationFilterParamsFromValues(values = {}) {
  return cleanParams({
    status: values.status,
    severity: values.severity,
    control_id: values.control_id,
    agent_id: values.agent_id
  });
}

export function complianceViolationFilterParamsFromForm(form) {
  return complianceViolationFilterParamsFromValues(Object.fromEntries(new FormData(form)));
}

export function complianceViolationPatchPayloadFromValues(values = {}) {
  return cleanParams({
    status: values.status,
    reason: values.reason
  });
}

export function complianceViolationPatchPayloadFromForm(form, status) {
  return complianceViolationPatchPayloadFromValues({
    ...Object.fromEntries(new FormData(form)),
    status
  });
}

export function complianceReportPayloadFromValues(values = {}) {
  return cleanParams({
    framework_id: values.framework_id,
    name: values.name,
    date_from: values.date_from,
    date_to: values.date_to
  });
}

export function complianceReportPayloadFromForm(form) {
  return complianceReportPayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function complianceReportAttestationPayloadFromValues(values = {}) {
  return cleanParams({
    statement: values.statement,
    signature_ref: values.signature_ref
  });
}

export function complianceReportAttestationPayloadFromForm(form) {
  return complianceReportAttestationPayloadFromValues(Object.fromEntries(new FormData(form)));
}

function evidenceByControlId(evidence = []) {
  const grouped = new Map();
  for (const item of evidence) {
    const rows = grouped.get(item.control_id) ?? [];
    rows.push(item);
    grouped.set(item.control_id, rows);
  }
  return grouped;
}

function latestEvidence(evidence = []) {
  return [...evidence].sort((left, right) =>
    String(right.freshness_at).localeCompare(String(left.freshness_at))
  )[0];
}

function filterInput(name, label, value, placeholder) {
  return `
    <label>
      <span>${escapeHtml(label)}</span>
      <input name="${escapeHtml(name)}" value="${escapeHtml(value ?? "")}" placeholder="${escapeHtml(placeholder)}">
    </label>
  `;
}

function cleanParams(values) {
  return Object.fromEntries(
    Object.entries(values).filter(([, value]) => value !== undefined && value !== null && value !== "")
  );
}
