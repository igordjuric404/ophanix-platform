# Policy Simulator And Evaluation Feed Completion

## Second-Pass Status

Status: `Audit finding revised` and `Confirmed gap`.

## Implementation Status

Status: `Completed` on 2026-05-01.

Completed work:

- Added policy evaluation summary/trend aggregation and `GET /api/v1/policy-evaluations/summary`.
- Added policy evaluation SSE streaming via `GET /api/v1/policy-evaluations/stream`.
- Persisted agent registration simulation decisions into `policy_evaluations`.
- Persisted provider credential and integration health decisions into `policy_evaluations`.
- Added frontend summary/trend rendering and EventSource-based policy feed refresh handling.

Validation:

- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_policy_evaluations*.py' -v`
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_mcp_proxy_traffic_phase*.py' -v`
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_runtime_sessions_and_rings_phase*.py' -v`
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_agent_registration_phase*.py' -v`
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_provider_secrets_health_phase*.py' -v`
- `node --test test/policy-evaluations.test.js`
- `npm run typecheck`
- `npm run lint`
- `npm test`

The broad first-audit gap has been mostly implemented in `2de9148`: the product now has `policy_evaluations` migrations, repository/API support, simulator and live evaluation endpoints, MCP/runtime producer writes, policy frontend simulator/feed UI, and focused backend/frontend tests. The remaining gap is narrower: the original plan also required decision trends, live feed updates, and decisions from agents and framework integrations. Current code covers MCP proxy and runtime producers, but not agent/framework-integration policy decision producers, evaluation feed charts/trends, or live update handling.

## Second-Pass Delta Plan

### Goal

Finish the remaining live-observability parts of `02-policy-governance/01-policy-management/04-policy-simulator-evaluation-feed.md` without reworking the completed simulator/evaluation repository.

### Evidence

- Implemented: `packages/product-platform/src/product_platform/policies/evaluations.py`, `packages/product-platform/src/product_platform/policies/evaluation_repository.py`, migration `0042_policy_evaluations`, `/api/v1/policy-evaluations/*`, and `frontend/src/policies.js`.
- Implemented producer coverage: MCP proxy and runtime decisions are persisted by helpers in `packages/product-platform/src/product_platform/api/app.py`.
- Missing: no policy-evaluation-specific SSE/live feed endpoint or frontend `EventSource` handling; no decision trend/chart aggregation; no producer tests for agent-registration decisions or framework integration/provider-health decisions.

### Implementation Approach

1. Add a lightweight evaluation summary endpoint or extend the list endpoint with grouped counts for decision/action/time buckets.
2. Add a policy-evaluation event stream, or reuse audit SSE with a policy-evaluation filter and frontend subscription that updates the feed without a full page reload.
3. Persist existing agent registration simulation/approval decisions into `policy_evaluations` where a real policy decision occurs.
4. Persist framework integration and provider-health policy decisions where those flows already gate or evaluate behavior.
5. Keep persistence non-blocking for feed writes, but keep policy decision failures fail-closed.

### Likely Files

- `packages/product-platform/src/product_platform/api/app.py`
- `packages/product-platform/src/product_platform/policies/evaluation_repository.py`
- `packages/product-platform/src/product_platform/policies/models.py`
- `packages/product-platform/frontend/src/apiClient.js`
- `packages/product-platform/frontend/src/policies.js`
- `packages/product-platform/frontend/src/app.js`
- `packages/product-platform/tests/test_policy_evaluations_phase*.py`
- `packages/product-platform/frontend/test/policy-evaluations.test.js`

### Test Plan

- Backend test that agent registration policy simulation writes a scoped evaluation row when appropriate.
- Backend test that an integration/provider-health decision writes a scoped evaluation row.
- Backend test for summary/trend aggregation by decision and action.
- Frontend test that decision trend data renders.
- Frontend test that a streamed/new evaluation updates or reloads the feed.
- Re-run focused policy evaluation tests and frontend validation.

### Acceptance Criteria

- Policy evaluation feed includes MCP, runtime, agent, and framework-integration decisions.
- Feed can show trends/counts by decision, action, and time bucket.
- UI receives or refreshes new live evaluations without manual navigation.
- Existing simulator/evaluate/list/detail behavior remains covered and passing.

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
