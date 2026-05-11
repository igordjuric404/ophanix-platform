# Ophanix Product Platform

FastAPI control plane and static application shell for the productized Ophanix governance platform.

## One-command Startup

Run the local platform without manual migrations, seeding, or server setup:

```bash
./start.sh
```

The script starts the API, worker loop, sample MCP/agent services, SQLite migrations/seed, and a local frontend proxy.

Open `http://127.0.0.1:3000` and sign in with `admin@example.com`.

To run the Docker Compose demo stack instead:

```bash
./start.sh --docker
```

## Local API

```bash
python3 -m product_platform.cli serve --host 127.0.0.1 --port 8088
```

The legacy shorthand still works because omitting a subcommand starts the API:

```bash
python3 -m product_platform.cli --host 127.0.0.1 --port 8088
```

## Database Migrations

Local database migrations use the standard library SQLite driver. Set `OPHANIX_DATABASE_URL` to a `sqlite:///...` URL or use the default `sqlite:///ophanix_product.db`.

```bash
PYTHONPATH=src OPHANIX_DATABASE_URL=sqlite:///ophanix_product.db python3 -m product_platform.cli db migrate
PYTHONPATH=src OPHANIX_DATABASE_URL=sqlite:///ophanix_product.db python3 -m product_platform.cli db rollback
PYTHONPATH=src OPHANIX_DATABASE_URL=sqlite:///ophanix_product.db python3 -m product_platform.cli db seed
PYTHONPATH=src OPHANIX_DATABASE_URL=sqlite:///ophanix_product.db python3 -m product_platform.cli db reset-demo
```

## Tool Gateway Python SDK

Python agents can call governed tools through the lightweight `ophanix_tool_gateway`
SDK package. Existing internal imports from `product_platform.tool_gateway` continue
to work as compatibility exports:

```python
from ophanix_tool_gateway import (
    AsyncOphanixToolGatewayClient,
    EnvironmentTokenProvider,
    OphanixToolGatewayClient,
    ToolAuthenticationError,
    ToolDeniedError,
    ToolGatewayError,
)

with OphanixToolGatewayClient(
    base_url="https://gateway.example.com",
    token_provider=EnvironmentTokenProvider("OPHANIX_GATEWAY_TOKEN"),
) as client:
    try:
        tools = client.list_all_tools()
        result = client.call_tool("claims.lookup", {"claim_id": "claim_123"})
    except ToolDeniedError as exc:
        print(f"Denied by gateway policy: {exc.reason_code}")
    except ToolAuthenticationError:
        print("Gateway token was rejected")
    except ToolGatewayError as exc:
        print(f"Gateway call failed: {exc.code or exc.status_code}")
    else:
        print([tool.name for tool in tools])
        print(result.result)
```

Gateway tokens are issued for a specific agent, organization, environment, scope, and tool resource. Keep them in environment variables or a runtime secret store rather than application source. Production tokens must come from the Product Platform credential issuance flow or an equivalent cryptographically random issuer; local fixture tokens are not suitable for production. Use HTTPS for non-local SDK gateway URLs. Plain HTTP SDK gateway URLs are accepted for localhost development only; non-local HTTP requires the explicit `allow_insecure_http=True` opt-in.

`list_tools()`, `list_all_tools()`, and `get_tool()` use the gateway-authenticated discovery route and only return active tools callable by the configured agent credential. Discovery requests retry transient gateway failures by default; tool invocations are not retried automatically because the server contract does not yet provide idempotency keys for mutating calls.

Use `AsyncOphanixToolGatewayClient` in async agent runtimes; it mirrors the synchronous API with `await client.call_tool(...)`, `await client.list_tools(...)`, `await client.list_all_tools(...)`, and `await client.get_tool(...)`.

The SDK validates payloads as strict JSON objects, rejects non-finite numbers and non-string object keys, applies a configurable `max_payload_bytes` cap, adds an SDK `User-Agent`, redacts sensitive fields from exception diagnostic bodies, partitions opt-in discovery caches by credential fingerprint, expires cached discovery with `cache_ttl_seconds`, and keeps static tokens out of generated `repr()` output. Optional SDK telemetry hooks receive immutable token-free metadata only.

Server-side Tool Gateway runtime paths enforce bearer authentication, an explicit runtime-route allowlist, a configurable request body cap (`OPHANIX_TOOL_GATEWAY_MAX_BODY_BYTES`, default `1000000`), a configurable upstream response cap (`OPHANIX_TOOL_GATEWAY_MAX_UPSTREAM_RESPONSE_BYTES`, default `1000000`), and a bounded in-process rate limit (`OPHANIX_TOOL_GATEWAY_RATE_LIMIT_MAX_REQUESTS` per `OPHANIX_TOOL_GATEWAY_RATE_LIMIT_WINDOW_SECONDS`, capped by `OPHANIX_TOOL_GATEWAY_RATE_LIMIT_MAX_KEYS`). Production deployments should still enforce global edge rate limits and request-size limits at the ingress layer.

Upstream targets currently support `auth_mode="none"` only. Secret-backed upstream authentication must be implemented before registering bearer, API-key, or OAuth upstream targets. Upstream base URLs must use HTTPS and reject credentials, query strings, fragments, metadata hosts, loopback addresses, private/link-local/reserved IP literals, and hostnames that resolve to forbidden addresses during validation. Keep egress firewall rules in place as the final SSRF boundary.

Production app startup fails when `OPHANIX_SESSION_SECRET` is left at the development default, development login is explicitly enabled, or no database is configured. API docs and OpenAPI are enabled by default only in local/test environments; set `OPHANIX_ENABLE_API_DOCS=true` intentionally if an internal environment needs them.

Direct HTTP examples and deterministic fixture tokens are local-only demonstrations. Production agents should use the SDK so token handling, payload validation, timeouts, error redaction, discovery pagination, and typed errors stay consistent.

The standalone package README in `../ophanix-tool-gateway-sdk/README.md` contains the fuller API reference, troubleshooting guide, retry options, and concurrency notes.

## Tests

CI runs the Python test suites with pytest. The tests are written as
`unittest` classes, so either runner can execute them locally:

```bash
PYTHONPATH=src python3 -m pytest tests -q --tb=short
PYTHONPATH=src python3 -m unittest discover -s tests -v
```
