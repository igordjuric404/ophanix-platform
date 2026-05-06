# Tool Invocation Endpoint

## Feature Scope

Create the external HTTP endpoint that agents call instead of calling protected business APIs directly. This endpoint authenticates the agent, validates the requested tool and payload, asks for a policy decision, and returns either a denied response or a forwarding result from a pluggable executor.

## Atomic Boundary

This plan is complete when `POST /api/v1/tools/{tool_name}/invoke` can authenticate, validate, decide, and return a structured allow or deny response using a mocked executor. It is independently testable without real upstream APIs.

## Objectives

- Provide the direct HTTP integration path from the problem statement.
- Keep the runtime request/response contract stable for SDK and non-SDK callers.
- Ensure denied calls never reach the upstream executor.
- Attach request id and correlation id to every response.

## Existing Repo Assets To Reuse

- Product API shell route conventions.
- Gateway Token Verification.
- Tool Contract Registry.
- Tool Policy Decision service.
- Existing MCP gateway request ideas from `packages/agent-os/src/agent_os/mcp_gateway.py`.

## Out Of Scope

- Real upstream HTTP forwarding.
- Response redaction.
- SDK packaging.
- Human approval workflow.

## Data Model

No new primary tables beyond the decision and audit tables created by related plans.

Request model:

- `tool_name`: path parameter.
- `payload`: object.
- `correlation_id`: optional header or body field.
- `idempotency_key`: optional header.

Response model:

- `request_id`
- `correlation_id`
- `tool_name`
- `decision`
- `reason_code`
- `result`
- `error`

## API Surface

Implement:

- `POST /api/v1/tools/{tool_name}/invoke`

Response behavior:

- `200` for allowed invocation with executor result.
- `403` for authenticated but denied invocation.
- `401` for missing or invalid credential.
- `404` for tools that should not be disclosed to the caller.
- `422` for invalid payload schema.

## UI Surface

No dedicated UI. The endpoint produces decision and audit records consumed by later UI plans.

## Implementation Phases

### Phase 1: Route Contract

Steps:

1. Add request and response models.
2. Add route under `/api/v1/tools/{tool_name}/invoke`.
3. Require bearer token verification.
4. Propagate or create request id and correlation id.

Tests:

- API test missing token returns `401`.
- API test valid token reaches route handler.
- API test correlation id is preserved.
- API test response includes request id.

### Phase 2: Payload Validation

Steps:

1. Resolve active tool by name.
2. Validate request payload against the tool input schema.
3. Return standard validation errors for schema mismatch.
4. Ensure validation happens before policy execution where safe and useful.

Tests:

- API test valid payload is accepted.
- API test missing required payload field returns `422`.
- API test unknown tool returns safe error response.

### Phase 3: Decision And Mock Execution

Steps:

1. Call the Tool Policy Decision service.
2. Return `403` for denied decisions.
3. Use a mock or in-memory executor for allowed decisions.
4. Ensure denied decisions never call the executor.

Tests:

- API test allowed decision calls executor once.
- API test denied decision does not call executor.
- API test denial response includes reason code.
- Integration test decision record is created for allowed and denied calls.

## Independent Verification

- Seed an active agent, active tool, and permission.
- Call the endpoint with a valid bearer token and valid payload.
- Confirm the mock executor result is returned.
- Revoke the permission and confirm the endpoint returns `403` and does not execute.

## Dependencies

- Gateway Token Verification.
- Tool Contract Registry.
- Tool Policy Decision.
- Product API shell.

## Definition Of Done

- External agents have a stable HTTP invocation endpoint.
- Authentication, schema validation, and policy decision run in order.
- Denied calls fail before execution.
- The endpoint can be used by the SDK and direct HTTP examples.

