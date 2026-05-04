# Compliance Report Builder

## Feature Scope

Build a report workflow that generates compliance reports from control status, evidence items, violations, and selected audit events. Reports should be previewable, exportable, and auditable.

## Existing Repo Assets To Reuse

- Governance attestation concepts from `packages/agent-compliance`.
- Evidence library and audit explorer.
- Existing report-like artifacts in examples can guide content.

## Out Of Scope

- Custom drag-and-drop report designer.
- Legal signing and external notary.

## Data Model

Tables:

- `compliance_reports`: id, organization_id, environment_id, framework_id, name, status, date_from, date_to, generated_by, artifact_uri, summary_json, created_at.
- `report_evidence_items`: report_id, evidence_item_id.
- `attestations`: id, report_id, attested_by, statement, signature_ref, created_at.

## API Surface

Implement:

- `POST /api/v1/compliance/reports`
- `GET /api/v1/compliance/reports`
- `GET /api/v1/compliance/reports/{id}`
- `POST /api/v1/compliance/reports/{id}/generate`
- `GET /api/v1/compliance/reports/{id}/download`
- `POST /api/v1/compliance/reports/{id}/attest`

## UI Surface

Compliance -> Reports:

- Report list.
- Report builder.
- Preview page.
- Evidence appendix.
- Download and attest actions.

## Implementation Phases

### Phase 1: Report Definition

Steps:

1. Add report tables.
2. Add create report endpoint with framework, date range, environment, and options.
3. Validate date range and framework.
4. Store report as draft.

Tests:

- API test create draft report.
- API test invalid date range rejected.
- API test report is scoped to organization/environment.

### Phase 2: Evidence Selection

Steps:

1. Select evidence items matching framework, date range, environment, and controls.
2. Include open violations summary.
3. Include audit event count and hash verification summary.
4. Store selected evidence links.

Tests:

- Unit test evidence selection by date range.
- Integration test report links selected evidence.
- Unit test open violations included in summary.

### Phase 3: Report Rendering

Steps:

1. Render Markdown report first.
2. Add JSON export.
3. Add PDF export if renderer is available.
4. Store artifact URI.
5. Emit audit event when generated.

Tests:

- Unit test Markdown contains framework and controls.
- Integration test generated artifact is stored.
- API test download returns artifact.
- Integration test generation emits audit event.

### Phase 4: UI Preview And Attestation

Steps:

1. Build report builder form.
2. Build preview page with sections: summary, control status, evidence, violations, audit hash status.
3. Add attestation form requiring statement.
4. Add report list and download action.

Tests:

- Component test builder validates required fields.
- Component test preview renders generated report.
- Component test attestation requires statement.

## Overall Validation

- Generate report for demo scenario.
- Confirm it includes policy, identity, credential, MCP, discovery, and approval evidence.
- Download Markdown or JSON.
- Add attestation and verify audit event.

## Dependencies

- Control Map and Evidence Library.
- Audit Explorer.
- Artifact store or workflow artifacts.
- Background worker.

## Definition Of Done

- Compliance reports are generated from real product evidence, not hand-written demo summaries.
