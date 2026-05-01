# Policy Bindings And Rollout

## Feature Scope

Bind policies to product resources: agents, agent groups, MCP servers, MCP tools, runtime actions, environments, framework connectors, and discovery states. Support enforce, shadow, disabled, staged rollout percentage, and exceptions.

## Existing Repo Assets To Reuse

- Existing policy evaluator can evaluate the selected active policy version.
- Shared policy scope concepts from `shared.py`.
- Example policies from Agent OS and AgentMesh.

## Out Of Scope

- Policy body editing.
- Policy simulation details beyond binding selection.

## Data Model

Tables:

- `policy_bindings`: id, organization_id, environment_id, policy_id, policy_version_id, target_type, target_id, mode, rollout_percentage, priority, status, created_by, created_at.
- `policy_exceptions`: id, binding_id, target_type, target_id, reason, expires_at, created_by, approved_by, created_at.
- `policy_rollout_events`: id, binding_id, previous_percentage, next_percentage, actor_id, reason, created_at.

Modes:

- enforce.
- shadow.
- audit-only.
- disabled.

## API Surface

Implement:

- `POST /api/v1/policy-bindings`
- `GET /api/v1/policy-bindings`
- `PATCH /api/v1/policy-bindings/{id}`
- `DELETE /api/v1/policy-bindings/{id}`
- `POST /api/v1/policy-bindings/{id}/promote`
- `POST /api/v1/policy-bindings/{id}/exceptions`
- `GET /api/v1/policy-exceptions`

## UI Surface

Policies -> Bindings:

- Binding matrix.
- Create binding wizard.
- Rollout controls.
- Exceptions table.

## Implementation Phases

### Phase 1: Binding Data Model And API

Steps:

1. Create binding and exception tables.
2. Validate target type and target id.
3. Ensure binding target belongs to current organization/environment.
4. Emit audit event on create/update/delete.

Tests:

- API test create agent binding.
- API test invalid target is rejected.
- API test binding cannot target another organization.
- Integration test audit event emitted.

### Phase 2: Binding Resolution Service

Steps:

1. Implement resolver that returns applicable bindings for an evaluation context.
2. Apply status, mode, target match, priority, and rollout percentage.
3. Exclude expired exceptions.
4. Return deterministic ordering.

Tests:

- Unit test agent-specific binding wins over environment binding when priority is higher.
- Unit test disabled binding is ignored.
- Unit test rollout percentage is deterministic by correlation id or agent id.
- Unit test active exception excludes binding.

### Phase 3: Rollout And Exceptions

Steps:

1. Add promote endpoint to change mode or rollout percentage.
2. Require reason for promotions and exceptions.
3. Add exception expiration.
4. Emit rollout and audit events.

Tests:

- API test promote shadow to enforce.
- API test exception requires expiration or explicit no-expiry permission.
- Integration test expired exception no longer applies.

### Phase 4: Bindings UI

Steps:

1. Build binding matrix table.
2. Build create binding wizard.
3. Add mode and rollout controls.
4. Add exception creation modal.

Tests:

- Component test binding table renders target labels.
- Component test create wizard validates target selection.
- Component test promote requires reason.

## Overall Validation

- Bind policy to demo MCP tool in shadow mode.
- Run evaluation and verify shadow result.
- Promote to enforce and verify denial/enforcement.
- Create temporary exception and verify behavior changes.

## Dependencies

- Policy library.
- Agent inventory.
- MCP server/tool registry.
- Runtime action registry when available.
- Event pipeline.

## Definition Of Done

- Policies can be attached to real product resources with controlled rollout and auditable exceptions.
