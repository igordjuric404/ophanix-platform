# Tool Gateway SDK Production Readiness Audit - V3

Date: 2026-05-11  
Scope: `ophanix-platform` Tool Gateway SDK, matching product-platform gateway runtime, tests, docs, packaging, CI, and release posture.  
Mode: Strict production-readiness review. No implementation fixes were made.

## Executive Summary

This repository is materially improved from the earlier audit state, but the current state still does not justify broad external production readiness.

Current strict scores:

| Area | Current score | Prior latest score in `13-sdk-review-remediation.md` | Direction | Strict assessment |
|---|---:|---:|---|---|
| Implementation quality | 6 / 10 | 7 / 10 | Lowered | Functional and well covered in many unit paths, but still capped by high-impact runtime design gaps and a newly identified health-check bug. |
| Ease of use | 7 / 10 | 7 / 10 | Upheld | The SDK API is usable and documented, but unsupported upstream auth, beta status, and unclear production credential/publishing paths remain adoption friction. |
| Security and reliability | 5 / 10 | 6 / 10 | Lowered | Multiple high-severity reliability/security gaps remain: no idempotency contract, no upstream auth, DNS rebinding risk, local-only rate limiting, post-read size caps, and weak production DB posture. |

No confirmed critical issue was found in the current tracked package artifacts. Multiple high-severity issues remain. The strongest current blockers are:

- Manual upstream health checks are currently wired incorrectly: an async route passes an `httpx.AsyncClient` into a synchronous health checker.
- Tool invocation keeps a database transaction open across the upstream network call.
- The product runtime database layer is SQLite-only with one shared connection and serialized transactions.
- Upstream authentication is unsupported beyond `auth_mode="none"`.
- Tool invocation has no server-side idempotency key or safe retry contract.
- Upstream URL validation still has DNS failure and DNS rebinding gaps.
- Response-size limits are checked after HTTPX has already materialized response bodies.
- Release/publish provenance is still under-evidenced and references missing pipeline documentation.

Passing tests are meaningful but not sufficient. The tests prove many happy and negative paths, but they do not prove production-grade concurrency, multi-worker behavior, live installed-wheel-to-running-gateway integration, real publish execution, or egress-control enforcement.

## Prior Review Summary And Challenge

### 1. Previously Reported Issues

The requested context file, `docs/product-platform-worktree/execution-logs/06-tool-gateway-logs/13-sdk-review-remediation.md`, records several waves of review and remediation. The major prior issue groups were:

- SDK packaging was originally entangled with `ophanix-product-platform`; a standalone SDK package was needed.
- SDK behavior lacked strong input validation, response validation, timeout/retry controls, cache partitioning, async support, and redaction.
- Gateway discovery originally exposed the wrong route or shape for SDK consumers.
- Runtime gateway behavior lacked sufficient request-body limits, upstream response limits, rate limiting, denial handling, failed-response handling, and resource-bound scope checks.
- Upstream `auth_mode` values were accepted without implementation.
- Tool invocation lacked idempotency semantics and therefore could not safely retry mutating calls.
- CI and publish workflows did not adequately cover product-platform and the standalone SDK.
- Local DB artifacts and package artifact contents created data/package leakage risk.
- Production startup defaults were not fail-closed enough.
- Redaction, SSRF prevention, token parsing, credential scope validation, and release validation needed hardening.
- Production-like concurrency/load/SSRF integration tests were missing.
- SDK remained pre-1.0 beta.

### 2. Fixes Claimed

The remediation log claims these fixes, among others:

- Added a dedicated `packages/ophanix-tool-gateway-sdk` package with `py.typed`, README, changelog, security policy, tests, and release validator.
- Added sync and async SDK clients, environment token provider, stricter payload validation, response validation, error redaction, SDK user agent, discovery retries, bounded caches, cache partitioning by token fingerprint, and telemetry hooks.
- Added gateway-authenticated discovery at `/api/v1/gateway/tools`.
- Hardened gateway auth parsing, production startup validation, request body caps, upstream response caps, rate limiting, response policy handling, and direct HTTP docs.
- Restricted supported upstream auth modes to `none` and made unsupported persisted auth modes fail closed.
- Added async upstream execution with `httpx.AsyncClient`.
- Added transaction serialization for the shared SQLite connection.
- Added CI matrix coverage for product-platform and SDK, release validation, dependency audit, package build checks, and publish workflow coverage.
- Added artifact denylist checks for the SDK release validator and package excludes for product-platform.
- Added docs describing current limitations and production adoption expectations.

### 3. Validation Evidence Claimed

The remediation log claims:

- Full product test suite passed in prior runs.
- Tool Gateway focused tests passed.
- Standalone SDK tests passed.
- SDK mypy strict mode passed.
- Ruff passed.
- SDK release validator passed, with release and security extras.
- Product-platform build artifacts excluded DB/sqlite/pycache files.
- `.github/workflows/ci.yml` and `.github/workflows/publish.yml` parsed.
- Some strict git validation intentionally failed while worktree was dirty during remediation.

Fresh validation performed during this audit:

- `packages/product-platform`: `env PYTHONPATH=src python3 -m pytest tests/test_tool_gateway_*.py -q --tb=short` -> `258 passed`.
- `packages/product-platform`: `env PYTHONPATH=src python3 -m pytest tests -q --tb=short` -> `755 passed`, 47 warnings.
- `packages/ophanix-tool-gateway-sdk`: `env PYTHONPATH=src python3 -m pytest tests -q --tb=short` -> `5 passed`.
- `packages/product-platform`: `python3 -m ruff check .` -> passed.
- `packages/ophanix-tool-gateway-sdk`: `python3 -m ruff check .` -> passed.
- `packages/ophanix-tool-gateway-sdk`: `python3 -m mypy src tests` -> passed.
- `packages/ophanix-tool-gateway-sdk`: `python3 scripts/validate_release.py --skip-twine-check` -> passed.
- Repo root: `python3 -m compileall -q` over product-platform gateway/API and SDK paths -> passed.
- `packages/product-platform`: `python3 -m pip wheel . --no-deps --wheel-dir /tmp/ophanix-product-platform-audit-wheel` -> passed.
- Product-platform wheel inspection -> no DB files observed in the wheel.
- Standalone SDK and vendored product SDK source files currently match by `cmp`.
- `git status --short` before creating this audit artifact was clean.

### 4. Scores Previously Assigned

The requested remediation file is internally inconsistent because it records multiple review/remediation epochs.

- Earlier optimistic scores in the file included approximately Implementation `8.1`, Ease of use `8.3`, Security/reliability `8.3`.
- Later V2 remediation sections reduced the baseline and then reported latest scores of Implementation `7 / 10`, Ease of use `7 / 10`, Security/reliability `6 / 10`.
- The final strict baseline used for this audit comparison is the latest one: `7 / 10`, `7 / 10`, `6 / 10`.

### 5. Suspicious Or Under-Evidenced Prior Conclusions

- The prior conclusion that async forwarding was fixed is too broad. Upstream invocation uses async execution, but manual upstream health checking still passes an `httpx.AsyncClient` into a synchronous checker.
- The prior conclusion that SQLite transaction handling was fixed is too lenient. Serialization avoids interleaving but keeps a single SQLite connection, no production DB backend, and long transactions.
- The prior “production startup guard” conclusion is too lenient. It rejects the default DB URL, but any other `sqlite:///...` URL is accepted in production.
- The prior response-size-cap conclusion is too lenient. Caps are checked before JSON parsing, but after HTTPX has already read/materialized the body.
- The prior SSRF conclusion is too lenient. Validation allows unresolved hostnames and does not re-resolve/pin hostnames at invocation time.
- The prior rate-limit conclusion is too lenient. The implementation is bounded but process-local and not a production distributed limiter.
- The prior release/publish conclusion is under-evidenced. The publish workflow references missing `docs/internal/pypi-publishing.md` and `pipelines/pypi-publish.yml` paths.
- The prior “tool-scoped credential validation fixed” conclusion is partly correct for `resource_type="tool"`, but other arbitrary resource types remain open-ended.
- The prior scoring did not account enough for missing live installed-wheel-to-running-gateway tests, load tests, multi-worker tests, and publish workflow execution evidence.

### 6. Areas Not Deeply Reviewed Before

- Manual upstream health-check route behavior with the default app-level `httpx.AsyncClient`.
- Transaction lifetime around tool invocation, especially network awaits inside DB transactions.
- Production DB backend support beyond SQLite.
- Actual publish pipeline existence, not only package build.
- Production setting guardrails for gateway safety limits and token-hash pepper.
- Response policy behavior when the policy row exists but is inactive.
- Offset pagination stability under changing tool definitions.
- Security-policy intake completeness.
- Cross-file contradictions between docs and runtime OpenAPI/docs behavior.

## Repository Surface Reviewed

### Pass 1 Repository Map

Relevant files and directories reviewed:

- SDK package:
  - `packages/ophanix-tool-gateway-sdk/pyproject.toml`
  - `packages/ophanix-tool-gateway-sdk/README.md`
  - `packages/ophanix-tool-gateway-sdk/CHANGELOG.md`
  - `packages/ophanix-tool-gateway-sdk/SECURITY.md`
  - `packages/ophanix-tool-gateway-sdk/scripts/validate_release.py`
  - `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/__init__.py`
  - `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py`
  - `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/py.typed`
  - `packages/ophanix-tool-gateway-sdk/tests/*`
- Product vendored SDK:
  - `packages/product-platform/src/ophanix_tool_gateway/__init__.py`
  - `packages/product-platform/src/ophanix_tool_gateway/sdk.py`
  - `packages/product-platform/src/ophanix_tool_gateway/py.typed`
- Product gateway runtime:
  - `packages/product-platform/src/product_platform/api/app.py`
  - `packages/product-platform/src/product_platform/api/settings.py`
  - `packages/product-platform/src/product_platform/tool_gateway/auth.py`
  - `packages/product-platform/src/product_platform/tool_gateway/decision.py`
  - `packages/product-platform/src/product_platform/tool_gateway/direct_http_examples.py`
  - `packages/product-platform/src/product_platform/tool_gateway/health.py`
  - `packages/product-platform/src/product_platform/tool_gateway/invocation.py`
  - `packages/product-platform/src/product_platform/tool_gateway/models.py`
  - `packages/product-platform/src/product_platform/tool_gateway/repository.py`
  - `packages/product-platform/src/product_platform/tool_gateway/response.py`
  - `packages/product-platform/src/product_platform/tool_gateway/runtime_audit.py`
  - `packages/product-platform/src/product_platform/tool_gateway/schemas.py`
- Product auth/credential/database surfaces:
  - `packages/product-platform/src/product_platform/agents/credentials.py`
  - `packages/product-platform/src/product_platform/agents/models.py`
  - `packages/product-platform/src/product_platform/db/connection.py`
  - `packages/product-platform/src/product_platform/db/migrator.py`
  - `packages/product-platform/src/product_platform/db/repositories.py`
  - `packages/product-platform/src/product_platform/db/testing.py`
- Product tests:
  - `packages/product-platform/tests/test_tool_gateway_*.py`
  - Full `packages/product-platform/tests` suite.
- Packaging/build/release/CI:
  - `packages/product-platform/pyproject.toml`
  - `packages/product-platform/README.md`
  - `.github/workflows/ci.yml`
  - `.github/workflows/publish.yml`
  - `.gitignore`
- Prior audit/remediation context:
  - `docs/product-platform-worktree/execution-logs/06-tool-gateway-logs/13-sdk-review-remediation.md`
  - `docs/product-platform-worktree/execution-logs/06-tool-gateway-logs/14-sdk-production-readiness-audit.md`
  - `docs/product-platform-worktree/execution-logs/06-tool-gateway-logs/15-sdk-production-readiness-audit-v2.md`

## Exhaustive Issue Register

### SDK-AUDIT-001: Manual Upstream Health Check Uses Async HTTP Client In Synchronous Checker

- Category: Runtime behavior / reliability
- Severity: High
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/api/app.py`; `packages/product-platform/src/product_platform/tool_gateway/health.py`
- Evidence: `app.py:808` creates `app.state.tool_gateway_http_client = httpx.AsyncClient()`. `app.py:6088-6102` is an async route but passes that client into `ToolUpstreamHealthChecker(...).check_target(target_id)`. `health.py:51-71` is synchronous and calls `self.http_client.get(...)`, then immediately reads `response.status_code`. With `httpx.AsyncClient`, `.get()` returns a coroutine.
- Why it matters: The default app route can mark healthy targets unhealthy, persist misleading health state, and emit un-awaited coroutine warnings instead of performing the probe.
- Root cause or likely root cause: Async invocation remediation reused the app-level async client without making the health checker async or providing a sync client.
- Impact on production readiness: High. Operators cannot trust manual upstream health checks.
- Impact on developer experience, if applicable: Debugging healthy upstreams as unhealthy wastes operator time.
- Impact on security or reliability, if applicable: Reliability impact; health state may drive fail-closed behavior and incident response.
- Whether it was mentioned in the prior review log: Not specifically.
- Whether a previous fix claimed to address it: The prior log claimed async upstream execution and health cleanup were fixed generally.
- Whether that previous fix is sufficient: No.
- Recommended remediation: Provide an async health checker or call a sync client from a worker thread; add type validation so sync checkers cannot receive async clients.
- Suggested validation or test: Route-level test using the default `create_app()` state and a mocked async transport proving the health URL is awaited and status is persisted correctly.
- Whether it should affect scoring: Yes; lowers implementation and reliability.

### SDK-AUDIT-002: Tool Invocation Holds Database Transaction Open Across Upstream Network Call

- Category: Runtime behavior / reliability
- Severity: High
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/api/app.py`
- Evidence: `app.py:3149` opens `with _audit_database().transaction() as connection:`. The route creates runtime action rows, then executes and awaits upstream work at `app.py:3281-3292` inside the same transaction. It continues response policy work and returns at `app.py:3499-3507` before leaving the transaction block.
- Why it matters: A slow or hung upstream holds DB locks and a serialized transaction across network I/O.
- Root cause or likely root cause: Runtime auditing, policy evaluation, upstream dispatch, response processing, and final audit update are implemented as one large transactional block.
- Impact on production readiness: High. This can create request pileups, lock contention, long rollback scopes, and lower throughput.
- Impact on developer experience, if applicable: Consumers may see gateway latency or failures unrelated to their upstream latency alone.
- Impact on security or reliability, if applicable: Reliability impact; can amplify upstream incidents into platform-wide DB contention.
- Whether it was mentioned in the prior review log: Related SQLite/transaction concerns were mentioned.
- Whether a previous fix claimed to address it: Yes, transaction serialization was claimed as a fix.
- Whether that previous fix is sufficient: No. Serialization avoids interleaving but makes long transaction scope more damaging.
- Recommended remediation: Split the workflow into short transactions: evaluate and create action, commit, perform upstream call outside DB transaction, then update action in a new transaction.
- Suggested validation or test: Concurrency test with one slow upstream invocation and a second gateway/database write proving the second request is not blocked for the upstream duration.
- Whether it should affect scoring: Yes; caps implementation and reliability.

### SDK-AUDIT-003: Product Runtime Database Layer Is SQLite-Only With One Shared Connection

- Category: Architecture / reliability
- Severity: High
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/db/connection.py`; `packages/product-platform/src/product_platform/db/migrator.py`; `packages/product-platform/src/product_platform/api/settings.py`; `packages/product-platform/src/product_platform/api/app.py`
- Evidence: `migrator.py:31-32` rejects non-`sqlite:///` URLs. `migrator.py:46-52` opens `sqlite3.connect(..., check_same_thread=False)`. `connection.py:18-24` keeps one process-local connection. `connection.py:30-40` serializes all transactions with one `RLock`. Production startup only rejects the default DB URL at `app.py:773`, not SQLite generally.
- Why it matters: SQLite plus a single shared connection is not a broad production database architecture for multi-worker/high-concurrency gateway traffic.
- Root cause or likely root cause: Product-platform is still using a local/demo DB architecture while presenting production-readiness claims.
- Impact on production readiness: High. Multi-instance deployments cannot share state safely through this layer, and write throughput is limited.
- Impact on developer experience, if applicable: External teams must discover the DB limitation late and design around it.
- Impact on security or reliability, if applicable: Reliability impact; transaction locking and local file persistence are fragile under production deployment patterns.
- Whether it was mentioned in the prior review log: Yes.
- Whether a previous fix claimed to address it: Yes, transaction serialization and default DB guard were claimed.
- Whether that previous fix is sufficient: No. It does not add a production DB backend or pooling.
- Recommended remediation: Add a production database backend with migrations, connection pooling, transaction isolation strategy, and deployment docs.
- Suggested validation or test: Run product-platform tests against the production DB backend and add multi-worker concurrency tests.
- Whether it should affect scoring: Yes; caps implementation and reliability.

### SDK-AUDIT-004: Production Guard Accepts Arbitrary SQLite URLs

- Category: Deployment safety
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/api/app.py`; `packages/product-platform/src/product_platform/api/settings.py`
- Evidence: `settings.py:61` defaults to `sqlite:///ophanix_product.db`. `app.py:773` rejects only that exact default in non-local mode. A production value such as `sqlite:///prod.db` passes the guard while still using SQLite.
- Why it matters: The guard can create false confidence that production DB configuration is safe.
- Root cause or likely root cause: The guard checks a default string rather than supported production database capabilities.
- Impact on production readiness: Medium. Deployments can pass startup while relying on a local DB file.
- Impact on developer experience, if applicable: Operators may misread startup success as production DB readiness.
- Impact on security or reliability, if applicable: Reliability impact from local file DB use.
- Whether it was mentioned in the prior review log: Partially.
- Whether a previous fix claimed to address it: Yes, production startup validation was claimed.
- Whether that previous fix is sufficient: No.
- Recommended remediation: In non-local environments, reject SQLite unless explicitly running a documented single-node mode, or implement a production DB adapter.
- Suggested validation or test: Production-mode settings test with `OPHANIX_DATABASE_URL=sqlite:///custom.db` should fail unless explicitly allowed.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-005: Upstream Authentication Is Unsupported Beyond `auth_mode="none"`

- Category: Public API / security / adoption
- Severity: High
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/tool_gateway/models.py`; `packages/product-platform/src/product_platform/tool_gateway/invocation.py`; docs
- Evidence: `models.py:17` sets `SUPPORTED_UPSTREAM_AUTH_MODES = {"none"}`. `invocation.py:266-270` fails closed for any persisted non-`none` auth mode. `packages/product-platform/README.md:90` documents that secret-backed upstream authentication is not implemented.
- Why it matters: Real production upstream APIs commonly require bearer tokens, API keys, OAuth, mTLS, or signed requests.
- Root cause or likely root cause: Secret-backed upstream credential design, storage, rotation, and injection remain deferred.
- Impact on production readiness: High. Many production tools cannot be registered safely or at all.
- Impact on developer experience, if applicable: Integrators can build an SDK integration but then discover protected upstreams are unsupported.
- Impact on security or reliability, if applicable: Security/adoption impact; teams may be tempted to embed credentials in URLs, payloads, or proxy shims.
- Whether it was mentioned in the prior review log: Yes.
- Whether a previous fix claimed to address it: Yes, prior fix restricted modes and documented deferral.
- Whether that previous fix is sufficient: No. It is fail-closed but not production-complete.
- Recommended remediation: Implement upstream credential references through a secret manager, supported auth schemes, rotation, audit, and tests.
- Suggested validation or test: End-to-end tests for bearer/API-key upstream auth that prove secrets are not persisted in plaintext, not logged, and are injected only at request time.
- Whether it should affect scoring: Yes; caps ease of use and security/reliability.

### SDK-AUDIT-006: Tool Invocation Has No Server-Side Idempotency Or Safe Retry Contract

- Category: Reliability / API contract
- Severity: High
- Confidence: High
- File path or area: SDK and runtime invocation contract
- Evidence: `packages/ophanix-tool-gateway-sdk/README.md:146-149` and `170-172` state invocations are not retried because the contract lacks idempotency keys. `sdk.py:369-388` posts invocation once and does not retry. No server route accepts or persists an idempotency key.
- Why it matters: Consumers cannot safely retry network timeouts for mutating tools without risking duplicate side effects.
- Root cause or likely root cause: The API has no durable idempotency key model, replay response semantics, or per-tool mutability metadata.
- Impact on production readiness: High. Network blips and ambiguous upstream outcomes are normal production conditions.
- Impact on developer experience, if applicable: SDK consumers must invent their own idempotency discipline outside the contract.
- Impact on security or reliability, if applicable: Reliability impact; duplicate side effects or lost operations are possible.
- Whether it was mentioned in the prior review log: Yes.
- Whether a previous fix claimed to address it: The prior log deferred it with rationale.
- Whether that previous fix is sufficient: No, documentation is not behavior.
- Recommended remediation: Add `Idempotency-Key` or equivalent contract, per-tool idempotency metadata, durable request/result storage, replay rules, and SDK support.
- Suggested validation or test: Tests for repeated requests with the same idempotency key, conflicting payloads, timeout/retry replay, and non-idempotent tool rejection.
- Whether it should affect scoring: Yes; caps implementation and reliability.

### SDK-AUDIT-007: Upstream URL Validation Has DNS Failure And DNS Rebinding Gaps

- Category: Security / SSRF
- Severity: High
- Confidence: Medium
- File path or area: `packages/product-platform/src/product_platform/tool_gateway/models.py`; `packages/product-platform/src/product_platform/tool_gateway/invocation.py`
- Evidence: `models.py:538-544` returns `False` when `socket.getaddrinfo()` raises `socket.gaierror`, allowing unresolved hostnames. `invocation.py:352-371` later builds the URL from stored `base_url` without re-resolving or pinning the address at invocation time.
- Why it matters: A hostname can fail resolution during validation or later rebind to loopback/private/metadata IPs.
- Root cause or likely root cause: SSRF validation is registration-time best effort and relies on external egress policy for final enforcement.
- Impact on production readiness: High for deployments where users or compromised operators can register/update upstream targets.
- Impact on developer experience, if applicable: Operators must understand and supply external network controls not enforced by code.
- Impact on security or reliability, if applicable: Security impact; SSRF boundary is incomplete without egress firewalling.
- Whether it was mentioned in the prior review log: Yes, SSRF hardening was discussed.
- Whether a previous fix claimed to address it: Yes.
- Whether that previous fix is sufficient: Partially. It rejects many unsafe cases but not DNS failure/rebinding.
- Recommended remediation: Add runtime egress enforcement, DNS pinning or connect-time IP validation, allowlists, and fail-closed unresolved-host policy for production.
- Suggested validation or test: Integration tests for unresolved hostnames, DNS rebinding simulation, IPv6 edge cases, and private-address resolution at invocation time.
- Whether it should affect scoring: Yes; caps security/reliability.

### SDK-AUDIT-008: SDK And Server Response Byte Caps Are Checked After HTTPX Materializes Bodies

- Category: Reliability / resource safety
- Severity: High
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py`; `packages/product-platform/src/product_platform/tool_gateway/invocation.py`
- Evidence: SDK `_response_data()` calls `_ensure_response_within_limit(response)` at `sdk.py:1380`, but `response.content` is already available at `sdk.py:1410-1417`. Server `_response_body()` similarly checks `response.content` at `invocation.py:387-393` after `http_client.request()` completed at `invocation.py:283-294`.
- Why it matters: A malicious or broken gateway/upstream can still force memory allocation before the cap rejects the body.
- Root cause or likely root cause: The code uses regular HTTPX request APIs instead of streaming with a byte-counting reader.
- Impact on production readiness: High for untrusted or high-volume upstream/gateway responses.
- Impact on developer experience, if applicable: The docs imply caps are stronger than they are.
- Impact on security or reliability, if applicable: Reliability/resource exhaustion impact.
- Whether it was mentioned in the prior review log: Response caps were mentioned, but this nuance was underemphasized.
- Whether a previous fix claimed to address it: Yes, caps before JSON parsing were claimed.
- Whether that previous fix is sufficient: No. Before JSON parsing is not before network/body materialization.
- Recommended remediation: Use streaming response reads with hard byte ceilings and abort once the cap is exceeded.
- Suggested validation or test: Test a chunked response without `Content-Length` that exceeds the cap and assert the client/server stops reading after the limit.
- Whether it should affect scoring: Yes; caps reliability.

### SDK-AUDIT-009: Response Policy Inactive State Can Bypass Redaction While Still Allowing Full Response Storage

- Category: Security / data handling
- Severity: High
- Confidence: Medium
- File path or area: `packages/product-platform/src/product_platform/tool_gateway/response.py`; `packages/product-platform/src/product_platform/api/app.py`
- Evidence: `response.py:25-30` returns the raw execution unchanged when `policy["status"]` is not active. Later, `app.py:3478-3481` uses `store_full_response=bool(response_policy["store_full_response"])` whenever a policy row exists, regardless of active status.
- Why it matters: An inactive policy row with `store_full_response=True` can persist unredacted upstream response bodies.
- Root cause or likely root cause: Response visibility/redaction status and response persistence flags are evaluated in separate places with different status handling.
- Impact on production readiness: High if upstream responses can contain credentials, PII, or regulated data.
- Impact on developer experience, if applicable: Operators may think disabling a policy disables all policy-controlled storage behavior.
- Impact on security or reliability, if applicable: Security/data leakage impact.
- Whether it was mentioned in the prior review log: Not specifically.
- Whether a previous fix claimed to address it: Response hardening was claimed generally.
- Whether that previous fix is sufficient: No.
- Recommended remediation: Gate `store_full_response` on active response policy after redaction, or forbid full-response storage unless active redaction policy succeeds.
- Suggested validation or test: Test inactive response policy with `store_full_response=True` and secret-like response body; assert raw body is not persisted.
- Whether it should affect scoring: Yes; lowers security score.

### SDK-AUDIT-010: OpenAPI Alias Remains Exposed When API Docs Are Disabled

- Category: Security / documentation consistency
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/api/app.py`; `packages/product-platform/README.md`
- Evidence: `app.py:797-798` disables FastAPI docs/OpenAPI URLs when `enable_api_docs` is false. But `app.py:3045-3049` always exposes `/api/openapi.json` and returns `app.openapi()`. `README.md:92` says API docs and OpenAPI are enabled by default only in local/test environments.
- Why it matters: Production deployments may unintentionally expose schema metadata even when docs are believed disabled.
- Root cause or likely root cause: A compatibility alias was added outside the docs gating condition.
- Impact on production readiness: Medium.
- Impact on developer experience, if applicable: Operators receive contradictory behavior.
- Impact on security or reliability, if applicable: Security information disclosure risk.
- Whether it was mentioned in the prior review log: Related docs/openapi concerns existed earlier.
- Whether a previous fix claimed to address it: Production docs gating was claimed.
- Whether that previous fix is sufficient: No.
- Recommended remediation: Apply `enable_api_docs` gating to `/api/openapi.json` or require explicit internal auth.
- Suggested validation or test: Production-mode test asserting `/api/openapi.json` returns 404 or auth-protected response when docs are disabled.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-011: Public System Config Advertises `/docs` Even When Docs Are Disabled

- Category: Documentation / runtime consistency
- Severity: Low
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/api/app.py`
- Evidence: `app.py:3055-3060` returns `docs_url="/docs"` unconditionally from `/api/v1/system/config`.
- Why it matters: Frontend clients or operators may show links to disabled docs.
- Root cause or likely root cause: Public config is not derived from the same `enable_api_docs` flag used to configure FastAPI.
- Impact on production readiness: Low.
- Impact on developer experience, if applicable: Confusing UI/integration metadata.
- Impact on security or reliability, if applicable: Minor security inconsistency when combined with SDK-AUDIT-010.
- Whether it was mentioned in the prior review log: Not specifically.
- Whether a previous fix claimed to address it: No.
- Whether that previous fix is sufficient: Not applicable.
- Recommended remediation: Return `None` when docs are disabled.
- Suggested validation or test: Production-mode config test asserting `docs_url is None`.
- Whether it should affect scoring: Yes, lightly.

### SDK-AUDIT-012: Production Settings Allow Gateway Safety Limits To Be Disabled

- Category: Deployment safety / reliability
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/api/settings.py`; `packages/product-platform/src/product_platform/api/app.py`
- Evidence: `settings.py:116-129` loads gateway body, rate-limit, max-key, and upstream response limits from environment as integers. `app.py:706-711` disables rate limiting when max requests or window are `<=0`. `app.py:739-741` disables body limiting when `max_body_bytes <= 0`. `_validate_production_settings()` at `app.py:675-686` does not validate these values.
- Why it matters: A typo or bad environment value can silently disable production resource safeguards.
- Root cause or likely root cause: Runtime limit knobs are treated as local flexibility rather than production safety constraints.
- Impact on production readiness: Medium.
- Impact on developer experience, if applicable: Operators have no startup-time feedback for unsafe values.
- Impact on security or reliability, if applicable: Reliability and DoS risk.
- Whether it was mentioned in the prior review log: Production guardrails were discussed.
- Whether a previous fix claimed to address it: Production settings hardening was claimed.
- Whether that previous fix is sufficient: No.
- Recommended remediation: Add production validation requiring positive bounded values for body size, upstream response size, rate-limit window, max requests, and max keys.
- Suggested validation or test: Non-local startup tests with zero/negative gateway safety limits should fail.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-013: Gateway Rate Limiter Is Process-Local And Not Distributed

- Category: Reliability / security
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/api/app.py`; docs
- Evidence: `app.py:809` initializes `app.state.tool_gateway_rate_limits = {}`. `app.py:706-732` mutates that dictionary per process. `README.md:88` documents it as bounded in-process and says production deployments should enforce global edge rate limits.
- Why it matters: Multi-worker or multi-instance deployments do not share limits.
- Root cause or likely root cause: Lightweight limiter was added as local safeguard, not production distributed control.
- Impact on production readiness: Medium.
- Impact on developer experience, if applicable: Teams must implement additional infrastructure to achieve documented production behavior.
- Impact on security or reliability, if applicable: Security/reliability DoS risk.
- Whether it was mentioned in the prior review log: Yes.
- Whether a previous fix claimed to address it: Yes, bounded in-process limiter was added and distributed need documented.
- Whether that previous fix is sufficient: Partially, but not for production-grade global limiting.
- Recommended remediation: Add Redis/edge/distributed rate limiter integration or make external rate limiting a hard deployment requirement with health checks.
- Suggested validation or test: Multi-process test showing shared enforcement or explicit startup failure without distributed limiter in production mode.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-014: Gateway Rate Limiter Has No Concurrency Guard Around Shared Dictionary

- Category: Reliability / correctness
- Severity: Low
- Confidence: Medium
- File path or area: `packages/product-platform/src/product_platform/api/app.py`
- Evidence: `app.py:714-731` reads and mutates `app.state.tool_gateway_rate_limits` without an async/thread lock.
- Why it matters: Concurrent requests can race counts and cleanup in threaded or unusual ASGI execution contexts.
- Root cause or likely root cause: The limiter assumes single-event-loop serialized access.
- Impact on production readiness: Low to medium depending on worker model.
- Impact on developer experience, if applicable: Rate-limit behavior may be slightly inconsistent under load.
- Impact on security or reliability, if applicable: Reliability/security impact if attackers exploit racey counting.
- Whether it was mentioned in the prior review log: No specific locking concern.
- Whether a previous fix claimed to address it: Rate limiter was claimed fixed generally.
- Whether that previous fix is sufficient: Not fully.
- Recommended remediation: Protect state with a lock or use a distributed atomic backend.
- Suggested validation or test: Concurrent request test proving exact counting under parallel access.
- Whether it should affect scoring: Yes, lightly.

### SDK-AUDIT-015: Request Body Limiter Monkeypatches Starlette Private `_receive`

- Category: Maintainability / runtime compatibility
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/api/app.py`
- Evidence: `app.py:742` reads `request._receive`, and `app.py:756` writes `request._receive = limited_receive`.
- Why it matters: This relies on private Starlette/FastAPI internals and may break with framework updates.
- Root cause or likely root cause: Middleware-level streaming size limit was implemented by wrapping the request receive callable directly.
- Impact on production readiness: Medium due framework upgrade fragility.
- Impact on developer experience, if applicable: Upgrades can fail in surprising ways.
- Impact on security or reliability, if applicable: Reliability and DoS-control risk if the hook stops working.
- Whether it was mentioned in the prior review log: Request body limits were discussed, private API risk was not prominent.
- Whether a previous fix claimed to address it: Body limiter was claimed fixed.
- Whether that previous fix is sufficient: Partially.
- Recommended remediation: Implement an ASGI middleware at the receive layer or use a supported framework/server body limit.
- Suggested validation or test: Framework-version compatibility test and chunked-body tests.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-016: SDK Treats Broad 403 Responses As `ToolDeniedError`

- Category: Public API / error semantics
- Severity: Medium
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py`; vendored copy
- Evidence: `sdk.py:388-397` calls `_raise_denied` for every HTTP 403. `_raise_denied()` at `sdk.py:1323-1335` converts any 403 with `body.reason_code` or `body.error.code` into `ToolDeniedError`.
- Why it matters: A generic gateway, proxy, WAF, or authz 403 with an error code can be misclassified as policy denial.
- Root cause or likely root cause: Status-code based branching happens before verifying the response is a gateway policy-denial shape.
- Impact on production readiness: Medium.
- Impact on developer experience, if applicable: Applications may handle infrastructure 403s as business policy denials.
- Impact on security or reliability, if applicable: Reliability/observability impact.
- Whether it was mentioned in the prior review log: Prior notes claimed structured 403 handling was improved.
- Whether a previous fix claimed to address it: Yes.
- Whether that previous fix is sufficient: No; classification remains broad.
- Recommended remediation: Require a gateway-specific denial discriminator, such as a known error envelope code namespace or `decision` object.
- Suggested validation or test: SDK test where 403 `{"error":{"code":"forbidden"}}` raises `ToolGatewayError`, while a real policy denial raises `ToolDeniedError`.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-017: Frozen SDK Dataclasses Are Only Shallowly Immutable

- Category: Public API / maintainability
- Severity: Low
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py`
- Evidence: `ToolCallResult` uses `decision: dict[str, Any] | None` at `sdk.py:174` and `result: Any`. `ToolDefinition` uses mutable dict schemas at `sdk.py:189-190`. `_optional_response_mapping_field()` returns the original dict at `sdk.py:1430-1443`. `_immutable_mapping()` at `sdk.py:1463-1464` shallow-copies only the top-level raw mapping.
- Why it matters: Callers can mutate nested objects despite frozen dataclasses.
- Root cause or likely root cause: Dataclass immutability was applied at the object attribute level but not deep-normalized.
- Impact on production readiness: Low.
- Impact on developer experience, if applicable: The API can surprise users who interpret frozen objects as immutable snapshots.
- Impact on security or reliability, if applicable: Low reliability/diagnostic integrity risk.
- Whether it was mentioned in the prior review log: Cache mutation was discussed; direct returned-object mutability less so.
- Whether a previous fix claimed to address it: Cached tool definitions are copied before return.
- Whether that previous fix is sufficient: Partially; non-cached/direct result structures remain mutable.
- Recommended remediation: Deep-copy and expose `MappingProxyType` recursively where practical, or document shallow immutability.
- Suggested validation or test: Test that mutating returned schemas/decision does not mutate raw/cached/internal state and document expected behavior.
- Whether it should affect scoring: Yes, lightly.

### SDK-AUDIT-018: Standalone SDK Test Suite Is Thin Compared With Vendored Product SDK Coverage

- Category: Testing
- Severity: Medium
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/tests`; `packages/product-platform/tests/test_tool_gateway_sdk_*.py`
- Evidence: Standalone SDK suite has only `test_package_smoke.py` and `test_sdk_behavior.py`; this audit run produced `5 passed`. Product-platform has many SDK behavior tests, but those run in the product package context.
- Why it matters: A standalone package can regress through packaging/import/dependency differences even if product vendored tests pass.
- Root cause or likely root cause: Behavioral tests were mostly added under product-platform before/during vendoring.
- Impact on production readiness: Medium.
- Impact on developer experience, if applicable: SDK consumers depend on standalone package behavior, not only product vendored behavior.
- Impact on security or reliability, if applicable: Reliability/test confidence impact.
- Whether it was mentioned in the prior review log: Related packaging/test coverage was mentioned.
- Whether a previous fix claimed to address it: Standalone smoke tests were added.
- Whether that previous fix is sufficient: No.
- Recommended remediation: Move or duplicate the full SDK behavior suite into the standalone package and run it against built wheels.
- Suggested validation or test: Installed-wheel SDK test suite with sync/async clients, retries, errors, caching, redaction, and type surface.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-019: No Live Installed-Wheel-To-Running-Gateway Integration Test

- Category: Testing / release readiness
- Severity: Medium
- Confidence: High
- File path or area: SDK tests, product-platform tests, CI
- Evidence: Product tests heavily use `TestClient`, fakes, and `httpx.MockTransport`; standalone SDK tests are package-local. No observed test installs the built SDK wheel, starts a real gateway process, and invokes tools over a real socket.
- Why it matters: Packaging, process startup, ASGI server behavior, networking, and SDK/runtime contract can fail outside in-process tests.
- Root cause or likely root cause: Validation is unit/in-process focused.
- Impact on production readiness: Medium to high.
- Impact on developer experience, if applicable: External teams may hit first-run integration issues not covered by CI.
- Impact on security or reliability, if applicable: Reliability/release confidence impact.
- Whether it was mentioned in the prior review log: Yes, production-like/live validation was deferred.
- Whether a previous fix claimed to address it: Deferred with rationale.
- Whether that previous fix is sufficient: No.
- Recommended remediation: Add CI integration job that builds the SDK wheel, installs it into a clean venv, starts the product API, provisions a demo gateway token/tool, and calls through HTTP.
- Suggested validation or test: Live smoke test for discovery, allow, deny, schema error, upstream failure, and response policy.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-020: No Production-Like Load Or Multi-Worker Validation

- Category: Testing / reliability
- Severity: High
- Confidence: High
- File path or area: Test suite / CI
- Evidence: The tests passed, but no reviewed test runs multi-worker ASGI, concurrent slow upstream invocations, distributed rate-limit behavior, or DB contention scenarios. The prior log explicitly says no production-like load/multi-worker harness was added.
- Why it matters: Current main risks are concurrency, database locking, and resource exhaustion; unit tests do not cover them.
- Root cause or likely root cause: Test coverage grew around functional phases, not operational profiles.
- Impact on production readiness: High.
- Impact on developer experience, if applicable: Adopters lack performance/reliability envelope data.
- Impact on security or reliability, if applicable: Reliability and DoS confidence impact.
- Whether it was mentioned in the prior review log: Yes.
- Whether a previous fix claimed to address it: Deferred.
- Whether that previous fix is sufficient: No.
- Recommended remediation: Add load/concurrency harness with slow upstreams, large responses, many credentials, multi-worker startup, and rate-limit pressure.
- Suggested validation or test: CI or nightly job producing p95/p99 latency, error rate, lock contention, and memory usage under representative load.
- Whether it should affect scoring: Yes; caps reliability.

### SDK-AUDIT-021: Product-Platform Lacks A Type-Checking Gate

- Category: Maintainability / CI
- Severity: Medium
- Confidence: High
- File path or area: `.github/workflows/ci.yml`; `packages/product-platform/pyproject.toml`
- Evidence: CI type checks only the SDK at `ci.yml:87-92`. Product-platform has no mypy configuration in `pyproject.toml` and no CI mypy step.
- Why it matters: The gateway runtime is large and typed enough to benefit from static checks, but no gate protects it.
- Root cause or likely root cause: SDK was prioritized for typed package publishing; product-platform remains dynamically checked.
- Impact on production readiness: Medium.
- Impact on developer experience, if applicable: Contributors get fewer early signals for API/typing regressions.
- Impact on security or reliability, if applicable: Reliability/maintainability impact.
- Whether it was mentioned in the prior review log: CI/type coverage was discussed primarily for SDK.
- Whether a previous fix claimed to address it: SDK mypy was added, not product-platform.
- Whether that previous fix is sufficient: No.
- Recommended remediation: Add incremental product-platform mypy/pyright coverage for gateway/runtime modules first.
- Suggested validation or test: CI gate for `product_platform.tool_gateway`, `product_platform.agents.credentials`, and relevant API models.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-022: CI Dependency Safety Check Is Non-Blocking

- Category: Security / CI
- Severity: Medium
- Confidence: High
- File path or area: `.github/workflows/ci.yml`
- Evidence: `ci.yml:185` runs `safety check 2>/dev/null || echo "Safety check completed with warnings"`.
- Why it matters: Vulnerability findings or tool failures do not fail CI.
- Root cause or likely root cause: Security job was made advisory to avoid blocking.
- Impact on production readiness: Medium.
- Impact on developer experience, if applicable: Contributors may miss vulnerability failures unless they inspect logs.
- Impact on security or reliability, if applicable: Security supply-chain impact.
- Whether it was mentioned in the prior review log: Dependency audit concerns were mentioned.
- Whether a previous fix claimed to address it: Release validator dependency audit was improved.
- Whether that previous fix is sufficient: No, main CI safety check is still advisory.
- Recommended remediation: Make dependency audit blocking, or clearly separate advisory and blocking jobs with policy.
- Suggested validation or test: CI test branch with known vulnerable dependency should fail the required job.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-023: CI Lint Gate Excludes Tests, Scripts, Examples, And Many Ruff Rules

- Category: CI / maintainability
- Severity: Low
- Confidence: High
- File path or area: `.github/workflows/ci.yml`
- Evidence: `ci.yml:85-86` runs `ruff check packages/${{ matrix.package }}/src/ --select E,F,W --ignore E501`.
- Why it matters: Test code, release scripts, examples, and broader Ruff rules can regress unnoticed in CI.
- Root cause or likely root cause: CI uses a minimal broad-repo lint command to reduce noise.
- Impact on production readiness: Low to medium.
- Impact on developer experience, if applicable: Local `ruff check .` can disagree with CI.
- Impact on security or reliability, if applicable: Minor maintainability/release-script risk.
- Whether it was mentioned in the prior review log: CI coverage was discussed generally.
- Whether a previous fix claimed to address it: CI lint was added/improved.
- Whether that previous fix is sufficient: Partially.
- Recommended remediation: Run package-local `ruff check .` or at least include `tests`, `scripts`, and package config.
- Suggested validation or test: CI should fail on a Ruff error in SDK `scripts/validate_release.py`.
- Whether it should affect scoring: Yes, lightly.

### SDK-AUDIT-024: CI Install Step Masks Dependency/Extra Problems With Fallbacks

- Category: CI / packaging
- Severity: Medium
- Confidence: High
- File path or area: `.github/workflows/ci.yml`
- Evidence: `ci.yml:127` falls back from `.[dev]` to `.[test]` to bare install, and `ci.yml:128` suppresses pytest/pytest-asyncio install failure with `|| true`.
- Why it matters: Missing or broken dev/test extras can be hidden by CI.
- Root cause or likely root cause: One generic workflow is handling packages with inconsistent extras.
- Impact on production readiness: Medium for release confidence.
- Impact on developer experience, if applicable: Local setup and CI setup may diverge.
- Impact on security or reliability, if applicable: Test coverage can silently weaken if dependency installation fails.
- Whether it was mentioned in the prior review log: CI coverage was discussed, but fallback masking remains.
- Whether a previous fix claimed to address it: CI matrix was claimed fixed.
- Whether that previous fix is sufficient: No.
- Recommended remediation: Use explicit package-specific install commands or require standardized extras.
- Suggested validation or test: CI should fail when `.[dev]` is missing for packages expected to expose dev extras.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-025: Publish Workflow References Missing Internal PyPI Publishing Docs And Pipeline

- Category: Release / supply chain
- Severity: High
- Confidence: High
- File path or area: `.github/workflows/publish.yml`; repo docs/pipelines
- Evidence: `publish.yml:34-37` says actual PyPI publishing is done via `pipelines/pypi-publish.yml` and points to `docs/internal/pypi-publishing.md`. Fresh checks found neither path in the repo.
- Why it matters: Build/sign/attest in GitHub Actions is not the actual publish path, and the actual path is not reviewable here.
- Root cause or likely root cause: External/internal release process references were copied into repo workflow comments without including the referenced artifacts.
- Impact on production readiness: High for external package adoption.
- Impact on developer experience, if applicable: Release owners and reviewers cannot follow the publish path from the repo.
- Impact on security or reliability, if applicable: Supply-chain provenance and rollback controls are under-evidenced.
- Whether it was mentioned in the prior review log: Yes, opaque publishing was mentioned and then claimed improved.
- Whether a previous fix claimed to address it: Yes, publish docs/workflow coverage was claimed.
- Whether that previous fix is sufficient: No.
- Recommended remediation: Add the referenced publishing policy/pipeline or update the workflow to point to an existing, reviewable release process.
- Suggested validation or test: Dry-run publish workflow or release checklist that links to existing files and records artifact provenance.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-026: Publish Workflow Hash-Checked Build Install Is Likely Incomplete For Transitive Dependencies

- Category: Release / CI reliability
- Severity: Medium
- Confidence: Medium
- File path or area: `.github/workflows/publish.yml`
- Evidence: `publish.yml:62-66` runs `pip install --require-hashes build==1.2.1 --hash=...` without `--no-deps` and without hashes for transitive dependencies.
- Why it matters: `pip --require-hashes` normally requires hashes for all installed requirements, so this workflow may fail in a clean runner or rely on preinstalled transitive dependencies.
- Root cause or likely root cause: Hash pinning was added inline rather than through a complete hashed requirements file.
- Impact on production readiness: Medium.
- Impact on developer experience, if applicable: Release workflow may fail unexpectedly.
- Impact on security or reliability, if applicable: Supply-chain/release reliability risk.
- Whether it was mentioned in the prior review log: Not specifically.
- Whether a previous fix claimed to address it: Publish hardening was claimed.
- Whether that previous fix is sufficient: Needs workflow execution proof.
- Recommended remediation: Use a complete hashed requirements file or `--no-deps` with preinstalled hashed dependencies.
- Suggested validation or test: Run the publish build job in a clean GitHub Actions environment.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-027: SDK Release Validator Install Smoke Uses `--no-deps`

- Category: Packaging / release validation
- Severity: Low
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/scripts/validate_release.py`
- Evidence: `_validate_installed_wheel()` installs the wheel with `--no-deps` at `validate_release.py:207-220`, then imports it at `validate_release.py:222-235`.
- Why it matters: The import smoke can pass because dependencies are already present in the validator environment, not because wheel dependency metadata resolves in a clean install.
- Root cause or likely root cause: The smoke test intentionally isolates wheel files but not dependency resolution.
- Impact on production readiness: Low because a separate dependency-audit path installs with dependencies.
- Impact on developer experience, if applicable: Local validation without `--require-dependency-audit` can overstate install confidence.
- Impact on security or reliability, if applicable: Packaging reliability risk.
- Whether it was mentioned in the prior review log: Release validator shallowness was mentioned and improved.
- Whether a previous fix claimed to address it: Yes.
- Whether that previous fix is sufficient: Partially.
- Recommended remediation: Add a clean install smoke without `--no-deps` as default, or make dependency-audit install required for release mode.
- Suggested validation or test: Remove `httpx` from the environment and prove wheel install brings it in.
- Whether it should affect scoring: Yes, lightly.

### SDK-AUDIT-028: SDK Strict Git Validation Ignores Vendored SDK Copy And Wider Release State

- Category: Release / repository consistency
- Severity: Low
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/scripts/validate_release.py`
- Evidence: `_validate_git_state()` checks only `git status --porcelain -- <package_root>` at `validate_release.py:113-124`. It does not check `packages/product-platform/src/ophanix_tool_gateway`.
- Why it matters: The standalone package can be clean while the vendored compatibility copy diverges.
- Root cause or likely root cause: Release validator is package-scoped.
- Impact on production readiness: Low to medium.
- Impact on developer experience, if applicable: Internal users importing the vendored copy can see different behavior.
- Impact on security or reliability, if applicable: Consistency/release risk.
- Whether it was mentioned in the prior review log: Duplicated SDK ownership was mentioned.
- Whether a previous fix claimed to address it: Parity exists now, but release validator does not enforce it.
- Whether that previous fix is sufficient: No.
- Recommended remediation: Add parity check for standalone and vendored SDK sources in CI/release validation.
- Suggested validation or test: CI job fails when the two `sdk.py` or `__init__.py` files differ.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-029: Product-Platform Package Lacks Equivalent Release Artifact Validator

- Category: Packaging / release
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/pyproject.toml`; CI
- Evidence: SDK has `scripts/validate_release.py`; product-platform only builds in CI/publish. This audit manually inspected a product wheel and found no DB files, but no product-specific validator equivalent was found.
- Why it matters: Product-platform includes the gateway runtime, migrations, examples, tests, and vendored SDK, but its artifact policy is less automated than the SDK package.
- Root cause or likely root cause: Release validation effort focused on standalone SDK.
- Impact on production readiness: Medium.
- Impact on developer experience, if applicable: Release owners must rely on generic build output.
- Impact on security or reliability, if applicable: Packaging/data leakage risk.
- Whether it was mentioned in the prior review log: Product artifact DB leakage was mentioned and pyproject excludes were added.
- Whether a previous fix claimed to address it: Product build/exclude was claimed.
- Whether that previous fix is sufficient: Partially.
- Recommended remediation: Add product-platform artifact validator checking forbidden files, migrations, license/readme, metadata, import smoke, and CLI smoke.
- Suggested validation or test: CI product release validation fails if `*.db`, `__pycache__`, or missing migrations appear in artifacts.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-030: Product-Platform Package Metadata Is Sparse

- Category: Packaging / DX
- Severity: Low
- Confidence: High
- File path or area: `packages/product-platform/pyproject.toml`
- Evidence: `pyproject.toml:5-21` defines name, version, description, readme, license, and dependencies, but no authors, maintainers, classifiers, project URLs, optional dev/test extras, or package stability classifiers.
- Why it matters: External consumers and package repositories have weak metadata for support, source, issues, and stability.
- Root cause or likely root cause: Product-platform package is treated as internal/demo control-plane package.
- Impact on production readiness: Low.
- Impact on developer experience, if applicable: Poor package discoverability/support cues.
- Impact on security or reliability, if applicable: Minor supply-chain traceability impact.
- Whether it was mentioned in the prior review log: Packaging metadata was discussed mostly for SDK.
- Whether a previous fix claimed to address it: No.
- Whether that previous fix is sufficient: Not applicable.
- Recommended remediation: Add authors, maintainers, URLs, classifiers, and standardized optional dependencies.
- Suggested validation or test: Metadata check in product release validator.
- Whether it should affect scoring: Yes, lightly.

### SDK-AUDIT-031: SDK And Product Versions Remain `0.1.0` / Beta

- Category: API stability / adoption
- Severity: Medium
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/pyproject.toml`; `packages/product-platform/pyproject.toml`; `packages/ophanix-tool-gateway-sdk/CHANGELOG.md`
- Evidence: SDK `pyproject.toml:7` is `0.1.0` and classifier `Development Status :: 4 - Beta` appears at `pyproject.toml:19`. Product-platform `pyproject.toml:7` is also `0.1.0`. Changelog only contains an initial beta package.
- Why it matters: Pre-1.0/beta status signals unstable APIs and weak compatibility guarantees.
- Root cause or likely root cause: Product/release policy has not declared GA or stability criteria.
- Impact on production readiness: Medium.
- Impact on developer experience, if applicable: External teams may block adoption on semver/stability policy.
- Impact on security or reliability, if applicable: Indirect reliability/governance impact from breaking-change risk.
- Whether it was mentioned in the prior review log: Yes.
- Whether a previous fix claimed to address it: Accepted remaining risk.
- Whether that previous fix is sufficient: No for production-ready scoring.
- Recommended remediation: Define stability policy, breaking-change policy, supported versions, and 1.0 criteria; only bump when evidence supports it.
- Suggested validation or test: Release checklist requiring API compatibility review and changelog entries.
- Whether it should affect scoring: Yes; caps ease of use/adoption.

### SDK-AUDIT-032: Ignored Local DB Artifacts Remain In Product Package Directory

- Category: Repository hygiene / data handling
- Severity: Low
- Confidence: High
- File path or area: `packages/product-platform/ophanix_product.db*`; `.gitignore`
- Evidence: Fresh scan found `packages/product-platform/ophanix_product.db` and `packages/product-platform/ophanix_product.db.backup.20260509152042`. `git check-ignore -v` shows `.gitignore:23-24` ignores them.
- Why it matters: They are not tracked or packaged now, but local DB artifacts near package roots are easy to leak through ad hoc zips, Docker contexts, or manual release mistakes.
- Root cause or likely root cause: Local development uses SQLite files in the package directory.
- Impact on production readiness: Low.
- Impact on developer experience, if applicable: Developers can accumulate local state in repo directories.
- Impact on security or reliability, if applicable: Data leakage risk outside controlled package builds.
- Whether it was mentioned in the prior review log: Yes.
- Whether a previous fix claimed to address it: Yes, DB files were ignored/excluded and accepted as remaining local risk.
- Whether that previous fix is sufficient: Partially for wheel/sdist, not for workspace hygiene.
- Recommended remediation: Move local DB defaults under `.local/` or `/tmp`, and add Docker/context denylist checks.
- Suggested validation or test: Artifact/context scan for local DB files in package roots.
- Whether it should affect scoring: Yes, lightly.

### SDK-AUDIT-033: Gateway Token Hash Pepper Is Not Required In Production

- Category: Security / credential storage
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/agents/credentials.py`; `packages/product-platform/src/product_platform/api/app.py`
- Evidence: `credentials.py:27-38` uses `OPHANIX_GATEWAY_TOKEN_HASH_PEPPER` if present, otherwise falls back to legacy SHA-256. `_validate_production_settings()` at `app.py:675-686` does not require the pepper.
- Why it matters: New production credentials can be stored with unsalted SHA-256 hashes if the env var is omitted.
- Root cause or likely root cause: Pepper migration was implemented as optional backward compatibility.
- Impact on production readiness: Medium.
- Impact on developer experience, if applicable: Operators do not receive startup feedback for missing credential-hardening config.
- Impact on security or reliability, if applicable: Security impact if token entropy or database confidentiality is compromised.
- Whether it was mentioned in the prior review log: Production config checks for pepper were noted as remaining possible work.
- Whether a previous fix claimed to address it: Partial token hashing improvements were claimed.
- Whether that previous fix is sufficient: No.
- Recommended remediation: Require a strong pepper in non-local environments and document rotation.
- Suggested validation or test: Production startup test fails without `OPHANIX_GATEWAY_TOKEN_HASH_PEPPER`.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-034: Legacy SHA-256 Token Hashes Are Accepted Indefinitely

- Category: Security / credential migration
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/agents/credentials.py`
- Evidence: `credential_token_hash_candidates()` at `credentials.py:47-52` returns both current HMAC and legacy SHA-256 candidates whenever a pepper is configured. Verification checks membership at `credentials.py:573`.
- Why it matters: Legacy hashes remain valid without an enforced migration deadline.
- Root cause or likely root cause: Compatibility migration path lacks cutoff/upgrade-on-use logic.
- Impact on production readiness: Medium.
- Impact on developer experience, if applicable: Operators lack clear migration status and deadlines.
- Impact on security or reliability, if applicable: Security impact from continued weaker hash acceptance.
- Whether it was mentioned in the prior review log: Not specifically as indefinite legacy acceptance.
- Whether a previous fix claimed to address it: Pepper support was implied by code, not fully addressed.
- Whether that previous fix is sufficient: No.
- Recommended remediation: Add migration tracking, upgrade-on-use, admin migration command, and cutoff date/config.
- Suggested validation or test: Tests for legacy token migration and rejection after cutoff.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-035: Token Hash Pepper Rotation Has No Key ID Or Multi-Pepper Model

- Category: Security / operations
- Severity: Medium
- Confidence: Medium
- File path or area: `packages/product-platform/src/product_platform/agents/credentials.py`
- Evidence: `hash_credential_token()` at `credentials.py:27-38` returns `hmac-sha256:<digest>` without key identifier. Candidate generation supports only current pepper plus legacy unpeppered hash.
- Why it matters: Rotating the pepper can invalidate existing HMAC-token hashes unless all credentials are migrated in lockstep.
- Root cause or likely root cause: Pepper support was added without a full key-rotation design.
- Impact on production readiness: Medium.
- Impact on developer experience, if applicable: Operators have no documented safe rotation path.
- Impact on security or reliability, if applicable: Security and availability risk during rotation.
- Whether it was mentioned in the prior review log: Not specifically.
- Whether a previous fix claimed to address it: No.
- Whether that previous fix is sufficient: Not applicable.
- Recommended remediation: Store hash version/key id, support current and previous peppers during rotation, and provide migration commands.
- Suggested validation or test: Rotation test proving old tokens work during grace period and migrate to new key id.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-036: Credential Metadata Raw-Token Guard Only Checks Exact Raw String

- Category: Security / data handling
- Severity: Low
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/agents/credentials.py`
- Evidence: `_ensure_secret_absent()` at `credentials.py:720-723` JSON-encodes metadata and rejects only when the exact `raw_token` substring appears.
- Why it matters: Encoded, truncated, bearer-prefixed, split, or transformed token material can still be stored.
- Root cause or likely root cause: Guard is a narrow safety check, not a secret scanner.
- Impact on production readiness: Low to medium.
- Impact on developer experience, if applicable: Developers may assume metadata is generally secret-safe.
- Impact on security or reliability, if applicable: Security/data leakage risk.
- Whether it was mentioned in the prior review log: Not specifically.
- Whether a previous fix claimed to address it: Token storage safety was generally discussed.
- Whether that previous fix is sufficient: No.
- Recommended remediation: Add metadata schema allowlist and broader secret-pattern scanning for credential metadata.
- Suggested validation or test: Metadata tests for bearer-prefixed, base64-like, and split token variants.
- Whether it should affect scoring: Yes, lightly.

### SDK-AUDIT-037: Credential Scope `resource_type` Is Open-Ended Outside Tool Resources

- Category: Authorization / API design
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/agents/models.py`; `packages/product-platform/src/product_platform/agents/credentials.py`
- Evidence: `CredentialScopeRequest` accepts arbitrary nonblank `resource_type` at `models.py:346-359`. `validate_scopes()` only validates active tool resources when `scope.resource_type == "tool"` at `credentials.py:643-667`; other resource types are accepted if the capability name is approved.
- Why it matters: Future or mistaken resource types can be issued without resource existence checks.
- Root cause or likely root cause: Scope model was kept generic, but validation is only implemented for tools.
- Impact on production readiness: Medium for authorization clarity.
- Impact on developer experience, if applicable: API users do not know which resource types are meaningful or enforced.
- Impact on security or reliability, if applicable: Authorization ambiguity.
- Whether it was mentioned in the prior review log: Partially; tool resource validation was claimed fixed.
- Whether a previous fix claimed to address it: Yes for `tool`.
- Whether that previous fix is sufficient: Partially.
- Recommended remediation: Enumerate supported resource types or validate each type through a registry.
- Suggested validation or test: Credential issuance tests for unsupported resource types should fail.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-038: Gateway Auth Failure Responses Expose Reason Codes

- Category: Security / information disclosure
- Severity: Low
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/api/app.py`
- Evidence: `_get_gateway_principal()` raises `HTTPException(status_code=401, detail=f"Gateway authentication failed: {exc.reason_code}")` at `app.py:1210-1213`.
- Why it matters: Unauthenticated callers can distinguish failure modes such as missing, expired, inactive, or malformed credential states if upstream error handling preserves the detail.
- Root cause or likely root cause: Operational diagnostics are returned directly to clients.
- Impact on production readiness: Low.
- Impact on developer experience, if applicable: Helpful diagnostics, but too much for unauthenticated callers.
- Impact on security or reliability, if applicable: Information disclosure/account enumeration signal.
- Whether it was mentioned in the prior review log: Not specifically.
- Whether a previous fix claimed to address it: Bearer parsing/auth hardening was claimed.
- Whether that previous fix is sufficient: No for response minimization.
- Recommended remediation: Return a generic 401 response externally; log/audit the reason code internally.
- Suggested validation or test: Auth failure tests assert generic body while audit table stores reason code.
- Whether it should affect scoring: Yes, lightly.

### SDK-AUDIT-039: Caller-Controlled Trace IDs Are Forwarded And Stored As Trusted Correlation Context

- Category: Observability / trust boundary
- Severity: Low
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/api/app.py`; `packages/product-platform/src/product_platform/tool_gateway/invocation.py`
- Evidence: `_trusted_trace_id()` accepts caller `X-Request-ID`/`X-Correlation-ID` if they match `TRACE_ID_PATTERN` at `app.py:617-644`; the values are returned in response headers at `app.py:871-872` and forwarded upstream at `invocation.py:273-279`.
- Why it matters: External callers can choose IDs that appear in audit, logs, and upstream systems.
- Root cause or likely root cause: Trace continuity favors caller-provided IDs without preserving a separate immutable server-generated ID.
- Impact on production readiness: Low.
- Impact on developer experience, if applicable: Useful for tracing, but provenance is ambiguous.
- Impact on security or reliability, if applicable: Observability integrity risk.
- Whether it was mentioned in the prior review log: Malformed trace IDs were addressed, trust-boundary issue less so.
- Whether a previous fix claimed to address it: Trace ID validation was claimed.
- Whether that previous fix is sufficient: Partially.
- Recommended remediation: Store both caller correlation ID and server request ID; distinguish trusted/internal IDs in audit and upstream headers.
- Suggested validation or test: Audit event test asserting server-generated immutable ID is present even when caller supplies correlation ID.
- Whether it should affect scoring: Yes, lightly.

### SDK-AUDIT-040: Redaction Regexes Are Recompiled On Every Response

- Category: Performance / reliability
- Severity: Low
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/tool_gateway/response.py`
- Evidence: `_redact_value()` calls `_compiled_redaction_rules()` at `response.py:78-85`, and `_compiled_redaction_rules()` runs `re.compile(pattern)` for every response.
- Why it matters: Under high invocation volume, repeated regex compilation adds overhead and can amplify expensive patterns.
- Root cause or likely root cause: Policy rules are stored as JSON and compiled in the response path without caching.
- Impact on production readiness: Low to medium depending on volume.
- Impact on developer experience, if applicable: Operators may see avoidable latency.
- Impact on security or reliability, if applicable: Reliability/performance impact.
- Whether it was mentioned in the prior review log: Prior remediation text suggested redaction hardening; compilation caching was not actually present.
- Whether a previous fix claimed to address it: Pattern validation was claimed.
- Whether that previous fix is sufficient: No for runtime compilation overhead.
- Recommended remediation: Compile and cache redaction rules by policy id/version/update timestamp.
- Suggested validation or test: Benchmark response processing with repeated invocations and assert compile count is bounded.
- Whether it should affect scoring: Yes, lightly.

### SDK-AUDIT-041: Regex Redaction Safety Is Heuristic, Not Enforced By A Safe Regex Engine Or Timeout

- Category: Security / reliability
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/tool_gateway/models.py`; `packages/product-platform/src/product_platform/tool_gateway/response.py`
- Evidence: `_validate_redaction_pattern()` at `models.py:512-524` rejects some nested/unbounded regex shapes. `response.py:85` uses Python `re.compile`; no regex timeout or safe-regex engine is used.
- Why it matters: Regex ReDoS defenses are incomplete and may miss pathological patterns.
- Root cause or likely root cause: Lightweight validation was added instead of a formally safe regex mechanism.
- Impact on production readiness: Medium.
- Impact on developer experience, if applicable: Operators may not know which patterns are safe.
- Impact on security or reliability, if applicable: Reliability/DoS risk.
- Whether it was mentioned in the prior review log: Yes; residual risk was accepted.
- Whether a previous fix claimed to address it: Pattern heuristics were added.
- Whether that previous fix is sufficient: Partially, not fully production-grade.
- Recommended remediation: Use a regex engine with timeouts or safe subset validation, and test worst-case inputs.
- Suggested validation or test: ReDoS corpus tests with strict time budgets.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-042: GET/DELETE Payload Query Serialization Uses Heuristic Secret Detection

- Category: Security / API design
- Severity: Medium
- Confidence: Medium
- File path or area: `packages/product-platform/src/product_platform/tool_gateway/invocation.py`
- Evidence: `_request_payload_kwargs()` sends non-path GET/DELETE payload fields as query params at `invocation.py:403-432`. It rejects keys containing a small token set at `invocation.py:24-32` and `417-424`, but other sensitive fields can still be serialized into URLs.
- Why it matters: URLs are commonly logged by proxies, upstreams, and observability tools.
- Root cause or likely root cause: The tool contract does not separate path/query/body schemas or require explicit query field allowlists.
- Impact on production readiness: Medium.
- Impact on developer experience, if applicable: Tool authors may not realize payload fields become query parameters.
- Impact on security or reliability, if applicable: Data leakage risk.
- Whether it was mentioned in the prior review log: Not specifically.
- Whether a previous fix claimed to address it: Secret-like query guard was likely added, but not enough.
- Whether that previous fix is sufficient: Partially.
- Recommended remediation: Require explicit query parameter schema/allowlist per GET/DELETE tool; default to rejecting unclassified fields.
- Suggested validation or test: Tests for sensitive but non-token-named fields and explicit query allowlists.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-043: Health Checker Persists Arbitrary Exception Summaries

- Category: Security / observability
- Severity: Low
- Confidence: Medium
- File path or area: `packages/product-platform/src/product_platform/tool_gateway/health.py`
- Evidence: `health.py:82-84` stores `_summarize_exception(exc)`, and `_summarize_exception()` at `health.py:94-96` returns class name plus exception text truncated to 300 chars.
- Why it matters: Exception text can include private hostnames, proxy details, URLs, or infrastructure hints.
- Root cause or likely root cause: Operational usefulness is prioritized over sanitized storage.
- Impact on production readiness: Low.
- Impact on developer experience, if applicable: Useful diagnostics, but may expose internals in UI/API.
- Impact on security or reliability, if applicable: Information disclosure risk.
- Whether it was mentioned in the prior review log: Not specifically.
- Whether a previous fix claimed to address it: No.
- Whether that previous fix is sufficient: Not applicable.
- Recommended remediation: Normalize common network errors and sanitize URLs/hosts before persistence.
- Suggested validation or test: Health-check test where exception contains credentials/URL and persisted error is sanitized.
- Whether it should affect scoring: Yes, lightly.

### SDK-AUDIT-044: Discovery Pagination Can Skip Or Duplicate Tools During Concurrent Changes

- Category: Reliability / API semantics
- Severity: Low
- Confidence: Medium
- File path or area: SDK list APIs; `packages/product-platform/src/product_platform/tool_gateway/repository.py`
- Evidence: SDK `list_all_tools()` paginates by offset at `sdk.py:437-459`. Gateway repository orders tools by `d.updated_at DESC, d.id DESC` at `repository.py:321-331`.
- Why it matters: If tool definitions are updated between pages, offset pagination over a mutable order can skip or duplicate items.
- Root cause or likely root cause: Offset pagination without stable snapshot/cursor.
- Impact on production readiness: Low to medium.
- Impact on developer experience, if applicable: Large tool catalogs can produce inconsistent discovery results.
- Impact on security or reliability, if applicable: Reliability/contract consistency risk.
- Whether it was mentioned in the prior review log: Pagination was discussed but not this concurrency edge.
- Whether a previous fix claimed to address it: `list_all_tools()` was added.
- Whether that previous fix is sufficient: Partially.
- Recommended remediation: Use cursor pagination based on stable sort keys or document non-snapshot semantics.
- Suggested validation or test: Concurrent update during pagination test proving no duplicate/skip with cursor design.
- Whether it should affect scoring: Yes, lightly.

### SDK-AUDIT-045: `list_all_tools()` Accumulates Results Without A Total Cap

- Category: Reliability / SDK resource usage
- Severity: Low
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py`
- Evidence: `sdk.py:451-459` repeatedly extends a list until the last page is short, with no `max_total` argument.
- Why it matters: Very large catalogs can consume unbounded client memory.
- Root cause or likely root cause: Convenience API assumes bounded tool catalogs.
- Impact on production readiness: Low.
- Impact on developer experience, if applicable: Users lack a built-in guardrail for large tenants.
- Impact on security or reliability, if applicable: Client-side reliability/resource risk.
- Whether it was mentioned in the prior review log: Not specifically.
- Whether a previous fix claimed to address it: `list_all_tools()` was added.
- Whether that previous fix is sufficient: Mostly for normal catalogs, not extreme cases.
- Recommended remediation: Add optional `max_total` or streaming iterator API.
- Suggested validation or test: SDK test that max-total stops pagination and raises/returns partial result intentionally.
- Whether it should affect scoring: Yes, lightly.

### SDK-AUDIT-046: API App Is A Large Monolith

- Category: Maintainability / architecture
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/api/app.py`
- Evidence: `app.py` is 10,969 lines. The Tool Gateway invocation route, auth middleware, system config, health, and many unrelated product areas live in the same file.
- Why it matters: Large monolithic route files increase review cost, change risk, and likelihood of cross-feature regressions.
- Root cause or likely root cause: Product routes were accumulated in one FastAPI app factory without module decomposition.
- Impact on production readiness: Medium.
- Impact on developer experience, if applicable: New contributors have to navigate a very large file to change gateway behavior.
- Impact on security or reliability, if applicable: Maintainability risk can become security/reliability risk.
- Whether it was mentioned in the prior review log: Maintainability concerns were discussed generally.
- Whether a previous fix claimed to address it: No meaningful decomposition claimed.
- Whether that previous fix is sufficient: Not applicable.
- Recommended remediation: Extract Tool Gateway routes/middleware, system routes, and other domains into routers/modules.
- Suggested validation or test: Refactor under existing test coverage; add import-level route registration tests.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-047: SDK Source Is Duplicated Between Standalone And Product Packages

- Category: Maintainability / release consistency
- Severity: Medium
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway`; `packages/product-platform/src/ophanix_tool_gateway`
- Evidence: Both packages contain full copies of `sdk.py` and `__init__.py`; `wc -l` shows 1,720-line copies. Fresh `cmp` showed they match now, but no symlink or release validator parity enforcement exists.
- Why it matters: Future changes can land in one copy and not the other.
- Root cause or likely root cause: Product package re-exports the SDK for compatibility without sharing one source of truth.
- Impact on production readiness: Medium.
- Impact on developer experience, if applicable: Internal and external imports can diverge.
- Impact on security or reliability, if applicable: Release consistency risk.
- Whether it was mentioned in the prior review log: Yes, duplicated source ownership was a residual cap.
- Whether a previous fix claimed to address it: Current source parity exists.
- Whether that previous fix is sufficient: No automated enforcement in release validator.
- Recommended remediation: Use a shared source path, generated vendored copy with check, or CI parity gate.
- Suggested validation or test: CI parity test comparing all files under both `ophanix_tool_gateway` package directories.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-048: SDK Lacks Generated API Reference

- Category: Documentation / DX
- Severity: Low
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/README.md`
- Evidence: README has a manual API reference section at `README.md:61-102`, but no generated docs/site or complete function/class reference was found.
- Why it matters: Manual docs can drift and do not expose all constructor details, dataclass fields, or error attributes in a navigable reference.
- Root cause or likely root cause: Lightweight package docs were prioritized.
- Impact on production readiness: Low.
- Impact on developer experience, if applicable: SDK consumers may need to read source for full behavior.
- Impact on security or reliability, if applicable: Indirect DX/reliability impact.
- Whether it was mentioned in the prior review log: Yes.
- Whether a previous fix claimed to address it: README was expanded.
- Whether that previous fix is sufficient: Partially.
- Recommended remediation: Generate API reference from type-annotated source and publish it with the package docs.
- Suggested validation or test: Docs build check and API symbol coverage check.
- Whether it should affect scoring: Yes, lightly.

### SDK-AUDIT-049: Production Credential Issuance Path Is Under-Documented For SDK Consumers

- Category: Documentation / adoption
- Severity: Medium
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/README.md`; `packages/product-platform/README.md`
- Evidence: SDK README says tokens are issued by Ophanix at `README.md:20-26`, but does not link to exact API/CLI/admin workflow for obtaining, rotating, or scoping production gateway tokens.
- Why it matters: SDK adoption begins with credential issuance; unclear token acquisition slows or blocks integration.
- Root cause or likely root cause: SDK docs focus on using a token, not provisioning one.
- Impact on production readiness: Medium for external adoption.
- Impact on developer experience, if applicable: Integrators must search product-platform APIs or ask maintainers.
- Impact on security or reliability, if applicable: Poor docs can lead to unsafe token handling or overbroad scopes.
- Whether it was mentioned in the prior review log: Docs/adoption checklist issues were mentioned.
- Whether a previous fix claimed to address it: README was expanded.
- Whether that previous fix is sufficient: Partially.
- Recommended remediation: Add a credential issuance and rotation guide with API examples and scope/resource examples.
- Suggested validation or test: New-user docs walkthrough from no token to first successful SDK call.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-050: Security Policy Lacks Concrete Private Intake Contact

- Category: Security / governance
- Severity: Low
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/SECURITY.md`
- Evidence: `SECURITY.md:12-15` says to use the repository security process or private organization channel, but does not name a security email, GitHub private vulnerability reporting URL, or explicit intake.
- Why it matters: Vulnerability reporters need a concrete confidential channel.
- Root cause or likely root cause: Generic security policy placeholder.
- Impact on production readiness: Low.
- Impact on developer experience, if applicable: Reporters may be unsure where to file sensitive issues.
- Impact on security or reliability, if applicable: Security response delay risk.
- Whether it was mentioned in the prior review log: Security policy was claimed added.
- Whether a previous fix claimed to address it: Yes.
- Whether that previous fix is sufficient: Partially.
- Recommended remediation: Add exact private reporting method and escalation path.
- Suggested validation or test: Documentation review confirms reporter can file without public disclosure.
- Whether it should affect scoring: Yes, lightly.

### SDK-AUDIT-051: Docs Overstate Response Cap Strength

- Category: Documentation / reliability
- Severity: Medium
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/README.md`; `packages/product-platform/README.md`; SDK/runtime code
- Evidence: SDK README says responses are capped before JSON parsing at `README.md:78-79` and `153-154`; product README describes upstream response caps at `README.md:88`. Code checks caps before JSON parsing but after HTTPX body materialization as described in SDK-AUDIT-008.
- Why it matters: Operators may assume memory-exhaustion protection is stronger than it is.
- Root cause or likely root cause: Documentation describes parse-level behavior, not transport/read-level behavior.
- Impact on production readiness: Medium.
- Impact on developer experience, if applicable: Misleading reliability expectations.
- Impact on security or reliability, if applicable: Resource-exhaustion risk is underdocumented.
- Whether it was mentioned in the prior review log: Response caps were claimed.
- Whether a previous fix claimed to address it: Yes.
- Whether that previous fix is sufficient: No.
- Recommended remediation: Clarify current cap semantics and implement streaming caps.
- Suggested validation or test: Docs review tied to streaming cap implementation tests.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-052: Docs Claim OpenAPI Is Gated But Runtime Alias Contradicts It

- Category: Documentation / cross-file consistency
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/README.md`; `packages/product-platform/src/product_platform/api/app.py`
- Evidence: `README.md:92` says API docs and OpenAPI are enabled by default only in local/test. `app.py:3045-3049` always exposes `/api/openapi.json`.
- Why it matters: Deployment docs are inaccurate for information-exposure posture.
- Root cause or likely root cause: Runtime alias was added after docs or not included in docs gating.
- Impact on production readiness: Medium.
- Impact on developer experience, if applicable: Operators cannot rely on docs.
- Impact on security or reliability, if applicable: Security documentation mismatch.
- Whether it was mentioned in the prior review log: Related docs gating was discussed.
- Whether a previous fix claimed to address it: Production docs gating was claimed.
- Whether that previous fix is sufficient: No.
- Recommended remediation: Fix runtime gating and update docs to match.
- Suggested validation or test: Production-mode docs/OpenAPI route tests and README verification.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-053: Direct HTTP Fixture Tokens Remain In Source

- Category: Security / examples
- Severity: Low
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/tool_gateway/direct_http_examples.py`; docs
- Evidence: `direct_http_examples.py:22-23` defines deterministic local-only allowed/denied tokens. Product README warns at `README.md:94` that direct HTTP examples and fixture tokens are local-only.
- Why it matters: Even with warnings, scanners and copy-paste users can mistake fixture tokens for usable credentials.
- Root cause or likely root cause: Deterministic examples are useful for tests and docs.
- Impact on production readiness: Low.
- Impact on developer experience, if applicable: Helpful for demos but risky for novices.
- Impact on security or reliability, if applicable: Low security/DX risk.
- Whether it was mentioned in the prior review log: Yes.
- Whether a previous fix claimed to address it: Warnings were added.
- Whether that previous fix is sufficient: Mostly, but residual risk remains.
- Recommended remediation: Keep fixtures clearly namespaced and ensure they are never accepted outside seeded local demo mode.
- Suggested validation or test: Production-mode test proving fixture tokens cannot authenticate unless explicitly seeded.
- Whether it should affect scoring: Yes, lightly.

### SDK-AUDIT-054: Dependency Version Strategy Does Not Prove Compatibility Across Ranges

- Category: Packaging / compatibility
- Severity: Low
- Confidence: Medium
- File path or area: `packages/ophanix-tool-gateway-sdk/pyproject.toml`; `packages/product-platform/pyproject.toml`; CI
- Evidence: SDK depends on `httpx>=0.27.0,<1.0` at SDK `pyproject.toml:15-17`; product-platform has broad FastAPI/httpx/jsonschema/Pydantic ranges at product `pyproject.toml:13-21`. CI installs current resolver results, not explicit min/latest matrices.
- Why it matters: Broad ranges can break consumers at old minimum or future maximum-adjacent versions.
- Root cause or likely root cause: Dependency ranges were chosen for flexibility without compatibility matrix.
- Impact on production readiness: Low to medium.
- Impact on developer experience, if applicable: Users with older lockfiles may see untested behavior.
- Impact on security or reliability, if applicable: Compatibility/reliability risk.
- Whether it was mentioned in the prior review log: Dependency audit was discussed, not range compatibility.
- Whether a previous fix claimed to address it: No.
- Whether that previous fix is sufficient: Not applicable.
- Recommended remediation: Add min-version and latest-version dependency matrix, or narrow ranges based on tested versions.
- Suggested validation or test: CI jobs with lowest supported dependencies and latest allowed dependencies.
- Whether it should affect scoring: Yes, lightly.

### SDK-AUDIT-055: Publish/Release Process Does Not Generate Or Verify SDK SBOM

- Category: Supply chain / release
- Severity: Medium
- Confidence: Medium
- File path or area: `.github/workflows/publish.yml`; SDK release docs
- Evidence: Publish workflow signs and attests artifacts at `publish.yml:89-98`, but no SDK-specific SBOM generation or SBOM verification step was found in the SDK release path.
- Why it matters: Production adopters often require SBOMs for dependency and vulnerability governance.
- Root cause or likely root cause: Release hardening focused on artifacts, twine, pip-audit, signing, and attestations.
- Impact on production readiness: Medium for enterprise adoption.
- Impact on developer experience, if applicable: Security reviewers need additional manual evidence.
- Impact on security or reliability, if applicable: Supply-chain transparency gap.
- Whether it was mentioned in the prior review log: Provenance/signing was discussed; SBOM not clearly closed.
- Whether a previous fix claimed to address it: Publish signing/attestation was claimed.
- Whether that previous fix is sufficient: Partially.
- Recommended remediation: Generate CycloneDX/SPDX SBOM for SDK and product-platform artifacts and upload/sign it.
- Suggested validation or test: Release validation fails if SBOM is missing or inconsistent with wheel metadata.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-056: Product Warning/Deprecation Debt Remains In Passing Tests

- Category: Maintainability / future compatibility
- Severity: Low
- Confidence: High
- File path or area: Product test run output; Pydantic/datetime usage
- Evidence: Full product test suite passed with 47 warnings, including Pydantic `json_encoders` deprecation and `datetime.utcnow()` deprecation warnings.
- Why it matters: Deprecations can become future breakages, especially under Python/Pydantic upgrades.
- Root cause or likely root cause: Older patterns remain in product code and dependencies.
- Impact on production readiness: Low.
- Impact on developer experience, if applicable: Warning noise can hide new warnings.
- Impact on security or reliability, if applicable: Future compatibility risk.
- Whether it was mentioned in the prior review log: Not specifically.
- Whether a previous fix claimed to address it: No.
- Whether that previous fix is sufficient: Not applicable.
- Recommended remediation: Track warnings as debt and make targeted warning categories fail once cleaned.
- Suggested validation or test: `pytest -W error` for selected packages after deprecation cleanup.
- Whether it should affect scoring: Yes, lightly.

### SDK-AUDIT-057: SDK Telemetry Hook Failures Are Only Debug-Logged

- Category: Observability / DX
- Severity: Low
- Confidence: Medium
- File path or area: `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py`
- Evidence: SDK defines telemetry hooks and imports `logging`; prior remediation notes describe hook exception containment. No public callback/error counter contract is documented in README.
- Why it matters: Applications may silently lose telemetry if hooks fail.
- Root cause or likely root cause: Hook failures are intentionally isolated from tool calls but not surfaced operationally.
- Impact on production readiness: Low.
- Impact on developer experience, if applicable: Integrators may not notice broken telemetry instrumentation.
- Impact on security or reliability, if applicable: Observability reliability risk.
- Whether it was mentioned in the prior review log: Telemetry hooks were claimed added.
- Whether a previous fix claimed to address it: Yes.
- Whether that previous fix is sufficient: Partially.
- Recommended remediation: Document hook failure semantics and optionally support an error hook or metric callback.
- Suggested validation or test: Test hook exception behavior and documented logging/metric result.
- Whether it should affect scoring: Yes, lightly.

### SDK-AUDIT-058: Public API Keeps Compatibility `status` Argument That Only Accepts Active

- Category: Public API / DX
- Severity: Low
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py`; SDK README
- Evidence: `list_tools()` exposes `status: Literal["active"] | None` at `sdk.py:423-430`; README `README.md:96-99` says legacy `status="active"` remains accepted only for compatibility.
- Why it matters: A public parameter that cannot vary meaningfully creates confusion and future breaking-change pressure.
- Root cause or likely root cause: Backward compatibility with earlier API shape.
- Impact on production readiness: Low.
- Impact on developer experience, if applicable: Users may search for inactive/draft tool discovery support that cannot work.
- Impact on security or reliability, if applicable: Minimal.
- Whether it was mentioned in the prior review log: Gateway-safe discovery shape was discussed.
- Whether a previous fix claimed to address it: Compatibility behavior was documented.
- Whether that previous fix is sufficient: Mostly, but still an API wart.
- Recommended remediation: Deprecate the parameter or document a removal timeline.
- Suggested validation or test: Deprecation warning or docs test for accepted values.
- Whether it should affect scoring: Yes, lightly.

## Issues Grouped By Category

- Runtime behavior: SDK-AUDIT-001, SDK-AUDIT-002, SDK-AUDIT-008, SDK-AUDIT-009, SDK-AUDIT-015, SDK-AUDIT-043.
- Security: SDK-AUDIT-007, SDK-AUDIT-009, SDK-AUDIT-010, SDK-AUDIT-012, SDK-AUDIT-013, SDK-AUDIT-033, SDK-AUDIT-034, SDK-AUDIT-035, SDK-AUDIT-036, SDK-AUDIT-037, SDK-AUDIT-038, SDK-AUDIT-039, SDK-AUDIT-041, SDK-AUDIT-042, SDK-AUDIT-050, SDK-AUDIT-053, SDK-AUDIT-055.
- Reliability: SDK-AUDIT-001, SDK-AUDIT-002, SDK-AUDIT-003, SDK-AUDIT-004, SDK-AUDIT-006, SDK-AUDIT-008, SDK-AUDIT-012, SDK-AUDIT-013, SDK-AUDIT-014, SDK-AUDIT-020, SDK-AUDIT-040, SDK-AUDIT-044, SDK-AUDIT-045, SDK-AUDIT-056, SDK-AUDIT-057.
- Public API and DX: SDK-AUDIT-005, SDK-AUDIT-016, SDK-AUDIT-017, SDK-AUDIT-031, SDK-AUDIT-048, SDK-AUDIT-049, SDK-AUDIT-058.
- Testing: SDK-AUDIT-018, SDK-AUDIT-019, SDK-AUDIT-020, SDK-AUDIT-021.
- Packaging and release: SDK-AUDIT-025, SDK-AUDIT-026, SDK-AUDIT-027, SDK-AUDIT-028, SDK-AUDIT-029, SDK-AUDIT-030, SDK-AUDIT-031, SDK-AUDIT-032, SDK-AUDIT-054, SDK-AUDIT-055.
- Documentation and consistency: SDK-AUDIT-010, SDK-AUDIT-011, SDK-AUDIT-048, SDK-AUDIT-049, SDK-AUDIT-050, SDK-AUDIT-051, SDK-AUDIT-052, SDK-AUDIT-058.
- Maintainability: SDK-AUDIT-021, SDK-AUDIT-023, SDK-AUDIT-024, SDK-AUDIT-046, SDK-AUDIT-047, SDK-AUDIT-056.

## Critical And High-Severity Blockers

No current issue was assigned Critical with high confidence.

High-severity blockers:

- SDK-AUDIT-001: Manual upstream health check uses async HTTP client in synchronous checker.
- SDK-AUDIT-002: Tool invocation holds DB transaction open across upstream network call.
- SDK-AUDIT-003: Product runtime DB layer is SQLite-only with one shared connection.
- SDK-AUDIT-005: Upstream authentication is unsupported beyond `auth_mode="none"`.
- SDK-AUDIT-006: Tool invocation lacks idempotency/safe retry contract.
- SDK-AUDIT-007: Upstream URL validation has DNS failure/rebinding gaps.
- SDK-AUDIT-008: Response byte caps are checked after body materialization.
- SDK-AUDIT-009: Inactive response policy can bypass redaction while still allowing full response storage.
- SDK-AUDIT-020: No production-like load or multi-worker validation.
- SDK-AUDIT-025: Publish workflow references missing internal PyPI publishing docs and pipeline.

## Medium-Severity Production Risks

Medium issues:

- SDK-AUDIT-004, SDK-AUDIT-010, SDK-AUDIT-012, SDK-AUDIT-013, SDK-AUDIT-015, SDK-AUDIT-016, SDK-AUDIT-018, SDK-AUDIT-019, SDK-AUDIT-021, SDK-AUDIT-022, SDK-AUDIT-024, SDK-AUDIT-026, SDK-AUDIT-029, SDK-AUDIT-031, SDK-AUDIT-033, SDK-AUDIT-034, SDK-AUDIT-035, SDK-AUDIT-037, SDK-AUDIT-041, SDK-AUDIT-042, SDK-AUDIT-046, SDK-AUDIT-047, SDK-AUDIT-049, SDK-AUDIT-051, SDK-AUDIT-052, SDK-AUDIT-055.

## Low-Severity And Nit-Level Issues

Low issues:

- SDK-AUDIT-011, SDK-AUDIT-014, SDK-AUDIT-017, SDK-AUDIT-023, SDK-AUDIT-027, SDK-AUDIT-028, SDK-AUDIT-030, SDK-AUDIT-032, SDK-AUDIT-036, SDK-AUDIT-038, SDK-AUDIT-039, SDK-AUDIT-040, SDK-AUDIT-043, SDK-AUDIT-044, SDK-AUDIT-045, SDK-AUDIT-048, SDK-AUDIT-050, SDK-AUDIT-053, SDK-AUDIT-054, SDK-AUDIT-056, SDK-AUDIT-057, SDK-AUDIT-058.

No issue was classified as pure Nit because each item has at least some production, DX, security, reliability, or release implication.

## Prior Findings Status Table

| Prior finding area | Prior status claimed | Current status | Current issue IDs | Challenge |
|---|---|---|---|---|
| Standalone SDK package exists | Fixed | Mostly fixed | SDK-AUDIT-018, SDK-AUDIT-047 | Package exists and builds, but standalone test depth and duplicate source ownership remain concerns. |
| Gateway discovery route | Fixed | Mostly fixed | SDK-AUDIT-044, SDK-AUDIT-045, SDK-AUDIT-058 | Active-only discovery works, but pagination semantics and API wart remain. |
| SDK validation/redaction/errors | Fixed | Partially fixed | SDK-AUDIT-016, SDK-AUDIT-017, SDK-AUDIT-051 | Core behavior improved, but 403 classification, shallow immutability, and cap wording remain. |
| Async upstream execution | Fixed | Partially fixed | SDK-AUDIT-001, SDK-AUDIT-002 | Invocation path is async, but health route is broken and invocation transaction scope is unsafe. |
| Shared SQLite transaction interleaving | Fixed | Partially fixed | SDK-AUDIT-002, SDK-AUDIT-003, SDK-AUDIT-004 | Serialization added, but production DB architecture remains weak. |
| Upstream auth accepted but unused | Deferred/fail-closed | Still blocker | SDK-AUDIT-005 | Fail-closed avoids false support but does not solve protected upstream adoption. |
| Invocation idempotency | Deferred | Still blocker | SDK-AUDIT-006 | Documentation does not remove production retry ambiguity. |
| Rate limiting | Fixed with residual distributed caveat | Partially fixed | SDK-AUDIT-012, SDK-AUDIT-013, SDK-AUDIT-014 | Bounded in-process limiter exists but can be disabled and is not distributed. |
| SSRF hardening | Fixed with egress caveat | Partially fixed | SDK-AUDIT-007 | DNS failure/rebinding risk remains. |
| Response caps | Fixed | Partially fixed | SDK-AUDIT-008, SDK-AUDIT-051 | Caps happen before JSON parse, not before read/materialization. |
| Response redaction policy | Fixed | Partially fixed | SDK-AUDIT-009, SDK-AUDIT-040, SDK-AUDIT-041 | Inactive-policy storage behavior and regex runtime risks remain. |
| Credential scope validation | Fixed | Partially fixed | SDK-AUDIT-037 | Tool resources are checked, arbitrary non-tool resource types are not. |
| Production startup defaults | Fixed | Partially fixed | SDK-AUDIT-004, SDK-AUDIT-012, SDK-AUDIT-033 | Default session/dev login checks exist, but SQLite custom URLs, safety limits, and pepper are not enforced. |
| CI coverage | Fixed | Partially fixed | SDK-AUDIT-021, SDK-AUDIT-022, SDK-AUDIT-023, SDK-AUDIT-024 | Matrix exists, but product type checking, security gates, and install/lint rigor are weaker than production-grade. |
| Release validation | Fixed | Partially fixed | SDK-AUDIT-025, SDK-AUDIT-026, SDK-AUDIT-027, SDK-AUDIT-028, SDK-AUDIT-029, SDK-AUDIT-055 | SDK validator improved, but publish path and product validator remain under-evidenced. |
| Local DB artifact leakage | Fixed/accepted risk | Mostly fixed, residual local risk | SDK-AUDIT-032 | Not in package wheel, but local artifacts remain in package directory. |
| SDK beta status | Accepted risk | Still adoption cap | SDK-AUDIT-031 | Beta/pre-1.0 still blocks broad external confidence. |
| Production-like load/multi-worker tests | Deferred | Still blocker | SDK-AUDIT-020 | No current repo evidence closes this. |

## Scoring Matrix

| Score area | Current score | Prior latest score | Uphold/raise/lower | Exact reasons | Score cap | Next score requires | Reach 8 requires | Reach 9 requires |
|---|---:|---:|---|---|---|---|---|---|
| Implementation quality | 6 / 10 | 7 / 10 | Lowered | Functionality and tests are broad, but health route bug, long transaction scope, SQLite-only DB, missing idempotency, duplicated SDK source, and no load validation are material. | 6 | Fix SDK-AUDIT-001 and SDK-AUDIT-002, add live gateway test. | Add production DB/pooling strategy, idempotency, product type gate, and multi-worker validation. | Demonstrate clean architecture, robust live/load tests, enforced source parity, and release-executed evidence with only minor residual issues. |
| Ease of use | 7 / 10 | 7 / 10 | Upheld | SDK API and README are usable; errors and async support are decent. Still capped by unsupported upstream auth, beta status, credential issuance docs, generated API docs, and publishing opacity. | 7 | Add credential issuance guide and clarify publishing/docs inconsistencies. | Implement upstream auth and publish complete API reference/stability policy. | GA-level docs, examples, migration guides, stable semver, and proven external onboarding path. |
| Security and reliability | 5 / 10 | 6 / 10 | Lowered | Multiple high-severity unresolved risks remain: DNS rebinding, post-read caps, no idempotency, no upstream auth, local rate limiting, SQLite architecture, inactive-policy storage risk, and advisory CI security gate. | 5 | Fix health bug, response policy storage, production safety validation, and make security audit blocking. | Add streaming caps, runtime egress enforcement, distributed rate limiting, idempotency, upstream auth, and load tests. | Formal threat model, SBOM/provenance, production DB, chaos/failure tests, key rotation model, and mature operational controls. |

## Score Cap Explanation

Implementation quality cannot exceed 6 while a default manual health route is incorrectly wired, tool invocation keeps DB transactions open across upstream calls, and the product runtime remains SQLite-only.

Ease of use can hold at 7 because the SDK itself is reasonably ergonomic, but it cannot reach 8 while upstream auth is unsupported, the SDK is beta, and production credential issuance/publishing paths are not fully documented.

Security and reliability cannot exceed 5 under this strict scale because several unresolved high-severity issues interact: protected upstreams are unsupported, retry/idempotency is absent, SSRF controls rely on external egress enforcement, size caps are post-read, rate limiting is local, and production DB behavior is not production-grade.

Adversarial score-6-or-lower case: The repo has enough evidence for a 5-6 rating because high-severity runtime, release, security, and reliability risks remain despite passing tests. A production incident could plausibly arise from DB lock contention, duplicate retries, broken health state, local rate-limit bypass across workers, or oversized responses.

Adversarial score-8-or-higher case: To justify 8+, the repo would need implemented upstream auth, idempotency, streaming caps, production DB/pooling support, distributed rate limiting, live installed-wheel integration tests, load/multi-worker tests, and an executed/reviewable release pipeline. The current repo does not contain that evidence.

## Required Fixes To Reach Production Readiness

Minimum required before claiming controlled production readiness:

1. Fix SDK-AUDIT-001 so manual upstream health checks work with the default app HTTP client.
2. Fix SDK-AUDIT-002 by moving upstream calls outside DB transactions.
3. Establish a production database backend or explicitly limit support to single-node SQLite with operational guardrails.
4. Add production validation for gateway safety limits and token-hash pepper.
5. Fix inactive response policy full-response storage behavior.
6. Add live installed-wheel-to-running-gateway integration tests.
7. Make dependency/security audit failures block required CI or release gates.
8. Correct OpenAPI/docs gating contradictions.

## Required Fixes To Reach 8 Out Of 10

Required for a defensible 8:

1. Implement upstream authentication through secret references with rotation and audit.
2. Implement invocation idempotency keys, persistence, replay rules, and SDK support.
3. Replace post-read response caps with streaming byte caps.
4. Add production DB/pooling support and run tests against it.
5. Add distributed rate limiting or enforce an external limiter as a deployment prerequisite.
6. Add production-like concurrency/load/multi-worker tests.
7. Add SDK source parity enforcement or eliminate duplicated SDK source.
8. Complete publish path documentation and execute the release workflow in CI/release environment.

## Required Fixes To Reach 9 Out Of 10

Required for a defensible 9:

1. Complete formal threat model for Tool Gateway SDK/runtime, including SSRF, token storage, upstream auth, response storage, and retries.
2. Add safe-regex or timeout-enforced redaction and benchmarked response policy processing.
3. Add SBOM generation/signing/verification and complete provenance evidence.
4. Add GA stability policy, migration guide, generated API reference, and compatibility guarantees.
5. Add min/latest dependency compatibility matrix.
6. Add chaos/failure-mode tests for upstream timeouts, partial failures, DB contention, DNS rebinding, and retry replay.
7. Add operational dashboards/metrics guidance for gateway auth failures, denial rates, rate-limit hits, upstream health, response blocking, and SDK error classes.
8. Demonstrate at least one clean external adopter workflow from token issuance through production invocation and rotation.

## Recommended Remediation Order

1. Fix the broken manual upstream health route.
2. Shorten tool invocation transaction scope.
3. Fix response-policy inactive/full-storage behavior.
4. Add production settings validation for safety limits and pepper.
5. Correct OpenAPI/docs gating behavior and docs.
6. Add live installed-wheel gateway integration test.
7. Add product-platform release validator and CI security gate hardening.
8. Decide production DB architecture and implement/test it.
9. Design upstream auth and idempotency together.
10. Implement streaming size caps and distributed rate-limit strategy.
11. Add load/multi-worker/SSRF integration harness.
12. Resolve release provenance and SBOM gaps.
13. Improve docs, API reference, credential issuance guide, and stability policy.

## Validation Plan

Suggested validation after remediation:

- Unit tests:
  - Async health route with default app `httpx.AsyncClient`.
  - Inactive response policy with `store_full_response=True`.
  - Production settings failing for unsafe gateway limit values and missing pepper.
  - SDK 403 classification for generic versus policy-denial responses.
  - Credential legacy hash migration and pepper rotation behavior.
- Integration tests:
  - Installed SDK wheel calling a real running gateway over HTTP.
  - Slow upstream invocation while another DB write proceeds.
  - Chunked oversized upstream response stops reading at cap.
  - DNS rebinding/unresolved-host SSRF controls.
  - Multi-worker rate-limit behavior.
- Release tests:
  - Product-platform artifact validator.
  - SDK vendored/standalone parity check.
  - Publish workflow dry run with existing referenced pipeline docs.
  - SBOM generation and verification.
- Operational tests:
  - Load test with concurrent invocations, slow upstreams, denied calls, schema failures, and large responses.
  - Chaos test for upstream timeout, connection reset, malformed JSON, and cancelled requests.

## Final Strict Assessment

The current repository is a solid beta-quality implementation with meaningful remediation already completed, but it is not broadly production-ready.

The SDK client surface is usable, typed, and reasonably documented. The server-side gateway path is functional under tests. However, production readiness requires more than functional tests: the current repo still has high-severity runtime, reliability, security, and release-evidence gaps. The strict current score is:

- Implementation quality: 6 / 10.
- Ease of use: 7 / 10.
- Security and reliability: 5 / 10.

Controlled internal use is defensible only with strong external compensating controls: single-node expectations or a separately validated DB strategy, ingress/body/rate limits, egress firewalling, no protected upstream auth requirement, no automatic retries for mutating tools, and careful response-storage policy. Broad external production adoption is not defensible until upstream auth, idempotency, production DB/concurrency validation, streaming caps, and release provenance are closed.
