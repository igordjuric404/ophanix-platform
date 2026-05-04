# Execution Log: Workflow Runner And Artifact Store

## Phase Overview

| Phase | Goal | Status | Biggest checklist items |
| --- | --- | --- | --- |
| Phase 1: Remaining Gap Verification And Tests | Verify workflow/artifact gaps and add focused failing tests for worker-backed execution, real adapters, and generated artifact integration. | Done | Inspect workflow API/repository/runner/worker/artifact/compliance/audit export paths; add deterministic tests. |
| Phase 2: Worker-Backed Workflow Execution | Execute queued workflow runs through the existing worker runtime, preserving deterministic test execution. | Done | Job registration; queue/start/complete/fail/cancel state; audit events; tests. |
| Phase 3: Real Workflow Adapters | Replace placeholder workflow adapters with meaningful in-process checks or allowlisted repo scripts. | Done | Governance verify, integrity, marketplace evaluate, security scan, SBOM, dependency confusion; adapter tests. |
| Phase 4: Generated Artifact Integration | Store workflow outputs, audit exports, and compliance reports as checksumed artifact rows with links. | Done | Artifact provider integration; links to workflow_run/audit_export/compliance_report; API/download behavior; tests. |
| Phase 5: Frontend And Aggregate Validation | Surface linked generated artifacts and run full validation. | Done | Workflow/compliance UI updates; frontend tests; backend focused and aggregate tests. |

## Current Phase Detailed Checklist: Phase 1

- [x] Read `audit-report-second-pass.md`.
- [x] Read `follow-ups/workflow-runner-and-artifacts/plan.md`.
- [x] Re-read previous follow-up execution log for existing implementation details.
- [x] Inspect workflow API/repository/runner and worker runtime extension points.
- [x] Inspect artifact repository/storage and compliance/audit export artifact URI behavior.
- [x] Add or update backend tests for queued worker-backed workflow execution.
- [x] Add or update backend tests that detect placeholder workflow adapters.
- [x] Add or update backend tests for compliance/audit generated artifact rows and links.
- [x] Add or update frontend tests for linked generated artifacts where needed.
- [x] Run the focused tests and confirm intended failures before implementation.
- [x] Document commands, outputs, and next implementation target.

## Current Phase Detailed Checklist: Phase 2

- [x] Add persistent queued-job lookup support to `JobStateRepository`.
- [x] Add a workflow worker executor that picks queued `workflow.run` jobs and updates workflow/job states.
- [x] Create a `workflow.run` background job when a workflow run is created with `run_immediately: false`.
- [x] Preserve existing immediate-run behavior for deterministic API flows.
- [x] Store a workflow output artifact when worker execution completes.
- [x] Run focused workflow second-pass tests and inspect remaining failures before adapter work.
- [x] Update this log with files changed, commands, outputs, and remaining Phase 3 work.

## Current Phase Detailed Checklist: Phase 3

- [x] Replace `_run_simple_python_check` placeholder adapters with meaningful checks.
- [x] Replace print-only shell adapters for security, SBOM, and dependency confusion with input-sensitive allowlisted adapters.
- [x] Keep command refs stable for existing seeded workflow definitions.
- [x] Run focused workflow second-pass tests and inspect remaining failures before generated artifact work.
- [x] Run existing workflow runner phase tests for adapter regressions.
- [x] Update this log with files changed, commands, outputs, and remaining Phase 4 work.

## Current Phase Detailed Checklist: Phase 4

- [x] Add helper(s) to create artifact rows from generated JSON/Markdown content.
- [x] Create and link `audit.export` artifacts during `/api/v1/audit/export`.
- [x] Create and link `compliance.report` artifacts during compliance report generation.
- [x] Preserve existing audit export and compliance report response contracts.
- [x] Run focused second-pass and compliance regression tests.
- [x] Update this log with files changed, commands, outputs, and remaining Phase 5 work.

## Current Phase Detailed Checklist: Phase 5

- [x] Inspect workflow/compliance frontend artifact rendering coverage.
- [x] Add or adjust frontend tests only if linked generated artifacts are not already visible through existing artifact workspace.
- [x] Run all workflow runner backend tests, compliance backend regressions, and frontend workflow/compliance tests.
- [x] Run aggregate frontend validation and `git diff --check`.
- [x] Update follow-up plan and execution log with completion evidence.
- [x] Mark this follow-up complete and identify the next follow-up folder.

## Activity Log

- 2026-05-01: Created execution log. This follow-up will start only after policy simulator/evaluation feed is fully implemented, tested, and documented.
- 2026-05-01: Started after completing the policy simulator/evaluation feed follow-up. Re-read `docs/product-platform-worktree/follow-up-execution-logs/03-workflow-runner-and-artifacts.md`; the first pass added the safe runner, workflow run/log APIs, artifact storage/link APIs, attestations, and frontend workflow workspace. The second-pass plan remains focused on queued worker-backed execution, replacing placeholder adapters with meaningful checks, and storing generated audit/compliance outputs as artifacts.
- 2026-05-01: Inspected `api/app.py`, `workflows/runner.py`, `workflows/repository.py`, `worker/runtime.py`, `worker/store.py`, `artifacts/*`, and compliance report/audit export paths. Confirmed queued workflow runs currently create only `workflow_runs` rows, not `background_jobs`; non-policy workflow adapters are placeholder checks or print-only shell commands; audit exports and compliance report generation set logical artifact URIs without creating `artifacts` rows.
- 2026-05-01: Added `packages/product-platform/tests/test_workflow_runner_second_pass.py` covering queued worker-backed execution plus workflow output artifact links, non-placeholder adapters for seeded command refs, and generated audit/compliance artifact rows. Ran `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_workflow_runner_second_pass.py' -v`; all 3 tests failed as intended: queued run job lookup returned 404, governance placeholder returned `succeeded`, and audit export artifact list was empty.
- 2026-05-01: Added `JobStateRepository.next_queued_job`, `product_platform.workflows.worker.WorkflowRunWorker`, `WorkflowJobExecution`, and `WORKFLOW_JOB_TYPE`. Queued workflow creation now persists a `workflow.run` background job using the workflow run id as the job id, and the worker updates workflow/job states, emits workflow lifecycle audit events, and stores a linked `workflow.output` artifact on completion. Workflow cancellation now also attempts to cancel the paired background job.
- 2026-05-01: Ran `PYTHONPATH=src python3 -m py_compile src/product_platform/api/app.py src/product_platform/workflows/worker.py src/product_platform/worker/store.py`; command exited 0. Re-ran `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_workflow_runner_second_pass.py' -v`; queued workflow worker/artifact test passed, with remaining failures limited to placeholder adapters and generated audit/compliance artifacts. Phase 2 is complete.
- 2026-05-01: Replaced placeholder seeded workflow adapters in `workflows/runner.py` with deterministic input-sensitive in-process checks for governance verification, integrity checks, marketplace evaluation, security scanning, SBOM generation, and dependency-confusion manifest validation. Command refs remain unchanged.
- 2026-05-01: Ran `PYTHONPATH=src python3 -m py_compile src/product_platform/workflows/runner.py`; command exited 0. Ran `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_workflow_runner_phase*.py' -v`; 16 tests passed in 2.062s. Re-ran `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_workflow_runner_second_pass.py' -v`; worker and adapter tests passed, leaving only generated audit/compliance artifact assertions failing. Phase 3 is complete.
- 2026-05-01: Added `_create_generated_artifact` helper in `api/app.py`. `/api/v1/audit/export` now creates and links an `audit.export` artifact, and compliance report generation now creates and links a `compliance.report` artifact while preserving existing `artifact_uri` response behavior.
- 2026-05-01: Ran `PYTHONPATH=src python3 -m py_compile src/product_platform/api/app.py`; command exited 0. Ran `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_workflow_runner_second_pass.py' -v`; 3 tests passed in 0.528s. Ran `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_compliance_phase1.py' -v`; 2 tests passed in 0.341s. Ran `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_compliance_phase4.py' -v`; 4 tests passed in 0.697s. Phase 4 is complete.
- 2026-05-01: Inspected frontend artifact rendering. Existing workflow artifact workspace lists generated artifacts and their links; added compliance report preview rendering for linked `compliance.report` artifacts and loaded those artifacts in compliance state. Updated `frontend/test/compliance.test.js` coverage.
- 2026-05-01: Ran `node --test test/workflows.test.js test/compliance.test.js`; 16 tests passed in 568.931ms. Ran `npm run typecheck`; command exited 0. Ran `npm run lint`; command exited 0 with `frontend lint ok: 15 routes`. Ran `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_workflow_runner*.py' -v`; 19 tests passed in 2.685s. Ran `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_compliance_phase*.py' -v`; 15 tests passed in 2.784s. Ran `npm test`; 195 frontend tests passed in 532.567ms. Ran `git diff --check`; command exited 0.
- 2026-05-01: Completed the workflow runner and artifact store follow-up. Queued runs are worker-backed via persisted `workflow.run` jobs, seeded adapters are no longer placeholders, workflow/audit/compliance outputs create linked artifact rows, and the relevant frontend/backend tests pass. Next follow-up folder: `demo-cloud-runtime-verification`.
