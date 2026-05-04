# Execution Log: 06 Demo Delivery / Demo Environment Reset

Source plan: `docs/product-platform-worktree/06-demo-delivery/01-demo-lab/02-demo-environment-reset.md`

## Phase Overview

### Phase 1: Reset Scope Definition
- Goal: Define reset/preserve boundaries, add demo markers, and document deletion order.
- Status: Done
- Biggest checklist items:
  - [x] Define demo-cleared tables.
  - [x] Define preserved admin/system/provider configuration.
  - [x] Add queryable demo markers where safe.
  - [x] Document reset order.

### Phase 2: Reset Job
- Goal: Run an idempotent reset that clears demo-created state, reloads seeds, and emits audit.
- Status: Done
- Biggest checklist items:
  - [x] Add reset job/runtime behavior.
  - [x] Delete or archive demo records in dependency order.
  - [x] Reload scenario, policies, fixtures, and optional MCP/sample agents.
  - [x] Emit high-level reset audit event.

### Phase 3: Baseline Status
- Goal: Report healthy/degraded baseline prerequisites and reuse checks in the UI.
- Status: Done
- Biggest checklist items:
  - [x] Add baseline status endpoint.
  - [x] Check seed policy pack, scenario, MCP server, sample agents, and provider credentials.
  - [x] Return missing/degraded items.
  - [x] Add API/UI coverage for degraded checks.

### Phase 4: UI
- Goal: Build reset page with typed confirmation, progress, summary, and links back to the scenario catalog.
- Status: Done
- Biggest checklist items:
  - [x] Render reset scope summary.
  - [x] Require typed confirmation.
  - [x] Render progress/result summary.
  - [x] Link back to scenario catalog.

## Detailed Checklist: Phase 1 Reset Scope Definition

- [x] Re-read scenario runner logs before starting reset work.
- [x] Review scenario-created tables/resources from Phase 1-4 of scenario runner.
- [x] Define `demo_reset_runs` schema and demo markers needed for scenario-owned records.
- [x] Implement reset scope helper listing cleared and preserved tables.
- [x] Add tests for cleared table inclusion, preserved table exclusion, and demo marker queryability.
- [x] Update this execution log with implementation details and command outcomes.

## Detailed Checklist: Phase 2 Reset Job

- [x] Re-read completed reset Phase 1 log and completed scenario-runner log.
- [x] Inspect existing audit/API/background-worker conventions.
- [x] Add reset request/run response models.
- [x] Implement reset run persistence helpers for create, complete/fail, list, and get.
- [x] Implement reset execution that deletes `demo_step_runs`, `demo_runs`, and demo-lab audit events in dependency order.
- [x] Reseed demo data after clearing, including scenario and policy placeholders.
- [x] Emit a high-level `demo.reset.completed` audit event.
- [x] Add `POST /api/v1/demo/reset`, `GET /api/v1/demo/reset-runs`, and `GET /api/v1/demo/reset-runs/{id}`.
- [x] Add integration test reset clears demo audit events and preserves admin user.
- [x] Add integration test reset reloads seed scenario.
- [x] Add integration test reset is idempotent.
- [x] Run focused Phase 2 backend tests.
- [x] Inspect outputs and fix failures until green.
- [x] Update this execution log with files changed, commands run, observed output, issues, deviations, and next-phase notes.

## Detailed Checklist: Phase 3 Baseline Status

- [x] Re-read completed reset Phase 1/2 logs and the reset implementation plan.
- [x] Inspect existing agent, MCP server, and provider credential schemas/helpers.
- [x] Add baseline response models for overall status and individual prerequisite checks.
- [x] Add deterministic baseline fixture seeding for optional sample agents and MCP server.
- [x] Implement reusable baseline checker for policy placeholders, scenario/steps, MCP server, sample agents, and provider credentials.
- [x] Add `GET /api/v1/demo/baseline-status`.
- [x] Ensure reset leaves baseline status healthy when required fixtures are present.
- [x] Return degraded status with missing item details when the MCP server fixture is absent.
- [x] Add API test baseline healthy after reset.
- [x] Add API test missing MCP server returns degraded.
- [x] Run focused Phase 3 backend tests.
- [x] Inspect outputs and fix failures until green.
- [x] Update this execution log with files changed, commands run, observed output, issues, deviations, and next-phase notes.

## Detailed Checklist: Phase 4 UI

- [x] Re-read completed reset Phase 1-3 logs and the reset implementation plan.
- [x] Add reset scope and preserved-record summary renderer.
- [x] Add reset confirmation form requiring typed `RESET`.
- [x] Add reset result/progress summary from reset-run history.
- [x] Add link back to the scenario catalog after reset.
- [x] Load reset-run history into Demo Lab state.
- [x] Wire reset form submit to `resetDemoEnvironment()` and refresh Demo Lab.
- [x] Add component test reset requires typed confirmation.
- [x] Add component test reset progress renders.
- [x] Add component test result summary shows cleared and seeded counts.
- [x] Run focused Phase 4 frontend tests/typecheck.
- [x] Inspect outputs and fix failures until green.
- [x] Run final Demo Environment Reset backend/frontend validation.
- [x] Update this execution log with files changed, commands run, observed output, issues, deviations, and next-feature notes.

## Progress Notes

- 2026-05-01: Initial execution log created from implementation plan. Work is blocked until Scenario Catalog And Runner is complete.
- 2026-05-01: Started Phase 1 after Scenario Catalog And Runner completed. Scenario-generated reset scope is `demo_runs`, `demo_step_runs`, and `audit_events` where `source_component = 'demo-lab'`; preserved scope includes users, organizations, environments, system settings, and connector/provider credentials.
- 2026-05-01: Added migration `0041_demo_reset_runs` for reset execution history. Verified `test_db_phase1.py` passes with 3 tests, including apply/rollback through `0041`.
- 2026-05-01: Added `product_platform.demo.reset` with `demo_reset_scope()` and `query_demo_markers()`. Added `test_demo_environment_reset_phase1.py`; verified 3 tests pass for clear order, preserved-table exclusion, and real scenario marker counts.
- 2026-05-01: Started Phase 2. Existing job APIs execute immediate work synchronously when requested, matching the scenario runner approach; audit event hashes must be removed before clearing demo-lab audit events because SQLite foreign keys are enabled.
- 2026-05-01: Added reset request/status/response models, `DemoResetRepository`, `DemoEnvironmentResetService`, reset run serialization, reset audit event creation, and audit hash-chain rebuild after demo-lab audit deletion. Added `test_demo_environment_reset_phase2.py`.
- 2026-05-01: First Phase 2 test run failed because reset returned `failed`; reset summary showed `no such column: environment_id`. Root cause was counting preserved `provider_credentials` by environment, but that table is organization-scoped. Patched the count to use `organization_id` only.
- 2026-05-01: Reran `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_demo_environment_reset_phase2.py' -v`; passed 3 tests covering audit/run clearing, admin preservation, seed reload, audit event emission, hash verification, and idempotency.
- 2026-05-01: Added reset API endpoints in `api/app.py`: `POST /api/v1/demo/reset`, `GET /api/v1/demo/reset-runs`, and `GET /api/v1/demo/reset-runs/{reset_id}`. The reset endpoint requires typed confirmation `RESET` and `JOB_CANCEL`.
- 2026-05-01: Extended `test_demo_environment_reset_phase2.py` with API coverage. `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_demo_environment_reset_phase2.py' -v` passed 5 tests.
- 2026-05-01: Added baseline status models, `demo/baseline.py`, deterministic sample agent/MCP fixture seeding, and `GET /api/v1/demo/baseline-status`. Provider credential is optional and reports `warning` when absent without degrading the overall baseline.
- 2026-05-01: Added `test_demo_environment_reset_phase3.py`. `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_demo_environment_reset_phase3.py' -v` passed 2 tests for healthy-after-reset and degraded missing MCP server.
- 2026-05-01: Added Demo Lab prerequisites rendering, baseline API client methods, and Demo Lab baseline loading. `node --test test/demo.test.js` passed 8 tests; `npm run typecheck` passed.
- 2026-05-01: Focused DB phase 4 regression check initially failed because `reset_demo_data()` did not clear newly seeded agent/MCP rows or pre-existing workflow definitions before deleting the environment/organization. Updated deletion order; rerun `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_db_phase4.py' -v` passed 3 tests.
- 2026-05-01: Added Demo Lab reset panel with reset scope summary, typed `RESET` confirmation form, latest reset progress/result summary, and Scenario Catalog link. Loaded reset-run history in Demo Lab state and wired form submission to `resetDemoEnvironment()`.
- 2026-05-01: Extended frontend Demo Lab tests for reset confirmation, progress rendering, result cleared/seeded counts, catalog link, and reset API client path. `node --test test/demo.test.js` passed 12 tests; `npm run typecheck` passed.
- 2026-05-01: Final Demo Environment Reset validation passed:
  - `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_db_phase1.py' -v` -> passed, 3 tests.
  - `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_db_phase4.py' -v` -> passed, 3 tests.
  - `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_demo_scenario_catalog_phase1.py' -v` -> passed, 5 tests.
  - `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_demo_scenario_runner_phase2.py' -v` -> passed, 7 tests.
  - `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_demo_live_evidence_phase3.py' -v` -> passed, 3 tests.
  - `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_demo_environment_reset_phase1.py' -v` -> passed, 3 tests.
  - `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_demo_environment_reset_phase2.py' -v` -> passed, 5 tests.
  - `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_demo_environment_reset_phase3.py' -v` -> passed, 2 tests.
  - `node --test test/demo.test.js` -> passed, 12 tests.
  - `npm run typecheck` -> passed.
  - `npm run lint` -> passed.

## Phase 4 Completion Notes

- Implemented reset panel, scope summary, typed confirmation payload parsing, progress/result summary, and Scenario Catalog link in `packages/product-platform/frontend/src/demo.js`.
- Loaded reset-run history and wired reset submit handling in `packages/product-platform/frontend/src/app.js`.
- Added reset/baseline API client methods in `packages/product-platform/frontend/src/apiClient.js`.
- Extended frontend tests in `packages/product-platform/frontend/test/demo.test.js`.
- No additional deviations from the plan.

## Feature Completion Notes

- Demo Environment Reset is complete across all four phases.
- Implemented backend reset scope, reset history schema, reset job/service/API, baseline status API, deterministic baseline fixtures, and Demo Lab reset UI.
- Persistent execution logs for this feature are complete. Next feature folder should start by reading this log and the next implementation plan file.

## Phase 3 Completion Notes

- Implemented baseline models in `packages/product-platform/src/product_platform/demo/models.py`.
- Implemented baseline checks in `packages/product-platform/src/product_platform/demo/baseline.py`.
- Seeded stable demo sample agents and MCP server in `packages/product-platform/src/product_platform/db/seed.py`.
- Added the baseline status API in `packages/product-platform/src/product_platform/api/app.py`.
- Added backend coverage in `packages/product-platform/tests/test_demo_environment_reset_phase3.py`.
- Added frontend prerequisites rendering and API client loading in `packages/product-platform/frontend/src/demo.js`, `frontend/src/apiClient.js`, `frontend/src/app.js`, and `frontend/test/demo.test.js`.
- Commands run:
  - `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_demo_environment_reset_phase3.py' -v` -> passed, 2 tests.
  - `node --test test/demo.test.js` -> passed, 8 tests.
  - `npm run typecheck` -> passed.
  - `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_db_phase4.py' -v` -> initially failed, then passed after legacy reset cleanup fix.
- No plan deviation. Phase 4 should build the reset page controls and result summary on the existing Demo Lab route.

## Phase 2 Completion Notes

- Implemented reset models in `packages/product-platform/src/product_platform/demo/models.py`.
- Implemented reset repository/service, ordered deletion, reseeding, reset audit events, and audit hash-chain rebuild in `packages/product-platform/src/product_platform/demo/reset.py`.
- Implemented authenticated reset APIs in `packages/product-platform/src/product_platform/api/app.py`.
- Added Phase 2 tests in `packages/product-platform/tests/test_demo_environment_reset_phase2.py`.
- Commands run:
  - `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_demo_environment_reset_phase2.py' -v` -> initially failed, then passed after provider credential scope fix.
  - `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_db_phase1.py' -v` -> passed, 3 tests.
  - `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_demo_environment_reset_phase1.py' -v` -> passed, 3 tests.
  - `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_demo_environment_reset_phase2.py' -v` -> passed, 5 tests.
- Conservative deviation: reset execution is synchronous in-process, matching the existing scenario runner and immediate job API style. The reset history table records job-like execution state for UI polling/history.
- Phase 3 should add reusable baseline prerequisite checks and expose `GET /api/v1/demo/baseline-status`.

## Phase 1 Completion Notes

- Implemented reset history schema in `packages/product-platform/src/product_platform/db/migrations/0041_demo_reset_runs.up.sql` and rollback in `0041_demo_reset_runs.down.sql`.
- Implemented reset boundary helpers in `packages/product-platform/src/product_platform/demo/reset.py`.
- Updated migration coverage in `packages/product-platform/tests/test_db_phase1.py`.
- Added Phase 1 reset tests in `packages/product-platform/tests/test_demo_environment_reset_phase1.py`.
- Commands run:
  - `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_db_phase1.py' -v` -> passed, 3 tests.
  - `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_demo_environment_reset_phase1.py' -v` -> passed, 3 tests.
- No deviations from the implementation plan. Phase 2 should build the executable reset job on this scope.
