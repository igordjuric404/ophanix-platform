# Compliance Report Builder Execution Log

Source plan: `docs/product-platform-worktree/02-policy-governance/02-compliance/03-compliance-report-builder.md`

## Phase Overview

| Phase | Goal | Status | Biggest Checklist Items |
| --- | --- | --- | --- |
| Phase 1: Report Definition | Store report drafts and validate framework/date/environment scope. | Not Started | Tables; create endpoint; range/framework validation; draft status. |
| Phase 2: Evidence Selection | Link evidence, violations, audit counts, and hash status into report summaries. | Not Started | Evidence selector; violation summary; audit count/hash summary; link table. |
| Phase 3: Report Rendering | Render Markdown/JSON artifacts and emit audit events. | Not Started | Markdown renderer; JSON export; artifact URI; download endpoint. |
| Phase 4: UI Preview And Attestation | Build report builder, preview, download, and attestation UI. | Not Started | Builder form; preview sections; statement-required attestation; report list. |

## Detailed Checklist

### Phase 1: Report Definition

- [ ] Add `compliance_reports`, `report_evidence_items`, and `attestations` tables.
- [ ] Add repository create/list/get operations.
- [ ] Add date range validation.
- [ ] Validate framework belongs to organization.
- [ ] Validate environment belongs to organization when supplied.
- [ ] Store report as draft.
- [ ] Add `POST /api/v1/compliance/reports`.
- [ ] Add `GET /api/v1/compliance/reports`.
- [ ] Add `GET /api/v1/compliance/reports/{id}`.
- [ ] Test create draft report.
- [ ] Test invalid date range rejected.
- [ ] Test report organization/environment scoping.

### Phase 2: Evidence Selection

- [ ] Select evidence by framework, date range, environment, and controls.
- [ ] Include open violation counts by severity.
- [ ] Include audit event count.
- [ ] Include hash verification summary.
- [ ] Store selected evidence links.
- [ ] Test selection by date range.
- [ ] Test generated report links evidence.
- [ ] Test open violations included in summary.

### Phase 3: Report Rendering

- [ ] Render Markdown report.
- [ ] Render JSON export.
- [ ] Store artifact URI/content reference.
- [ ] Emit audit event when generated.
- [ ] Add `POST /api/v1/compliance/reports/{id}/generate`.
- [ ] Add `GET /api/v1/compliance/reports/{id}/download`.
- [ ] Test Markdown contains framework and controls.
- [ ] Test generated artifact is stored.
- [ ] Test download returns artifact.
- [ ] Test generation emits audit event.

### Phase 4: UI Preview And Attestation

- [ ] Add frontend API client methods.
- [ ] Build report builder form.
- [ ] Build report list.
- [ ] Build preview sections for summary, control status, evidence, violations, and audit hash status.
- [ ] Build download action.
- [ ] Build attestation form requiring statement.
- [ ] Add `POST /api/v1/compliance/reports/{id}/attest`.
- [ ] Component test builder validates required fields.
- [ ] Component test preview renders generated report.
- [ ] Component test attestation requires statement.

## Progress Notes

- 2026-05-01: Created initial execution log from the implementation plan.
