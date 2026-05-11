# Tool Gateway SDK Migration Notes

## Preferred Import Path

Use the standalone package import for new code:

```python
from ophanix_tool_gateway import OphanixToolGatewayClient
```

Earlier internal callers may still import from `product_platform.tool_gateway`.
That path is a compatibility shim and should not be used for new integrations.

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

## Custom HTTP Clients

Custom injected HTTP clients must expose `stream()` by default so the SDK can
enforce response-size limits before materializing a body. Use
`allow_buffered_custom_http_client=True` only when the injected client already
enforces equivalent limits.
