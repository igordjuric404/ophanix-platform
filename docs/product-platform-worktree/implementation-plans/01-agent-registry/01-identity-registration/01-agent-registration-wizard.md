# Agent Registration Wizard

## Feature Scope

Build the product workflow for registering a governed agent from the UI. The wizard creates product registry records, calls existing AgentMesh identity primitives, assigns owner/sponsor, requests capabilities, binds initial policies, issues an initial credential, and emits audit events.

## Existing Repo Assets To Reuse

- `AgentIdentity` from `packages/agent-mesh/src/agentmesh/identity/agent_id.py`.
- `AgentRegistry` from `packages/agent-mesh/src/agentmesh/services/registry/agent_registry.py`.
- `LifecycleManager` from `packages/agent-mesh/src/agentmesh/lifecycle/manager.py`.
- Existing examples under `packages/agent-mesh/examples`.

## Out Of Scope

- Credential rotation after registration. Covered by credential lifecycle plan.
- Discovery-based registration. Covered by discovery reconciliation.

## Data Model

Tables:

- `agents`: id, organization_id, environment_id, name, description, framework, runtime_type, endpoint_url, owner_user_id, sponsor_user_id, status, created_at.
- `agent_identities`: id, agent_id, did, public_key_fingerprint, key_type, identity_status, created_at.
- `agent_capabilities`: id, agent_id, capability_name, resource_type, status, requested_by, approved_by, created_at.
- `agent_protocols`: id, agent_id, protocol, endpoint, status.

## API Surface

Implement:

- `POST /api/v1/agents/registration-drafts`
- `PATCH /api/v1/agents/registration-drafts/{id}`
- `POST /api/v1/agents/registration-drafts/{id}/simulate`
- `POST /api/v1/agents/registration-drafts/{id}/submit`
- `POST /api/v1/agents/{id}/approve`
- `POST /api/v1/agents/{id}/activate`

## UI Surface

Agents -> Register Agent wizard:

1. Agent details.
2. Runtime and framework.
3. Identity.
4. Capabilities.
5. Policies.
6. Bootstrap.

## Implementation Phases

### Phase 1: Draft Registration API

Steps:

1. Add registration draft storage or use `agents` with draft status.
2. Validate required fields: name, owner, sponsor, framework, runtime.
3. Enforce uniqueness of agent name per organization/environment.
4. Emit audit event when draft is created.

Tests:

- API test creates draft.
- API test duplicate name is rejected.
- API test Viewer cannot create draft.
- Integration test audit event is emitted.

### Phase 2: Identity Creation

Steps:

1. Add adapter that calls `AgentIdentity.create`.
2. Store DID and public key fingerprint in `agent_identities`.
3. Keep private key material out of product DB.
4. Return bootstrap material once if generated locally.

Tests:

- Unit test adapter creates valid identity object.
- API test identity is persisted with agent.
- Security test response does not include private key after initial bootstrap step.

### Phase 3: Capability And Policy Selection

Steps:

1. Add capability request form and API validation.
2. Store requested capabilities as pending.
3. Allow selecting policy packs or policy bindings by environment.
4. Add simulation endpoint that checks first action against selected policies.

Tests:

- API test stores requested capability.
- API test invalid capability name is rejected.
- Integration test policy simulation returns decision before submission.

### Phase 4: Submit, Approve, Activate

Steps:

1. Move draft to pending approval.
2. Allow approver with correct role to approve capabilities.
3. Call lifecycle adapter to activate.
4. Issue initial credential through credential feature when available; until then create pending credential task.

Tests:

- API test submit changes status to pending approval.
- API test unauthorized user cannot approve.
- API test approved agent can be activated.
- Integration test activation emits lifecycle audit event.

## Overall Validation

- Register a demo agent end to end from the UI.
- Verify DID exists.
- Verify capabilities are stored.
- Verify bootstrap output can be used by sample agent.
- Verify audit trail contains draft, submit, approve, and activate events.

## Dependencies

- Product API shell.
- Auth/RBAC.
- Database schema.
- Event pipeline.
- Policy binding API for full policy selection.
- Credential issuance for complete activation.

## Definition Of Done

- A user can register a real agent without editing repo files.
- The registered agent has identity, owner, sponsor, capabilities, and lifecycle state.
- Registration is fully auditable.
