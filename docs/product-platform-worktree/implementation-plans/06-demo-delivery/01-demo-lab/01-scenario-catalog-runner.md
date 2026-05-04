# Scenario Catalog And Runner

## Feature Scope

Build the Demo Lab scenario catalog and runner. A user can select a governed scenario, verify prerequisites, start the scenario, watch each step execute, and see live evidence links to dashboard pages.

## Existing Repo Assets To Reuse

- End-to-end scenario from `docs/product-platform-plan/05-end-to-end-demo-scenario.md`.
- Existing examples for OpenAI Agents, CrewAI, smolagents, LangChain, Agent OS, AgentMesh, MCP, SRE, and hypervisor.
- Demo data concepts should be replaced by live scenario state.

## Out Of Scope

- Resetting the environment. Covered separately.
- Production deployment.

## Data Model

Tables:

- `demo_scenarios`: id, name, slug, description, value_proof, status, required_services_json, created_at.
- `demo_steps`: id, scenario_id, step_order, title, expected_result, action_type, action_config_json.
- `demo_runs`: id, scenario_id, status, started_by, started_at, finished_at, summary_json.
- `demo_step_runs`: id, demo_run_id, demo_step_id, status, result_json, started_at, finished_at.

## API Surface

Implement:

- `GET /api/v1/demo/scenarios`
- `GET /api/v1/demo/scenarios/{id}`
- `POST /api/v1/demo/scenarios/{id}/runs`
- `GET /api/v1/demo/runs/{id}`
- `POST /api/v1/demo/runs/{id}/continue`
- `POST /api/v1/demo/runs/{id}/cancel`

## UI Surface

Demo Lab -> Scenario Catalog.

Demo Lab -> Scenario Runner.

Demo Lab -> Live Evidence.

## Implementation Phases

### Phase 1: Scenario Definitions

Steps:

1. Add scenario and step tables.
2. Seed customer-support refund scenario.
3. Define each step with expected proof links: Agents, Policies, MCP, Mesh, Trust, Runtime, Discovery, Compliance, Observability.
4. Add API to list scenarios.

Tests:

- Integration test scenario seed is idempotent.
- API test scenario detail returns ordered steps.
- Unit test required services list is parseable.

### Phase 2: Runner Engine

Steps:

1. Add background job or synchronous runner for demo steps.
2. Implement step action types: register agents, import policies, register MCP server, run agent prompt, request approval, rotate credential, run discovery, run saga, generate report.
3. Store step status and result.
4. Emit audit events for run start, step completion, and run completion.

Tests:

- Unit test step executor dispatches by action type.
- Integration test run creates step runs.
- Integration test failed step marks run failed.
- Integration test run emits audit events.

### Phase 3: Live Evidence Links

Steps:

1. Capture created resource IDs and correlation IDs in step result.
2. Generate links to relevant dashboard pages.
3. Show expected versus actual result for each step.
4. Add proof checklist.

Tests:

- Unit test evidence link builder creates policy feed link.
- Unit test correlation id is stored in step result.
- Component test proof checklist marks completed steps.

### Phase 4: UI

Steps:

1. Build scenario catalog.
2. Build scenario detail with prerequisites and step list.
3. Build run page with live timeline.
4. Add start, continue, cancel controls.

Tests:

- Component test catalog renders scenario.
- Component test run timeline updates step status.
- Component test cancel button calls API.

## Overall Validation

- Start customer-support refund scenario.
- Watch allowed action, approval, denial, trust update, credential rotation, discovery, saga, and report steps.
- Confirm every step links to real product state.

## Dependencies

- Most product vertical slices.
- Background worker.
- Event pipeline.
- Provider secrets and MCP server.

## Definition Of Done

- Demo Lab can run a real scenario and prove platform value without random dashboard data.
