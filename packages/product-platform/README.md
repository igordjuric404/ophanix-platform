# Ophanix Product Platform

FastAPI control plane and static application shell for the productized Ophanix governance platform.

## One-command Startup

Run the local platform without manual migrations, seeding, or server setup:

```bash
./start.sh
```

The script starts the API, worker loop, sample MCP/agent services, PostgreSQL migrations/seed, and a local frontend proxy.

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

Database migrations support PostgreSQL only. Local development, tests, cloud
preview, staging, and production all use a `postgresql://...` URL. The default
local URL is `postgresql://ophanix:ophanix-local@127.0.0.1:5432/ophanix_product`.

```bash
docker compose -f docker-compose.demo.yml up -d postgres
export OPHANIX_DATABASE_URL=postgresql://ophanix:ophanix-local@127.0.0.1:5432/ophanix_product
PYTHONPATH=src python3 -m product_platform.cli db migrate
PYTHONPATH=src python3 -m product_platform.cli db rollback
PYTHONPATH=src python3 -m product_platform.cli db seed
PYTHONPATH=src python3 -m product_platform.cli db reset-demo
```

For the full checked-in local stack:

```bash
docker compose -f docker-compose.demo.yml up --build
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
            raise RuntimeError(
                compatibility.incompatibility_reason
                or "SDK and gateway contract versions do not match"
            )
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

`list_tools()`, `list_all_tools()`, and `get_tool()` use the gateway-authenticated discovery route and only return active tools callable by the configured agent credential. Discovery requests retry transient gateway failures by default. `list_all_tools()` and `get_tool()` prefer signed cursor pagination with a gateway snapshot boundary and fall back to offset pagination only for older gateways; `list_all_tools()` also defaults to a hard `max_total=10000` cap. Tool invocations support `Idempotency-Key` through the SDK `idempotency_key` argument or the direct HTTP header; completed responses are replayed for the same credential, tool, key, and payload, conflicting payload reuse returns `idempotency_conflict`, in-progress duplicates return `idempotency_in_progress`, and stale unfinished records return `idempotency_stale` after `OPHANIX_TOOL_GATEWAY_IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS` so callers can stop retrying a key with unknown outcome. The SDK only retries idempotent calls for transport, gateway availability/throttling, and in-progress duplicate cases; terminal execution failures such as `upstream_error` are stored and replayed for the same key rather than re-executed.
`check_compatibility()` probes `/api/v1/gateway/capabilities`; SDK `0.1.x`
expects gateway contract `tool-gateway.v1` and enforces the advertised
`min_sdk_version`. `get_tool()` reports
`tool_not_visible` when a definition is not returned by discovery because the
SDK cannot distinguish missing tools from authorization-hidden tools.

Use `AsyncOphanixToolGatewayClient` in async agent runtimes; it mirrors the synchronous API with `await client.call_tool(...)`, `await client.list_tools(...)`, `await client.list_all_tools(...)`, and `await client.get_tool(...)`.

The SDK validates payloads as strict JSON objects, rejects non-finite numbers, non-string object keys, cyclic payloads, and payloads nested deeper than 50 levels, rejects `Bearer `-prefixed raw token values before sending requests, applies a configurable `max_payload_bytes` cap, adds an SDK `User-Agent`, redacts sensitive fields from exception diagnostic bodies, partitions opt-in discovery caches by process-local HMAC credential fingerprint, expires cached discovery with `cache_ttl_seconds`, and keeps static tokens out of generated `repr()` output. Optional SDK telemetry hooks receive immutable token-free metadata only and can be configured to fail closed with `raise_event_hook_errors=True`.

Server-side Tool Gateway runtime paths enforce bearer authentication, an explicit runtime-route allowlist, a configurable ASGI request body cap (`OPHANIX_TOOL_GATEWAY_MAX_BODY_BYTES`, default `1000000`), a configurable upstream response cap (`OPHANIX_TOOL_GATEWAY_MAX_UPSTREAM_RESPONSE_BYTES`, default `1000000`), and PostgreSQL-backed fixed-window rate limiting (`OPHANIX_TOOL_GATEWAY_RATE_LIMIT_MAX_REQUESTS` per `OPHANIX_TOOL_GATEWAY_RATE_LIMIT_WINDOW_SECONDS`, capped by `OPHANIX_TOOL_GATEWAY_RATE_LIMIT_MAX_KEYS`). Previously unseen authorization values that exceed the key budget fall into a per-client overflow bucket so callers cannot evade limits by rotating token strings. Gateway `429` responses include `Retry-After`. The default HTTPX executor enforces the upstream response cap while streaming bytes and before JSON parsing. It also includes a PostgreSQL-backed circuit breaker (`OPHANIX_TOOL_GATEWAY_CIRCUIT_BREAKER_FAILURE_THRESHOLD`, default `5`; `OPHANIX_TOOL_GATEWAY_CIRCUIT_BREAKER_COOLDOWN_SECONDS`, default `30`) so repeated `5xx`, timeout, or connection failures temporarily stop calls to a failing upstream target across app instances that share the same database. Custom executors or injected HTTP clients must provide equivalent streaming limits, safe error messages, and failure behavior.

Denied Tool Gateway invocations return a coarse agent-facing
`tool_call_denied` reason while decision records and runtime audit records
retain the detailed internal reason code and policy identifiers for operators.
Allowed agent-facing invocation responses expose only a coarse decision summary,
not internal policy IDs. Failed upstream responses do not expose failed
execution envelopes back to agents; inspect runtime actions for upstream status
and safe summaries.

Upstream targets support `auth_mode="none"`, `auth_mode="bearer"`, and `auth_mode="api_key"`. Bearer and API-key targets must use `auth_config_json.secret_ref` to point at an operator-managed secret-provider entry; raw upstream secrets are not accepted in target configuration and are not returned by target read APIs. Local/test environments default to the in-memory demo provider. Production must set `OPHANIX_SECRET_MANAGER_REF=env` or `OPHANIX_SECRET_MANAGER_REF=env:<ENV_VAR_PREFIX>` and inject upstream secrets as environment variables. For example, `secret_ref="secref_partner_claims"` with the default provider reads `OPHANIX_SECRET_SECREF_PARTNER_CLAIMS`; `secret_ref="env:PARTNER_TOKEN"` reads `PARTNER_TOKEN` exactly. API-key targets may set `auth_config_json.header_name` and a single-token `auth_config_json.header_prefix`; the default header is `X-API-Key`. OAuth and dynamic per-tenant upstream auth remain future product work.

GET and DELETE upstream targets do not automatically serialize arbitrary payload fields into query parameters. Non-path payload fields require an explicit `query_parameter_allowlist` on the upstream target and still reject credential-like field names such as `token`, `secret`, `password`, `authorization`, and `api_key`.

Upstream base URLs must use HTTPS and reject credentials, query strings, fragments, metadata hosts, loopback addresses, private/link-local/reserved IP literals, and hostnames that resolve to forbidden addresses during validation. Production must set `OPHANIX_TOOL_GATEWAY_UPSTREAM_HOST_ALLOWLIST` to approved exact hostnames or wildcard patterns such as `*.partner.example.com`; target writes and runtime invocation reject hosts outside that allowlist. Unresolved upstream hostnames fail closed by default in every environment; local/test fixtures must explicitly set `OPHANIX_ALLOW_UNRESOLVED_UPSTREAM_HOSTS=true`, and that override is rejected in production. Runtime invocation revalidates the persisted base URL before forwarding. Keep egress firewall, proxy, or VPC rules in place as the final SSRF boundary because application DNS checks alone cannot pin every possible downstream route.

Production app startup fails when `OPHANIX_SESSION_SECRET` is left at the development default, development login is explicitly enabled, `OPHANIX_DATABASE_URL` is not a PostgreSQL URL, `OPHANIX_SECRET_MANAGER_REF` is missing or unsupported, `OPHANIX_GATEWAY_TOKEN_HASH_PEPPER` is missing, legacy gateway-token hash acceptance is enabled, unresolved upstream hosts are allowed, `OPHANIX_TOOL_GATEWAY_UPSTREAM_HOST_ALLOWLIST` is empty, any Tool Gateway safety limit is zero or negative, or no database is configured. Disabling Tool Gateway response policy is blocked outside local/test environments unless `OPHANIX_ALLOW_DISABLED_TOOL_RESPONSE_POLICY=true` is deliberately set. API docs, `/openapi.json`, and `/api/openapi.json` are enabled by default only in local/test environments; set `OPHANIX_ENABLE_API_DOCS=true` intentionally if an internal environment needs them. `/api/v1/system/config` returns `docs_url: null` when docs are disabled.

Operators can remove old replay bodies after the configured retention window:

```bash
python3 -m product_platform.cli db cleanup-idempotency
python3 -m product_platform.cli db cleanup-idempotency --retention-seconds 604800
```

Gateway credential token hashes use `OPHANIX_GATEWAY_TOKEN_HASH_PEPPER` when set. Operators can label the current pepper with `OPHANIX_GATEWAY_TOKEN_HASH_PEPPER_ID`, accept old peppers during rotation with `OPHANIX_GATEWAY_TOKEN_HASH_PREVIOUS_PEPPERS` entries like `old-key:old-pepper`, and temporarily allow legacy unpeppered hashes with `OPHANIX_GATEWAY_TOKEN_HASH_ACCEPT_LEGACY=true` only outside production. Production startup rejects legacy hash acceptance.

PostgreSQL is the only supported product-platform database backend. The
repository layer uses psycopg against PostgreSQL in every environment; local
development starts a Postgres 16 container through `docker-compose.demo.yml`.
Runtime transactions use a bounded connection pool controlled by
`OPHANIX_DATABASE_MAX_POOL_SIZE` (default `5`).

Direct HTTP examples and deterministic fixture tokens are local-only demonstrations. The example helper now includes basic local URL validation, raw-token checks, response-size caps, non-JSON handling, and timeout usage, but production agents should still use the SDK so token handling, payload validation, retries, error redaction, discovery pagination, and typed errors stay consistent.

MVP support boundary: this package can support controlled internal or design
partner SDK pilots where operators own tokens, upstream allowlists, ingress
limits, and incident response. It is not an enterprise production certification.
Durable idempotency, SDK-gated retries, shared rate/circuit state, PostgreSQL-only
runtime support, PyPI package publication, and artifact SBOM generation are
implemented. Multi-worker/load evidence, final provenance handoff, and
deployment egress enforcement remain post-MVP hardening.

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
python3 -m pip install '.[release,security]'
python3 scripts/validate_release.py --require-dependency-audit
```

The validator builds a wheel and source distribution, checks required package
files and type markers, rejects generated/local artifacts such as database
databases and `__pycache__`, verifies the product wheel does not ship the
standalone `ophanix_tool_gateway` package, installs the wheel into a temporary
target, imports the product package, writes a local CycloneDX SBOM with artifact
hashes and direct runtime dependency components, runs dependency audit when
requested, and runs `twine check`. The product dependency-audit mode installs
the wheel plus public runtime dependencies from wheel metadata. Internal Ophanix
packages such as `agent-discovery`, `agentmesh-platform`, and
`ophanix-tool-gateway-sdk` are listed in the SBOM and manifest but are excluded
from this public-index audit because they are validated in their own package
release pipelines or internal deployment SBOMs.
