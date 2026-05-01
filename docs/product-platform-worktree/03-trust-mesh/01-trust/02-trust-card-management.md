# Trust Card Management

## Feature Scope

Issue, verify, list, revoke, and display signed trust cards for registered agents. Trust cards should reflect current identity, capabilities, trust score, issuer, validity window, and revocation status.

## Existing Repo Assets To Reuse

- `TrustedAgentCard` and `CardRegistry` from `packages/agent-mesh/src/agentmesh/trust/cards.py`.
- Agent identity and trust score data from product registry and trust pipeline.

## Out Of Scope

- Cross-organization trust federation.
- External trust providers.

## Data Model

Tables:

- `trust_cards`: id, agent_id, issuer, card_json, signature, status, valid_from, valid_until, issued_at.
- `trust_card_revocations`: id, trust_card_id, reason, revoked_by, revoked_at.

## API Surface

Implement:

- `POST /api/v1/trust/cards`
- `GET /api/v1/trust/cards`
- `GET /api/v1/trust/cards/{id}`
- `POST /api/v1/trust/cards/{id}/verify`
- `POST /api/v1/trust/cards/{id}/revoke`
- `GET /api/v1/agents/{id}/trust-card`

## UI Surface

Trust -> Trust Cards:

- Trust card inventory.
- Card detail.
- Verify action.
- Revoke action.

Agent Detail -> Identity and Trust tabs:

- Current trust card.

## Implementation Phases

### Phase 1: Card Issuance Adapter

Steps:

1. Build adapter around `TrustedAgentCard`.
2. Populate card from product agent, identity, capabilities, and current trust score.
3. Sign card using demo signing key provider.
4. Store card JSON and signature.

Tests:

- Unit test card payload includes DID and capabilities.
- Unit test signature verifies using card registry.
- Integration test issued card is persisted.

### Phase 2: Verification And Revocation

Steps:

1. Add verify endpoint using `CardRegistry`.
2. Add revocation table and endpoint.
3. Ensure revoked card verification reports revoked status.
4. Emit audit event for issuance and revocation.

Tests:

- API test verify valid card.
- API test revoked card reports revoked.
- API test revocation requires reason.
- Integration test audit events emitted.

### Phase 3: Current Card Selection

Steps:

1. Define current card as latest valid non-revoked card for agent.
2. Expire old cards by validity window.
3. Add endpoint for current card.
4. Add warning when no valid card exists.

Tests:

- Unit test latest valid card selected.
- Unit test expired card not selected.
- API test agent without card returns clear empty state.

### Phase 4: UI

Steps:

1. Build trust card inventory table.
2. Build card detail viewer with payload, signature, verification, revocation status.
3. Add issue and revoke actions.
4. Add current card panel to agent detail.

Tests:

- Component test card detail renders DID and score.
- Component test revoked badge appears.
- Component test verify action shows result.

## Overall Validation

- Issue card for demo agent.
- Verify it.
- Revoke it.
- Confirm agent detail warns that current trust card is invalid.

## Dependencies

- Agent registry.
- Trust score pipeline.
- Signing key provider.
- Event pipeline.

## Definition Of Done

- Trust cards are first-class product artifacts with issuance, verification, revocation, and audit history.
