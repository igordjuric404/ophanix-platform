# Saga Builder And Monitor

## Feature Scope

Build product support for multi-step governed workflows using sagas: define steps, required capabilities, retry policy, timeout, compensation, execute the saga, and monitor progress.

## Existing Repo Assets To Reuse

- Saga orchestrator from `packages/agent-hypervisor/src/hypervisor/saga`.
- Hypervisor API saga concepts.
- Runtime sessions.

## Out Of Scope

- Full distributed workflow engine.
- Arbitrary user code execution.

## Data Model

Tables:

- `sagas`: id, organization_id, environment_id, name, status, created_by, started_at, finished_at, correlation_id.
- `saga_steps`: id, saga_id, step_order, name, action_name, target_agent_id, required_capability, timeout_seconds, retry_count, compensation_action, status, result_json.
- `saga_events`: id, saga_id, step_id, event_type, message, payload_json, created_at.

## API Surface

Implement:

- `POST /api/v1/runtime/sagas`
- `GET /api/v1/runtime/sagas`
- `GET /api/v1/runtime/sagas/{id}`
- `POST /api/v1/runtime/sagas/{id}/steps`
- `POST /api/v1/runtime/sagas/{id}/execute`
- `POST /api/v1/runtime/sagas/{id}/cancel`

## UI Surface

Runtime -> Sagas:

- Saga list.
- Saga builder.
- Execution monitor.
- Step detail drawer.

## Implementation Phases

### Phase 1: Saga Definition API

Steps:

1. Create saga tables.
2. Add API to create saga and add steps.
3. Validate step order and required capabilities.
4. Add draft status.

Tests:

- API test creates saga.
- API test adds ordered steps.
- API test invalid capability is rejected.

### Phase 2: Demo-Safe Executor

Steps:

1. Implement executor interface with demo-safe actions only.
2. Wire executor to existing saga orchestrator.
3. Record step status and result.
4. Support configured failure fixture for compensation demo.

Tests:

- Unit test successful executor step.
- Unit test failed step triggers compensation.
- Integration test step events are persisted.

### Phase 3: Execution API And Audit

Steps:

1. Add execute endpoint.
2. Create runtime session or link existing session.
3. Emit audit events for saga start, step success/failure, compensation, completion.
4. Update trust/SRE events through event pipeline.

Tests:

- API test executes simple saga.
- Integration test failed step emits compensation event.
- Integration test completed saga has final status.

### Phase 4: UI

Steps:

1. Build saga list.
2. Build saga builder with step form.
3. Build execution timeline.
4. Add retry/cancel controls where supported.

Tests:

- Component test builder adds step.
- Component test execution monitor renders step states.
- Component test failed step shows compensation action.

## Overall Validation

- Build refund saga: lookup order, issue refund, send email.
- Execute success case.
- Execute failure case with compensation.
- Confirm audit, runtime, and observability events.

## Dependencies

- Runtime sessions.
- Agent registry.
- Policy evaluation.
- Event pipeline.
- Background worker if async execution is used.

## Definition Of Done

- Multi-step governed workflows are visible, executable, and auditable.
