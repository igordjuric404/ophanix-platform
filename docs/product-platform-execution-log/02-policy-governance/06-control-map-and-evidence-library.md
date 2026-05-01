# Control Map And Evidence Library Execution Log

Source plan: `docs/product-platform-worktree/02-policy-governance/02-compliance/02-control-map-evidence-library.md`

## Phase Overview

| Phase | Goal | Status | Biggest Checklist Items |
| --- | --- | --- | --- |
| Phase 1: Framework And Control Seed | Create and seed demo compliance frameworks and controls. | Not Started | Tables; SOC 2/GDPR/EU AI/Internal seeds; admin import; read APIs. |
| Phase 2: Evidence Mapping Engine | Recompute evidence items from audit events and mapping rules. | Not Started | Rule predicates; recompute job; create/update evidence; freshness/status. |
| Phase 3: Violations | Generate and operate governance violations. | Not Started | Denied/stale/missing/high-risk rules; severity/status; resolve; audit events. |
| Phase 4: UI | Build control map, evidence library, and violations queue. | Not Started | Framework tabs; freshness indicators; evidence filters/drawer; violation filters. |

## Detailed Checklist

### Phase 1: Framework And Control Seed

- [ ] Add framework/control/mapping/evidence/violation tables.
- [ ] Seed SOC 2 framework.
- [ ] Seed GDPR framework.
- [ ] Seed EU AI Act framework.
- [ ] Seed internal policy framework.
- [ ] Seed controls for identity, policy enforcement, credentials, MCP governance, audit, discovery, and approval.
- [ ] Ensure seed is idempotent.
- [ ] Add `GET /api/v1/compliance/frameworks`.
- [ ] Add `POST /api/v1/compliance/frameworks`.
- [ ] Add `GET /api/v1/compliance/controls`.
- [ ] Add `POST /api/v1/compliance/control-mappings`.
- [ ] Test seed idempotency.
- [ ] Test framework/control APIs.
- [ ] Test Viewer can read controls.

### Phase 2: Evidence Mapping Engine

- [ ] Define mapping rules from event type/source/predicate to controls.
- [ ] Add recompute service over audit events.
- [ ] Create or update evidence items.
- [ ] Track evidence freshness.
- [ ] Compute evidence status.
- [ ] Add `GET /api/v1/compliance/evidence`.
- [ ] Add `POST /api/v1/compliance/evidence/recompute`.
- [ ] Test policy decision maps to policy enforcement control.
- [ ] Test credential rotation maps to credential control.
- [ ] Test recompute creates evidence.

### Phase 3: Violations

- [ ] Define violation creation rules from denied actions.
- [ ] Define stale evidence and missing control rules.
- [ ] Define high-risk finding rules.
- [ ] Add violation status storage.
- [ ] Add resolve action.
- [ ] Emit audit event for violation status changes.
- [ ] Add `GET /api/v1/compliance/violations`.
- [ ] Test high-severity denial creates violation.
- [ ] Test lists open violations.
- [ ] Test resolve action emits audit event.

### Phase 4: UI

- [ ] Add frontend API client methods.
- [ ] Build Control Map framework tabs.
- [ ] Build control status table.
- [ ] Build evidence freshness indicators.
- [ ] Build Evidence Library filters and drawer.
- [ ] Build Violations queue with severity filter.
- [ ] Component test control map renders status.
- [ ] Component test evidence drawer opens linked audit event.
- [ ] Component test violations filter by severity.

## Progress Notes

- 2026-05-01: Created initial execution log from the implementation plan.
