# Chaos And Rollout Operations

## Feature Scope

Expose chaos experiment and rollout controls for governed agents. Users can create safe experiments, run them with blast-radius controls, and manage staged rollouts for agent/model/policy changes.

## Existing Repo Assets To Reuse

- Chaos engine from `packages/agent-sre/src/agent_sre/chaos`.
- Rollout modules from `packages/agent-sre`.
- Agent SRE examples for canary model upgrades and chaos chatbot.

## Out Of Scope

- Arbitrary destructive fault injection.
- Full deployment controller integration.

## Data Model

Tables:

- `chaos_experiments`: id, organization_id, environment_id, name, fault_type, target_type, target_id, blast_radius_json, guardrails_json, status, created_by, created_at.
- `chaos_runs`: id, experiment_id, status, started_at, finished_at, result_json.
- `rollouts`: id, organization_id, environment_id, name, target_type, target_id, strategy, status, current_stage, config_json, created_at.
- `rollout_events`: id, rollout_id, stage, decision, metrics_json, created_at.

## API Surface

Implement:

- `POST /api/v1/observability/chaos/experiments`
- `GET /api/v1/observability/chaos/experiments`
- `POST /api/v1/observability/chaos/experiments/{id}/run`
- `POST /api/v1/observability/chaos/runs/{id}/stop`
- `POST /api/v1/observability/rollouts`
- `GET /api/v1/observability/rollouts`
- `POST /api/v1/observability/rollouts/{id}/advance`
- `POST /api/v1/observability/rollouts/{id}/rollback`

## UI Surface

Observability -> Chaos.

Observability -> Rollouts.

## Implementation Phases

### Phase 1: Chaos Experiment Definitions

Steps:

1. Create experiment tables.
2. Add API to define latency, error, timeout, trust perturbation, and policy-denial experiments.
3. Require guardrails and blast radius.
4. Reject experiments targeting production unless feature flag enables it.

Tests:

- API test creates demo chaos experiment.
- API test missing guardrail rejected.
- API test production target rejected by default.

### Phase 2: Chaos Run Execution

Steps:

1. Add chaos run job.
2. Wrap existing chaos engine where possible.
3. Persist run status and result.
4. Emit audit and incident/SLO events when guardrails trip.

Tests:

- Integration test run starts and completes.
- Unit test guardrail breach stops run.
- Integration test run emits audit event.

### Phase 3: Rollout Definitions

Steps:

1. Add rollout tables.
2. Support canary and percentage rollout strategies.
3. Link rollout gates to SLO, policy deny rate, trust score, and incident status.
4. Store current stage.

Tests:

- API test creates canary rollout.
- Unit test gate evaluation blocks advance when SLO unhealthy.
- Integration test rollout event stored.

### Phase 4: Rollout Actions And UI

Steps:

1. Add advance and rollback endpoints.
2. Build chaos experiment list and run detail.
3. Build rollout list and stage timeline.
4. Add confirmation modals for run/advance/rollback.

Tests:

- API test advance changes stage.
- API test rollback changes status.
- Component test rollout timeline renders stages.
- Component test chaos run confirmation requires blast-radius acknowledgement.

## Overall Validation

- Create safe latency chaos experiment against demo agent.
- Run it and observe SLO impact.
- Create canary rollout and block advance when guardrail fails.

## Dependencies

- SLO/cost/incident dashboard.
- Background worker.
- Event pipeline.

## Definition Of Done

- Chaos and rollout operations are controlled, guarded, observable, and auditable.
