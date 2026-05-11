# Tool Gateway SDK API Reference

This is the supported public surface for the `ophanix-tool-gateway-sdk` `0.x`
line.

## Clients

### `OphanixToolGatewayClient`

Synchronous client. Use as a context manager or call `close()`.

Constructor:

```python
OphanixToolGatewayClient(
    *,
    base_url: str,
    token_provider: TokenProvider,
    timeout_seconds: float = 5.0,
    max_payload_bytes: int = 1_000_000,
    max_response_bytes: int = 1_000_000,
    max_cache_entries: int = 256,
    http_client: httpx.Client | None = None,
    cache_tools: bool = False,
    cache_ttl_seconds: float = 300.0,
    event_hook: Callable[[Mapping[str, Any]], None] | None = None,
    allow_insecure_http: bool = False,
    user_agent: str | None = None,
    discovery_max_retries: int = 2,
    discovery_retry_backoff_seconds: float = 0.2,
    discovery_retry_max_sleep_seconds: float = 5.0,
    discovery_retry_jitter_ratio: float = 0.2,
)
```

Methods:

- `call_tool(tool_name: str, payload: dict[str, Any], correlation_id: str | None = None) -> ToolCallResult`
- `list_tools(owner_team: str | None = None, limit: int = 50, offset: int = 0) -> list[ToolDefinition]`
- `list_all_tools(owner_team: str | None = None, page_size: int = 200, max_total: int | None = None) -> list[ToolDefinition]`
- `get_tool(tool_name: str) -> ToolDefinition`
- `clear_tool_cache() -> None`
- `close() -> None`

### `AsyncOphanixToolGatewayClient`

Async client with the same constructor options and method names. `call_tool`,
`list_tools`, `list_all_tools`, `get_tool`, and `close` are awaitable.

## Token Providers

- `EnvironmentTokenProvider(env_var: str = "OPHANIX_GATEWAY_TOKEN")`
- `StaticTokenProvider(token: str)`

Custom providers must expose `get_token()` and return the raw bearer token
without the `Bearer` prefix.

## Data Classes

- `ToolDefinition`: `id`, `name`, `display_name`, `description`, `owner_team`,
  `status`, `required_scope`, optional input/output schemas, and immutable raw
  response metadata.
- `ToolCallResult`: `request_id`, `correlation_id`, `tool_name`, `result`,
  `reason_code`, optional `decision`, and immutable raw response metadata.

## Errors

- `ToolAuthenticationError`: gateway credential was missing, expired, revoked,
  or invalid.
- `ToolDeniedError`: gateway policy denied the authenticated call.
- `ToolGatewayError`: transport, gateway, upstream, response-size, malformed
  response, or other SDK-level failure.

All SDK errors expose `message`, `status_code`, `code`, `request_id`,
`correlation_id`, `retry_after_seconds`, and sanitized `response_body` where
available.
