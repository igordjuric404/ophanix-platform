# Discovery Scan Runner Execution Log

## Phase Overview

| Phase | Goal | Status | Biggest Checklist Items |
| --- | --- | --- | --- |
| Phase 1: Scanner Registry | Register built-in scanners, expose metadata, validate configs, and report availability. | Done | Process/config/GitHub metadata; validation; availability; unit/API tests. |
| Phase 2: Scan Targets | Create and list scoped scan targets with scanner-specific validation. | Done | Target API; config path validation; GitHub token ref validation; environment scoping; tests. |
| Phase 3: Manual Run Execution | Run configured scanners through jobs, persist run states/findings, and audit start/completion. | Done | Job type; scanner invocation; raw finding persistence; failed run errors; tests. |
| Phase 4: Scheduled Runs | Connect targets to schedules, prevent overlapping runs, and show next run time. | Done | Schedules; UI controls; overlap guard; next run; tests. |
| Phase 5: Scan Run UI | Render scan run table and detail with findings, counts, duration, errors, and future reconciliation links. | Done | Table; detail drawer/page; counts; error state; component tests. |
| Overall Validation | Configure a repo/config scan, run it from UI/API, persist findings, and verify scan history/audit. | Done | Target; manual run; raw findings; history; audit. |

## Detailed Checklist: Phase 1, Scanner Registry

- [x] Review prior execution logs and implementation plan before starting.
- [x] Register process/config/GitHub built-in scanner types.
- [x] Expose metadata through `GET /api/v1/discovery/scanners`.
- [x] Validate required config by scanner type.
- [x] Include scanner availability status.
- [x] Unit test registry includes expected built-ins.
- [x] API test scanner list returns metadata.
- [x] Unit test invalid scanner config fails validation.

## Activity

- 2026-04-30: Created the initial execution log from `docs/product-platform-worktree/01-agent-registry/02-shadow-ai/01-discovery-scan-runner.md`.
- 2026-04-30: Reviewed the registry README, credential completion log, and discovery scan runner implementation plan before starting Phase 1. Confirmed existing `agent-discovery` scanners auto-register process/config/GitHub scanners. Added focused tests in `packages/product-platform/tests/test_discovery_scan_runner_phase1.py` for built-in registry metadata, invalid config validation, and `GET /api/v1/discovery/scanners`. Command `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_discovery_scan_runner_phase1.py' -v`; result: expected import failure because `product_platform.discovery` does not exist yet.
- 2026-04-30: Implemented `product_platform.discovery` registry/models and `GET /api/v1/discovery/scanners`, backed by the existing `agent-discovery` process/config/GitHub scanner registry. Command `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_discovery_scan_runner_phase1.py' -v`; result: 3 tests passed.
- 2026-04-30: Ran full backend regression before moving to Phase 2. Command `PYTHONPATH=src python3 -m unittest discover -s tests -v`; result: 126 tests passed.
- 2026-04-30: Re-read this execution log and the implementation plan before Phase 2. Added focused tests in `packages/product-platform/tests/test_discovery_scan_runner_phase2.py` for config target creation, invalid scanner rejection, and environment-scoped target listing. Command `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_discovery_scan_runner_phase2.py' -v`; result: expected 404 failures because target APIs do not exist yet.

## Detailed Checklist: Phase 2, Scan Targets

- [x] Re-read this execution log and implementation plan before coding.
- [x] Add discovery scanner/target/run/finding tables.
- [x] Add discovery target request/response models.
- [x] Add discovery repository for target persistence and environment scoping.
- [x] Add target creation API.
- [x] Add target listing API.
- [x] Validate config target path for config scanner.
- [x] Validate GitHub token reference for GitHub scanner.
- [x] API test creates config scan target.
- [x] API test invalid target type is rejected.
- [x] API test target is scoped to environment.

## Phase 2 Implementation Notes

- 2026-04-30: Confirmed `0004_discovery_scan_runner` migration adds `discovery_scanners`, `discovery_targets`, `discovery_runs`, and `discovery_raw_findings`, and database migration tests expect the new migration sequence.
- 2026-04-30: Added discovery target request/response models in `packages/product-platform/src/product_platform/discovery/models.py`.
- 2026-04-30: Added `packages/product-platform/src/product_platform/discovery/repository.py` with scanner-specific target type validation, config path validation through the scanner registry, GitHub `credentials_ref` validation, environment-scoped target persistence, and response serialization.
- 2026-04-30: Added `POST /api/v1/discovery/targets` and `GET /api/v1/discovery/targets` in `packages/product-platform/src/product_platform/api/app.py`.
- 2026-04-30: Command `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_discovery_scan_runner_phase2.py' -v`; result: 3 tests passed.
- 2026-04-30: Command `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_db_phase1.py' -v`; result: 3 tests passed and migration `0004` applied/rolled back cleanly.
- 2026-04-30: Command `PYTHONPATH=src python3 -m unittest discover -s tests -v`; result: 129 backend tests passed. Phase 2 complete.

## Detailed Checklist: Phase 3, Manual Run Execution

- [x] Re-read this execution log and implementation plan before coding.
- [x] Add focused tests for manual config scan persistence, failed scan errors, and audit start/completion.
- [x] Add discovery run request/response/raw finding API models.
- [x] Add discovery repository methods for run creation, status updates, raw finding persistence, and scoped run retrieval.
- [x] Add scan runner service that invokes the selected scanner from a persisted target.
- [x] Persist successful run summary with raw finding count and scanner errors.
- [x] Persist failed run error details.
- [x] Emit audit event when a manual scan starts.
- [x] Emit audit event when a manual scan completes or fails.
- [x] Add `POST /api/v1/discovery/runs`.
- [x] Add `GET /api/v1/discovery/runs`.
- [x] Add `GET /api/v1/discovery/runs/{id}`.
- [x] Integration test config scanner run persists findings.
- [x] Integration test failed scan records error.
- [x] Integration test completion emits audit event.

## Phase 3 Implementation Notes

- 2026-04-30: Added focused Phase 3 integration tests in `packages/product-platform/tests/test_discovery_scan_runner_phase3.py` for config scanner run persistence, deleted-target failure handling, and audit start/completion events.
- 2026-04-30: Command `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_discovery_scan_runner_phase3.py' -v`; result: expected failures/errors because `/api/v1/discovery/runs` is not implemented yet (`404` and missing run id cascade).
- 2026-04-30: Added run/raw finding API models, repository methods, `DiscoveryScanRunner`, and `POST/GET /api/v1/discovery/runs` plus `GET /api/v1/discovery/runs/{id}`. Manual runs now validate the stored target config, invoke the registered scanner, persist raw findings, record succeeded/failed terminal state, and emit `discovery.scan.started` plus `discovery.scan.completed` or `discovery.scan.failed`.
- 2026-04-30: Command `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_discovery_scan_runner_phase3.py' -v`; result: 3 tests passed.
- 2026-04-30: Command `PYTHONPATH=src python3 -m unittest discover -s tests -v`; result: 132 backend tests passed. Phase 3 complete.

## Detailed Checklist: Phase 4, Scheduled Runs

- [x] Re-read this execution log and implementation plan before coding.
- [x] Add tests for target schedule creation/update, scheduled enqueue, overlap guard, and next run display data.
- [x] Add target schedule fields to request/response models.
- [x] Add repository support for attaching schedules to targets and exposing next run metadata.
- [x] Connect discovery target schedules to background job schedules.
- [x] Add scan runner overlap guard for the same target.
- [x] Add API support for manual/hourly/daily target schedule controls.
- [x] Add scheduled job execution path for discovery scan payloads.
- [x] Unit test overlapping run is skipped.
- [x] Integration test schedule enqueues run.
- [x] Component/API test target page data shows next run.

## Phase 4 Implementation Notes

- 2026-04-30: Added `packages/product-platform/tests/test_discovery_scan_runner_phase4.py` covering hourly target schedule creation and next-run metadata, scheduled enqueue into `background_jobs` with `discovery.scan` payload, and overlap skip behavior when a target already has a running run.
- 2026-04-30: Command `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_discovery_scan_runner_phase4.py' -v`; result: expected failures because `PATCH /api/v1/discovery/targets/{target_id}/schedule` is not implemented and the scan runner does not yet skip overlapping target runs.
- 2026-04-30: Added an immediate `discovery.scan` job execution test to ensure scheduled job payloads can drive the persisted discovery runner path. Command `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_discovery_scan_runner_phase4.py' -v`; result: expected single failure because the job API still rejects immediate non-`demo.noop` jobs with `400`.
- 2026-04-30: Added schedule fields to target models/responses, schedule persistence through `job_schedules`, `PATCH /api/v1/discovery/targets/{target_id}/schedule`, overlap skip behavior, and immediate `discovery.scan` job execution through `POST /api/v1/jobs`.
- 2026-04-30: Command `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_discovery_scan_runner_phase4.py' -v`; result: 4 tests passed.
- 2026-04-30: Command `PYTHONPATH=src python3 -m unittest discover -s tests -v`; result: 136 backend tests passed. Phase 4 complete.

## Detailed Checklist: Phase 5, Scan Run UI

- [x] Re-read this execution log and implementation plan before coding.
- [x] Add frontend API client methods for scanners, targets, schedules, and scan runs.
- [x] Build Discovery -> Scan Runs workspace with scanner cards.
- [x] Build target table with schedule mode and next run.
- [x] Build run history table with status, raw finding count, high-risk placeholder, duration, and errors.
- [x] Build run detail panel/drawer with raw findings and future reconciliation link placeholder.
- [x] Add schedule controls for manual/hourly/daily.
- [x] Add run-now action wired to manual scan API.
- [x] Component/API tests added for route rendering, run table, run detail, error state, and API endpoints.
- [x] Component test run table renders status.
- [x] Component test run detail renders raw findings.
- [x] Component test error state is visible.

## Phase 5 Implementation Notes

- 2026-04-30: Added `packages/product-platform/frontend/test/discovery-scan-runner.test.js` covering the `/discovery` route, run table status/counts/duration, raw finding detail, failed run error state, and discovery API client endpoints.
- 2026-04-30: Command `npm test -- discovery-scan-runner.test.js`; result: command-level path error because the package script did not resolve the bare filename from `test/`.
- 2026-04-30: Command `node --test test/discovery-scan-runner.test.js`; result: expected module failure because `packages/product-platform/frontend/src/discovery.js` does not exist yet.
- 2026-04-30: Added `packages/product-platform/frontend/src/discovery.js`, wired `/discovery` in `renderShell`, added discovery API client methods, loaded discovery data on route entry/bootstrap, wired schedule update/run-now/open-run UI handlers, added discovery styles, and added discovery files to frontend typecheck coverage.
- 2026-04-30: Command `node --test test/discovery-scan-runner.test.js`; result: 5 tests passed.
- 2026-04-30: Command `npm run validate`; result: frontend lint passed, typecheck passed, and 56 frontend tests passed. Phase 5 complete.

## Detailed Checklist: Overall Validation

- [x] Re-read this execution log and implementation plan before overall validation.
- [x] Add an end-to-end backend validation test for configuring and running a config scan through API.
- [x] Create deterministic repo/config fixture with `agentmesh.yaml`.
- [x] Create discovery target through API.
- [x] Run discovery scan through API.
- [x] Assert raw findings persisted and available through run detail.
- [x] Assert run appears in scan history.
- [x] Assert discovery audit events were emitted.
- [x] Run full backend regression.
- [x] Run full frontend validation.

## Overall Validation Notes

- 2026-04-30: Added `packages/product-platform/tests/test_discovery_scan_runner_overall.py` to exercise the full API flow: login, create config target, scan a temp repo with `agentmesh.yaml`, fetch run detail/raw findings, verify run history, and verify `discovery.scan.started`/`discovery.scan.completed` audit events.
- 2026-04-30: Command `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_discovery_scan_runner_overall.py' -v`; result: 1 test passed.
- 2026-04-30: Command `PYTHONPATH=src python3 -m unittest discover -s tests -v`; result: 137 backend tests passed.
- 2026-04-30: Command `npm run validate`; result: frontend lint passed, typecheck passed, and 56 frontend tests passed. Discovery Scan Runner complete.

## Completion Summary

- Backend: scanner registry, target persistence, manual runs, raw finding persistence, run history/detail, target schedules, overlap skip behavior, immediate `discovery.scan` job execution, and discovery audit events.
- Frontend: `/discovery` scan workspace with scanner cards, target schedule controls, run-now controls, run history, run detail/raw findings, error visibility, and discovery API client methods.
- Remaining: Discovery findings reconciliation is intentionally separate and covered by `02-discovery-findings-reconciliation.md`.
