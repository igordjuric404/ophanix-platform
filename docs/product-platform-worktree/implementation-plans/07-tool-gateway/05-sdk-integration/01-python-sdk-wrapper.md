# Python SDK Wrapper

## Feature Scope

Create a small optional Python SDK wrapper for external agent runtimes. The SDK calls the Tool Gateway HTTP endpoint, attaches credentials, forwards correlation metadata, and returns a typed result to the agent code.

## Atomic Boundary

This plan is complete when Python callers can use `client.call_tool("claims.lookup", payload)` against a mocked gateway. It is independently testable with HTTP mocks and does not require real upstream tools.

## Objectives

- Make gateway adoption easy for Python-based agents.
- Keep the SDK thin so direct HTTP remains the source of truth.
- Support bearer token providers instead of hard-coded tokens.
- Surface denied responses as typed gateway errors.

## Existing Repo Assets To Reuse

- Existing Python packaging patterns in `packages/product-platform`.
- Gateway invocation endpoint contract.
- Credential handling concepts from agent mesh.
- Existing test conventions in product platform tests.

## Out Of Scope

- SDKs for TypeScript, Java, or other languages.
- Credential issuance from the SDK.
- Agent orchestration.
- Tool schema discovery beyond optional helper methods.

## Data Model

No database tables.

SDK types:

- `OphanixToolGatewayClient`
- `TokenProvider`
- `ToolCallResult`
- `ToolGatewayError`
- `ToolDeniedError`

## API Surface

SDK methods:

- `call_tool(tool_name: str, payload: dict, correlation_id: str | None = None) -> ToolCallResult`
- `get_tool(tool_name: str) -> ToolDefinition`
- `list_tools() -> list[ToolDefinition]`

HTTP endpoints consumed:

- `POST /api/v1/tools/{tool_name}/invoke`
- `GET /api/v1/tools`

## UI Surface

No UI.

## Implementation Phases

### Phase 1: Client Skeleton

Steps:

1. Add SDK package module in the product platform or a dedicated SDK package.
2. Define client configuration with base URL, timeout, and token provider.
3. Add typed result and error classes.
4. Add basic unit tests for configuration validation.

Tests:

- Unit test client requires base URL.
- Unit test timeout defaults are applied.
- Unit test static token provider returns bearer token.

### Phase 2: Tool Call Method

Steps:

1. Implement `call_tool`.
2. Attach bearer token from token provider.
3. Send correlation id header when provided.
4. Map `403` responses to `ToolDeniedError`.
5. Map gateway and upstream failures to typed errors.

Tests:

- Unit test successful call returns result.
- Unit test denied response raises `ToolDeniedError` with reason code.
- Unit test token provider is called for each request.
- Unit test correlation id is sent.

### Phase 3: Tool Discovery Helpers

Steps:

1. Implement `list_tools`.
2. Implement `get_tool` by name or id according to API support.
3. Cache only when explicitly configured.
4. Keep discovery helpers optional for minimal runtime callers.

Tests:

- Unit test list tools maps response to typed definitions.
- Unit test get tool handles not found.
- Unit test cache is disabled by default.

## Independent Verification

- Run SDK tests against an HTTP mock.
- Configure a mock `POST /api/v1/tools/claims.lookup/invoke` to return allow.
- Confirm `call_tool("claims.lookup", {"claim_id": "c-1"})` returns a typed result.
- Configure the mock to return `403` and confirm the SDK raises `ToolDeniedError`.

## Dependencies

- Tool Invocation Endpoint.
- Tool Contract Registry API.

## Definition Of Done

- Python agents can call the gateway with a small typed client.
- Denied responses are easy for agent code to handle.
- The SDK does not bypass or duplicate gateway policy logic.

