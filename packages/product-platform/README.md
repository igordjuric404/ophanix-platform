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
        compatibility = client.check_compatibility()
        if not compatibility.compatible:
            raise RuntimeError("SDK and gateway contract versions do not match")
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
`check_compatibility()` probes `/api/v1/gateway/capabilities`; SDK `0.1.x`
expects gateway contract `tool-gateway.v1`. `get_tool()` reports
`tool_not_visible` when a definition is not returned by discovery because the
SDK cannot distinguish missing tools from authorization-hidden tools.

Use `AsyncOphanixToolGatewayClient` in async agent runtimes; it mirrors the synchronous API with `await client.call_tool(...)`, `await client.list_tools(...)`, `await client.list_all_tools(...)`, and `await client.get_tool(...)`.

The SDK validates payloads as strict JSON objects, rejects non-finite numbers and non-string object keys, rejects `Bearer `-prefixed raw token values before sending requests, applies a configurable `max_payload_bytes` cap, adds an SDK `User-Agent`, redacts sensitive fields from exception diagnostic bodies, partitions opt-in discovery caches by process-local HMAC credential fingerprint, expires cached discovery with `cache_ttl_seconds`, and keeps static tokens out of generated `repr()` output. Optional SDK telemetry hooks receive immutable token-free metadata only and can be configured to fail closed with `raise_event_hook_errors=True`.

Server-side Tool Gateway runtime paths enforce bearer authentication, an explicit runtime-route allowlist, a configurable ASGI request body cap (`OPHANIX_TOOL_GATEWAY_MAX_BODY_BYTES`, default `1000000`), a configurable upstream response cap (`OPHANIX_TOOL_GATEWAY_MAX_UPSTREAM_RESPONSE_BYTES`, default `1000000`), and a bounded in-process rate limit (`OPHANIX_TOOL_GATEWAY_RATE_LIMIT_MAX_REQUESTS` per `OPHANIX_TOOL_GATEWAY_RATE_LIMIT_WINDOW_SECONDS`, capped by `OPHANIX_TOOL_GATEWAY_RATE_LIMIT_MAX_KEYS`). Previously unseen authorization values that exceed the key budget fall into a per-client overflow bucket so attackers cannot evade limits by rotating token strings. Gateway `429` responses include `Retry-After`. The default HTTPX executor enforces the upstream response cap while streaming bytes and before JSON parsing. Custom executors or injected HTTP clients must provide equivalent streaming limits. Production deployments should still enforce global edge rate limits and request-size limits at the ingress layer because the built-in limiter is process-local.

Denied Tool Gateway invocations return a coarse agent-facing
`tool_call_denied` reason while decision records and runtime audit records
retain the detailed internal reason code for operators. Failed upstream
responses do not expose failed execution envelopes back to agents; inspect
runtime actions for upstream status and safe summaries.

Upstream targets support `auth_mode="none"`, `auth_mode="bearer"`, and `auth_mode="api_key"`. Bearer and API-key targets must use `auth_config_json.secret_ref` to point at an operator-managed secret-provider entry; raw upstream secrets are not accepted in target configuration and are not returned by target read APIs. Local/test environments default to the in-memory demo provider. Production must set `OPHANIX_SECRET_MANAGER_REF=env` or `OPHANIX_SECRET_MANAGER_REF=env:<ENV_VAR_PREFIX>` and inject upstream secrets as environment variables. For example, `secret_ref="secref_partner_claims"` with the default provider reads `OPHANIX_SECRET_SECREF_PARTNER_CLAIMS`; `secret_ref="env:PARTNER_TOKEN"` reads `PARTNER_TOKEN` exactly. API-key targets may set `auth_config_json.header_name` and a single-token `auth_config_json.header_prefix`; the default header is `X-API-Key`. OAuth and dynamic per-tenant upstream auth remain future product work.

GET and DELETE upstream targets do not automatically serialize arbitrary payload fields into query parameters. Non-path payload fields require an explicit `query_parameter_allowlist` on the upstream target and still reject credential-like field names such as `token`, `secret`, `password`, `authorization`, and `api_key`.

Upstream base URLs must use HTTPS and reject credentials, query strings, fragments, metadata hosts, loopback addresses, private/link-local/reserved IP literals, and hostnames that resolve to forbidden addresses during validation. Production must set `OPHANIX_TOOL_GATEWAY_UPSTREAM_HOST_ALLOWLIST` to approved exact hostnames or wildcard patterns such as `*.partner.example.com`; target writes and runtime invocation reject hosts outside that allowlist. Unresolved upstream hostnames fail closed outside local/test environments, and `OPHANIX_ALLOW_UNRESOLVED_UPSTREAM_HOSTS=true` is rejected in production. Runtime invocation revalidates the persisted base URL before forwarding. Keep egress firewall rules in place as the final SSRF boundary.

Production app startup fails when `OPHANIX_SESSION_SECRET` is left at the development default, development login is explicitly enabled, SQLite is configured, `OPHANIX_SECRET_MANAGER_REF` is missing or unsupported, `OPHANIX_GATEWAY_TOKEN_HASH_PEPPER` is missing, legacy gateway-token hash acceptance is enabled, unresolved upstream hosts are allowed, `OPHANIX_TOOL_GATEWAY_UPSTREAM_HOST_ALLOWLIST` is empty, any Tool Gateway safety limit is zero or negative, or no database is configured. API docs, `/openapi.json`, and `/api/openapi.json` are enabled by default only in local/test environments; set `OPHANIX_ENABLE_API_DOCS=true` intentionally if an internal environment needs them. `/api/v1/system/config` returns `docs_url: null` when docs are disabled.

Gateway credential token hashes use `OPHANIX_GATEWAY_TOKEN_HASH_PEPPER` when set. Operators can label the current pepper with `OPHANIX_GATEWAY_TOKEN_HASH_PEPPER_ID`, accept old peppers during rotation with `OPHANIX_GATEWAY_TOKEN_HASH_PREVIOUS_PEPPERS` entries like `old-key:old-pepper`, and temporarily allow legacy unpeppered hashes with `OPHANIX_GATEWAY_TOKEN_HASH_ACCEPT_LEGACY=true` only outside production. Production startup rejects legacy hash acceptance.

The product runtime remains SQLite-backed in this worktree. That is acceptable for local demos, internal SDK evaluation, and focused MVP tests with one process and controlled traffic, but broad production adoption still requires an externally managed production database layer, backup/restore procedure, distributed rate limiting or edge enforcement, and multi-worker/load validation.

Direct HTTP examples and deterministic fixture tokens are local-only demonstrations. Production agents should use the SDK so token handling, payload validation, timeouts, error redaction, discovery pagination, and typed errors stay consistent.

MVP support boundary: this package can support controlled internal or design
partner SDK pilots where operators own tokens, upstream allowlists, ingress
limits, and incident response. It is not an enterprise production certification.
Durable idempotency, cursor pagination, distributed rate limiting, upstream
circuit breakers, signed provenance, and SBOM publication remain required before
serious production pilots.

The standalone package README in `../ophanix-tool-gateway-sdk/README.md` contains the fuller API reference, troubleshooting guide, retry options, and concurrency notes.

Security and operations references:

- `../../docs/product-platform-worktree/tool-gateway-threat-model.md`
- `../../docs/product-platform-worktree/tool-gateway-production-runbook.md`

## Tests

CI runs the Python test suites with pytest. The tests are written as
`unittest` classes, so either runner can execute them locally:

```bash
python3 -m pytest tests -q --tb=short
python3 -m unittest discover -s tests -v
```

## Release Validation

Validate product package artifacts before publishing or handing them to an
internal release pipeline:

```bash
python3 -m pip install '.[release]'
python3 scripts/validate_release.py
```

The validator builds a wheel and source distribution, checks required package
files and type markers, rejects generated/local artifacts such as SQLite
databases and `__pycache__`, installs the wheel into a temporary target, imports
the product package and vendored SDK, and runs `twine check`.
