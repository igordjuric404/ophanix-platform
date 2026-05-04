# Handshakes And Trust Thresholds

## Feature Scope

Productize trust thresholds and peer handshakes. Users can configure minimum trust for handoff, MCP tool use, privileged runtime action, marketplace install, and protocol bridge use. The platform records handshake attempts and failure reasons.

## Existing Repo Assets To Reuse

- Trust handshake from `packages/agent-mesh/src/agentmesh/trust/handshake.py`.
- Trust scores and trust cards from this workstream.
- Policy bindings for action-specific enforcement.

## Out Of Scope

- Mesh topology visualization.
- Protocol bridge runtime implementation.

## Data Model

Tables:

- `trust_thresholds`: id, organization_id, environment_id, threshold_type, target_type, target_id, min_score, required_tier, enabled.
- `handshake_events`: id, source_agent_id, target_agent_id, purpose, required_score, source_score, target_score, result, reason, correlation_id, created_at.

## API Surface

Implement:

- `GET /api/v1/trust/thresholds`
- `POST /api/v1/trust/thresholds`
- `PATCH /api/v1/trust/thresholds/{id}`
- `POST /api/v1/trust/handshakes/simulate`
- `POST /api/v1/trust/handshakes/record`
- `GET /api/v1/trust/handshakes`

## UI Surface

Trust -> Thresholds.

Trust -> Handshakes.

Mesh -> Handshakes.

## Implementation Phases

### Phase 1: Threshold Configuration

Steps:

1. Create threshold table.
2. Seed defaults for handoff, MCP use, privileged runtime action, marketplace install.
3. Add CRUD API.
4. Validate score range 0 to 1000.

Tests:

- API test creates threshold.
- API test invalid score is rejected.
- Integration test default thresholds are seeded.

### Phase 2: Threshold Resolver

Steps:

1. Implement resolver for threshold type and target.
2. Support most-specific target first, then environment default.
3. Return required score and tier.
4. Fail closed when required threshold cannot be resolved for protected action.

Tests:

- Unit test tool-specific threshold overrides default.
- Unit test disabled threshold is ignored.
- Unit test missing protected threshold fails closed.

### Phase 3: Handshake Recording

Steps:

1. Add simulate endpoint for UI/testing.
2. Add record endpoint for mesh/framework adapters.
3. Use trust scores and threshold resolver to determine result.
4. Store failure reason: low trust, missing capability, revoked card, missing identity, expired credential.

Tests:

- API test successful simulated handshake.
- API test low trust fails with reason.
- API test revoked trust card fails when card requirement enabled.
- Integration test handshake writes audit event.

### Phase 4: UI

Steps:

1. Build threshold table and editor.
2. Build handshake log with source/target filters.
3. Add handshake detail drawer.
4. Add simulate form.

Tests:

- Component test threshold form validates score.
- Component test handshake table renders failure reason.
- Component test simulate form shows result.

## Overall Validation

- Configure handoff threshold 700.
- Attempt handoff from high-trust agent and low-trust agent.
- Confirm allowed and denied handshakes appear with reasons.

## Dependencies

- Trust score pipeline.
- Trust card management.
- Agent inventory.
- Event pipeline.

## Definition Of Done

- Trust thresholds are configurable and handshake outcomes are visible and explainable.
