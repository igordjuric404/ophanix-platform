# Control Map And Evidence Library

## Feature Scope

Map audit events and workflow artifacts to compliance controls. Build a control map and evidence library that show whether governance controls have current, sufficient evidence.

## Existing Repo Assets To Reuse

- Compliance attestation concepts from `packages/agent-compliance`.
- Audit events from the product event pipeline.
- Existing compliance-related examples and governance tests.

## Out Of Scope

- Generating final reports.
- Custom enterprise control framework builder.

## Data Model

Tables:

- `control_frameworks`: id, organization_id, name, version, description, status.
- `controls`: id, framework_id, control_code, title, description, required_evidence_types_json, owner_user_id.
- `control_mappings`: id, control_id, event_type, source_component, predicate_json, evidence_type.
- `evidence_items`: id, organization_id, environment_id, control_id, source_type, source_id, title, summary, freshness_at, status, created_at.
- `violations`: id, control_id, agent_id, severity, status, reason, source_event_id, created_at.

## API Surface

Implement:

- `GET /api/v1/compliance/frameworks`
- `POST /api/v1/compliance/frameworks`
- `GET /api/v1/compliance/controls`
- `POST /api/v1/compliance/control-mappings`
- `GET /api/v1/compliance/evidence`
- `POST /api/v1/compliance/evidence/recompute`
- `GET /api/v1/compliance/violations`

## UI Surface

Compliance -> Control Map:

- Framework tabs.
- Control status table.
- Evidence freshness.

Compliance -> Evidence Library:

- Evidence table.
- Evidence detail drawer.
- Linked audit events and artifacts.

Compliance -> Violations:

- Violation queue.

## Implementation Phases

### Phase 1: Framework And Control Seed

Steps:

1. Add control framework and control tables.
2. Seed demo frameworks: SOC 2, GDPR, EU AI Act, internal policy.
3. Seed minimal controls for identity, policy enforcement, credentials, MCP governance, audit, discovery, approval.
4. Add CRUD or admin-only import for frameworks.

Tests:

- Integration test seed is idempotent.
- API test lists frameworks and controls.
- API test Viewer can read controls.

### Phase 2: Evidence Mapping Engine

Steps:

1. Define mapping rules from event type/source/predicate to control evidence.
2. Implement recompute job over audit events.
3. Create or update evidence items.
4. Track freshness and status.

Tests:

- Unit test policy decision event maps to policy enforcement control.
- Unit test credential rotation event maps to credential control.
- Integration test recompute creates evidence item.

### Phase 3: Violations

Steps:

1. Define violation creation rules from denied actions, stale evidence, missing controls, and high-risk findings.
2. Store violation severity and status.
3. Add acknowledge and resolve actions later or as simple patch.
4. Emit audit events for violation status changes.

Tests:

- Unit test high-severity denial creates violation.
- API test lists open violations.
- Integration test resolve action emits audit event.

### Phase 4: UI

Steps:

1. Build Control Map with framework tabs.
2. Build evidence freshness indicators.
3. Build Evidence Library with filters by framework, control, source, freshness, status.
4. Build Violations queue.

Tests:

- Component test control map renders status.
- Component test evidence drawer opens linked audit event.
- Component test violations can be filtered by severity.

## Overall Validation

- Run demo scenario.
- Recompute evidence.
- Confirm controls show fresh evidence.
- Confirm blocked action appears as violation or evidence depending on rule.

## Dependencies

- Audit Explorer.
- Event pipeline.
- Background worker.

## Definition Of Done

- Runtime governance activity becomes mapped compliance evidence.
- Users can see what controls have evidence and where gaps remain.
