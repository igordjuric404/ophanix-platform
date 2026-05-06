# Upstream Target Health

## Feature Scope

Register the protected business API targets that tools route to and expose their health state. This plan lets operators define where a tool goes, how the gateway reaches it, and whether the target is available before runtime forwarding is implemented.

## Atomic Boundary

This plan is complete when a tool can be linked to a target, target health can be checked, and unhealthy targets are visible through API responses. It can be tested with mocked HTTP health probes.

## Objectives

- Keep upstream URLs out of unstructured tool metadata.
- Support different targets per organization and environment.
- Give the runtime a single route resolution record for each tool.
- Detect unhealthy targets before production traffic depends on them.

## Existing Repo Assets To Reuse

- Dependency health patterns from `packages/product-platform/src/product_platform/api/dependencies.py`.
- Provider health-check ideas from ecosystem operations plans.
- Product DB repository conventions.

## Out Of Scope

- Actual tool invocation forwarding.
- Secret injection for upstream authentication.
- Runtime retries and timeouts beyond health probe settings.
- Provider secrets management.

## Data Model

Tables:

- `tool_upstream_targets`: id, organization_id, environment_id, tool_id, base_url, path_template, method, auth_mode, timeout_ms, status, created_at, updated_at.
- `tool_upstream_health_checks`: id, target_id, health_url, expected_status, interval_seconds, last_status, last_checked_at, last_error, enabled.

Status values:

- `configured`
- `healthy`
- `degraded`
- `unhealthy`
- `disabled`

## API Surface

Implement:

- `POST /api/v1/tools/{id}/upstream-target`
- `GET /api/v1/tools/{id}/upstream-target`
- `PATCH /api/v1/tool-upstream-targets/{id}`
- `POST /api/v1/tool-upstream-targets/{id}/check-health`
- `GET /api/v1/tool-upstream-targets/{id}/health`

## UI Surface

Tool Gateway -> Tools -> Upstream:

- Base URL and path template.
- HTTP method and timeout.
- Authentication mode.
- Last health check status and error.
- Manual "check now" action.

## Implementation Phases

### Phase 1: Target Store

Steps:

1. Add target and health-check tables.
2. Add repository methods to create, fetch, update, and resolve a target by tool.
3. Ensure each active tool has at most one active target per environment.
4. Validate supported methods and URL shape.

Tests:

- Integration test creates a target for a tool.
- Integration test duplicate active target is rejected.
- Unit test invalid URL is rejected.
- Repository test resolves target by tool name.

### Phase 2: Health Probe Adapter

Steps:

1. Add a health checker that calls the configured `health_url`.
2. Respect timeout and expected status.
3. Persist last status, last checked time, and last error.
4. Fail closed when the health check raises an exception.

Tests:

- Unit test healthy response marks target healthy.
- Unit test unexpected status marks target degraded.
- Unit test timeout marks target unhealthy.
- Unit test exception stores a useful error summary.

### Phase 3: API Routes

Steps:

1. Add target request and response models.
2. Implement create, get, patch, manual health check, and health status routes.
3. Require appropriate operator permissions for target writes.
4. Emit audit events when target settings change.

Tests:

- API test creates target for an existing tool.
- API test cannot create target for disabled tool.
- API test manual health check persists result.
- API test target writes require the expected permission.

## Independent Verification

- Register a tool and target with a mocked healthy endpoint.
- Run a manual health check and confirm `healthy`.
- Change the mock to return `500` and confirm the target records `degraded` or `unhealthy`.
- Confirm the tool detail API includes current target health.

## Dependencies

- Tool Contract Registry.
- Product API shell.
- Auth, tenancy, and RBAC.

## Definition Of Done

- Tools can be mapped to upstream HTTP targets.
- Target health is visible and persisted.
- Runtime plans can resolve a target without parsing free-form metadata.

