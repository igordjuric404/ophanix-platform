# Execution Log: 06 Demo Delivery / Scenario Catalog And Runner

Source plan: `docs/product-platform-worktree/06-demo-delivery/01-demo-lab/01-scenario-catalog-runner.md`

External docs consulted:
- FastAPI Testing docs: https://fastapi.tiangolo.com/tutorial/testing/

## Phase Overview

### Phase 1: Scenario Definitions
- Goal: Persist demo scenario/step definitions, seed the customer-support refund scenario idempotently, and expose scenario list/detail APIs.
- Status: Done
- Biggest checklist items:
  - [x] Add `demo_scenarios` and `demo_steps` tables.
  - [x] Seed the customer-support refund scenario and ordered proof steps.
  - [x] Define expected proof links for Agents, Policies, MCP, Mesh, Trust, Runtime, Discovery, Compliance, and Observability.
  - [x] Add `GET /api/v1/demo/scenarios` and `GET /api/v1/demo/scenarios/{id}`.
  - [x] Add integration/API/unit coverage for idempotent seed, ordered steps, and parseable required services.

### Phase 2: Runner Engine
- Goal: Execute scenario steps, store run state, and audit run/step lifecycle.
- Status: Done
- Biggest checklist items:
  - [x] Add `demo_runs` and `demo_step_runs` persistence behavior.
  - [x] Implement supported action type dispatch.
  - [x] Persist step results and failure state.
  - [x] Emit audit events for start, step completion/failure, and run completion/failure.

### Phase 3: Live Evidence Links
- Goal: Capture resource IDs/correlation IDs and render proof checklist evidence for completed scenario steps.
- Status: Done
- Biggest checklist items:
  - [x] Store created resource and correlation IDs in step results.
  - [x] Generate dashboard evidence links.
  - [x] Return expected versus actual step results.
  - [x] Add proof checklist data and frontend rendering coverage.

### Phase 4: UI
- Goal: Build Demo Lab scenario catalog/detail/run screens with start, continue, and cancel controls.
- Status: Done
- Biggest checklist items:
  - [x] Render scenario catalog.
  - [x] Render scenario detail with prerequisites and steps.
  - [x] Render run timeline.
  - [x] Wire start, continue, and cancel controls to API methods.

## Detailed Checklist: Phase 1 Scenario Definitions

- [x] Review existing migration, seed, API, and frontend state conventions.
- [x] Create migration `0039_demo_scenarios` with `demo_scenarios` and `demo_steps` tables plus rollback.
- [x] Add demo scenario domain models/response helpers.
- [x] Add demo scenario repository with idempotent seed and ordered detail queries.
- [x] Extend `seed_demo_data` to seed customer-support refund scenario.
- [x] Define required service parsing helper and unit coverage.
- [x] Define customer-support refund step list with expected proof links for Agents, Policies, MCP, Mesh, Trust, Runtime, Discovery, Compliance, and Observability.
- [x] Add authenticated scenario list/detail API endpoints.
- [x] Add integration test proving scenario seed is idempotent.
- [x] Add API test proving scenario detail returns ordered steps.
- [x] Run focused backend tests for Phase 1.
- [x] Inspect outputs and fix failures until green.
- [x] Update this execution log with files changed, commands run, observed output, issues, deviations, and next-phase notes.

## Detailed Checklist: Phase 2 Runner Engine

- [x] Re-read Phase 1 execution log and Scenario Catalog And Runner implementation plan.
- [x] Create migration `0040_demo_runs` with `demo_runs` and `demo_step_runs` tables plus rollback.
- [x] Update DB migration tests for migration `0040`.
- [x] Add demo run/step-run API models and response helpers.
- [x] Extend `DemoScenarioRepository` with run creation, run retrieval, step-run listing, status updates, and failure/cancel handling.
- [x] Implement a synchronous `DemoScenarioRunner` that executes one step at a time.
- [x] Implement step action dispatch for `register_agents`, `import_policies`, `register_mcp_server`, `run_agent_prompt`, `request_approval`, `rotate_credential`, `run_discovery`, `run_saga`, and `generate_report`.
- [x] Store each step status and result JSON.
- [x] Mark failed steps and overall run as failed when an action raises/fails.
- [x] Emit audit events for run start, step completion/failure, and run completion/failure/cancel.
- [x] Add API endpoints for start, get run, continue, and cancel.
- [x] Add unit test proving step executor dispatches by action type.
- [x] Add integration test proving a run creates step runs.
- [x] Add integration test proving a failed step marks run failed.
- [x] Add integration/API test proving run emits audit events.
- [x] Run focused backend tests for Phase 2.
- [x] Inspect outputs and fix failures until green.
- [x] Update this execution log with files changed, commands run, observed output, issues, deviations, and next-phase notes.

## Detailed Checklist: Phase 3 Live Evidence Links

- [x] Re-read completed Phase 1/2 execution log and Scenario Catalog And Runner Phase 3 plan.
- [x] Add evidence-link and proof-checklist response models.
- [x] Add backend evidence link builder that maps step proof areas and resource IDs to dashboard routes.
- [x] Add policy evidence/feed route generation with correlation ID query parameter.
- [x] Enrich step-run responses with `actual_result`, evidence links, and proof checklist items.
- [x] Confirm correlation IDs are persisted in step result JSON.
- [x] Add unit test for evidence link builder policy feed link.
- [x] Add unit/integration test for correlation ID stored in step result.
- [x] Add frontend Demo Lab proof checklist renderer.
- [x] Add component test proving completed steps are marked completed.
- [x] Run focused backend and frontend tests for Phase 3.
- [x] Inspect outputs and fix failures until green.
- [x] Update this execution log with files changed, commands run, observed output, issues, deviations, and next-phase notes.

## Detailed Checklist: Phase 4 UI

- [x] Re-read completed Phase 1-3 execution log and Scenario Catalog And Runner Phase 4 plan.
- [x] Add demo API client methods for list/detail/start/get/continue/cancel.
- [x] Expand frontend Demo Lab renderer with scenario catalog.
- [x] Build scenario detail with prerequisites, value proof, and ordered step list.
- [x] Build run timeline with live step status, expected/actual result, and proof checklist.
- [x] Add start, continue, and cancel controls with stable data attributes.
- [x] Wire `/demo-lab` into `renderShell`.
- [x] Add Demo Lab state loading and refresh helpers in `app.js`.
- [x] Add route navigation/bootstrap loading for `/demo-lab`.
- [x] Add click handlers for start, continue, cancel, and scenario selection.
- [x] Add component test catalog renders scenario.
- [x] Add component test run timeline updates step status.
- [x] Add component/API-client test cancel button/API method path.
- [x] Run focused frontend tests/typecheck for Phase 4.
- [x] Inspect outputs and fix failures until green.
- [x] Update this execution log with files changed, commands run, observed output, issues, deviations, and next-phase notes.

## Progress Notes

- 2026-05-01: Created initial execution log and set Phase 1 to In Progress after reading the implementation plan and existing product-platform conventions.
- 2026-05-01: Added `0039_demo_scenarios` migration with tenant/environment-scoped `demo_scenarios`, ordered `demo_steps`, proof-link JSON, indexes, and rollback. Updated `tests/test_db_phase1.py` to expect migration `0039`, assert demo tables exist, and verify rollback removes demo tables before `0038`.
- 2026-05-01: Commands run:
  - `python -m pytest tests/test_db_phase1.py` failed because `python` is not installed in this shell.
  - `python3 -m pytest tests/test_db_phase1.py` failed because pytest is not installed in the system interpreter.
  - `PYTHONPATH=src python3 -m unittest tests.test_db_phase1 -v` failed because `tests` is not a package.
  - `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_db_phase1.py' -v` initially failed with stale expected migration assertions ending at `0038`, then passed after test updates: 3 tests OK.
- 2026-05-01: Added `product_platform.demo` package:
  - `catalog.py` seeds the customer-support refund scenario with nine ordered steps and proof links covering Agents, Policies, MCP, Mesh, Runtime, Trust, Discovery, Compliance, and Observability.
  - `models.py` defines required-service, proof-link, scenario summary/detail, and step response models plus JSON parsing helpers.
  - `repository.py` lists scenarios, resolves scenario id or slug, returns ordered steps, and serializes rows.
  - `db/seed.py` now calls `seed_demo_scenarios`.
- 2026-05-01: Added `tests/test_demo_scenario_catalog_phase1.py`. Command `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_demo_scenario_catalog_phase1.py' -v` passed: 3 tests OK.
- 2026-05-01: Added authenticated Demo Lab scenario APIs in `api/app.py`:
  - `GET /api/v1/demo/scenarios` lists environment-scoped scenario summaries and requires `JOB_RUN`.
  - `GET /api/v1/demo/scenarios/{scenario_id}` returns detail by id or slug with ordered steps and requires `JOB_RUN`.
- 2026-05-01: Extended `tests/test_demo_scenario_catalog_phase1.py` with API list/detail coverage. Command `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_demo_scenario_catalog_phase1.py' -v` passed: 5 tests OK.
- 2026-05-01: Final Phase 1 verification commands:
  - `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_db_phase1.py' -v` passed: 3 tests OK.
  - `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_demo_scenario_catalog_phase1.py' -v` passed: 5 tests OK.
- 2026-05-01: Phase 1 complete. Implementation files: `db/migrations/0039_demo_scenarios.*.sql`, `product_platform/demo/*`, `db/seed.py`, `api/app.py`, `tests/test_db_phase1.py`, and `tests/test_demo_scenario_catalog_phase1.py`. Next phase is Runner Engine.
- 2026-05-01: Started Phase 2 Runner Engine after re-reading this log and `docs/product-platform-worktree/06-demo-delivery/01-demo-lab/01-scenario-catalog-runner.md`. Conservative assumption: implement a synchronous runner because the plan allows background job or synchronous runner and current API tests are in-process.
- 2026-05-01: Added `0040_demo_runs` migration with `demo_runs` and `demo_step_runs`, status/result JSON, indexes, and rollback. Updated `tests/test_db_phase1.py` for migration `0040`. Command `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_db_phase1.py' -v` passed: 3 tests OK.
- 2026-05-01: Added run/step-run models and repository methods for `create_run`, `get_run`, ordered `list_step_runs`, next pending step lookup, step status/result updates, aggregate run status refresh, cancellation, and run response serialization.
- 2026-05-01: Added `tests/test_demo_scenario_runner_phase2.py`. Command `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_demo_scenario_runner_phase2.py' -v` passed: 2 tests OK.
- 2026-05-01: Added `product_platform/demo/runner.py` with `DemoStepExecutor`, `DemoScenarioRunner`, deterministic dispatch for all nine action types, failure handling, correlation IDs in results, and audit event emission for step/run lifecycle.
- 2026-05-01: Added Demo Lab run APIs in `api/app.py`: start run, get run, continue run, and cancel run. Start/continue emit canonical audit events; cancel requires `JOB_CANCEL` and emits `demo.run.canceled`.
- 2026-05-01: Extended `tests/test_demo_scenario_runner_phase2.py` for dispatch, run completion, failed-step failure, API start/get/continue/cancel, and audit events. Command `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_demo_scenario_runner_phase2.py' -v` passed: 7 tests OK.
- 2026-05-01: Final Phase 2 verification commands:
  - `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_db_phase1.py' -v` passed: 3 tests OK.
  - `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_demo_scenario_catalog_phase1.py' -v` passed: 5 tests OK.
  - `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_demo_scenario_runner_phase2.py' -v` passed: 7 tests OK.
- 2026-05-01: Phase 2 complete. Implementation files: `db/migrations/0040_demo_runs.*.sql`, `demo/models.py`, `demo/repository.py`, `demo/runner.py`, `api/app.py`, `tests/test_db_phase1.py`, and `tests/test_demo_scenario_runner_phase2.py`. Next phase is Live Evidence Links.
- 2026-05-01: Started Phase 3 Live Evidence Links after re-reading this log, the Phase 3 plan, and frontend component/test conventions.
- 2026-05-01: Added `demo/evidence.py`, evidence/proof response models, and enriched `demo_step_run_response` with `actual_result`, `evidence_links`, and `proof_checklist`.
- 2026-05-01: Added `tests/test_demo_live_evidence_phase3.py` for policy evidence link generation, persisted correlation IDs, and expected-vs-actual proof checklist data. Command `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_demo_live_evidence_phase3.py' -v` passed: 3 tests OK.
- 2026-05-01: Added `frontend/src/demo.js` proof checklist renderer and `frontend/test/demo.test.js`. Updated `frontend/package.json` typecheck to include both files.
- 2026-05-01: Frontend commands:
  - `node --test test/demo.test.js` passed: 2 tests OK.
  - `npm run typecheck` passed.
- 2026-05-01: Final Phase 3 verification commands:
  - `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_demo_live_evidence_phase3.py' -v` passed: 3 tests OK.
  - `node --test test/demo.test.js` passed: 2 tests OK.
  - `npm run typecheck` passed.
- 2026-05-01: Phase 3 complete. Implementation files: `demo/evidence.py`, `demo/models.py`, `demo/repository.py`, `tests/test_demo_live_evidence_phase3.py`, `frontend/src/demo.js`, `frontend/test/demo.test.js`, and `frontend/package.json`. Next phase is UI.
- 2026-05-01: Started Phase 4 UI after re-reading this log, the Phase 4 plan, and frontend route/API/client conventions. `/demo-lab` is currently a placeholder route, and demo API client methods are not yet present.
- 2026-05-01: Expanded `frontend/src/demo.js` with Demo Lab page, scenario catalog, scenario detail, run timeline, proof checklist integration, and start/continue/cancel data attributes. Added demo API client methods in `apiClient.js` and wired `/demo-lab` into `renderShell`.
- 2026-05-01: Extended `frontend/test/demo.test.js` for catalog rendering, page rendering, timeline status updates, proof checklist, and cancel API path. First `node --test test/demo.test.js` run failed because timeline rendering only read `stepRun.actual_result`; patched fallback to proof-checklist actual result. Rerun passed: 6 tests OK.
- 2026-05-01: Added Demo Lab load/refresh helpers, navigation/bootstrap route loading, and scenario open/start/continue/cancel click handlers in `frontend/src/app.js`.
- 2026-05-01: Phase 4 focused commands:
  - `node --test test/demo.test.js` passed: 6 tests OK.
  - `npm run typecheck` passed.
- 2026-05-01: Final Scenario Catalog And Runner verification commands:
  - `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_db_phase1.py' -v` passed: 3 tests OK.
  - `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_demo_scenario_catalog_phase1.py' -v` passed: 5 tests OK.
  - `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_demo_scenario_runner_phase2.py' -v` passed: 7 tests OK.
  - `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_demo_live_evidence_phase3.py' -v` passed: 3 tests OK.
  - `node --test test/demo.test.js` passed: 6 tests OK.
  - `npm run typecheck` passed.
  - `npm run lint` passed.
- 2026-05-01: Scenario Catalog And Runner complete. No deviations except the documented conservative synchronous-runner choice allowed by the plan. Next plan file: Demo Environment Reset.
