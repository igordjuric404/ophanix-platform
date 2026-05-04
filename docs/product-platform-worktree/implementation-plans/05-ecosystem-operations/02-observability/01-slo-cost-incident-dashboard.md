# SLO, Cost, And Incident Dashboard

## Feature Scope

Persist and visualize SLOs, cost budgets, cost events, incidents, and alerts for governed agents. The dashboard links operational signals to policies, agents, MCP calls, trust changes, and runtime actions.

## Existing Repo Assets To Reuse

- SLO, cost, incident, and circuit breaker modules from `packages/agent-sre`.
- Agent SRE FastAPI concepts.
- Grafana dashboards as reference.

## Out Of Scope

- Chaos experiments and rollouts.
- Full PagerDuty/ServiceNow integration.

## Data Model

Tables:

- `slo_objectives`: id, organization_id, environment_id, name, target_type, target_id, sli, target_value, window, status.
- `slo_measurements`: id, slo_id, value, error_budget_remaining, burn_rate, measured_at.
- `cost_budgets`: id, organization_id, environment_id, target_type, target_id, period, amount_limit, action_on_breach, status.
- `cost_events`: id, target_type, target_id, provider, model, amount, units, correlation_id, created_at.
- `incidents`: id, organization_id, environment_id, severity, status, title, summary, owner_user_id, correlation_id, started_at, resolved_at.

## API Surface

Implement:

- `POST /api/v1/observability/slo`
- `GET /api/v1/observability/slo`
- `POST /api/v1/observability/slo/{id}/measurements`
- `POST /api/v1/observability/cost-budgets`
- `GET /api/v1/observability/costs`
- `GET /api/v1/observability/incidents`
- `POST /api/v1/observability/incidents/{id}/ack`
- `POST /api/v1/observability/incidents/{id}/resolve`

## UI Surface

Observability -> Overview.

Observability -> SLOs.

Observability -> Costs.

Observability -> Incidents.

## Implementation Phases

### Phase 1: SLO Store And Measurements

Steps:

1. Create SLO tables.
2. Wrap Agent SRE objective calculations.
3. Add create/list endpoints.
4. Add measurement ingestion endpoint.

Tests:

- API test creates SLO.
- Unit test burn-rate calculation.
- Integration test measurement updates status.

### Phase 2: Cost Budgets

Steps:

1. Create budget and event tables.
2. Add budget create/list endpoints.
3. Add cost event ingestion.
4. Evaluate breach action: warn, throttle placeholder, kill switch link.

Tests:

- API test creates budget.
- Integration test cost event updates budget used.
- Unit test breach action computed correctly.

### Phase 3: Incidents

Steps:

1. Create incident table.
2. Add incident creation from high-severity audit events or manual API.
3. Add acknowledge and resolve endpoints.
4. Link incident to correlation id and related events.

Tests:

- API test create incident.
- API test acknowledge changes status.
- API test resolve requires resolution note.
- Integration test incident links to audit events.

### Phase 4: UI

Steps:

1. Build observability overview cards.
2. Build SLO table and detail chart.
3. Build cost charts by agent, provider, model, tool.
4. Build incident queue and detail drawer.

Tests:

- Component test SLO table renders burn rate.
- Component test cost chart handles empty state.
- Component test incident resolve requires note.

## Overall Validation

- Create SLO for demo agent task success.
- Ingest success/failure measurements.
- Ingest model cost events.
- Trigger incident from repeated denials.
- Confirm all are visible and linked to audit.

## Dependencies

- Event pipeline.
- Agent inventory.
- Runtime/MCP/policy events.

## Definition Of Done

- Operational health is persistent and correlated with governance activity.
