# Audit Explorer Execution Log

Source plan: `docs/product-platform-worktree/02-policy-governance/02-compliance/01-audit-explorer.md`

## Phase Overview

| Phase | Goal | Status | Biggest Checklist Items |
| --- | --- | --- | --- |
| Phase 1: Query Filters | Expand audit querying for compliance-grade filtering and pagination. | Not Started | Time, type, source, actor, agent, resource, decision, severity, policy, correlation filters; stable sort. |
| Phase 2: Explorer Table UI | Build filterable audit table with event detail drawers. | Not Started | Table; filter bar/drawer; row click; severity/decision badges. |
| Phase 3: Correlation Timeline | Show ordered event sequences by correlation id. | Not Started | Timeline grouping; source components; quick links; empty state. |
| Phase 4: Verification And Export | Verify hashes and export filtered event sets. | Not Started | Event/range verification; export endpoint; UI result; artifact fallback. |

## Detailed Checklist

### Phase 1: Query Filters

- [ ] Add source component and actor filters to `AuditEventQuery`.
- [ ] Add environment and policy version filters where useful.
- [ ] Preserve stable sorting by created time and id.
- [ ] Confirm pagination does not skip events.
- [ ] Add API query params for new filters.
- [ ] Test event type filter.
- [ ] Test correlation id filter.
- [ ] Test pagination stability.

### Phase 2: Explorer Table UI

- [ ] Add frontend API client methods for verify range/export.
- [ ] Build audit explorer route/surface.
- [ ] Build table with event type, source, actor, resource, decision, severity, correlation, and time.
- [ ] Build simple and advanced filters with URL query state.
- [ ] Open existing audit event drawer on row click.
- [ ] Render severity and decision badges.
- [ ] Component test event table renders.
- [ ] Component test filters update URL.
- [ ] Component test row click opens drawer.

### Phase 3: Correlation Timeline

- [ ] Add API filter for correlation timeline.
- [ ] Build timeline ordered by created time and id.
- [ ] Show event sequence and source components.
- [ ] Link from audit detail to correlation timeline.
- [ ] Add empty state for missing correlation.
- [ ] Component test timeline orders events.
- [ ] API test correlation query returns all events.
- [ ] Component test empty correlation state.

### Phase 4: Verification And Export

- [ ] Add `POST /api/v1/audit/export`.
- [ ] Store export requests in `audit_exports` or return deterministic inline artifact metadata.
- [ ] Use existing hash verification for event/range checks.
- [ ] Display verification result in UI.
- [ ] Add export action for current filters.
- [ ] Test hash verification success.
- [ ] Test tampered hash verification failure.
- [ ] Component test export sends filters.

## Progress Notes

- 2026-05-01: Created initial execution log from the implementation plan.
