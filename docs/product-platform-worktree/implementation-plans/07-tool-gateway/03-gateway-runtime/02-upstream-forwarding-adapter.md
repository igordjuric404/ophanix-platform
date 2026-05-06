# Upstream Forwarding Adapter

## Feature Scope

Implement the adapter that forwards an allowed tool invocation to its registered upstream business API. This plan replaces the invocation endpoint's mock executor with an HTTP executor that resolves the tool target, sends the request, and returns the upstream response metadata.

## Atomic Boundary

This plan is complete when an allowed invocation can be forwarded to a mocked HTTP upstream with configured method, path, timeout, and correlation headers. It is independently testable with an HTTP mock server.

## Objectives

- Keep upstream routing behind a small adapter interface.
- Preserve request and correlation metadata across the gateway boundary.
- Enforce timeout and response size limits.
- Return structured upstream errors without leaking internal secrets.

## Existing Repo Assets To Reuse

- Upstream Target Health.
- Product API dependency injection patterns.
- Any existing HTTP client wrapper used by the product platform.
- Credential redaction helpers from Agent OS where useful.

## Out Of Scope

- Upstream secret storage and rotation.
- Response schema validation and redaction.
- Human approval workflow.
- Streaming responses.

## Data Model

No new primary tables are required.

Use:

- `tool_upstream_targets`
- `tool_upstream_health_checks`
- `tool_policy_decisions`
- audit records from runtime plans.

## API Surface

No new public routes.

The adapter is used by:

- `POST /api/v1/tools/{tool_name}/invoke`

Internal interface:

- `execute_tool_call(tool, target, payload, context) -> ToolExecutionResult`

## UI Surface

No dedicated UI. Execution status is shown through audit and decision feed plans.

## Implementation Phases

### Phase 1: Executor Interface

Steps:

1. Define `ToolExecutionResult` with status, body, headers summary, latency, and error fields.
2. Define an executor interface so tests can swap mock and HTTP executors.
3. Wire the invocation endpoint to use the configured executor.
4. Preserve existing denial behavior.

Tests:

- Unit test mock executor result maps to invocation response.
- API test denied calls still skip executor.
- Unit test executor errors map to a controlled gateway error.

### Phase 2: Target Resolution

Steps:

1. Resolve the active upstream target for the tool and environment.
2. Reject execution when no active target exists.
3. Optionally reject execution when target status is unhealthy if fail-closed mode is enabled.
4. Build the upstream URL from base URL and path template.

Tests:

- Unit test target URL is built correctly.
- Unit test missing target returns controlled error.
- Unit test unhealthy target is blocked when fail-closed is enabled.
- Integration test environment-specific target is selected.

### Phase 3: HTTP Forwarding

Steps:

1. Forward payload using configured HTTP method.
2. Add request id and correlation id headers.
3. Apply configured timeout.
4. Capture upstream status, latency, and body.
5. Normalize timeout and connection errors.

Tests:

- Integration test successful upstream call returns body.
- Integration test request id and correlation id are forwarded.
- Integration test timeout returns gateway timeout error.
- Integration test upstream `500` is returned as structured execution failure.

## Independent Verification

- Configure a tool target pointing at a local mock HTTP server.
- Call the invocation endpoint with a valid token and payload.
- Confirm the mock server receives the expected method, path, body, and headers.
- Stop the mock server and confirm the gateway returns a controlled error.

## Dependencies

- Tool Invocation Endpoint.
- Upstream Target Health.
- Tool Policy Decision.

## Definition Of Done

- Allowed tool calls can be forwarded to registered upstream HTTP APIs.
- Routing uses target records, not hard-coded URLs.
- Timeouts and upstream failures return consistent gateway errors.
- Correlation metadata reaches the upstream service.

