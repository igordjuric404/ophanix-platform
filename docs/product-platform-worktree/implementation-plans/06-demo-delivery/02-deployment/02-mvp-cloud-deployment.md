# MVP Cloud Deployment

## Feature Scope

Define the first sellable cloud deployment architecture for pilots: containerized web/API/worker, managed PostgreSQL, managed Redis or queue, object storage, identity provider, secret manager, TLS, observability, backups, and migrations.

## Existing Repo Assets To Reuse

- Local compose once available.
- Existing package Dockerfiles and deployment examples as references.
- Observability integrations from Agent SRE.

## Out Of Scope

- Full enterprise Kubernetes/Helm.
- Air-gapped deployment.
- Multi-region active-active.

## Data Model

No application schema changes. Add deployment configuration and migration execution model.

## API Surface

No new feature API. Ensure existing health/readiness endpoints work behind cloud load balancer.

## UI Surface

Settings -> System Health should show deployment dependency status.

## Implementation Phases

### Phase 1: Container Images

Steps:

1. Define production Dockerfile for frontend.
2. Define production Dockerfile for API.
3. Define production Dockerfile for worker.
4. Add image build workflow.

Tests:

- Build all images locally.
- Run API image with test database URL.
- Run worker image and execute no-op job.

### Phase 2: Managed Services Configuration

Steps:

1. Define required environment variables.
2. Connect managed PostgreSQL.
3. Connect managed Redis or queue.
4. Connect object storage.
5. Connect secret manager.

Tests:

- API readiness fails when required service missing.
- API readiness passes when services configured.
- Artifact upload/download works against object storage.

### Phase 3: Auth, TLS, And Network

Steps:

1. Configure identity provider for user login.
2. Configure TLS termination.
3. Restrict internal service network access.
4. Configure API CORS for frontend domain.

Tests:

- Login works with IdP test user.
- Unauthenticated API calls are rejected.
- TLS endpoint passes basic browser validation.
- CORS allows only configured frontend domain.

### Phase 4: Migrations, Backups, Observability

Steps:

1. Add migration execution step in deployment pipeline.
2. Configure database backups.
3. Configure logs, metrics, and traces.
4. Add alert for unhealthy API/worker.

Tests:

- Migration runs once per deploy.
- Backup restore is tested in staging.
- Health alert triggers on stopped worker.
- Logs include request id and correlation id.

### Phase 5: Pilot Readiness Checklist

Steps:

1. Define tenant provisioning process.
2. Define support access and break-glass policy.
3. Define data retention defaults.
4. Define rollback procedure.

Tests:

- Provision a pilot tenant in staging.
- Run smoke demo.
- Execute rollback drill.
- Verify retention settings.

## Overall Validation

- Deploy MVP stack to staging cloud.
- Log in through IdP.
- Run a reduced demo scenario.
- Verify persistence after restart.
- Verify backups and observability.

## Dependencies

- Local demo compose.
- Auth/RBAC.
- Artifact store.
- Provider secrets.
- Event pipeline.

## Definition Of Done

- The platform can be piloted outside a developer laptop with durable storage, auth, TLS, observability, and backups.
