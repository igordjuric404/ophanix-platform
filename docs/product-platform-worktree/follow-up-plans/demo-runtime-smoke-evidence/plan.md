# Demo Runtime Smoke Evidence

## Feature Scope

Close the remaining `06-demo-delivery` verification gap by producing real Docker/runtime smoke evidence for the product-platform demo and cloud-preview artifacts. The current implementation is statically tested and functionally migrated in React; this plan verifies that the checked-in deployment paths run outside the unit-test harness.

## Existing Repo Assets To Reuse

- `packages/product-platform/deploy/cloud/smoke-images.sh`.
- `packages/product-platform/deploy/local-demo-smoke.sh`.
- `packages/product-platform/docker-compose.demo.yml`.
- `packages/product-platform/deploy/cloud/Dockerfile.api`.
- `packages/product-platform/deploy/cloud/Dockerfile.worker`.
- `packages/product-platform/deploy/cloud/Dockerfile.frontend`.
- `packages/product-platform/LOCAL_DEMO.md`.
- `packages/product-platform/deploy/cloud/PILOT_READINESS.md`.
- Demo Lab backend APIs and React `DemoLabPage`.

## Out Of Scope

- Full production infrastructure provisioning.
- Implementing managed PostgreSQL unless pilot acceptance explicitly rejects the documented SQLite cloud-preview scope.
- Rewriting Dockerfiles before smoke evidence shows a real failure.

## Data Model

No data model changes are expected. Preserve the current SQLite cloud-preview scope unless a separate database-runtime plan is created.

## API Surface

No product API changes are expected. Verify existing `/health`, `/ready`, auth, Demo Lab reset, and Demo Lab run endpoints from containers/compose.

## UI Surface

No major UI changes are expected. If runtime smoke reveals inaccurate system-status or readiness messaging, update the shell copy and tests together.

## Implementation Phases

### Phase 1: Docker-Capable Environment Prep

Steps:

1. Use an environment with Docker daemon access and working registry/base-image metadata access.
2. Confirm required base images can be pulled or are cached.
3. Record Docker and Compose versions in a follow-up execution log.

Tests:

- `docker version`.
- `docker compose version`.

### Phase 2: Production Image Smoke

Steps:

1. Run `sh deploy/cloud/smoke-images.sh`.
2. Capture frontend, API, and worker image build results.
3. Capture API `/health` and `/ready` responses.
4. Capture worker no-op command output.

Tests:

- `sh deploy/cloud/smoke-images.sh`.
- Focused cloud deployment unit tests still pass.

### Phase 3: Local Compose Smoke

Steps:

1. Run `docker compose --env-file .env.example -f docker-compose.demo.yml up --build --wait --wait-timeout 120`.
2. Verify API, worker, frontend, MCP service, and sample agent health.
3. Run `sh deploy/local-demo-smoke.sh`.
4. Confirm Demo Lab baseline, reset, and scenario start from the composed API.

Tests:

- Compose up/down smoke succeeds.
- `sh deploy/local-demo-smoke.sh` succeeds.
- Local compose focused tests pass with localhost binding allowed.

### Phase 4: Pilot Scope Decision

Steps:

1. Reconfirm whether pilot readiness accepts SQLite-on-volume cloud preview.
2. If PostgreSQL is required, create a separate database runtime plan rather than mixing it into smoke verification.
3. Update `PILOT_READINESS.md` or the execution log with the accepted scope and evidence links.

Tests:

- Documentation reflects the exact runtime evidence gathered.

## Overall Validation

- Production images build and smoke successfully.
- Local compose stack starts, becomes healthy, resets Demo Lab, and starts a demo scenario.
- Cloud-preview limitations are explicit and accepted or split into a new implementation plan.

## Dependencies

- Docker daemon and registry/base-image access.
- Current backend and frontend validation should be green before smoke runs.

## Definition Of Done

- Demo delivery has runtime smoke evidence, not just static Dockerfile/config tests.
- Any remaining deployment limitation is documented as an explicit pilot-scope decision.
