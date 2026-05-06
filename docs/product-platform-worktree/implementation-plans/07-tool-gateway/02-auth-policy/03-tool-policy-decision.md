# Tool Policy Decision

## Feature Scope

Build the deterministic allow or deny decision adapter used by the Tool Gateway. The adapter combines authenticated agent identity, agent lifecycle, tool status, permission binding, required scope, and optional policy hooks into a single decision result.

## Atomic Boundary

This plan is complete when a pure service can decide whether a specific agent may call a specific tool with a specific payload. It can be tested without real upstream APIs by using seeded agents, tools, permissions, and policy fixtures.

## Objectives

- Centralize gateway authorization in one service.
- Return structured decisions with reason codes for audit and UI.
- Fail closed on missing identity, missing tool, disabled tool, missing binding, insufficient scope, or evaluation errors.
- Keep the MVP policy simple while leaving room for richer policy language later.

## Existing Repo Assets To Reuse

- `MCPGateway` decision concepts from `packages/agent-os/src/agent_os/mcp_gateway.py`.
- Policy engine patterns from `packages/agent-mesh/src/agentmesh/governance`.
- Policy evaluation plans from `02-policy-governance`.
- Trust thresholds from `03-trust-mesh` when available.

## Out Of Scope

- Human approval workflow.
- Full policy language authoring.
- MCP protected resource metadata.
- Upstream forwarding.
- UI rendering of decisions.

## Data Model

Tables:

- `tool_policy_decisions`: id, organization_id, environment_id, agent_id, tool_id, permission_id, decision, reason_code, reason_message, matched_policy_id, request_id, correlation_id, payload_summary_json, created_at.

Decision values:

- `allow`
- `deny`

Reason codes:

- `agent_missing`
- `agent_inactive`
- `tool_missing`
- `tool_inactive`
- `permission_missing`
- `scope_insufficient`
- `policy_denied`
- `policy_error`
- `allowed`

## API Surface

Implement internal service methods first:

- `evaluate_tool_call(principal, tool_name, payload, correlation_id) -> ToolPolicyDecision`

Optional debug endpoint for operators:

- `POST /api/v1/tool-policy/evaluate`

The debug endpoint must not execute the tool.

## UI Surface

No primary UI in this plan. Decision records are consumed by the audit and decision-feed plans.

## Implementation Phases

### Phase 1: Decision Model

Steps:

1. Define decision input and output models.
2. Include decision id, allow or deny value, reason code, reason message, matched policy id, and resolved tool id.
3. Add safe payload summarization that avoids storing full sensitive payloads.
4. Add a repository for decision persistence.

Tests:

- Unit test decision model serializes reason codes.
- Unit test payload summary redacts credential-like values.
- Integration test decision record can be persisted and fetched.

### Phase 2: Deterministic Checks

Steps:

1. Reject missing or inactive agent principal.
2. Resolve active tool by name.
3. Reject disabled or retired tool.
4. Resolve active permission binding.
5. Compare requested scope to required scope.

Tests:

- Unit test active agent with active permission is allowed.
- Unit test suspended agent is denied.
- Unit test disabled tool is denied.
- Unit test missing permission is denied.
- Unit test insufficient scope is denied.

### Phase 3: Policy Hook

Steps:

1. Add a simple policy hook interface that receives agent, tool, binding, payload summary, and request context.
2. Support allow and deny results.
3. Fail closed when the policy hook raises an error.
4. Persist matched policy id when available.

Tests:

- Unit test policy allow preserves allow decision.
- Unit test policy deny overrides permission.
- Unit test policy exception returns `policy_error` deny.
- Integration test matched policy id is persisted.

## Independent Verification

- Seed an active agent, active tool, and matching permission.
- Evaluate a call and confirm `allow`.
- Disable the tool and evaluate again to confirm `deny`.
- Remove the permission and confirm `permission_missing`.
- Force the policy hook to raise and confirm `policy_error`.

## Dependencies

- Gateway Token Verification.
- Tool Contract Registry.
- Agent Tool Permission Bindings.
- Policy governance foundations.

## Definition Of Done

- Tool authorization has one deterministic decision service.
- Denied decisions include stable reason codes.
- Decision records are persisted safely.
- Runtime invocation can call the service before forwarding.

