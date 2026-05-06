# Tool Contract Registry

## Feature Scope

Create the product registry for callable tools. A tool is a named contract with an input schema, optional output schema, required scope, owner, lifecycle status, and a link to an upstream target. This plan only defines and manages tool metadata; it does not execute calls.

## Atomic Boundary

This plan is complete when tools can be created, listed, updated, disabled, and validated as contracts. It is independently testable with repository and API tests using seeded tool definitions.

## Objectives

- Treat every callable API as a first-class product resource.
- Give policy and gateway code a stable lookup key such as `claims.lookup`.
- Validate input and output schemas before the runtime uses a tool.
- Support disabled tools so operators can stop new invocations without deleting history.

## Existing Repo Assets To Reuse

- Product API conventions from `packages/product-platform/src/product_platform/api/app.py`.
- Repository patterns from `packages/product-platform/src/product_platform/db/repositories.py`.
- Existing MCP tool registry tests as a reference for shape and status filtering.
- Policy and audit event conventions from previous platform foundation plans.

## Out Of Scope

- Gateway execution.
- Agent-to-tool permission assignment.
- Runtime policy decisions.
- UI beyond any minimal list/detail endpoint consumers.

## Data Model

Tables:

- `tool_definitions`: id, organization_id, environment_id, name, display_name, description, owner_team, status, required_scope, input_schema_json, output_schema_json, created_by, created_at, updated_at.
- `tool_definition_versions`: id, tool_id, version, input_schema_json, output_schema_json, required_scope, change_summary, created_by, created_at.

Status values:

- `draft`
- `active`
- `disabled`
- `retired`

## API Surface

Implement:

- `POST /api/v1/tools`
- `GET /api/v1/tools`
- `GET /api/v1/tools/{id}`
- `PATCH /api/v1/tools/{id}`
- `POST /api/v1/tools/{id}/activate`
- `POST /api/v1/tools/{id}/disable`
- `GET /api/v1/tools/{id}/versions`

## UI Surface

Tool Gateway -> Tools:

- Tool table with name, owner, required scope, status, and updated time.
- Tool detail panel showing schema, version history, and upstream target link.

## Implementation Phases

### Phase 1: Registry Store

Steps:

1. Create tables for tool definitions and tool definition versions.
2. Add a repository for tool CRUD and name lookup by organization and environment.
3. Enforce unique active tool names per organization and environment.
4. Save an initial version when a tool is created.

Tests:

- Integration test creates a tool definition.
- Integration test duplicate name in the same organization and environment is rejected.
- Integration test same name in a different environment is allowed.
- Repository test filters by status.

### Phase 2: Schema Validation

Steps:

1. Validate `input_schema_json` is valid JSON Schema.
2. Validate `output_schema_json` when provided.
3. Reject activation when the input schema is missing or invalid.
4. Store schema validation errors in the API error response.

Tests:

- Unit test valid JSON Schema is accepted.
- Unit test invalid JSON Schema is rejected with a clear error.
- API test activation fails when schema is invalid.

### Phase 3: API Routes

Steps:

1. Add tool registry request and response models.
2. Implement create, list, get, patch, activate, disable, and version list routes.
3. Add organization and environment scoping through existing request context.
4. Emit audit events for create, update, activate, disable, and retire actions.

Tests:

- API test creates and retrieves a tool.
- API test list supports status and owner filters.
- API test patch creates a new version when schema or required scope changes.
- Integration test audit events are emitted for lifecycle changes.

## Independent Verification

- Seed one draft tool and one active tool.
- Confirm listing returns both with status filters.
- Confirm invalid schemas cannot be activated.
- Confirm disabling an active tool changes its status without removing version history.

## Dependencies

- Product API shell.
- Canonical database schema.
- Auth, tenancy, and RBAC.
- Event audit pipeline.

## Definition Of Done

- Tool definitions are persisted and versioned.
- Tool schemas are validated before activation.
- Tool lifecycle changes are auditable.
- Other gateway plans can resolve an active tool by name.

