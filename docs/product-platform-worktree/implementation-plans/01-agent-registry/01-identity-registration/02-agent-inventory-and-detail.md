# Agent Inventory And Detail

## Feature Scope

Build the agent inventory table and agent detail page. This feature lets users inspect all registered agents, filter by governance state, and drill into identity, policies, credentials, trust, runtime, audit, and integration context.

## Existing Repo Assets To Reuse

- Agent registry fields from `AgentRegistry`.
- Lifecycle summary from `LifecycleManager`.
- Trust card and credential models from AgentMesh.
- Dashboard requirements from `docs/product-platform-plan/04-dashboard-specification.md`.

## Out Of Scope

- Agent registration wizard.
- Credential rotation actions.
- Trust score calculation.

## Data Model

Uses:

- `agents`.
- `agent_identities`.
- `agent_capabilities`.
- `agent_protocols`.
- `agent_heartbeats`.
- `agent_lifecycle_events`.
- Joins to policies, credentials, trust, audit, runtime, and integrations as those features land.

## API Surface

Implement:

- `GET /api/v1/agents`
- `GET /api/v1/agents/{id}`
- `GET /api/v1/agents/{id}/timeline`
- `GET /api/v1/agents/{id}/audit`
- `PATCH /api/v1/agents/{id}`

## UI Surface

Agents -> Inventory:

- Table with filters and row actions.

Agent detail tabs:

- Overview.
- Identity.
- Policies.
- Credentials.
- Trust.
- Audit.
- Runtime.
- Integrations.

## Implementation Phases

### Phase 1: Inventory API

Steps:

1. Implement paginated agent list.
2. Add filters for status, owner, sponsor, framework, protocol, trust tier, capability, environment.
3. Add sorting by name, status, trust score, credential expiry, last heartbeat.
4. Return summary fields needed by the table.

Tests:

- API test list returns only current organization/environment.
- API test status filter works.
- API test pagination is stable.
- API test sorting by last heartbeat works.

### Phase 2: Inventory UI

Steps:

1. Build table with all required columns.
2. Add filter bar and saved default sort.
3. Add row actions: open, suspend placeholder, rotate credential placeholder, change owner placeholder, decommission placeholder.
4. Link actions to real endpoints only when those features exist.

Tests:

- Component test renders agent row.
- Component test filters call API with expected params.
- Component test empty state suggests registering an agent.

### Phase 3: Agent Detail API

Steps:

1. Implement aggregate detail endpoint.
2. Include identity, lifecycle summary, capabilities, protocols, and latest heartbeat.
3. Add timeline endpoint combining lifecycle and audit events.
4. Fail with 404 for inaccessible agent.

Tests:

- API test detail returns expected sections.
- API test inaccessible agent is hidden.
- Integration test timeline returns ordered events.

### Phase 4: Agent Detail UI

Steps:

1. Build Overview tab with status, trust, owner, sponsor, last heartbeat, credential status.
2. Build Identity tab with DID and key fingerprint.
3. Build placeholder-aware tabs for policies, credentials, trust, runtime, and integrations.
4. Build Audit tab using shared event drawer.

Tests:

- Component test Overview tab renders.
- Component test Identity tab renders DID.
- Component test Audit tab opens event drawer.

## Overall Validation

- Register or seed multiple agents.
- Filter and sort inventory.
- Open detail page and verify all related state is visible.
- Confirm no cross-environment data appears.

## Dependencies

- Agent registration data.
- Event pipeline.
- Frontend shell.
- Shared detail drawers.

## Definition Of Done

- Agent inventory is the central operational list for the product.
- Detail page gives enough context to operate a registered agent without reading repo internals.
