# Product API Shell

## Feature Scope

Create the central FastAPI control plane that all product UI and agents call. This feature establishes the service skeleton, routing conventions, health checks, config loading, dependency injection, request IDs, error format, and OpenAPI generation. It does not implement specific agent, policy, MCP, trust, or compliance business logic.

## Existing Repo Assets To Reuse

- FastAPI style from `packages/agent-os/src/agent_os/server/app.py`.
- FastAPI style from `packages/agent-hypervisor/src/hypervisor/api/server.py`.
- FastAPI style from `packages/agent-sre/src/agent_sre/api/server.py`.
- Existing package APIs should be wrapped later through adapters, not copied into this shell.

## Out Of Scope

- User authentication and RBAC. Covered by `02-auth-rbac-tenancy.md`.
- Database schema. Covered by `03-canonical-database-schema.md`.
- Feature-specific routes. Covered by their own plans.

## Data Model

No persistent tables are required in this feature. Define shared request metadata types only:

- `RequestContext`: request id, correlation id, organization id, environment id, user id, actor type.
- `ApiError`: code, message, details, request id.
- `HealthStatus`: status, version, dependencies, uptime.

## API Surface

Implement:

- `GET /health`
- `GET /ready`
- `GET /version`
- `GET /api/openapi.json`
- `GET /api/v1/system/config`
- `GET /api/v1/system/dependencies`

All feature routes should be mounted under `/api/v1`.

## UI Surface

No dedicated UI beyond system health consumers. The frontend shell should use `/ready`, `/version`, and `/system/dependencies` for its global status indicator.

## Implementation Phases

### Phase 1: Service Skeleton

Steps:

1. Create a product API package or service folder following the repo's Python packaging convention.
2. Add a FastAPI app factory.
3. Add settings loading from environment variables.
4. Add CORS configuration for local frontend development.
5. Add `/health`, `/ready`, and `/version`.

Tests:

- Unit test app factory returns a FastAPI instance.
- API test verifies `/health` returns `200`.
- API test verifies `/version` includes app version and build metadata.

### Phase 2: Request Context And Errors

Steps:

1. Add middleware that creates or propagates `X-Request-ID`.
2. Read `X-Correlation-ID` if provided; otherwise use request id.
3. Add structured error handlers for validation errors and unhandled exceptions.
4. Ensure every JSON error response includes `request_id`.

Tests:

- API test verifies supplied `X-Request-ID` is echoed.
- API test verifies missing `X-Request-ID` creates one.
- API test verifies validation errors use standard error format.

### Phase 3: Dependency Registry

Steps:

1. Define a dependency health-check interface.
2. Register placeholder checks for database, Redis, worker, event store, and model provider.
3. Return dependency status from `/ready` and `/system/dependencies`.
4. Mark `/ready` unhealthy when required dependencies fail.

Tests:

- Unit test dependency checker handles healthy and unhealthy dependencies.
- API test verifies `/ready` status changes when a required dependency is unhealthy.
- API test verifies optional dependencies do not fail readiness.

## Overall Validation

- Start the API locally.
- Confirm OpenAPI renders.
- Confirm request IDs are present in successful and failing responses.
- Confirm health, readiness, version, and dependency endpoints work without feature modules installed.

## Dependencies

- FastAPI.
- Uvicorn or equivalent ASGI server.
- Pydantic settings.

## Definition Of Done

- A single control plane API process can start.
- It exposes stable system endpoints.
- It has consistent error and request metadata.
- Later feature routers can be added without changing the shell contract.
