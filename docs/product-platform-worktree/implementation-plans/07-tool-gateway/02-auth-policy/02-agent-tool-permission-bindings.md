# Agent Tool Permission Bindings

## Feature Scope

Create explicit bindings between agents and tools. A binding says which active agent may call which active tool, with which scope, in which environment. This plan defines permission state only; it does not make runtime decisions or execute tools.

## Atomic Boundary

This plan is complete when an operator can grant, list, update, and revoke an agent's access to a registered tool. It is independently testable with seeded agents and tools.

## Objectives

- Make tool access visible and reviewable.
- Avoid granting access through implicit naming conventions.
- Support least-privilege scopes per tool.
- Provide clean input for the policy decision adapter.

## Existing Repo Assets To Reuse

- Agent inventory and detail plans from `01-agent-registry`.
- Tool Contract Registry from this feature.
- Product RBAC and audit event patterns.
- Policy binding conventions from `02-policy-governance/01-policy-management/03-policy-bindings-rollout.md`.

## Out Of Scope

- Gateway token verification.
- Dynamic policy language.
- Runtime allow or deny decisions.
- Access review and certification workflows.

## Data Model

Tables:

- `agent_tool_permissions`: id, organization_id, environment_id, agent_id, tool_id, scope, status, granted_by, granted_reason, granted_at, revoked_by, revoked_reason, revoked_at, expires_at.
- `agent_tool_permission_history`: id, permission_id, action, actor_user_id, reason, previous_status, new_status, created_at.

Status values:

- `active`
- `paused`
- `revoked`
- `expired`

## API Surface

Implement:

- `POST /api/v1/agents/{agent_id}/tool-permissions`
- `GET /api/v1/agents/{agent_id}/tool-permissions`
- `GET /api/v1/tools/{tool_id}/agent-permissions`
- `PATCH /api/v1/agent-tool-permissions/{id}`
- `POST /api/v1/agent-tool-permissions/{id}/pause`
- `POST /api/v1/agent-tool-permissions/{id}/revoke`

## UI Surface

Agent Detail -> Tool Permissions:

- Active tool permission table.
- Scope and expiration fields.
- Grant, pause, and revoke actions with reason capture.

Tool Detail -> Allowed Agents:

- List of agents that can call the tool.
- Binding status and expiry.

## Implementation Phases

### Phase 1: Permission Store

Steps:

1. Create permission and permission history tables.
2. Add repository methods for grant, list, pause, revoke, and active lookup.
3. Enforce uniqueness for active agent-tool permission pairs per environment.
4. Reject bindings for retired tools or retired agents.

Tests:

- Integration test grants permission for active agent and active tool.
- Integration test duplicate active grant is rejected.
- Integration test grant to retired tool is rejected.
- Repository test active lookup ignores revoked permissions.

### Phase 2: Permission API

Steps:

1. Add request and response models.
2. Implement grant, list, update, pause, and revoke routes.
3. Require reason fields for pause and revoke.
4. Emit audit events for permission changes.

Tests:

- API test grants permission with scope.
- API test list by agent returns tool metadata.
- API test list by tool returns agent metadata.
- API test revoke requires reason.
- API test writes require the expected operator permission.

### Phase 3: Expiration Handling

Steps:

1. Support optional `expires_at`.
2. Treat expired permissions as inactive in active lookup.
3. Add a lightweight repository method to mark stale permissions expired.
4. Expose expired state in list endpoints.

Tests:

- Unit test expired permission is not active.
- Repository test expiration filter works.
- API test expired permission appears with `expired` status.

## Independent Verification

- Register an active agent and active tool.
- Grant the agent `claims.lookup:read`.
- Confirm the permission appears on both agent and tool detail endpoints.
- Revoke the grant and confirm active lookup returns no binding.

## Dependencies

- Agent registration.
- Tool Contract Registry.
- Auth, tenancy, and RBAC.
- Event audit pipeline.

## Definition Of Done

- Agent-to-tool permissions are explicit and auditable.
- Revoked and expired permissions are not considered active.
- Policy decision code can resolve a binding by agent, tool, scope, and environment.

