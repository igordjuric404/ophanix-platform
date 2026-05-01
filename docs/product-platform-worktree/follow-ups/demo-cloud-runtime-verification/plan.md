# Demo Cloud Runtime Verification Completion

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
