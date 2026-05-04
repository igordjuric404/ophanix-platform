# Execution Log: Workflow Runner And Artifact Store

## Phase Overview

| Phase | Goal | Status | Biggest checklist items |
| --- | --- | --- | --- |
| Phase 1: Safe Runner Interface | Add allowlisted runner registry, safe command execution, timeouts, and log capture. | Done | Registry; adapters; allowlist; timeout tests. |
| Phase 2: Run State, Logs, Worker, And Audit | Persist workflow runs/logs and emit run lifecycle audit events. | Done | Migrations/repository; worker execution; cancel; audit tests. |
| Phase 3: Artifact Storage And Links | Add artifact provider, metadata, upload/download APIs, and target links. | Done | Storage interface; checksum; path safety; link validation. |
| Phase 4: Attestations | Add artifact attestations with signer, statement validation, and audit events. | Done | Attestation API; audit emission; authorization tests. |
| Phase 5: UI | Replace workflow placeholders with catalog, run forms, logs, artifacts, and attestations. | Done | Frontend client/routes; generated forms; component tests; validation. |

## Current Phase Detailed Checklist: Phase 1

- [x] Review previous execution logs before starting this follow-up.
- [x] Re-read `follow-ups/workflow-runner-and-artifacts/plan.md`.
- [x] Inspect workflow catalog/repository, worker runtime, deployment artifact helper, and existing tests.
- [x] Break Phase 1 into small testable implementation chunks before editing.
- [x] Run focused tests after each chunk and update this log with exact outcomes.

## Activity Log

- 2026-05-01: Created initial log from the follow-up plan. Work has not started.
- 2026-05-01: Reviewed the completed policy and compliance execution logs, re-read the workflow runner/artifact plan, and inspected workflow catalog/repository, worker runtime/store/API tests, deployment `LocalArtifactStore`, and current `/api/v1/workflows`/jobs behavior. Confirmed there is no workflow-specific safe runner, run/log persistence, artifact API, or workflow UI yet. Phase 1 moved to In Progress.
- 2026-05-01: Added `product_platform.workflows.runner` with an allowlisted registry, in-process adapters, shell command registration, timeout handling, cwd containment, and line-by-line logs. Added `tests/test_workflow_runner_phase1.py`. First focused run failed because the policy lint fixture was invalid; replaced it with the repo's valid policy shape. Re-ran `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_workflow_runner_phase1.py' -v`; 5 tests passed in 0.067s. Ran `PYTHONPATH=src python3 -m unittest discover -s tests -p '*workflow*phase1.py' -v`; 8 tests passed in 0.561s. Phase 1 is Done.

## Current Phase Detailed Checklist: Phase 2

- [x] Re-read this execution log and implementation plan before Phase 2.
- [x] Inspect existing foundation `workflow_runs` table and generic job run APIs.
- [x] Add workflow run/log migration that preserves existing foundation rows.
- [x] Extend workflow models and repository for create/list/get/cancel/log storage.
- [x] Execute workflow runs through the safe runner with synchronous fallback for tests.
- [x] Emit workflow run audit events for queued/started/completed/failed/canceled lifecycle.
- [x] Add workflow run API endpoints and cancellation behavior.
- [x] Add backend tests for ordered logs, failed exit codes/summaries, audit events, and cancel rejection of completed runs.
- [x] Run focused Phase 2 workflow tests and document outcomes.

- 2026-05-01: Re-read the workflow log and plan before Phase 2, then inspected the existing foundation `workflow_runs` table, generic `background_jobs`/`job_runs`, and `/api/v1/jobs` behavior. Phase 2 moved to In Progress.
- 2026-05-01: Added `0047_workflow_runs_logs` migration to add plan-aligned columns to existing `workflow_runs` and create ordered `workflow_logs`. Extended workflow models/repository with run creation, start/complete/cancel, log replacement, list/get, and response serialization. Ran `python3 -m py_compile packages/product-platform/src/product_platform/workflows/models.py packages/product-platform/src/product_platform/workflows/repository.py packages/product-platform/src/product_platform/workflows/runner.py`; command exited 0.
- 2026-05-01: Added workflow run API endpoints for create, list, get, and cancel. Run creation validates inputs, executes through the safe runner when `run_immediately` is true, stores logs/summary/exit code, and emits queued/running/terminal audit events; cancel emits a canceled audit event. Ran `python3 -m py_compile packages/product-platform/src/product_platform/api/app.py packages/product-platform/src/product_platform/workflows/models.py packages/product-platform/src/product_platform/workflows/repository.py packages/product-platform/src/product_platform/workflows/runner.py`; command exited 0.
- 2026-05-01: Added `tests/test_workflow_runner_phase2.py` for successful policy lint runs with ordered logs/audit events, failed lint runs with non-zero exit code/summary, canceling queued runs, rejecting cancel on completed runs, and required input validation. First run had one assertion using the old `detail` error shape; updated it to this app's `ApiError.message`. Re-ran `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_workflow_runner_phase2.py' -v`; 4 tests passed in 0.665s. Ran `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_workflow_runner_phase*.py' -v`; 9 tests passed in 0.751s. Phase 2 is Done.

## Current Phase Detailed Checklist: Phase 3

- [x] Re-read this execution log and implementation plan before Phase 3.
- [x] Add artifact metadata/link migration and API models.
- [x] Define artifact storage provider interface and local filesystem provider with path safety.
- [x] Implement artifact repository upload/list/detail/download/link behavior with deterministic checksums.
- [x] Add artifact upload/list/detail/download/link APIs.
- [x] Add backend tests for checksum determinism, storage/download, path traversal rejection, and link target validation.
- [x] Run focused Phase 3 artifact tests and document outcomes.

- 2026-05-01: Re-read the workflow log and plan before Phase 3. Phase 3 moved to In Progress.
- 2026-05-01: Added `0048_artifacts` migration, artifact API models, local filesystem artifact provider with key/path safety, deterministic SHA-256 checksum helper, and `ArtifactRepository` for upload/list/detail/download/link behavior with target validation for workflow runs, plugin assessments, audit exports, compliance reports, and evidence items. An initial compile/read command was run from the parent directory and failed with missing relative paths; re-ran from `ophanix-platform`. `python3 -m py_compile packages/product-platform/src/product_platform/artifacts/models.py packages/product-platform/src/product_platform/artifacts/storage.py packages/product-platform/src/product_platform/artifacts/repository.py packages/product-platform/src/product_platform/api/settings.py` exited 0.
- 2026-05-01: Wired artifact endpoints in `api/app.py`: upload, list, detail, download, and link creation. Endpoints use the selected organization/environment context, `JOB_RUN` authorization, local artifact storage from `Settings.artifact_storage_path`, and translate artifact validation/not-found/storage errors to API errors. Ran `python3 -m py_compile packages/product-platform/src/product_platform/api/app.py packages/product-platform/src/product_platform/artifacts/models.py packages/product-platform/src/product_platform/artifacts/storage.py packages/product-platform/src/product_platform/artifacts/repository.py`; command exited 0.
- 2026-05-01: Added `tests/test_workflow_runner_phase3.py` covering deterministic checksum calculation, API upload/list/download, local file persistence, artifact-to-workflow-run links, storage/API path traversal rejection, invalid link target types, and missing target validation. Ran `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_workflow_runner_phase3.py' -v`; 4 tests passed in 0.687s.
- 2026-05-01: Ran `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_workflow_runner_phase*.py' -v`; all 13 Phase 1-3 workflow runner tests passed in 1.505s. Phase 3 is Done.

## Current Phase Detailed Checklist: Phase 4

- [x] Re-read this execution log and implementation plan before Phase 4.
- [x] Add artifact attestation migration and API models.
- [x] Extend artifact repository for attestation create/list behavior with required statement and optional signature reference.
- [x] Add `POST /api/v1/artifacts/{artifact_id}/attest` API with authorization and audit event emission.
- [x] Include attestation history in artifact detail/download responses.
- [x] Add backend tests for required statements, unauthorized users, successful attestation persistence, and audit events.
- [x] Run focused Phase 4 attestation tests and the full workflow follow-up suite; document outcomes.

- 2026-05-01: Re-read the updated workflow execution log and follow-up plan before Phase 4. Inspected the compliance report attestation model/repository/API pattern and decided to require `AUDIT_WRITE` for artifact attestations while keeping artifact upload/list/download under `JOB_RUN`.
- 2026-05-01: Added `0049_artifact_attestations` migration, artifact attestation request/response models, repository create/list behavior, and attestation history on `ArtifactResponse`. Ran `python3 -m py_compile packages/product-platform/src/product_platform/artifacts/models.py packages/product-platform/src/product_platform/artifacts/repository.py`; command exited 0.
- 2026-05-01: Added `POST /api/v1/artifacts/{artifact_id}/attest` with `AUDIT_WRITE` authorization, artifact lookup, persisted signer statement/signature reference, and `artifact.attested` audit event emission. Because `ArtifactResponse` now includes repository-loaded attestations, detail and download responses expose attestation history. Ran `python3 -m py_compile packages/product-platform/src/product_platform/api/app.py packages/product-platform/src/product_platform/artifacts/models.py packages/product-platform/src/product_platform/artifacts/repository.py`; command exited 0.
- 2026-05-01: Added `tests/test_workflow_runner_phase4.py` for required attestation statement validation, operator-without-`AUDIT_WRITE` rejection, successful attestation persistence, detail/download attestation history, and `artifact.attested` audit event payloads. First run failed because the test expected an email-derived user id; dev login uses UUID5 ids. Updated the test to read the admin user id from the login response. Re-ran `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_workflow_runner_phase4.py' -v`; 3 tests passed in 0.529s.
- 2026-05-01: Ran `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_workflow_runner_phase*.py' -v`; all 16 Phase 1-4 workflow runner tests passed in 2.133s. Phase 4 is Done.

## Current Phase Detailed Checklist: Phase 5

- [x] Re-read this execution log and implementation plan before Phase 5.
- [x] Inspect existing frontend route/navigation/API client/test patterns for workflows.
- [x] Add workflow and artifact API client methods.
- [x] Replace workflow placeholder route with catalog, run form, run list/detail logs, artifact list/detail/download, and attestation controls.
- [x] Generate/validate run forms from workflow input schemas.
- [x] Add frontend tests for catalog rendering, run form validation, run logs, artifact detail/download, and attestation required statement behavior.
- [x] Run focused workflow frontend tests plus frontend typecheck/lint; document outcomes.

- 2026-05-01: Re-read the workflow log and follow-up plan before Phase 5. Inspected `render.js`, `app.js`, `apiClient.js`, `compliance.js`, `compliance.test.js`, navigation permissions, and frontend scripts. Confirmed `/workflows` still renders the generic placeholder and there are no workflow/artifact client methods yet.
- 2026-05-01: Added workflow and artifact API client methods for listing workflows/runs/artifacts, creating/canceling runs, fetching/downloading artifacts, linking artifacts, and attesting artifacts. Ran `node --check src/apiClient.js`; command exited 0.
- 2026-05-01: Added `src/workflows.js` with catalog/run/artifact renderers, schema-derived run inputs, workflow run payload validation, artifact upload base64 encoding, and attestation payload validation. Wired `/workflows` in `render.js`, added workflow state loading/refresh and click/submit handlers in `app.js`, and added small workflow CSS rules. Ran `node --check src/workflows.js && node --check src/render.js && node --check src/app.js`; command exited 0.
- 2026-05-01: Added `test/workflows.test.js` and included workflow files in frontend typecheck/lint coverage. Tests cover the workflows route replacing the placeholder, catalog/run form rendering, run logs, artifact detail/download/attestation history, required workflow input validation, artifact upload/attestation payload validation, and API client endpoint paths. First run failed because empty optional workflow inputs did not fall back to schema defaults; updated `workflowRunPayloadFromValues` to apply defaults for blank optional values. Re-ran `node --test test/workflows.test.js`; 7 tests passed.
- 2026-05-01: Ran `npm run typecheck`; command exited 0. Ran `npm run lint`; command exited 0 with `frontend lint ok: 15 routes`. Re-ran backend regression `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_workflow_runner_phase*.py' -v`; all 16 workflow runner tests passed in 2.074s. Phase 5 is Done and the workflow runner/artifact follow-up is complete.
