# Lifecycle State Workflows

## Feature Scope

Productize agent lifecycle management: approve, reject, activate, suspend, resume, change owner, decommission, heartbeat, orphan detection, and lifecycle timeline.

## Existing Repo Assets To Reuse

- `LifecycleManager` from `packages/agent-mesh/src/agentmesh/lifecycle/manager.py`.
- `OrphanDetector` from `packages/agent-mesh/src/agentmesh/lifecycle/orphan_detector.py`.
- Existing lifecycle states: pending approval, provisioned, active, suspended, rotating credentials, decommissioning, decommissioned, orphaned.

## Out Of Scope

- Agent registration field collection.
- Discovery findings.
- Credential rotation implementation beyond lifecycle event hooks.

## Data Model

Tables:

- `agent_lifecycle_events`: id, agent_id, previous_state, next_state, actor_id, reason, metadata_json, created_at.
- `agent_heartbeats`: id, agent_id, observed_at, status, metadata_json.
- Add lifecycle fields to `agents`: status, last_heartbeat_at, decommissioned_at.

## API Surface

Implement:

- `POST /api/v1/agents/{id}/approve`
- `POST /api/v1/agents/{id}/reject`
- `POST /api/v1/agents/{id}/activate`
- `POST /api/v1/agents/{id}/suspend`
- `POST /api/v1/agents/{id}/resume`
- `POST /api/v1/agents/{id}/change-owner`
- `POST /api/v1/agents/{id}/decommission`
- `POST /api/v1/agents/{id}/heartbeat`
- `POST /api/v1/agents/orphan-detection/run`

## UI Surface

Agents -> Lifecycle:

- Lifecycle funnel.
- Approval queue.
- Orphan candidates.
- Lifecycle event table.

Agent Detail -> Lifecycle timeline.

## Implementation Phases

### Phase 1: Lifecycle Adapter

Steps:

1. Implement adapter around existing `LifecycleManager`.
2. Map product agent status to lifecycle manager states.
3. Persist lifecycle events in product DB.
4. Emit audit event for every transition.

Tests:

- Unit test valid state transition.
- Unit test invalid transition fails.
- Integration test transition persists lifecycle event.
- Integration test audit event emitted.

### Phase 2: Lifecycle APIs

Steps:

1. Add action endpoints with reason fields.
2. Enforce permissions per action.
3. Validate transition before writing.
4. Return updated agent summary.

Tests:

- API test suspend active agent.
- API test cannot activate rejected agent.
- API test reason is required for suspend and decommission.
- API test Viewer cannot mutate lifecycle.

### Phase 3: Heartbeats And Orphan Detection

Steps:

1. Add heartbeat endpoint for agents and SDKs.
2. Update `last_heartbeat_at`.
3. Implement orphan detection job using heartbeat age, owner status, and agent status.
4. Mark orphan candidates or orphaned agents according to configured threshold.

Tests:

- API test heartbeat updates last heartbeat.
- Unit test orphan detector marks stale active agent.
- Integration test orphan job emits lifecycle and audit events.

### Phase 4: Lifecycle UI

Steps:

1. Build lifecycle funnel.
2. Build approval queue.
3. Build orphan candidates table.
4. Add lifecycle timeline to agent detail.
5. Add action confirmation modals.

Tests:

- Component test approval queue renders pending agents.
- Component test suspend action requires reason.
- Component test orphan table links to agent detail.

## Overall Validation

- Move an agent from pending to active.
- Suspend and resume it.
- Send heartbeat and verify freshness.
- Simulate stale heartbeat and verify orphan detection.

## Dependencies

- Agent registry.
- Auth/RBAC.
- Event pipeline.
- Background worker for orphan detection.

## Definition Of Done

- Agent lifecycle can be operated entirely from API/UI.
- Every lifecycle transition is auditable.
- Stale and ownerless agents are surfaced as operational risks.
