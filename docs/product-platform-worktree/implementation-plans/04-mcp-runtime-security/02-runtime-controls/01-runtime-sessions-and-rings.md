# Runtime Sessions And Rings

## Feature Scope

Productize runtime sessions and ring enforcement. Users can view sessions, inspect actions, see ring decisions, and configure ring thresholds for runtime actions.

## Existing Repo Assets To Reuse

- Hypervisor API models and server concepts from `packages/agent-hypervisor/src/hypervisor/api`.
- Ring classifier/enforcer from `packages/agent-hypervisor/src/hypervisor/rings`.
- Session concepts from hypervisor.

## Out Of Scope

- Ring elevation implementation beyond showing current public-preview denial.
- Saga builder.
- Sandbox profiles and kill switch.

## Data Model

Tables:

- `runtime_sessions`: id, organization_id, environment_id, agent_id, state, ring, sponsor_user_id, started_at, ended_at, metadata_json.
- `runtime_actions`: id, session_id, action_name, resource_type, required_ring, decision, reason, latency_ms, correlation_id, created_at.
- `runtime_ring_decisions`: id, runtime_action_id, agent_trust_score, required_ring, assigned_ring, result, reason, created_at.
- `runtime_ring_rules`: id, organization_id, environment_id, action_pattern, required_ring, min_trust_score, enabled.

## API Surface

Implement:

- `POST /api/v1/runtime/sessions`
- `GET /api/v1/runtime/sessions`
- `GET /api/v1/runtime/sessions/{id}`
- `POST /api/v1/runtime/sessions/{id}/actions`
- `GET /api/v1/runtime/ring-decisions`
- `GET /api/v1/runtime/ring-rules`
- `POST /api/v1/runtime/ring-rules`

## UI Surface

Runtime -> Sessions.

Runtime -> Rings.

Agent Detail -> Runtime tab.

## Implementation Phases

### Phase 1: Session Store

Steps:

1. Create session and action tables.
2. Add API to create and list sessions.
3. Validate agent exists and is active.
4. Emit audit event when session starts and ends.

Tests:

- API test creates session for active agent.
- API test cannot create session for suspended agent.
- Integration test session start emits audit event.

### Phase 2: Ring Decision Adapter

Steps:

1. Wrap existing ring classifier/enforcer.
2. Resolve trust score and action descriptor.
3. Store ring decision and action result.
4. Represent public-preview limitations honestly in reason fields.

Tests:

- Unit test privileged action maps to required ring.
- Unit test low trust fails Ring 1 action.
- Integration test ring decision is persisted.

### Phase 3: Ring Rules

Steps:

1. Add ring rule configuration table and API.
2. Allow action pattern to override default classifier.
3. Validate ring values and trust thresholds.
4. Emit audit event on rule changes.

Tests:

- API test creates ring rule.
- Unit test custom rule overrides default classification.
- API test invalid ring rejected.

### Phase 4: UI

Steps:

1. Build sessions table.
2. Build session detail timeline.
3. Build ring decisions table and charts.
4. Build ring rule editor.

Tests:

- Component test sessions table renders state.
- Component test ring decision shows reason.
- Component test ring rule form validates threshold.

## Overall Validation

- Start demo runtime session.
- Submit safe action and privileged action.
- Confirm ring decisions and audit events.
- Confirm UI explains denied Ring 0/elevation limitations.

## Dependencies

- Agent registry.
- Trust score pipeline.
- Event pipeline.

## Definition Of Done

- Runtime sessions and ring decisions are visible, persistent, and tied to trust and audit evidence.
