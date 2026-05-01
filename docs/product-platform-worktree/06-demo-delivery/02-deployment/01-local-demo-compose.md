# Local Demo Compose

## Feature Scope

Package the demo platform into a local Docker Compose setup with web UI, control plane API, worker, PostgreSQL, Redis, optional OTel/Prometheus/Grafana, sample MCP server, and sample agents.

## Existing Repo Assets To Reuse

- Docker Compose examples under `packages/agent-mesh/examples/docker-compose`, `packages/agent-hypervisor/examples/docker-compose`, and Agent OS examples.
- Existing demo apps and sample agents as references.

## Out Of Scope

- Production hardening.
- Kubernetes deployment.

## Data Model

No product schema changes. Compose must run migrations and seed demo data.

## API Surface

No new product API beyond health and prerequisites endpoints.

## UI Surface

Demo Lab -> Prerequisites should reflect compose service health.

## Implementation Phases

### Phase 1: Compose Services

Steps:

1. Define services: frontend, api, worker, postgres, redis.
2. Add health checks for each service.
3. Mount repo or build local images according to project convention.
4. Configure environment variables through `.env.example`.

Tests:

- Compose config validates.
- API health returns healthy with database and Redis.
- Worker starts and can execute no-op job.

### Phase 2: Demo Services

Steps:

1. Add local MCP server service.
2. Add sample support, refund, and research agent services or runner commands.
3. Add optional OPA service.
4. Add optional OTel/Prometheus/Grafana services.

Tests:

- MCP server health check passes.
- Sample agent can heartbeat to API.
- Optional OPA health is detected when enabled.

### Phase 3: Migrations And Seed

Steps:

1. Add startup command or separate init service for migrations.
2. Add seed command for demo org, admin user, policies, scenario, MCP registration.
3. Ensure repeated compose up does not duplicate seed data.

Tests:

- Fresh volume migration succeeds.
- Seed runs idempotently.
- Demo Lab baseline status is healthy after startup.

### Phase 4: Documentation

Steps:

1. Add README with commands to start, stop, reset, view logs.
2. Document required model provider key and optional tokens.
3. Document expected demo URL and login.
4. Document troubleshooting for ports and missing credentials.

Tests:

- Follow README from clean checkout.
- Verify URLs and commands are accurate.
- Verify missing optional credentials produce degraded, not failed, status.

## Overall Validation

- From clean machine with Docker, start compose stack.
- Open web UI.
- Run Demo Lab scenario.
- Reset environment.

## Dependencies

- Product API.
- Frontend shell.
- Worker.
- Scenario runner.
- Provider health checks.

## Definition Of Done

- A demo can be started locally with a predictable command and uses live product state.
