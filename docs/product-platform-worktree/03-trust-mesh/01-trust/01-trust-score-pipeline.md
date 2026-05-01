# Trust Score Pipeline

## Feature Scope

Create a persistent trust signal and trust score pipeline. It consumes policy, MCP, credential, runtime, discovery, marketplace, and SRE events, converts them into trust deltas, updates score dimensions, and exposes trust history to the dashboard.

## Existing Repo Assets To Reuse

- Reward scoring from `packages/agent-mesh/src/agentmesh/reward/scoring.py`.
- Trust engine from `packages/agent-mesh/src/agentmesh/reward/engine.py`.
- Existing trust dashboard concepts from AgentMesh examples.

## Out Of Scope

- Trust card issuance.
- Agent-to-agent handshakes.
- Custom ML scoring models.

## Data Model

Tables:

- `trust_scores`: id, agent_id, score, tier, dimensions_json, calculated_at.
- `trust_events`: id, agent_id, source_event_id, dimension, delta, reason, score_before, score_after, created_at.
- `trust_rules`: id, organization_id, event_type, dimension, delta, min_delta, max_delta, enabled, config_json.
- `trust_recalculation_runs`: id, organization_id, environment_id, status, started_at, finished_at, summary_json.

## API Surface

Implement:

- `GET /api/v1/trust/scores`
- `GET /api/v1/trust/scores/{agent_id}`
- `GET /api/v1/trust/events`
- `POST /api/v1/trust/recalculate`
- `GET /api/v1/trust/rules`
- `PATCH /api/v1/trust/rules/{id}`

## UI Surface

Trust -> Leaderboard.

Trust -> Score Events.

Agent Detail -> Trust tab.

Overview trust cards.

## Implementation Phases

### Phase 1: Trust Data Model

Steps:

1. Create trust score, event, rule, and recalculation tables.
2. Seed default trust rules for allow, deny, escalation, credential rotation, credential expiry, MCP block, discovery shadow finding, runtime kill switch.
3. Add repository methods.

Tests:

- Integration test seed rules are idempotent.
- Integration test creates trust score.
- Unit test tier calculation maps score to expected tier.

### Phase 2: Event To Trust Signal Mapping

Steps:

1. Subscribe or query audit events by event type.
2. Map each supported event to dimension and delta using trust rules.
3. Ignore events without agent id or disabled rules.
4. Store trust event with source event link.

Tests:

- Unit test policy allow creates positive compliance delta.
- Unit test policy deny creates negative compliance delta.
- Unit test credential rotation creates positive security delta.
- Unit test disabled rule creates no event.

### Phase 3: Score Recalculation

Steps:

1. Implement recalculation job per agent and environment.
2. Apply deltas with bounds from 0 to 1000.
3. Update dimensions and overall score.
4. Emit trust score changed event.

Tests:

- Unit test score cannot exceed 1000.
- Unit test score cannot go below 0.
- Integration test recalculation updates score and creates trust event.
- Integration test trust changed event is written to audit.

### Phase 4: Trust UI

Steps:

1. Build Leaderboard table.
2. Build trust score trend chart.
3. Build Score Events table with filters.
4. Add Agent Detail trust tab with explainable deltas.

Tests:

- Component test leaderboard renders score and tier.
- Component test score events filter by dimension.
- Component test agent trust tab renders trend.

## Overall Validation

- Run demo allowed and denied actions.
- Recalculate trust.
- Confirm score changed and event links to original audit event.
- Confirm UI explains why score changed.

## Dependencies

- Event pipeline.
- Agent inventory.
- Background worker.

## Definition Of Done

- Trust scores are derived from real governance events and are explainable in the UI.
