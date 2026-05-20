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
    http_client: SyncGatewayHttpClient | httpx.Client | None = None,
    cache_tools: bool = False,
    cache_ttl_seconds: float = 300.0,
    event_hook: TelemetryEventHook | None = None,
    allow_insecure_http: bool = False,
    user_agent: str | None = None,
    discovery_max_retries: int = 2,
    discovery_retry_backoff_seconds: float = 0.2,
    discovery_retry_max_sleep_seconds: float = 5.0,
    discovery_retry_jitter_ratio: float = 0.2,
    invocation_max_retries: int = 2,
    invocation_retry_backoff_seconds: float = 0.2,
    invocation_retry_max_sleep_seconds: float = 5.0,
    invocation_retry_jitter_ratio: float = 0.2,
    allow_buffered_custom_http_client: bool = False,
    raise_event_hook_errors: bool = False,
)
```

Payloads must be JSON objects, fit within `max_payload_bytes`, and stay within
the SDK's fixed nesting-depth cap of 50 levels.

Methods:

- `call_tool(tool_name: str, payload: dict[str, Any], correlation_id: str | None = None, idempotency_key: str | None = None, traceparent: str | None = None, tracestate: str | None = None, baggage: str | None = None, runtime_session_id: str | None = None, runtime_run_id: str | None = None) -> ToolCallResult`
- `create_runtime_session(agent_id: str, environment_id: str, ring: int = 2, sponsor_user_id: str | None = None, metadata: Mapping[str, Any] | None = None, correlation_id: str | None = None, traceparent: str | None = None, tracestate: str | None = None, baggage: str | None = None) -> RuntimeSession`
- `get_runtime_session(session_id: str, environment_id: str, correlation_id: str | None = None) -> RuntimeSession`
- `list_runtime_session_runs(session_id: str, environment_id: str, correlation_id: str | None = None) -> list[RuntimeRun]`
- `list_runtime_checkpoints(session_id: str, environment_id: str, correlation_id: str | None = None) -> list[RuntimeCheckpointReference]`
- `stream_runtime_events(environment_id: str, event_type: str | None = None, last_event_id: str | None = None, limit: int = 100, runtime_session_id: str | None = None, runtime_run_id: str | None = None, correlation_id: str | None = None) -> list[RuntimeEvent]`
- `check_compatibility() -> GatewayCompatibility`
- `list_tools(status: Literal["active"] | None = None, owner_team: str | None = None, limit: int = 50, offset: int = 0) -> list[ToolDefinition]`
- `list_all_tools(owner_team: str | None = None, page_size: int = 200, max_total: int | None = 10000) -> list[ToolDefinition]`
- `get_tool(tool_name: str) -> ToolDefinition`
- `clear_tool_cache() -> None`
- `close() -> None`

### `AsyncOphanixToolGatewayClient`

Async client with the same constructor options and method names. `call_tool`,
the runtime session/run/checkpoint/event helpers, `check_compatibility`,
`list_tools`, `list_all_tools`, `get_tool`, `aclear_tool_cache`, and `close`
are awaitable. Prefer `await client.aclear_tool_cache()` in async runtimes so
cache mutation uses the async lock.

### `ToolGatewayClientConfig`

Reusable configuration accepted by `OphanixToolGatewayClient.from_config(...)`
and `AsyncOphanixToolGatewayClient.from_config(...)`. It includes timeout,
payload/response caps, cache settings, discovery retry settings, idempotent
invocation retry settings, custom client streaming policy, user agent, and
event-hook failure mode, compatibility enforcement, and raw success-response
retention. `ToolGatewayClientOptions` is an alias for the same type. `base_url`,
`token_provider`, `http_client`, and `event_hook` remain constructor inputs.

Recommended profile starting points:

- Controlled pilot: use defaults, keep discovery caching disabled, and pass
  `idempotency_key` for any invocation that may need retries.
- Stable internal worker: tune timeout and payload/response caps for the
  workload, enable short-lived discovery caching only when permission and tool
  contract churn is low, and keep `max_cache_entries` bounded.
- Strict tests: set discovery and invocation retry counts to `0`,
  `cache_tools=False`, and `raise_event_hook_errors=True`.

## Adapter Protocols

- `TokenProvider`: sync `get_token() -> str`.
- `AsyncTokenProvider`: sync or awaitable `get_token() -> str | Awaitable[str]`.
- `SyncGatewayHttpClient`: custom sync HTTP adapter with `stream()`, `get()`,
  `post()`, and `close()`.
- `AsyncGatewayHttpClient`: custom async HTTP adapter with `stream()`, `get()`,
  `post()`, and `aclose()`.

Buffered custom HTTP clients are rejected. `allow_buffered_custom_http_client`
is retained only as a constructor-compatibility field; response-size caps
require streaming support.

## Token Providers

- `EnvironmentTokenProvider(env_var: str = "OPHANIX_GATEWAY_TOKEN")`
- `StaticTokenProvider(token: str)`

Custom providers must expose `get_token()` and return the raw bearer token
without the `Bearer` prefix.

Token strings with the `Bearer ` prefix, whitespace, or unsupported characters
raise `ToolGatewayValidationError` before a network request is sent. Tokens must
be 4096 characters or fewer.

## Data Classes

- `ToolDefinition`: `id`, `name`, `display_name`, `description`, `owner_team`,
  `status`, `required_scope`, optional input/output schemas, and immutable raw
  response metadata.
- `ToolCallResult`: `request_id`, `correlation_id`, `tool_name`, `result`,
  `body`, `reason_code`, optional `decision`, and immutable raw response
  metadata. `body` unwraps the standard gateway execution envelope when present.
  `raw` omits the potentially sensitive `result` field unless
  `include_raw_response=True` is configured.
- `RuntimeSession`: Product Platform runtime session binding with
  organization, environment, agent, creator, ring, memory scope, thread ID,
  trace context, metadata, and raw response metadata.
- `RuntimeRun`: session run timeline with status, source, trace/correlation
  IDs, recovery state, metadata, timestamps, and `RuntimeRunStep` children.
- `RuntimeRunStep`: timeline step linked to runtime actions, saga steps,
  checkpoint IDs, policy decisions, trace spans, artifacts, and metadata.
- `RuntimeCheckpointReference`: checkpoint view derived from run steps with the
  checkpoint ID, run/session/step IDs, status, recovery state, and metadata.
- `RuntimeEvent`: typed audit/SSE event with actor, agent, resource, decision,
  severity, correlation/trace IDs, payload, and created timestamp.
- `GatewayCompatibility`: `compatible`, `sdk_version`,
  `expected_gateway_contract_version`, `gateway_contract_version`,
  `min_sdk_version`, `min_sdk_version_satisfied`, `incompatibility_reason`,
  gateway-published operational limits, idempotency metadata, pagination modes,
  and immutable raw response metadata.

`raw` fields are diagnostic snapshots rather than stable extension contracts.
Successful `ToolCallResult.raw` values may include the full agent-facing tool
response, so do not log them unless your application has already classified that
payload as safe. `ToolCallResult.decision` is a coarse agent-facing summary and
does not include internal policy IDs.

## Errors

- `ToolAuthenticationError`: gateway credential was missing, expired, revoked,
  or invalid.
- `ToolDeniedError`: gateway policy denied the authenticated call.
- `ToolGatewayError`: transport, gateway, upstream, response-size, malformed
  response, or other SDK-level failure.
- `ToolGatewayValidationError`: local configuration or caller input was invalid.
  This is a `ValueError` subclass.

All SDK errors expose `message`, `status_code`, `code`, `request_id`,
`correlation_id`, `retry_after_seconds`, and sanitized `response_body` where
available.

Sanitized `response_body` values redact common credential and PII-like keys:
`authorization`, `api_key`, `credential`, `password`, `secret`, `token`, `key`,
`email`, `phone`, `address`, and `ssn`.

## Event Hook Schema

| Event | Fields |
| --- | --- |
| `tool_call.start` | `tool_name`, `correlation_id`, `idempotent` |
| `tool_call.success` | `tool_name`, `request_id`, `correlation_id`, `reason_code`, `elapsed_ms` |
| `tool_call.denied` | `tool_name`, `status_code`, `elapsed_ms` |
| `tool_call.error` | `tool_name`, `status_code` or `code`, `elapsed_ms` |
| `tool_call.retry` | `tool_name`, `attempt`, `delay_seconds`, `status_code`, `code` |
| `tool_discovery.retry` | `attempt`, `delay_seconds`, `status_code` |

Invocation retries are gated by `idempotency_key`. Without a key, `call_tool`
does not retry transient failures because the SDK cannot prove that the upstream
operation is safe to repeat. With a key, retries are still limited to transport,
gateway availability/throttling, and `idempotency_in_progress` cases. Terminal
execution failures returned by the gateway, such as `upstream_error`,
`upstream_timeout`, `upstream_circuit_open`, and idempotency replays, are not
retried automatically because the gateway would replay the stored terminal
response for the same key instead of safely re-executing the upstream operation.
`idempotency_persistence_failed` is never retried automatically because it means
the upstream outcome may already have happened and must be reconciled before
issuing a new idempotency key.

`check_compatibility()` reports incompatible when the gateway contract version
does not match or when the gateway `min_sdk_version` is higher than the installed
SDK version.

## Compatibility And Deprecations

- `list_tools(status="active")` is accepted for compatibility and emits a
  `DeprecationWarning`. Gateway discovery is always active-only.
- `product_platform.tool_gateway` imports are compatibility shims for earlier
  internal callers through the `0.1.x` line. Prefer `ophanix_tool_gateway` for
  new code.
