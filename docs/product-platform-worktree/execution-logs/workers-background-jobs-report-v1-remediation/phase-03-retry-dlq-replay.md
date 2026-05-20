# Execution Log: Phase 3 - Retry DLQ Replay

## 1. Phase Overview

| Phase | Goal | Status | Related Findings | Key Checklist Items |
|---|---|---|---|---|
| Phase 1: Production Worker Consumer | Ship the real persistent worker consumer through CLI and demo/deployment paths. | Done | F-WRK-001 | Inspect CLI/compose; wire persistent worker loop; register handlers; add readiness/smoke tests; update report/logs. |
| Phase 2: Queue Routing Leases Heartbeats | Add production-safe queue routing, priority, leases, stale recovery, worker identity, and heartbeats. | Done | F-WRK-004 | Extend job model/store; add migration; implement claim ordering/recovery; add race/lease tests. |
| Phase 3: Retry DLQ Replay | Operationalize retries, backoff, terminal dead-letter visibility, and manual replay/cancel. | Done | F-WRK-002 | Define retry policy; add DLQ state; add replay API/store methods; add retry/DLQ tests. |
| Phase 4: Job Idempotency Dedupe | Add generic idempotency keys and duplicate-safe enqueue semantics. | Done | F-WRK-003 | Add idempotency fields/constraints; return existing duplicate jobs; update scheduler/API/docs/tests. |

## 2. Current Phase Checklist

- [x] Re-read Phase 2 completion notes before starting.
- [x] Verify F-WRK-002 against store retry helpers, workflow worker failure paths, and API routes.
- [x] Add terminal dead-letter status or equivalent queryable DLQ state.
- [x] Add retry backoff and next scheduled retry behavior.
- [x] Ensure persistent worker requeues transient failures until max attempts.
- [x] Ensure exhausted jobs retain failure reason, logs, and retry metadata.
- [x] Add manual replay API/store path for failed/dead-lettered jobs.
- [x] Add operator cancel/replay authorization tests where API changes apply.
- [x] Add `test_job_retries_then_enters_dlq`.
- [x] Add manual replay regression test.
- [x] Run focused worker/API tests.
- [x] Update selected audit report remediation status for F-WRK-002.
- [x] Update execution index.

## 3. Implementation Notes

- Files created:
  - `packages/product-platform/src/product_platform/db/migrations/0093_background_job_retry_dlq.up.sql`
  - `packages/product-platform/src/product_platform/db/migrations/0093_background_job_retry_dlq.down.sql`
  - `packages/product-platform/tests/test_workers_background_jobs_phase3.py`
- Files modified:
  - `packages/product-platform/src/product_platform/db/migrations/0001_base_schema.up.sql`
  - `packages/product-platform/src/product_platform/worker/store.py`
  - `packages/product-platform/src/product_platform/worker/api_models.py`
  - `packages/product-platform/src/product_platform/worker/persistent.py`
  - `packages/product-platform/src/product_platform/workflows/repository.py`
  - `packages/product-platform/src/product_platform/workflows/worker.py`
  - `packages/product-platform/src/product_platform/api/app.py`
  - `packages/product-platform/tests/test_db_phase1.py`
  - `docs/audits/features/workers-background-jobs/report-v1`
  - `docs/product-platform-worktree/execution-logs/workers-background-jobs-report-v1-remediation/00-execution-index.md`
- Added job retry metadata: `retry_backoff_seconds`, `next_retry_at`, `dead_lettered_at`, and `dead_letter_reason`.
- Added `JobStatus.DEAD_LETTERED`, automatic retry/dead-letter handling via `record_failed_attempt`, and manual replay via `replay`.
- Persistent workers now call the retry-aware failure path.
- Workflow workers now schedule retries for failed workflow runs and reset failed workflow runs back to queued while retries remain.
- Workflow-created jobs now default to three attempts instead of one.
- Job list API supports status filtering, and failed/dead-lettered jobs can be replayed or canceled through server-side authorized endpoints.

## 4. Commands Run

| Command | Exit Code | Result | Relevant Output Summary |
|---|---:|---|---|
| Startup worker store/workflow worker/test inspection commands listed in `00-execution-index.md` | 0 | Passed | Confirmed `requeue_for_retry` exists, but workflow jobs can be one-shot and exhausted jobs do not have a first-class DLQ/replay path. |
| `python3 -m py_compile src/product_platform/worker/store.py src/product_platform/worker/api_models.py src/product_platform/worker/persistent.py src/product_platform/workflows/repository.py src/product_platform/workflows/worker.py src/product_platform/api/app.py tests/test_workers_background_jobs_phase3.py tests/test_db_phase1.py` | 0 | Passed | Phase 3 source and tests compiled. |
| `PYTHONPATH=src:tests python3 -m unittest test_workers_background_jobs_phase3 test_workers_background_jobs_phase2 test_workers_background_jobs_phase1 test_worker_phase2 test_worker_phase4 -v` | 0 | Passed | Focused worker/API regression suite passed 26 tests. |
| `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_db_phase1.py' -v` | 0 | Passed | Database migration suite passed 5 tests in 88.070s. |
| `python3 -m ruff check src/product_platform/worker/store.py src/product_platform/worker/api_models.py src/product_platform/worker/persistent.py src/product_platform/workflows/repository.py src/product_platform/workflows/worker.py src/product_platform/api/app.py tests/test_workers_background_jobs_phase3.py tests/test_db_phase1.py` | 0 | Passed | Ruff reported all checks passed. |

## 5. Observed Output

- `JobStatus` currently has queued/running/succeeded/failed/canceled.
- `requeue_for_retry` can requeue failed jobs when attempts are below max attempts.
- Prior runtime reliability logs document terminal failed jobs as the current DLQ-equivalent, which this phase should improve for the selected report.
- New focused tests prove persistent worker retry scheduling, scheduled retry claim blocking, terminal dead-lettering, workflow retry requeue, queryable DLQ listing, operator replay, viewer replay denial, and canceling failed jobs.
- Migration tests prove retry/DLQ columns apply and roll back.

## 6. Issues Encountered and Fixes

None.

## 7. Deviations From Plan

None.

## 8. Remaining Work for Next Phase

Phase 4 will add generic idempotency and duplicate-safe enqueue semantics.

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
