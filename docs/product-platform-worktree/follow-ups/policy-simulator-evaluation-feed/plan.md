# Policy Simulator And Evaluation Feed Completion

## Feature Scope

Complete the missing policy evaluation product surface from `02-policy-governance/01-policy-management/04-policy-simulator-evaluation-feed.md`. Users should be able to simulate policy decisions before deployment and inspect live policy decisions from agents, MCP proxy calls, runtime controls, and integrations.

## Existing Repo Assets To Reuse

- `product_platform.policies` library, versioning, linting, and bindings.
- Existing audit event pipeline and policy decision audit event shape.
- Existing MCP proxy and runtime decision events as live evaluation producers.
- Frontend policy workspace patterns in `frontend/src/policies.js`.

## Out Of Scope

- Rewriting the policy library, editor, or binding rollout features.
- Building a full OPA/Cedar service deployment.
- Compliance control mapping and report generation.

## Data Model

Add or complete:

- `policy_evaluations`: id, organization_id, environment_id, policy_id, policy_version_id, binding_id, agent_id, action, resource_type, resource_id, context_json, decision, matched_rule, reason, latency_ms, mode, correlation_id, created_at.

Use existing audit/event tables for decision audit visibility.

## API Surface

Implement:

- `POST /api/v1/policy-evaluations/simulate`
- `POST /api/v1/policy-evaluations/evaluate`
- `GET /api/v1/policy-evaluations`
- `GET /api/v1/policy-evaluations/{id}`

The evaluate endpoint should fail closed, persist live decisions, and emit audit events. Simulator decisions may be persisted with `mode = "simulate"` and should be clearly marked.

## UI Surface

Policies -> Simulator:

- Agent/action/resource form.
- Policy version or active binding selector.
- Context JSON editor with validation.
- Decision result panel showing decision, matched rule, reason, latency, and audit preview.

Policies -> Evaluation Feed:

- Filterable decision table.
- Decision detail drawer.
- Filters for decision, mode, agent, action, policy, and correlation id.

## Implementation Phases

### Phase 1: Evaluation Adapter

Steps:

1. Implement an adapter that resolves active policy versions through existing binding rules.
2. Convert product evaluation context into local evaluator input.
3. Return decision, matched rule, reason, latency, and fail-closed errors.
4. Add backend selection hooks without requiring external services.

Tests:

- Unit test allow decision with a sample policy.
- Unit test deny decision with a sample policy.
- Unit test evaluation failure fails closed.
- Unit test latency is captured.

### Phase 2: Persistence And API

Steps:

1. Add `policy_evaluations` migration and repository.
2. Implement simulate/evaluate/list/detail endpoints.
3. Persist simulator and live evaluations with mode and correlation id.
4. Emit audit events for live evaluations.

Tests:

- Integration test simulation is persisted.
- Integration test live evaluation emits audit event.
- API test filters by decision, mode, and agent.
- API test tenant/environment scoping prevents cross-environment reads.

### Phase 3: Product Producers

Steps:

1. Wire MCP proxy policy decisions into the evaluation feed.
2. Wire runtime and agent-related decision points where a policy decision is already made.
3. Preserve existing audit behavior while adding evaluation rows.
4. Keep producer failures non-blocking only for feed persistence; actual policy decision failures still fail closed.

Tests:

- Integration test MCP policy decision appears in evaluation feed.
- Integration test runtime decision appears in evaluation feed.
- Regression test existing MCP/runtime audit events still emit.

### Phase 4: UI

Steps:

1. Add simulator controls and result rendering to the policy route.
2. Add evaluation feed table and filters.
3. Add decision detail drawer using shared drawer patterns.
4. Wire API client methods and app state loading.

Tests:

- Component test invalid JSON blocks simulator submission.
- Component test deny result renders matched rule and reason.
- Component test feed filters call the expected API query.
- Frontend validation passes with the policy tests included.

## Overall Validation

- Simulate allow, deny, and fail-closed cases.
- Trigger a live MCP or runtime decision.
- Confirm the decision appears in the evaluation feed and audit events.
- Run focused backend policy evaluation tests, relevant MCP/runtime regressions, and frontend policy validation.

## Dependencies

- Policy library and bindings.
- Event/audit pipeline.
- MCP proxy and runtime control events.

## Definition Of Done

- Policy behavior is testable before deployment and observable during live product operation.
- Evaluation rows are scoped, auditable, filterable, and covered by meaningful backend and frontend tests.
