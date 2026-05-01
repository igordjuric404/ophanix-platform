# Credential Issuance And Rotation

## Feature Scope

Build product workflows for issuing, listing, rotating, revoking, and monitoring agent credentials. This feature persists credential metadata, keeps secrets out of the database, and connects lifecycle, audit, and trust events.

## Existing Repo Assets To Reuse

- `Credential` and `CredentialManager` from `packages/agent-mesh/src/agentmesh/identity/credentials.py`.
- MCP session auth and message signing helpers from `packages/agent-os`.
- Lifecycle rotation state from `LifecycleManager`.

## Out Of Scope

- Human user API keys.
- Enterprise SPIFFE/SVID issuance.
- HSM/KMS integration beyond a provider interface.

## Data Model

Tables:

- `agent_credentials`: id, agent_id, credential_type, token_hash, issuer, status, issued_at, expires_at, revoked_at, last_used_at, metadata_json.
- `credential_scopes`: id, credential_id, scope, resource_type, resource_id.
- `credential_rotations`: id, agent_id, previous_credential_id, new_credential_id, reason, status, requested_by, completed_at.
- `credential_issuers`: id, organization_id, name, issuer_type, config_json, status.

## API Surface

Implement:

- `POST /api/v1/agents/{id}/credentials`
- `GET /api/v1/agents/{id}/credentials`
- `POST /api/v1/credentials/{id}/rotate`
- `POST /api/v1/credentials/{id}/revoke`
- `POST /api/v1/credentials/{id}/verify`
- `GET /api/v1/credentials/expiring`

## UI Surface

Agents -> Credentials:

- Active credentials table.
- Expiry calendar.
- Rotation queue.
- Revocations.
- Scope review.

Agent Detail -> Credentials tab.

## Implementation Phases

### Phase 1: Credential Metadata Store

Steps:

1. Create credential tables.
2. Add credential repository.
3. Store only token hash and metadata.
4. Add list endpoint with agent and status filters.

Tests:

- Integration test credential metadata insert.
- Security test raw token is not persisted.
- API test list filters by status.

### Phase 2: Issuance Adapter

Steps:

1. Wrap existing `CredentialManager` for credential creation.
2. Generate token once and return it only at creation time.
3. Store scopes and expiry.
4. Emit audit event and optional trust event.

Tests:

- Unit test issuance adapter returns credential once.
- API test issue credential with scopes.
- API test invalid scope is rejected.
- Integration test audit event emitted.

### Phase 3: Rotation And Revocation

Steps:

1. Implement rotate endpoint that revokes old credential and issues new one.
2. Implement revoke endpoint with required reason.
3. Record rotation event and lifecycle event.
4. Publish revocation event for gateways/agents to consume.

Tests:

- API test rotate creates new active credential.
- API test old credential becomes revoked.
- API test revoke requires reason.
- Integration test rotation emits audit and lifecycle events.

### Phase 4: Expiry Monitor

Steps:

1. Add background job for expiring credentials.
2. Generate notifications for credentials expiring within threshold.
3. Add optional auto-rotation policy hook.
4. Expose `GET /credentials/expiring`.

Tests:

- Unit test expiry threshold calculation.
- Integration test expiry job marks credential as expiring soon.
- API test expiring endpoint returns correct credentials.

### Phase 5: UI

Steps:

1. Build active credential table.
2. Build rotation queue view.
3. Build revocation confirmation modal.
4. Build scope review panel.
5. Add credential status to agent inventory.

Tests:

- Component test credential table renders status and expiry.
- Component test rotate action calls API.
- Component test revoke modal requires reason.

## Overall Validation

- Issue credential for demo agent.
- Use verify endpoint.
- Rotate credential.
- Confirm old credential is rejected.
- Confirm audit events and UI state update.

## Dependencies

- Agent registry.
- Lifecycle workflows.
- Event pipeline.
- Background worker.
- Secret provider interface for MVP.

## Definition Of Done

- Agent credentials are visible and operable from the product.
- Credential lifecycle is auditable.
- Secret material is not stored in plaintext in product DB.
