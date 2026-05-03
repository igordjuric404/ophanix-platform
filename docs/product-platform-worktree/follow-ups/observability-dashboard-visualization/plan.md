# Observability Dashboard Visualization

## Feature Scope

Complete the visual dashboard expectations from `05-ecosystem-operations/02-observability/01-slo-cost-incident-dashboard.md`. The current React observability page preserves behavior through tables and metric cards; this follow-up adds the planned SLO/detail and cost visualizations without changing backend semantics unnecessarily.

## Existing Repo Assets To Reuse

- `packages/product-platform/frontend/src/features/observability/ObservabilityPage.tsx`.
- `packages/product-platform/frontend/src/api/observability.ts`.
- `packages/product-platform/frontend/src/components/shared/MetricCard.tsx`.
- Existing observability backend APIs for SLOs, measurements, cost budgets/events/dashboard, incidents, chaos, and rollouts.
- Installed `recharts` dependency.

## Out Of Scope

- Building a full Grafana replacement.
- Adding external telemetry collectors.
- Changing SLO or cost calculation semantics unless an existing API cannot support the planned visuals.
- Redesigning incident, chaos, or rollout workflows.

## Data Model

No data model changes are expected. If current APIs do not expose enough time-series detail, prefer adding a small read-only summary endpoint over changing existing write paths.

## API Surface

Prefer existing APIs:

- Observability SLO list/detail and measurements.
- Cost dashboard summary.
- Cost event list/rollup data if available.

Optional additive API:

- `GET /api/v1/observability/costs/trends` or equivalent only if existing cost dashboard data cannot support the visual.

## UI Surface

Observability:

- SLO table plus selected SLO detail chart.
- Cost by provider/model/tool chart with accessible table fallback.
- Clear empty states when no measurements or cost events exist.
- Preserve incident, chaos, and rollout controls as-is unless a visual needs related context.

## Implementation Phases

### Phase 1: Data Shape Inventory

Steps:

1. Inspect current observability API responses and tests for available measurement and cost buckets.
2. Decide whether charts can be derived in the frontend or need a read-only summary endpoint.
3. Keep current tables as the source of precise detail.

Tests:

- Existing observability backend tests pass.
- Existing React observability tests pass before edits.

### Phase 2: SLO Detail Chart

Steps:

1. Add a compact Recharts line or area chart for recent SLO measurements/burn rate.
2. Provide text/table fallback for empty or single-point data.
3. Keep chart dimensions stable in the dashboard layout.

Tests:

- Component test renders multi-point SLO trend.
- Component test renders empty-state fallback.

### Phase 3: Cost Visuals

Steps:

1. Replace the current metric-grid-only cost chart area with charted provider/model/tool distribution.
2. Preserve metric cards and budget table for exact values.
3. Ensure currency formatting and zero/empty data remain professional.

Tests:

- Component test renders provider/model cost bars or slices.
- Component test verifies the fallback when no cost events exist.

### Phase 4: Validation

Steps:

1. Run focused observability React tests.
2. Run `npm run validate`.
3. Run focused backend observability tests if any API was added.
4. Run Playwright smoke with localhost binding allowed if smoke fixtures are touched.

## Overall Validation

- Demo observability data shows useful charts and exact tables.
- Empty local data remains understandable.
- Existing SLO/cost/incident/chaos/rollout behavior is unchanged.

## Dependencies

- Existing observability backend routes and seed data.
- Frontend chart dependency already present in `package.json`.

## Definition Of Done

- The observability dashboard includes real charted SLO and cost visuals matching the product plan.
- Charts are covered by meaningful tests and do not replace auditable tabular detail.

