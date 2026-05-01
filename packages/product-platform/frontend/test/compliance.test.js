import assert from "node:assert/strict";
import test from "node:test";

import { createApiClient } from "../src/apiClient.js";
import {
  auditEventFilterParamsFromValues,
  auditExportPayloadFromValues,
  complianceEvidenceFilterParamsFromValues,
  complianceReportAttestationPayloadFromValues,
  complianceReportPayloadFromValues,
  complianceViolationFilterParamsFromValues,
  complianceViolationPatchPayloadFromValues,
  renderAuditExplorer,
  renderCompliancePage,
  renderControlMap,
  renderEvidenceLibrary,
  renderReportBuilder,
  renderViolationQueue
} from "../src/compliance.js";

const policyEvent = {
  id: "evt_policy",
  organization_id: "org_default",
  environment_id: "env_default",
  event_type: "policy.decision",
  source_component: "policy-engine",
  actor_type: "user",
  actor_id: "user_admin",
  agent_id: "agent_1",
  resource_type: "policy_evaluation",
  resource_id: "peval_1",
  decision: "deny",
  severity: "warning",
  correlation_id: "corr-1",
  policy_id: "policy_1",
  policy_version_id: "pver_1",
  payload_json: { matched_rule: "deny_delete", reason: "blocked" },
  created_at: "2026-05-01T00:00:00+00:00"
};

const runtimeEvent = {
  ...policyEvent,
  id: "evt_runtime",
  event_type: "runtime.action",
  source_component: "runtime-control",
  resource_type: "runtime_action",
  resource_id: "raction_1",
  decision: "allow",
  severity: "info",
  created_at: "2026-05-01T00:00:01+00:00"
};

const framework = {
  id: "cf_soc2_org_default",
  organization_id: "org_default",
  name: "SOC 2",
  version: "2026",
  description: "Trust services",
  status: "active",
  created_at: "2026-05-01T00:00:00+00:00"
};

const control = {
  id: "ctrl_soc2_cc6_6_org_default",
  framework_id: framework.id,
  framework_name: "SOC 2",
  control_code: "CC6.6",
  title: "Policy Enforcement",
  description: "Policy decisions are recorded.",
  required_evidence_types: ["policy_decision"],
  owner_user_id: "user_admin"
};

const evidence = {
  id: "evid_policy",
  organization_id: "org_default",
  environment_id: "env_default",
  control_id: control.id,
  control_code: "CC6.6",
  source_type: "audit_event",
  source_id: "evt_policy",
  title: "policy_decision evidence from policy.decision",
  summary: "policy-engine recorded policy.decision decision=deny",
  freshness_at: "2026-05-01T00:00:00+00:00",
  status: "fresh",
  created_at: "2026-05-01T00:00:00+00:00"
};

const violation = {
  id: "cviol_1",
  organization_id: "org_default",
  environment_id: "env_default",
  control_id: control.id,
  control_code: "CC6.6",
  agent_id: "agent_1",
  severity: "critical",
  status: "open",
  reason: "blocked by policy",
  source_type: "audit_event",
  source_id: "evt_policy",
  source_event_id: "evt_policy",
  acknowledged_by: null,
  acknowledged_at: null,
  resolved_by: null,
  resolved_at: null,
  resolution_reason: null,
  created_at: "2026-05-01T00:00:00+00:00",
  updated_at: "2026-05-01T00:00:00+00:00"
};

const report = {
  id: "crep_1",
  organization_id: "org_default",
  environment_id: "env_default",
  framework_id: framework.id,
  framework_name: "SOC 2",
  name: "SOC 2 Evidence Report",
  status: "generated",
  date_from: "2026-01-01",
  date_to: "2026-12-31",
  generated_by: "user_admin",
  artifact_uri: "compliance-report://crep_1.md",
  summary: { evidence_count: 1, open_violation_count: 1 },
  created_at: "2026-05-01T00:00:00+00:00",
  updated_at: "2026-05-01T00:00:00+00:00",
  generated_at: "2026-05-01T00:00:00+00:00",
  evidence_item_ids: ["evid_policy"],
  attestation_count: 0,
  rendered_markdown: "# SOC 2 Evidence Report\n\n## Evidence\n"
};

const reportArtifact = {
  id: "art_report_1",
  organization_id: "org_default",
  environment_id: "env_default",
  artifact_type: "compliance.report",
  name: "crep_1.md",
  content_type: "text/markdown",
  storage_uri: "local-artifact://org_default/env_default/art_report_1/crep_1.md",
  checksum: "sha256-report",
  size_bytes: 1024,
  created_by: "user_admin",
  created_at: "2026-05-01T00:00:00+00:00",
  links: [
    {
      id: "alink_report_1",
      artifact_id: "art_report_1",
      target_type: "compliance_report",
      target_id: "crep_1",
      link_type: "report",
      created_at: "2026-05-01T00:00:00+00:00"
    }
  ],
  attestations: []
};

test("component audit explorer renders event table timeline and verification", () => {
  const html = renderAuditExplorer({
    events: [policyEvent, runtimeEvent],
    selectedEvent: policyEvent,
    verification: { valid: true, checked_count: 1 },
    relatedEvents: [policyEvent, runtimeEvent]
  });

  assert.match(html, /data-compliance-audit-table/);
  assert.match(html, /data-compliance-audit-row="evt_policy"/);
  assert.match(html, /data-compliance-correlation-timeline="corr-1"/);
  assert.match(html, /data-compliance-hash-verification="evt_policy"/);
  assert.match(html, /policy-engine/);
});

test("component compliance page renders audit explorer instead of placeholder", () => {
  const html = renderCompliancePage({
    complianceAuditEvents: [policyEvent],
    complianceFrameworks: [framework],
    complianceControls: [control],
    complianceEvidence: [evidence],
    complianceViolations: [violation],
    complianceReports: [report],
    selectedComplianceReport: report
  });

  assert.match(html, /data-route-page="\/compliance"/);
  assert.match(html, /data-compliance-workspace/);
  assert.match(html, /data-compliance-audit-explorer/);
  assert.match(html, /data-compliance-control-map/);
  assert.match(html, /data-compliance-evidence-library/);
  assert.match(html, /data-compliance-violations/);
  assert.match(html, /data-compliance-reports/);
});

test("component control map renders controls with fresh evidence counts", () => {
  const html = renderControlMap({
    frameworks: [framework],
    controls: [control],
    evidence: [evidence]
  });

  assert.match(html, /data-compliance-control-table/);
  assert.match(html, /data-compliance-control-row="ctrl_soc2_cc6_6_org_default"/);
  assert.match(html, /SOC 2/);
  assert.match(html, /CC6\.6/);
  assert.match(html, /policy_decision/);
});

test("component evidence library renders evidence and recompute result", () => {
  const html = renderEvidenceLibrary({
    controls: [control],
    evidence: [evidence],
    filters: { control_id: control.id, status: "fresh" },
    recomputeResult: { scanned_event_count: 2, evidence_count: 1, refreshed_count: 1 }
  });

  assert.match(html, /data-compliance-evidence-table/);
  assert.match(html, /data-compliance-evidence-row="evid_policy"/);
  assert.match(html, /policy_decision evidence from policy\.decision/);
  assert.match(html, /1 mapped \/ 1 refreshed/);
});

test("component violation queue renders severity filter and actions", () => {
  const html = renderViolationQueue({
    violations: [violation],
    filters: { status: "open", severity: "critical" }
  });

  assert.match(html, /data-compliance-violation-table/);
  assert.match(html, /data-compliance-violation-row="cviol_1"/);
  assert.match(html, /option value="critical" selected/);
  assert.match(html, /data-compliance-violation-ack="cviol_1"/);
  assert.match(html, /data-compliance-violation-resolve-form/);
});

test("component report builder renders report list preview and attestation", () => {
  const html = renderReportBuilder({
    frameworks: [framework],
    reports: [report],
    selectedReport: report,
    artifacts: [reportArtifact],
    attestationResult: { id: "ratt_1" }
  });

  assert.match(html, /data-compliance-report-create-form/);
  assert.match(html, /data-compliance-report-row="crep_1"/);
  assert.match(html, /data-compliance-report-preview="crep_1"/);
  assert.match(html, /data-compliance-report-artifact="art_report_1"/);
  assert.match(html, /# SOC 2 Evidence Report/);
  assert.match(html, /data-compliance-report-attest-form/);
  assert.match(html, /ratt_1/);
});

test("audit filter and export payload helpers omit empty values", () => {
  assert.deepEqual(
    auditEventFilterParamsFromValues({
      event_type: "policy.decision",
      source_component: "policy-engine",
      actor_id: "",
      decision: "deny"
    }),
    { event_type: "policy.decision", source_component: "policy-engine", decision: "deny" }
  );
  assert.deepEqual(
    auditExportPayloadFromValues({
      format: "csv",
      source_component: "policy-engine",
      decision: "deny",
      resource_id: ""
    }),
    { format: "csv", filters: { source_component: "policy-engine", decision: "deny" } }
  );
  assert.deepEqual(
    complianceEvidenceFilterParamsFromValues({
      control_id: control.id,
      status: "fresh",
      ignored: ""
    }),
    { control_id: control.id, status: "fresh" }
  );
  assert.deepEqual(
    complianceViolationFilterParamsFromValues({
      status: "open",
      severity: "critical",
      control_id: "",
      agent_id: undefined
    }),
    { status: "open", severity: "critical" }
  );
  assert.deepEqual(
    complianceViolationPatchPayloadFromValues({
      status: "resolved",
      reason: "done"
    }),
    { status: "resolved", reason: "done" }
  );
  assert.deepEqual(
    complianceReportPayloadFromValues({
      framework_id: framework.id,
      name: "SOC 2",
      date_from: "2026-01-01",
      date_to: "2026-12-31",
      ignored: ""
    }),
    {
      framework_id: framework.id,
      name: "SOC 2",
      date_from: "2026-01-01",
      date_to: "2026-12-31"
    }
  );
  assert.deepEqual(
    complianceReportAttestationPayloadFromValues({
      statement: "I attest",
      signature_ref: ""
    }),
    { statement: "I attest" }
  );
});

test("api client audit explorer export methods call expected endpoints", async () => {
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

  await client.listAuditEvents({ source_component: "policy-engine", actor_id: "user_admin" });
  await client.exportAuditEvents({ format: "json", filters: { decision: "deny" } });

  assert.deepEqual(calls, [
    ["/api/v1/audit/events?source_component=policy-engine&actor_id=user_admin", "GET", null],
    ["/api/v1/audit/export", "POST", { format: "json", filters: { decision: "deny" } }]
  ]);
});

test("api client compliance control and evidence methods call expected endpoints", async () => {
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

  await client.listComplianceFrameworks();
  await client.createComplianceFramework({ name: "ISO", version: "2026" });
  await client.listComplianceControls({ framework_id: framework.id });
  await client.createComplianceControlMapping({
    control_id: control.id,
    event_type: "policy.decision",
    evidence_type: "policy_decision"
  });
  await client.listComplianceEvidence({ control_id: control.id, status: "fresh" });
  await client.recomputeComplianceEvidence();
  await client.listComplianceViolations({ status: "open", severity: "critical" });
  await client.patchComplianceViolation("cviol 1", { status: "acknowledged" });
  await client.createComplianceReport({ framework_id: framework.id, name: "SOC 2" });
  await client.listComplianceReports({ status: "generated" });
  await client.getComplianceReport("crep 1");
  await client.generateComplianceReport("crep 1");
  await client.downloadComplianceReport("crep 1");
  await client.attestComplianceReport("crep 1", { statement: "I attest" });

  assert.deepEqual(calls, [
    ["/api/v1/compliance/frameworks", "GET", null],
    ["/api/v1/compliance/frameworks", "POST", { name: "ISO", version: "2026" }],
    [`/api/v1/compliance/controls?framework_id=${framework.id}`, "GET", null],
    [
      "/api/v1/compliance/control-mappings",
      "POST",
      {
        control_id: control.id,
        event_type: "policy.decision",
        evidence_type: "policy_decision"
      }
    ],
    [
      `/api/v1/compliance/evidence?control_id=${control.id}&status=fresh`,
      "GET",
      null
    ],
    ["/api/v1/compliance/evidence/recompute", "POST", null],
    ["/api/v1/compliance/violations?status=open&severity=critical", "GET", null],
    ["/api/v1/compliance/violations/cviol%201", "PATCH", { status: "acknowledged" }],
    [
      "/api/v1/compliance/reports",
      "POST",
      { framework_id: framework.id, name: "SOC 2" }
    ],
    ["/api/v1/compliance/reports?status=generated", "GET", null],
    ["/api/v1/compliance/reports/crep%201", "GET", null],
    ["/api/v1/compliance/reports/crep%201/generate", "POST", null],
    ["/api/v1/compliance/reports/crep%201/download", "GET", null],
    ["/api/v1/compliance/reports/crep%201/attest", "POST", { statement: "I attest" }]
  ]);
});
