# Sandbox Profiles And Kill Switch

## Feature Scope

Create UI and APIs for sandbox profiles and emergency kill-switch controls. Users can configure sandbox restrictions for demo/runtime actions and terminate agents, sessions, tools, plugins, or MCP servers with auditable reasons.

## Existing Repo Assets To Reuse

- Execution sandbox from `packages/agent-os/src/agent_os/sandbox.py`.
- Sandbox provider abstraction from `packages/agent-os/src/agent_os/sandbox_provider.py`.
- Hypervisor kill switch from `packages/agent-hypervisor/src/hypervisor/security/kill_switch.py`.

## Out Of Scope

- Claiming subprocess sandbox is production isolation.
- Implementing Firecracker/gVisor/Kubernetes isolation in this feature.

## Data Model

Tables:

- `sandbox_profiles`: id, organization_id, environment_id, name, provider_type, allowed_imports_json, blocked_imports_json, allowed_paths_json, network_policy_json, resource_limits_json, status.
- `sandbox_decisions`: id, profile_id, agent_id, action_name, decision, reason, created_at.
- `kill_switch_events`: id, organization_id, environment_id, target_type, target_id, scope, reason, actor_id, status, created_at.

## API Surface

Implement:

- `POST /api/v1/runtime/sandbox-profiles`
- `GET /api/v1/runtime/sandbox-profiles`
- `PATCH /api/v1/runtime/sandbox-profiles/{id}`
- `POST /api/v1/runtime/sandbox-profiles/{id}/test`
- `POST /api/v1/runtime/kill-switch`
- `GET /api/v1/runtime/kill-switch/events`

## UI Surface

Runtime -> Sandbox.

Runtime -> Kill Switch.

Agent Detail -> Runtime.

## Implementation Phases

### Phase 1: Sandbox Profile Store

Steps:

1. Create sandbox profile table.
2. Add CRUD API.
3. Validate provider type and restrictions.
4. Add clear warning for subprocess provider limitations.

Tests:

- API test creates sandbox profile.
- API test invalid provider type rejected.
- Component/API test subprocess limitation is visible.

### Phase 2: Sandbox Test Adapter

Steps:

1. Add test endpoint using existing sandbox where safe.
2. Accept sample code/action descriptor.
3. Return allow/deny and reason.
4. Store sandbox decision when tied to real agent/action.

Tests:

- Unit test blocked import is denied.
- API test allowed sample passes.
- API test dangerous sample denied.

### Phase 3: Kill Switch API

Steps:

1. Wrap hypervisor kill switch concepts.
2. Support target types: agent, session, MCP server, tool, plugin.
3. Require reason and typed confirmation.
4. Emit high-severity audit event.

Tests:

- API test kill switch requires reason.
- API test unsupported target rejected.
- Integration test kill event persisted and audited.

### Phase 4: UI

Steps:

1. Build sandbox profile list and editor.
2. Build sandbox test panel.
3. Build kill-switch form with target selector.
4. Add confirmation and post-action event detail.

Tests:

- Component test sandbox editor validates paths/imports.
- Component test kill switch requires typed confirmation.
- Component test kill event appears in history.

## Overall Validation

- Create sandbox profile blocking dangerous import.
- Test action and see denial.
- Trigger kill switch for demo session.
- Confirm audit event and runtime UI update.

## Dependencies

- Runtime sessions.
- Agent registry.
- MCP registry for MCP targets.
- Marketplace registry for plugin targets.
- Event pipeline.

## Definition Of Done

- Runtime containment configuration and emergency stop controls are operable and clearly auditable.
