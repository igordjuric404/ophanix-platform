# CLI Workflow Runner Execution Log

Source plan: `docs/product-platform-worktree/05-ecosystem-operations/04-workflows/01-cli-workflow-runner.md`

## Phase Overview

| Phase | Goal | Status | Biggest Checklist Items |
| --- | --- | --- | --- |
| Phase 1: Workflow Catalog | Seed and expose registered workflow definitions. | Done | Definition seed; input schemas; list API; schema validation. |
| Phase 2: Safe Runner Interface | Execute only registered workflows with safe execution constraints. | In Progress | Runner interface; command allowlist; stdout/stderr capture; timeout/workdir controls. |
| Phase 3: Run State And Logs | Persist workflow runs, logs, summaries, and audit events. | Not Started | Run/log tables; background worker; statuses/exit codes; audit events. |
| Phase 4: UI | Expose workflow catalog, run form, logs, and cancel action. | Not Started | Catalog; schema form; run detail/logs; cancel action. |

## Detailed Checklist

### Phase 1: Workflow Catalog

- [x] Re-read this execution log and the source plan before coding.
- [x] Add `workflow_definitions` database table.
- [x] Seed governance verify, integrity, policy lint, security scan, SBOM, dependency confusion, and marketplace evaluate definitions.
- [x] Store input schema per workflow.
- [x] Add `GET /api/v1/workflows`.
- [x] Integration test seed is idempotent.
- [x] API test workflow list includes expected definitions.
- [x] Unit test input schema validates required fields.
- [x] Run focused Phase 1 tests until passing.
- [x] Update this log with files changed, commands, observed output, issues, and next action.

### Phase 2: Safe Runner Interface

- [x] Re-read prior notes and the source plan before starting.
- [ ] Implement runner interface that calls Python functions where available before shelling out.
- [ ] Restrict command refs to registered workflows only.
- [ ] Capture stdout/stderr line by line.
- [ ] Set timeout and working directory allowlist.
- [ ] Unit test unknown workflow cannot execute arbitrary command.
- [ ] Integration test no-op registered workflow runs.
- [ ] Unit test timeout marks run failed.
- [ ] Run focused Phase 2 tests until passing.
- [ ] Update this log with files changed, commands, observed output, issues, and next action.

### Phase 3: Run State And Logs

- [ ] Re-read prior notes and the source plan before starting.
- [ ] Add `workflow_runs` and `workflow_logs` database tables.
- [ ] Execute runs through background worker or deterministic local executor.
- [ ] Store status, exit code, and summary.
- [ ] Emit audit event for run start/completion/failure.
- [ ] Add list/get/cancel run APIs.
- [ ] Integration test run logs are stored.
- [ ] Integration test failed workflow stores exit code.
- [ ] Integration test audit events emitted.
- [ ] Run focused Phase 3 tests until passing.
- [ ] Update this log with files changed, commands, observed output, issues, and next action.

### Phase 4: UI

- [ ] Re-read prior notes, source plan, and frontend patterns before starting.
- [ ] Build workflow catalog.
- [ ] Build run form from input schema.
- [ ] Build run detail with logs.
- [ ] Add cancel action.
- [ ] Component test catalog renders workflows.
- [ ] Component test run form validates input.
- [ ] Component test logs stream or refresh.
- [ ] Run focused frontend tests until passing.
- [ ] Run full workflow backend/frontend validation.
- [ ] Update this log with files changed, commands, observed output, issues, and next action.

## Overall Validation Checklist

- [ ] Run policy lint workflow from UI.
- [ ] See logs and result.
- [ ] Confirm run appears in audit events.
- [ ] Use output as evidence in compliance plan later.

## Progress Notes

- 2026-05-01: Created initial execution log from the implementation plan. Next action: start after Provider Secrets And Health Checks is complete.
- 2026-05-01: Started Phase 1 Workflow Catalog. Re-read this execution log, the source plan, existing background job/runtime workflow code, migration conventions, and frontend route permissions. Existing `workflow_runs` from the base schema is a minimal legacy job table, so Phase 1 will add `workflow_definitions` first and Phase 3 will extend run/log persistence without breaking existing job APIs. Next action: add migration `0038_workflow_definitions`, seed definitions, API models/repository, and focused Phase 1 tests.
- 2026-05-01: Added `0038_workflow_definitions` migration, rollback SQL, workflow catalog seed data, `product_platform.workflows` package scaffolding, catalog input schemas, repository/response model helpers, and a `seed_demo_data` hook. Updated `tests/test_db_phase1.py` for the new migration. First rollback run failed because the down migration missed the local convention of deleting its `schema_migrations` row; fixed `0038_workflow_definitions.down.sql`. Command: `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_db_phase1.py' -v`; result after fix: 3 tests passed. Next action: add `GET /api/v1/workflows` and Phase 1 API/schema tests.
- 2026-05-01: Completed Phase 1 Workflow Catalog. Added `GET /api/v1/workflows` to `api/app.py`, workflow response serialization, and `tests/test_cli_workflow_runner_phase1.py` covering idempotent seed, expected catalog definitions, and required-field input schema validation. Commands: `PYTHONPATH=src python3 -m compileall -q src/product_platform/api/app.py src/product_platform/workflows` passed; `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_cli_workflow_runner_phase1.py' -v` passed 3 tests. Next action: start Phase 2 Safe Runner Interface.
- 2026-05-01: Started Phase 2 Safe Runner Interface. Re-read prior notes/source plan and checked Python subprocess timeout/capture behavior in the official documentation. Next action: add registered-command runner with Python handler preference, shell command allowlist, line capture, timeout handling, and focused Phase 2 tests.
