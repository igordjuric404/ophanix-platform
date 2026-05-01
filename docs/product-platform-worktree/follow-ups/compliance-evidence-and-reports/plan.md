# Compliance Evidence And Reports Completion

## Second-Pass Status

Status: `Obsolete follow-up`.

The compliance-specific gap from the first audit is implemented in `2de9148`: audit explorer/export, control frameworks, controls, mappings, evidence recompute, violations, compliance reports, downloads, attestations, API routes, frontend route, and focused backend/frontend tests now exist and pass in aggregate verification. This plan is retained as historical context only. The remaining artifact-store integration concern is tracked in `follow-ups/workflow-runner-and-artifacts/plan.md`, because it affects audit exports, compliance reports, and workflow outputs together.

## Feature Scope

Implement the missing compliance surfaces from `02-policy-governance/02-compliance`: Audit Explorer product page/export, Control Map and Evidence Library, Violations, and Compliance Report Builder. The goal is to turn audit events, workflow artifacts, and governance decisions into defensible compliance evidence and reports.

## Existing Repo Assets To Reuse

- Audit event query, verification, stream, hash chain, and drawers.
- Policy, agent, MCP, runtime, discovery, trust, and observability audit events.
- Workflow/artifact follow-up once available.
- Existing frontend drawer and table patterns.

## Out Of Scope

- Legal signing or external notarization.
- Custom enterprise framework designer beyond seeded/importable framework definitions.
- PDF generation unless a renderer is already available locally.

## Data Model

Add:

- `audit_exports`: id, organization_id, filters_json, format, status, artifact_uri, created_by, created_at.
- `control_frameworks`: id, organization_id, name, version, description, status.
- `controls`: id, framework_id, control_code, title, description, required_evidence_types_json, owner_user_id.
- `control_mappings`: id, control_id, event_type, source_component, predicate_json, evidence_type.
- `evidence_items`: id, organization_id, environment_id, control_id, source_type, source_id, title, summary, freshness_at, status, created_at.
- `violations`: id, control_id, agent_id, severity, status, reason, source_event_id, created_at.
- `compliance_reports`: id, organization_id, environment_id, framework_id, name, status, date_from, date_to, generated_by, artifact_uri, summary_json, created_at.
- `report_evidence_items`: report_id, evidence_item_id.
- `report_attestations`: id, report_id, attested_by, statement, signature_ref, created_at.

If the artifact store follow-up lands first, use its artifact and attestation tables instead of duplicating durable artifact metadata.

## API Surface

Implement:

- `POST /api/v1/audit/export`
- `GET /api/v1/compliance/frameworks`
- `POST /api/v1/compliance/frameworks`
- `GET /api/v1/compliance/controls`
- `POST /api/v1/compliance/control-mappings`
- `GET /api/v1/compliance/evidence`
- `POST /api/v1/compliance/evidence/recompute`
- `GET /api/v1/compliance/violations`
- `PATCH /api/v1/compliance/violations/{id}`
- `POST /api/v1/compliance/reports`
- `GET /api/v1/compliance/reports`
- `GET /api/v1/compliance/reports/{id}`
- `POST /api/v1/compliance/reports/{id}/generate`
- `GET /api/v1/compliance/reports/{id}/download`
- `POST /api/v1/compliance/reports/{id}/attest`

## UI Surface

Compliance -> Audit Explorer:

- Event table, filters, correlation timeline, verification badge, export action.

Compliance -> Control Map:

- Framework tabs, controls table, evidence freshness indicators.

Compliance -> Evidence Library:

- Evidence table, evidence detail drawer, linked audit/artifact references.

Compliance -> Reports:

- Report list, builder, preview, download, attestation form.

Compliance -> Violations:

- Filterable violation queue with acknowledge/resolve actions.

## Implementation Phases

### Phase 1: Audit Explorer Page And Export

Steps:

1. Extend audit filters for all planned fields where missing.
2. Add audit explorer frontend route instead of placeholder compliance page.
3. Add correlation timeline and hash verification UI.
4. Add export request endpoint and store export metadata.

Tests:

- API test filters by source component, actor, resource, severity/decision where present.
- API test export stores requested filters.
- Component test event table and timeline render.
- Component test export button sends current filters.

### Phase 2: Control Map And Evidence Recompute

Steps:

1. Add framework/control/mapping/evidence migrations and repository.
2. Seed SOC 2, GDPR, EU AI Act, and internal demo controls idempotently.
3. Implement evidence recompute from audit events and available artifacts.
4. Track evidence freshness and status.

Tests:

- Integration test seed is idempotent.
- Unit test policy decision event maps to policy enforcement control.
- Unit test credential rotation maps to credential control.
- Integration test recompute creates or refreshes evidence.

### Phase 3: Violations

Steps:

1. Create violations from denied actions, stale evidence, missing controls, and high-risk findings.
2. Add acknowledge and resolve actions.
3. Emit audit events for violation status changes.
4. Surface violations in API and UI.

Tests:

- Unit test high-severity denial creates violation.
- API test lists open violations.
- API test resolve action requires reason and emits audit event.
- Component test violations can be filtered by severity.

### Phase 4: Report Builder

Steps:

1. Add report creation, validation, and evidence selection.
2. Render Markdown and JSON reports from real evidence and violations.
3. Store/download generated artifact via artifact store or local adapter.
4. Add attestation endpoint and UI.

Tests:

- API test create draft report and reject invalid date range.
- Integration test report selects matching evidence and open violations.
- Unit test Markdown contains framework, controls, evidence, violations, and hash status.
- API test attestation requires statement and emits audit event.
- Component test builder and preview render generated report.

## Overall Validation

- Run the demo scenario.
- Recompute compliance evidence.
- Confirm controls show fresh evidence and blocked actions surface as violations where configured.
- Generate and download a report containing policy, identity, credential, MCP, discovery, approval, and audit hash evidence.
- Add an attestation and verify the audit event.

## Dependencies

- Event/audit pipeline.
- Policy evaluation feed follow-up.
- Workflow/artifact store follow-up for durable generated outputs.

## Definition Of Done

- Compliance is no longer a placeholder route.
- Runtime governance activity becomes mapped, queryable, reportable evidence backed by tests and audit history.
