# Policy Simulator And Evaluation Feed

## Feature Scope

Build the real policy evaluation surface: a simulator for test inputs and a live evaluation feed for decisions made by agents, MCP proxy, runtime controls, and framework integrations.

## Existing Repo Assets To Reuse

- `PolicyEvaluator` from `packages/agent-os/src/agent_os/policies/evaluator.py`.
- OPA and Cedar backends from Agent OS.
- Existing policy decision/audit fields.

## Out Of Scope

- Policy authoring.
- Policy binding creation.
- MCP proxy execution.

## Data Model

Tables:

- `policy_evaluations`: id, organization_id, environment_id, policy_id, policy_version_id, binding_id, agent_id, action, resource_type, resource_id, context_json, decision, matched_rule, reason, latency_ms, mode, correlation_id, created_at.

## API Surface

Implement:

- `POST /api/v1/policy-evaluations/simulate`
- `POST /api/v1/policy-evaluations/evaluate`
- `GET /api/v1/policy-evaluations`
- `GET /api/v1/policy-evaluations/{id}`

## UI Surface

Policies -> Simulator:

- Input form.
- Context JSON editor.
- Decision output.

Policies -> Evaluation Feed:

- Decision table.
- Decision trends.
- Filters.
- Detail drawer.

## Implementation Phases

### Phase 1: Evaluation Adapter

Steps:

1. Implement adapter that loads active policy version body into existing evaluator.
2. Convert product evaluation context into evaluator input.
3. Capture decision, matched rule, reason, and latency.
4. Support local evaluator first; add backend selection hook for OPA/Cedar.

Tests:

- Unit test allow decision with sample policy.
- Unit test deny decision with sample policy.
- Unit test evaluation failure fails closed.
- Unit test latency is captured.

### Phase 2: Persisted Evaluations

Steps:

1. Create evaluation table.
2. Persist simulator and live evaluations with mode flag.
3. Emit audit event for live evaluations and optionally simulator evaluations.
4. Include correlation id.

Tests:

- Integration test evaluation is persisted.
- Integration test live evaluation emits audit event.
- API test filters by decision and agent.

### Phase 3: Simulator UI

Steps:

1. Build form for agent, action, resource, policy version, and context JSON.
2. Validate JSON before submission.
3. Render decision, matched rule, reason, latency, audit preview.
4. Allow saving scenario as reusable test case later.

Tests:

- Component test invalid JSON blocks submit.
- Component test deny result renders matched rule.
- Component test agent selector filters by environment.

### Phase 4: Evaluation Feed UI

Steps:

1. Build evaluation table with filters.
2. Add charts for decisions by time and by action.
3. Use shared detail drawer for evaluation detail.
4. Add live update stream for new evaluations.

Tests:

- Component test feed renders rows.
- Component test decision filter calls API.
- Integration UI test receives live update when event stream emits evaluation.

## Overall Validation

- Simulate allow, deny, and escalate cases.
- Trigger a live agent/MCP evaluation.
- Confirm decision appears in feed and audit explorer.
- Confirm trust pipeline can consume evaluation events later.

## Dependencies

- Policy library.
- Policy bindings.
- Event pipeline.
- Shared drawers.

## Definition Of Done

- Policy behavior is testable before deployment and observable during real operation.
