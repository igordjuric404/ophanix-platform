# Gateway Token Verification

## Feature Scope

Authenticate external agent calls to the Tool Gateway. The gateway accepts a bearer token, verifies it against Ophanix-issued agent credentials, resolves the agent identity, and rejects inactive, expired, revoked, or malformed credentials before any policy or upstream logic runs.

## Atomic Boundary

This plan is complete when gateway routes can verify a bearer token and return a request principal. It is independently testable with issued, expired, revoked, and malformed credential fixtures.

## Objectives

- Treat agent identity as a first-class principal.
- Fail closed before tool lookup or forwarding.
- Reuse the credential issuance and rotation feature where possible.
- Produce consistent `401` responses that include request metadata but not token material.

## Existing Repo Assets To Reuse

- Credential concepts from `packages/agent-mesh/src/agentmesh/identity/credentials.py`.
- Product credential metadata plans from `01-agent-registry/01-identity-registration/04-credential-issuance-rotation.md`.
- Product API auth dependencies from `packages/product-platform/src/product_platform/api/auth.py`.
- Request context and error handling from the Product API Shell.

## Out Of Scope

- Creating or rotating credentials.
- Full OAuth 2.1 dynamic client registration.
- Tool permission checks.
- Upstream authentication.

## Data Model

No new primary tables are required if `agent_credentials` exists.

Add indexed read support for:

- credential id.
- token hash.
- agent id.
- status.
- expires at.

Optional table:

- `gateway_token_verification_events`: id, organization_id, environment_id, agent_id, credential_id, result, reason, request_id, created_at.

## API Surface

This plan adds shared gateway authentication dependencies used by:

- `POST /api/v1/tools/{tool_name}/invoke`
- Future direct gateway endpoints under `/api/v1/gateway`

No public credential management endpoints are added here.

## UI Surface

No dedicated UI. Existing agent credential views should show last used time after this dependency verifies a token successfully.

## Implementation Phases

### Phase 1: Token Parser

Steps:

1. Parse `Authorization: Bearer <token>`.
2. Reject missing, non-bearer, empty, or oversized tokens.
3. Hash the presented token before lookup.
4. Avoid logging token values.

Tests:

- Unit test missing header returns `401`.
- Unit test non-bearer header returns `401`.
- Unit test empty token returns `401`.
- Security test token value is not present in logs or error details.

### Phase 2: Credential Verification

Steps:

1. Look up credential metadata by token hash.
2. Verify status is active.
3. Verify expiration is in the future.
4. Resolve the linked agent and lifecycle status.
5. Update credential `last_used_at` on successful verification.

Tests:

- Unit test active credential verifies.
- Unit test expired credential is rejected.
- Unit test revoked credential is rejected.
- Unit test credential for suspended agent is rejected.
- Integration test successful verification updates `last_used_at`.

### Phase 3: Gateway Principal

Steps:

1. Define `GatewayPrincipal` with organization id, environment id, agent id, credential id, scopes, and request id.
2. Attach the principal to gateway request handling.
3. Return consistent `401` errors for authentication failures.
4. Emit audit or verification events without token material.

Tests:

- API test verified request exposes principal to route handler.
- API test failed verification does not execute tool lookup.
- Integration test failed verification creates a safe audit event.

## Independent Verification

- Issue a test credential for an active agent.
- Call a temporary protected test route with the bearer token and confirm `200`.
- Revoke the credential and confirm the same token returns `401`.
- Suspend the agent and confirm even an otherwise valid token returns `401`.

## Dependencies

- Agent registration.
- Credential issuance and rotation.
- Auth, tenancy, and RBAC.
- Event audit pipeline.

## Definition Of Done

- Gateway routes have a reusable token verification dependency.
- Invalid credentials fail closed with `401`.
- Valid credentials resolve an agent principal and update last-used metadata.
- Token material is never persisted or logged in plaintext.

