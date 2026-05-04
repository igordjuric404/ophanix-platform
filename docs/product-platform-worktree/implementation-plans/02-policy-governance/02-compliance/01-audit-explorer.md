# Audit Explorer

## Feature Scope

Build the product UI and query API for exploring audit events. Users can filter, inspect, correlate, verify hashes, and export selected event sets.

## Existing Repo Assets To Reuse

- Event and audit pipeline.
- Existing audit logger concepts from Agent OS.
- Hypervisor audit commitment concepts.

## Out Of Scope

- Compliance control mapping.
- Report generation.

## Data Model

Uses:

- `audit_events`.
- `audit_event_hashes`.

Optional:

- `audit_exports`: id, organization_id, filters_json, format, status, artifact_uri, created_by, created_at.

## API Surface

Implement or extend:

- `GET /api/v1/audit/events`
- `GET /api/v1/audit/events/{id}`
- `POST /api/v1/audit/events/{id}/verify`
- `POST /api/v1/audit/verify-range`
- `POST /api/v1/audit/export`

## UI Surface

Compliance -> Audit Explorer:

- Event table.
- Filter builder.
- Correlation timeline.
- Raw JSON drawer.
- Hash verification badge.
- Export selected range.

## Implementation Phases

### Phase 1: Query Filters

Steps:

1. Add API filters for time range, event type, source component, actor, agent, resource, decision, severity, policy, correlation id.
2. Add pagination and stable sorting.
3. Add saved URL query state for frontend.

Tests:

- API test filters by event type.
- API test filters by correlation id.
- API test pagination does not skip events.

### Phase 2: Explorer Table UI

Steps:

1. Build table with key columns.
2. Add filter bar and advanced filter drawer.
3. Add row click to open Audit Event Drawer.
4. Add severity and decision badges.

Tests:

- Component test event table renders.
- Component test filters update URL.
- Component test row click opens drawer.

### Phase 3: Correlation Timeline

Steps:

1. Add correlation timeline view grouped by correlation id.
2. Show event sequence and source components.
3. Add quick link from any event detail to full correlation timeline.

Tests:

- Component test timeline orders events.
- API test correlation query returns all related events.
- Component test empty correlation state.

### Phase 4: Verification And Export

Steps:

1. Add hash verification action for event and range.
2. Display verification result.
3. Add export request for current filters.
4. Store export artifact through workflow/artifact system when available.

Tests:

- API test hash verification success.
- API test tampered hash verification failure.
- Component test export button sends filters.

## Overall Validation

- Open audit explorer after demo scenario.
- Filter to blocked MCP calls.
- Inspect raw event and related policy decision.
- Verify hash range.
- Export selected events.

## Dependencies

- Event and audit pipeline.
- Shared detail drawers.
- Background worker for export if asynchronous.

## Definition Of Done

- Audit events are explorable and defensible as product evidence.
