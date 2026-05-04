# Event And Audit Pipeline

## Feature Scope

Create the unified event and audit pipeline used by every product feature. The pipeline stores all governance events in one queryable table, emits live updates to the UI, and supports tamper-evident hash chaining.

## Existing Repo Assets To Reuse

- `GovernanceAuditLogger` and backends from `packages/agent-os/src/agent_os/audit_logger.py`.
- Hypervisor audit commitment concepts from `packages/agent-hypervisor`.
- AgentMesh event bus concepts from `packages/agent-mesh/src/agentmesh/events`.

## Out Of Scope

- Full compliance report generation. Covered separately.
- SIEM export. Later enterprise extension.

## Data Model

Tables:

- `audit_events`: id, organization_id, environment_id, event_type, source_component, actor_type, actor_id, agent_id, resource_type, resource_id, decision, severity, correlation_id, trace_id, policy_id, policy_version_id, trust_delta, payload_json, created_at.
- `audit_event_hashes`: event_id, previous_hash, current_hash, algorithm, created_at.
- `event_subscriptions`: id, organization_id, name, filters_json, destination_type, destination_config_json, enabled.

## API Surface

Implement:

- `POST /api/v1/audit/events`
- `GET /api/v1/audit/events`
- `GET /api/v1/audit/events/{id}`
- `GET /api/v1/audit/events/stream`
- `POST /api/v1/audit/events/{id}/verify`
- `POST /api/v1/audit/verify-range`

## UI Surface

Shared consumers:

- Audit Explorer.
- Live event panels.
- Detail drawers for policy, agent, MCP, runtime, trust, discovery, marketplace, and compliance pages.

## Implementation Phases

### Phase 1: Event Envelope

Steps:

1. Define a canonical event envelope model.
2. Add validation for required fields.
3. Add helper functions for policy decision, agent lifecycle, trust change, MCP call, runtime action, and workflow run events.
4. Ensure all events include organization and environment.

Tests:

- Unit test valid event envelope.
- Unit test invalid event missing organization fails.
- Unit test event helper creates expected event type and payload.

### Phase 2: Persistent Audit Store

Steps:

1. Create audit tables.
2. Implement insert and query repository.
3. Add filters for time range, event type, agent, decision, severity, policy, resource, and correlation id.
4. Add pagination.

Tests:

- Integration test inserts and reads event.
- Integration test filters by correlation id.
- Integration test pagination is stable by created time and id.

### Phase 3: Hash Chain

Steps:

1. Calculate current event hash from normalized event payload and previous hash.
2. Store hash metadata.
3. Add single-event and range verification.
4. Fail verification on modified payload.

Tests:

- Unit test canonical hash input is stable.
- Integration test hash chain verifies after inserts.
- Integration test tampered payload fails verification.

### Phase 4: Live Stream

Steps:

1. Publish newly inserted events to Redis or in-process pub/sub for local demo.
2. Add server-sent events or WebSocket stream endpoint.
3. Add filter support for stream subscribers.
4. Handle reconnect with `last_event_id`.

Tests:

- API test opens stream and receives inserted event.
- API test stream filter only receives matching event type.
- API test reconnect can resume from last event id.

## Overall Validation

- Trigger events from at least two sources and see them in one query.
- Verify hash chain for the event range.
- Open live stream and confirm UI receives new events.

## Dependencies

- Product API shell.
- Database schema.
- Redis or compatible live event backend.

## Definition Of Done

- All product features can write canonical events.
- Audit events are persisted, filterable, streamable, and hash-verifiable.
- The event contract is documented and stable.
