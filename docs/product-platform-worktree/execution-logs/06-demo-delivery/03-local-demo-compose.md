# Execution Log: 06 Demo Delivery / Local Demo Compose

Source plan: `docs/product-platform-worktree/06-demo-delivery/02-deployment/01-local-demo-compose.md`

## Phase Overview

### Phase 1: Compose Services
- Goal: Define local frontend/API/worker/PostgreSQL/Redis services with health checks and environment examples.
- Status: Done
- Biggest checklist items:
  - [x] Define frontend, API, worker, postgres, and redis services.
  - [x] Add service health checks.
  - [x] Configure local image/build/mount convention.
  - [x] Add `.env.example`.

### Phase 2: Demo Services
- Goal: Add local MCP/sample agent/optional policy and observability services.
- Status: Done
- Biggest checklist items:
  - [x] Add local MCP service.
  - [x] Add sample support/refund/research agent services or commands.
  - [x] Add optional OPA.
  - [x] Add optional OTel/Prometheus/Grafana.

### Phase 3: Migrations And Seed
- Goal: Run migrations and idempotent demo seeds during local startup.
- Status: Done
- Biggest checklist items:
  - [x] Add migration/init command or service.
  - [x] Seed org, admin, policies, scenario, and MCP registration.
  - [x] Ensure repeated startup does not duplicate data.
  - [x] Verify Demo Lab baseline is healthy after startup.

## Detailed Checklist: Phase 3 Migrations And Seed

- [x] Re-read completed compose Phase 1/2 logs and local compose plan.
- [x] Confirm compose init service runs migrations and seed command.
- [x] Add fresh-volume startup seed test.
- [x] Add repeated startup idempotency assertions.
- [x] Add Demo Lab baseline healthy assertion after startup seed.
- [x] Run focused Phase 3 tests.
- [x] Update this execution log with implementation details and command outcomes.

### Phase 4: Documentation
- Goal: Document local demo startup, reset, logs, credentials, URLs, and troubleshooting.
- Status: Done
- Biggest checklist items:
  - [x] Add README commands for start/stop/reset/logs.
  - [x] Document required and optional credentials.
  - [x] Document demo URL/login.
  - [x] Document degraded handling and troubleshooting.

## Detailed Checklist: Phase 4 Documentation

- [x] Re-read completed compose Phase 1-3 logs and local compose plan.
- [x] Add local demo README with start/stop/reset/log commands.
- [x] Document required and optional credentials.
- [x] Document demo URL and dev-login identity.
- [x] Document troubleshooting for ports, Docker, optional credentials, and degraded prerequisites.
- [x] Add documentation test for key commands/URLs/degraded behavior.
- [x] Run focused Phase 4 documentation tests.
- [x] Run final Local Demo Compose validation.
- [x] Update this execution log with implementation details and command outcomes.

## Detailed Checklist: Phase 1 Compose Services

- [x] Re-read scenario/reset logs before starting compose work.
- [x] Inspect existing root `docker-compose.yml`, Dockerfiles, package entrypoints, and worker command.
- [x] Define compose services and health checks.
- [x] Add `.env.example` values needed for local demo.
- [x] Validate compose config.
- [x] Run focused health/worker checks where feasible.
- [x] Update this execution log with implementation details and command outcomes.

## Detailed Checklist: Phase 2 Demo Services

- [x] Re-read Phase 1 compose log and local compose plan.
- [x] Add lightweight local MCP HTTP service command.
- [x] Add lightweight sample agent HTTP service command.
- [x] Add MCP service to compose with health check.
- [x] Add sample support, refund, and research agent services to compose with health checks.
- [x] Add optional OPA service under a profile.
- [x] Add optional OTel, Prometheus, and Grafana services under an observability profile.
- [x] Add service port env examples.
- [x] Add tests for MCP health and sample agent heartbeat.
- [x] Validate compose config with optional profiles.
- [x] Update this execution log with implementation details and command outcomes.

## Progress Notes

- 2026-05-01: Initial execution log created from implementation plan. Work is blocked until Scenario Catalog And Runner and Demo Environment Reset are complete.
- 2026-05-01: Started Phase 1 after Scenario Catalog And Runner and Demo Environment Reset completed. Existing product platform uses SQLite migrations and a static frontend shell; local compose will include Postgres/Redis service parity, while the current API database URL remains SQLite-backed for the local demo command path.
- 2026-05-01: Added `packages/product-platform/Dockerfile.demo`, `docker-compose.demo.yml`, `frontend/nginx.demo.conf`, and `.env.example`. The compose stack defines frontend, API, worker, Postgres, Redis, and migrate/seed services with health checks.
- 2026-05-01: Added `product_platform.cli worker noop` and `worker loop` for local worker health checks. First command run failed on `LocalWorker` import, then on `JobExecution.message`; fixed to use exported `Worker` and print `execution.result['ok']`.
- 2026-05-01: Commands run:
  - `docker compose --env-file .env.example -f docker-compose.demo.yml config` -> passed.
  - `PYTHONPATH=src python3 -m product_platform.cli worker noop` -> initially failed twice, then passed with `Worker no-op job succeeded: True`.
  - `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_local_demo_compose_phase1.py' -v` -> passed, 3 tests.
- 2026-05-01: Added `product_platform.demo.services` with lightweight stdlib HTTP services for local demo MCP and sample agents. Added `demo-service serve` and `demo-service health` CLI commands.
- 2026-05-01: Extended `docker-compose.demo.yml` with `sample-mcp`, `support-agent`, `refund-agent`, `research-agent`, optional `opa` profile, and optional `otel-collector`/`prometheus`/`grafana` observability profile. Added `observability/otel-collector.demo.yml` and `observability/prometheus.demo.yml`.
- 2026-05-01: Added `test_local_demo_compose_phase2.py`. First run failed on MCP/agent HTTP tests with sandbox `PermissionError: [Errno 1] Operation not permitted` when binding an ephemeral local socket. Reran the same focused test with local socket binding allowed; passed 3 tests.
- 2026-05-01: Added `test_local_demo_compose_phase3.py`. It verifies compose uses `migrate-seed` with `db seed`, fresh SQLite volume startup applies migrations/seeds, a repeated seed run does not duplicate rows, and Demo Lab baseline is healthy.
- 2026-05-01: Command `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_local_demo_compose_phase3.py' -v` passed 2 tests.
- 2026-05-01: Added `packages/product-platform/LOCAL_DEMO.md` with start/stop/reset/log commands, optional profile commands, URLs, dev-login email, credential notes, degraded optional credential behavior, and troubleshooting.
- 2026-05-01: Added `test_local_demo_compose_phase4.py`. Command `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_local_demo_compose_phase4.py' -v` passed 1 test.
- 2026-05-01: Final Local Demo Compose validation passed:
  - `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_local_demo_compose_phase1.py' -v` -> passed, 3 tests.
  - `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_local_demo_compose_phase2.py' -v` -> passed, 3 tests with local socket binding allowed.
  - `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_local_demo_compose_phase3.py' -v` -> passed, 2 tests.
  - `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_local_demo_compose_phase4.py' -v` -> passed, 1 test.

## Phase 4 Completion Notes

- Implemented local demo documentation in `packages/product-platform/LOCAL_DEMO.md`.
- Added focused documentation coverage in `packages/product-platform/tests/test_local_demo_compose_phase4.py`.

## Feature Completion Notes

- Local Demo Compose is complete across all four phases.
- Implemented local compose stack, demo service helpers, init/seed validation, and local demo documentation.
- Next feature: MVP Cloud Deployment.

## Phase 3 Completion Notes

- Reused the existing `db seed` CLI path for compose init; it applies migrations before seeding.
- Verified seeded counts after repeated startup: 2 policy placeholders, 1 demo scenario, 1 MCP server, and 3 sample agents.
- Verified Demo Lab baseline status is `healthy` after startup seed.

## Phase 2 Completion Notes

- Implemented local MCP health/tools endpoint and sample agent health/heartbeat endpoints.
- Implemented compose services and optional profile services with health checks.
- Commands run:
  - `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_local_demo_compose_phase2.py' -v` -> initial sandbox socket-bind failure, then passed with local socket binding allowed.
- No product-code deviations from the plan.

## Phase 1 Completion Notes

- Implemented local compose service skeleton with frontend nginx proxy, API, worker, Postgres, Redis, and migrate/seed service.
- Added focused compose tests in `packages/product-platform/tests/test_local_demo_compose_phase1.py`.
- Conservative deviation: product API migrations remain SQLite-backed because the existing migration runner only supports SQLite. Postgres is included for local service parity and future managed-service compatibility.
- Phase 2 should add local MCP/sample agent/optional policy and observability services.
