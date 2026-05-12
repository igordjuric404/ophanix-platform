# Tool Gateway SDK Migration Notes

## Preferred Import Path

Use the standalone package import for new code:

```python
from ophanix_tool_gateway import OphanixToolGatewayClient
```

Earlier internal callers may still import from `product_platform.tool_gateway`.
That path is a compatibility shim and should not be used for new integrations.
The shim is supported through the `0.1.x` SDK line. Removing it requires a
future migration note, changelog entry, and at least one minor pre-1.0 release
of notice.

## Deprecated `list_tools(status=...)`

Gateway discovery is active-only. `list_tools(status="active")` remains accepted
for compatibility and emits `DeprecationWarning`. Remove the `status` argument:

```python
tools = client.list_tools(owner_team="claims-platform")
```

## Token Provider Values

Token providers must return the raw token only. If existing code returns
`Bearer <token>`, change it to return `<token>`. The SDK adds the authorization
scheme itself and now rejects prefixed or whitespace-containing token values
before sending a network request.
Tokens must also be 4096 characters or fewer and use only the gateway token
grammar documented in the README.

## Client Configuration

New code that creates several sync or async clients can use
`ToolGatewayClientConfig` and `from_config(...)` instead of repeating every
constructor option. Existing constructor calls remain supported.

## Custom HTTP Clients

Custom injected HTTP clients must expose `stream()` so the SDK can enforce
response-size limits before materializing a body. Buffered injected clients are
now rejected even if `allow_buffered_custom_http_client=True` is supplied; that
field remains only for constructor compatibility.

The SDK now exports `SyncGatewayHttpClient` and `AsyncGatewayHttpClient`
Protocols. Existing adapters do not need code changes if they already provide
the required methods, but type-checking integrations should prefer those
Protocols over ad hoc `Any` annotations.

## Discovery And Compatibility

`list_all_tools()` now defaults to `max_total=10000` to avoid accidental
unbounded scans and prefers signed cursor pagination when the gateway supports
it. Pass `max_total=None` only when an integration intentionally accepts an
unbounded catalog scan.

`check_compatibility()` now marks the SDK incompatible when the gateway
advertises a `min_sdk_version` higher than the installed SDK version. Check
`GatewayCompatibility.incompatibility_reason` before starting long-running
workers.
