# Execution Log: Phase 2 - Demo-Safe Executor

## 1. Phase Overview

| Phase | Goal | Status | Related Findings | Key Checklist Items |
|---|---|---|---|---|
| Phase 1: Saga Definition API | Persist saga definitions and ordered steps with enough state for durable execution hardening. | Done | F-SAG-001, F-SAG-002, F-SAG-003 | Verify schema, add missing idempotency/manual repair fields, update repository serializers, add data model tests. |
| Phase 2: Demo-Safe Executor | Harden executor into durable checkpointed/idempotent activity execution. | Done | F-SAG-001, F-SAG-002, F-SAG-003, F-SAG-004 | Verify replay, propagate idempotency keys, add activity worker boundary, add retry/compensation tests. |
| Phase 3: Execution API And Audit | Ensure API execution/audit surfaces durable state, worker activity, and repair semantics. | Done | F-SAG-001, F-SAG-003, F-SAG-004 | Expose execution state, audit side-effect boundaries, validate authorization and audit tests. |
| Phase 4: UI | Ensure monitor surfaces step, compensation, retry, and manual repair states introduced by remediation. | Done | F-SAG-003, F-SAG-004 | Validate/adjust UI rendering and tests for new states and worker-backed execution. |

## 2. Current Phase Checklist

- [x] Re-read Phase 1 completion notes before starting.
- [x] Verify F-SAG-001 restart/replay behavior against current executor.
- [x] Verify F-SAG-002 checkpoint creation/restore/corruption behavior against current executor.
- [x] Add or update deterministic idempotency key generation for execute and compensation activities.
- [x] Persist idempotency key and external operation ID on every activity attempt.
- [x] Ensure duplicate retries reuse completed activity results and operation IDs.
- [x] Fail closed or mark manual repair when a non-idempotent retry would duplicate an external side effect.
- [x] Add worker-backed activity runner or adapter for saga step execution.
- [x] Preserve demo action semantics behind the worker-backed activity boundary for deterministic tests.
- [x] Add regression tests for restart recovery, checkpoint replay, idempotency-key reuse, worker execution, retry, and compensation failure.
- [x] Run focused executor tests.
- [x] Update selected audit report remediation status for executor-related findings when validated.
- [x] Update execution index.

## 3. Implementation Notes

- Added `WorkerBackedSagaActionRunner` in `runtime/saga_executor.py`.
- API saga execution now uses persistent `saga.activity` jobs while preserving deterministic demo-safe action contracts as worker handlers.
- `SagaExecutionService` now calls `start_activity_result` inside the hypervisor attempt callback so retries create durable attempt rows with the same idempotency key/external operation ID.
- `complete_activity_result` and `fail_activity_result` now attach worker job IDs and operation IDs to activity results and attempts.
- `saga_actions.py` now exposes typed action definitions with `supports_idempotency`.
- `SagaRepository.add_step` rejects non-idempotent action retries server-side.
- Added selected-report regression tests:
  - `test_saga_execution_survives_process_restart`
  - `test_saga_checkpoint_replay_skips_completed_step`
  - `test_saga_activity_retry_uses_idempotency_key`
  - `test_saga_step_executes_through_worker_activity`
  - `test_non_idempotent_activity_retry_is_rejected`

## 4. Commands Run

| Command | Exit Code | Result | Relevant Output Summary |
|---|---:|---|---|
| `PYTHONPATH=src:tests python3 -m unittest test_runtime_durable_execution_phase1 test_runtime_durable_execution_phase2 test_saga_builder_and_monitor_phase2 test_saga_builder_and_monitor_phase3 -v` | 0 | Passed | Existing durable and saga suites passed 18 tests after worker-backed runner wiring. |
| `python3 -m py_compile src/product_platform/runtime/saga_actions.py src/product_platform/runtime/sagas.py src/product_platform/runtime/saga_executor.py src/product_platform/api/app.py tests/test_saga_builder_and_monitor_phase1.py tests/test_runtime_durable_execution_phase1.py tests/test_runtime_durable_execution_phase2.py tests/test_saga_builder_and_monitor_phase3.py` | 0 | Passed | Touched runtime/API/test files compiled. |
| `PYTHONPATH=src:tests python3 -m unittest test_saga_builder_and_monitor_phase1 test_runtime_durable_execution_phase1 test_runtime_durable_execution_phase2 test_saga_builder_and_monitor_phase2 test_saga_builder_and_monitor_phase3 -v` | 0 | Passed | Focused saga suite passed 26 tests after report-named regression tests and non-idempotent retry rejection. |

## 5. Observed Output

- Existing recovery/checkpoint tests continued to pass after executor retry attempt recording moved inside the hypervisor attempt callback.
- The worker-backed API test confirmed three `saga.activity` jobs and job run records for a three-step saga, with each activity result linked to a worker job ID.
- The idempotency retry regression confirmed failed and succeeded attempts reuse one idempotency key and one external operation ID.
- The non-idempotent retry regression confirmed saga step creation fails closed when an action contract does not support idempotent retries.

## 6. Issues Encountered and Fixes

- First patch attempt for action metadata/test insertion failed because the target test context did not match the current file. Fixed by inspecting `test_saga_builder_and_monitor_phase1.py` and reapplying the patch at the correct insertion point.

## 7. Deviations From Plan

None yet.

## 8. Remaining Work for Next Phase

None. Phase 3 verified API/audit payloads for worker job IDs, idempotency keys, external operation IDs, and durable activity evidence.

## 9. Phase Completion Criteria

A phase is complete only when:

1. All related findings are fixed or explicitly blocked.
2. All acceptance criteria are satisfied.
3. Relevant tests are added or updated.
4. Relevant tests pass.
5. Type checks pass where applicable.
6. Lint passes where applicable.
7. Build passes where applicable.
8. The audit report is updated.
9. The execution log is updated.
10. The execution index is updated.
