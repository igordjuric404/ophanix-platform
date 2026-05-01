# Demo Cloud Runtime Verification Completion

## Second-Pass Status

Status: `Needs verification` and `Audit finding revised`.

The first-audit finding about misleading PostgreSQL/cloud claims has been revised: `2de9148` explicitly documents the MVP cloud preview as SQLite-on-durable-volume, rejects unsupported PostgreSQL database URLs in readiness, and adds deterministic readiness probes plus opt-in smoke scripts. The remaining gap is verification, not another static code path: this environment still cannot run Docker daemon-backed image builds or `docker compose up`, and the original `02-mvp-cloud-deployment.md` managed-PostgreSQL pilot scope is intentionally deferred rather than implemented.

## Second-Pass Delta Plan

### Goal

Produce real runtime evidence for the local compose stack and production images in a Docker-capable environment, and make the cloud deployment scope decision explicit for pilot acceptance.

### Evidence

- Implemented: `packages/product-platform/deploy/cloud/smoke-images.sh`, `packages/product-platform/deploy/local-demo-smoke.sh`, SQLite-aware cloud docs, `ReadinessProbes`, and cloud/local static tests.
- Verified locally in this audit: backend tests pass with localhost socket binding allowed; frontend validation passes.
- Not verified locally: `docker build`, API/worker/frontend image smoke runs, and `docker compose up --build --wait` because Docker daemon access is unavailable.
- Deferred scope: managed PostgreSQL runtime support from the original MVP cloud plan is not implemented.

### Implementation Approach

1. Run the checked-in smoke scripts in an environment where Docker daemon access is available.
2. Capture command outputs in the follow-up execution log, including image IDs, `/health`, `/ready`, worker no-op output, Demo Lab reset status, and scenario start status.
3. Decide whether pilot readiness accepts the documented SQLite cloud-preview scope or requires a new PostgreSQL implementation follow-up.
4. If PostgreSQL is required, create a separate database-runtime follow-up rather than folding it into static deployment verification.

### Likely Files

- `packages/product-platform/deploy/cloud/smoke-images.sh`
- `packages/product-platform/deploy/local-demo-smoke.sh`
- `packages/product-platform/LOCAL_DEMO.md`
- `packages/product-platform/deploy/cloud/PILOT_READINESS.md`
- `packages/product-platform/deploy/cloud/env.example`
- `packages/product-platform/src/product_platform/api/dependencies.py`
- `packages/product-platform/src/product_platform/db/migrator.py`
- `packages/product-platform/tests/test_mvp_cloud_deployment_phase*.py`
- `packages/product-platform/tests/test_local_demo_compose_phase*.py`

### Test Plan

- `sh deploy/cloud/smoke-images.sh` in a Docker-capable environment.
- `sh deploy/local-demo-smoke.sh` in a Docker-capable environment.
- `docker compose --env-file .env.example -f docker-compose.demo.yml up --build --wait --wait-timeout 120`.
- Backend deployment/local-demo focused tests, including localhost socket tests.
- Frontend `npm run validate`.

### Acceptance Criteria

- Production API, worker, and frontend images build successfully.
- API container responds to `/health` and `/ready`.
- Worker image can run the no-op smoke command.
- Compose stack starts cleanly, seeds idempotently, reports healthy baseline, resets Demo Lab, and starts the demo scenario.
- Pilot readiness explicitly accepts SQLite cloud preview or points to a separate PostgreSQL runtime plan.

## Feature Scope

Close the runtime verification gaps from `06-demo-delivery`: local compose should either use the database services it declares or clearly scope them as optional parity services, cloud readiness should verify actual configured dependencies where feasible, and production container images should be buildable and smoke tested in an environment with Docker.

## Existing Repo Assets To Reuse

- `docker-compose.demo.yml`, `Dockerfile.demo`, `LOCAL_DEMO.md`.
- `deploy/cloud/*` Dockerfiles, manifests, runbooks, and image workflow.
- `product_platform.db` connection/migration layer.
- `product_platform.api.dependencies` readiness registry.
- `product_platform.deployment` helpers.

## Out Of Scope

- Full production infrastructure provisioning.
- Switching every repository query to an ORM unless necessary.
- Multi-region or enterprise deployment hardening beyond MVP cloud readiness.

## Data Model

No product data model changes are required unless PostgreSQL support needs migration metadata adjustments. Preserve existing migration order and rollback behavior.

## API Surface

Extend existing `/ready` behavior in cloud mode so it can distinguish:

- Configured but unchecked dependencies.
- Reachable/healthy dependencies.
- Unreachable/unhealthy dependencies.

Avoid changing the public response shape unless tests and docs are updated together.

## UI Surface

No major UI changes are required. System dependency status in the existing shell should accurately reflect new readiness states.

## Implementation Phases

### Phase 1: Database Runtime Decision

Steps:

1. Decide whether MVP product-platform must support PostgreSQL now or explicitly remain SQLite for local/demo only.
2. If PostgreSQL is required, add a connection adapter and migration execution path that supports configured PostgreSQL URLs.
3. If PostgreSQL is deferred, update local/cloud docs and readiness to avoid claiming managed PostgreSQL is connected.
4. Keep SQLite test speed and local developer ergonomics.

Tests:

- Unit test `database_url` parsing for supported schemes.
- Integration/smoke test migration path for SQLite remains green.
- PostgreSQL smoke test using a local service or documented CI service if support is implemented.

### Phase 2: Readiness Checks

Steps:

1. Replace configuration-string-only cloud dependency checks with real probes where safe.
2. Probe database connection/migration-readiness.
3. Probe Redis/queue endpoint when configured.
4. Probe object storage and secret manager through adapter interfaces or deterministic smoke checks.
5. Preserve fast deterministic unit tests with fake adapters.

Tests:

- Readiness test configured-but-unreachable dependency reports unhealthy.
- Readiness test fake healthy adapters report ready.
- Regression test local mode still treats optional dependencies as non-blocking.

### Phase 3: Container Build And Smoke Verification

Steps:

1. Run production frontend/API/worker Docker builds in an environment with Docker daemon access.
2. Smoke start API image and call `/health` and `/ready`.
3. Smoke worker image with the no-op job.
4. Validate image workflow still builds all targets.

Tests:

- Docker build command succeeds for frontend, API, and worker.
- API container smoke test succeeds.
- Worker container smoke test succeeds.
- Existing static Dockerfile tests remain green.

### Phase 4: Local Compose End-To-End Check

Steps:

1. Run `docker compose --env-file .env.example -f docker-compose.demo.yml up` in a Docker-capable environment.
2. Confirm migrations and seeds run idempotently.
3. Confirm API, worker, frontend, MCP, and sample agent health checks are healthy.
4. Confirm Demo Lab scenario can start and reset from the composed stack.
5. Document any optional profile caveats.

Tests:

- Compose config test remains green.
- Compose up/down smoke run is documented and, if possible, automated as an opt-in test.
- Demo baseline healthy check passes against the composed API.

## Overall Validation

- Cloud/local deployment docs match real runtime behavior.
- `/ready` reflects actual dependency health in cloud mode.
- Production images build and smoke test successfully.
- Local compose can run the demo stack end to end in a Docker-capable environment.

## Dependencies

- Demo seed regression recovery follow-up, so aggregate tests are green before deployment smoke verification.
- Any chosen PostgreSQL/Redis/object-store client dependencies must be added intentionally.

## Definition Of Done

- Demo delivery is not just structurally tested; it has real runtime smoke evidence for containers, compose, and cloud dependency readiness.

## Implementation Status

Status: `Needs verification`.

Execution log: `docs/product-platform-worktree/second-pass-implementation-logs/demo-cloud-runtime-verification.md`.

Completed in this implementation pass:

- Re-verified the existing SQLite cloud-preview scope, readiness probes, smoke scripts, and focused tests.
- Started Docker Desktop after approval and confirmed Docker daemon access with Docker Desktop 4.44.3 / Engine 28.3.2.
- Removed the optional `# syntax=docker/dockerfile:1.7` directive from the three cloud Dockerfiles because they do not use Dockerfile 1.7-only features and the directive introduced an extra external BuildKit frontend resolution step before product image builds.
- Re-ran `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_mvp_cloud_deployment_phase*.py' -v`; result: 18 tests passed.
- Re-ran local demo focused tests with localhost socket binding allowed; result: 10 tests passed.
- Confirmed `docker compose --env-file .env.example -f docker-compose.demo.yml config` renders successfully.
- Confirmed `deploy/cloud/PILOT_READINESS.md` and `LOCAL_DEMO.md` explicitly document SQLite-on-volume as the current preview scope and PostgreSQL as deferred/service-parity, so no new PostgreSQL runtime follow-up was created.

Remaining verification blocker:

- `sh deploy/cloud/smoke-images.sh` now advances to base image metadata resolution for `python:3.11-slim`, but Docker registry/base-image metadata access stalls in this environment. The required base images are not cached locally.
- `docker compose --env-file .env.example -f docker-compose.demo.yml up --build --wait --wait-timeout 120` and `sh deploy/local-demo-smoke.sh` similarly reach external image pull/metadata for Redis, Postgres, and frontend/nginx images, then stall.
- The remaining gap is runtime evidence from an environment with working Docker registry/base-image access, not another known product-platform implementation task.
