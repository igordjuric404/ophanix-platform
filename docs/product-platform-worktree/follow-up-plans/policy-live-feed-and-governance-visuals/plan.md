# Policy Live Feed And Governance Visuals

## Feature Scope

Finish the remaining frontend refactor gaps in `02-policy-governance` for the policy simulator and evaluation feed. The feed should use the shared event-stream framework, receive live rows in React tests, show decision trends as real governance visuals, and use the shared detail-drawer pattern for evaluation inspection.

## Existing Repo Assets To Reuse

- `packages/product-platform/frontend/src/features/policies/PoliciesPage.tsx`.
- `packages/product-platform/frontend/src/api/policies.ts`.
- `packages/product-platform/frontend/src/lib/eventSource.ts`.
- `packages/product-platform/frontend/src/app/drawerContext.tsx`.
- `packages/product-platform/frontend/src/components/drawers/DetailDrawer.tsx`.
- Backend policy evaluation APIs and stream endpoint under `/api/v1/policy-evaluations/*`.
- Backend tests `test_policy_evaluations*.py`.

## Out Of Scope

- Rewriting policy evaluation semantics.
- Adding a new policy backend.
- Changing policy binding behavior.
- Rebuilding the compliance report product surface.

## Data Model

No data model changes are expected. Reuse `policy_evaluations` and existing summary/time-bucket responses.

## API Surface

Reuse:

- `POST /api/v1/policy-evaluations/simulate`
- `POST /api/v1/policy-evaluations/evaluate`
- `GET /api/v1/policy-evaluations`
- `GET /api/v1/policy-evaluations/{id}`
- `GET /api/v1/policy-evaluations/summary`
- `GET /api/v1/policy-evaluations/stream`

Only adjust API response shapes if a visual requires data that cannot be derived safely from existing summary/list responses.

## UI Surface

Policies -> Evaluation Feed:

- Keep filterable decision table.
- Add charted trends for decisions over time and action distribution.
- Open evaluation details through a shared drawer or drawer-compatible shared pattern.
- Receive live evaluation updates through the shared event-stream hook.

## Implementation Phases

### Phase 1: Shared Event Stream Wiring

Steps:

1. Replace direct `window.EventSource` management in `PoliciesPage` with `useEventStream`.
2. Stabilize params and query keys with `useMemo` so filter changes intentionally reconnect and ordinary renders do not.
3. Preserve deterministic row upsert behavior for streamed evaluations.
4. Invalidate summary/list queries when live events arrive.

Tests:

- Unit test `eventStreamUrl` preserves query params.
- React test uses a fake EventSource to emit an evaluation and verifies the row appears or the query invalidates/refetches.
- Regression test filters still call the expected API query.

### Phase 2: Shared Detail Pattern

Steps:

1. Move evaluation detail from inline-only rendering into the shared drawer framework or a small shared drawer variant.
2. Preserve correlation id, policy id, matched rule, resource, context payload, and audit navigation.
3. Keep keyboard close and deep-link behavior consistent with audit drawers where practical.

Tests:

- React test opens an evaluation detail drawer.
- React test verifies context payload and correlation id are visible.
- Existing drawer tests still pass.

### Phase 3: Governance Visuals

Steps:

1. Add Recharts-based decision trend and action distribution components with accessible table/text fallbacks.
2. Use the existing summary endpoint where possible.
3. Keep visual styling aligned with the existing compact operations dashboard.
4. Avoid hiding table data behind charts.

Tests:

- Component test renders time-bucket trend data.
- Component test renders action/decision counts.
- `npm run validate`.

## Overall Validation

- Simulate a deny decision and see it in the table and detail drawer.
- Emit or mock a live streamed evaluation and see the feed update.
- Confirm decision trends render from summary data.
- Backend policy evaluation tests still pass.

## Dependencies

- `00-platform-foundation` shared drawer framework.
- Existing policy evaluation summary/stream backend.
- Frontend legacy retirement should preserve new Vitest coverage.

## Definition Of Done

- Policy evaluation feed follows the shared React framework patterns.
- Live update behavior is tested in the React UI.
- Decision trends are visually useful and remain auditable through tables/details.

