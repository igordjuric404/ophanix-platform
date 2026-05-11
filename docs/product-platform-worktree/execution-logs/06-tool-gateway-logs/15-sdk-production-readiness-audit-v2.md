# Tool Gateway SDK Production Readiness Audit - V2

Date: 2026-05-11

Scope: strict production-readiness audit of the Ophanix Tool Gateway SDK and the
relevant `ophanix-platform` repository surface: SDK API, server gateway runtime,
tests, packaging, release workflow, documentation, examples, CI, and adoption
path.

This audit is intentionally adversarial. It records issues found in the current
repository state. It does not implement fixes.

This V2 supersedes the conclusions in
`14-sdk-production-readiness-audit.md` where that file is contradicted by the
current repository state. In particular, the prior V1 audit contains stale
claims that the SDK package and product-platform CI/publish coverage were
untracked or omitted. Current verification found a clean worktree, visible CI
coverage for both packages, and successful wheel builds.

## Executive Summary

Current strict scores:

| Category | Current score | Prior score in requested log | Direction |
| --- | ---: | --- | --- |
| Implementation quality | 6 / 10 | Not assigned | New strict score |
| Ease of use | 6 / 10 | Not assigned | New strict score |
| Security and reliability | 5 / 10 | Not assigned | New strict score |

The standalone SDK builds, imports, exposes a typed sync/async API, and has
substantially more validation than the original review state. That is not enough
to call the current repository production-ready.

The strongest blockers are:

- Upstream URL validation permits loopback and DNS-resolved private targets,
  leaving a material SSRF risk.
- A hidden principal probe endpoint exposes credential context to any valid
  gateway bearer token holder.
- Gateway invocation performs blocking upstream HTTP calls inside an async
  FastAPI endpoint.
- Runtime database handling uses a single shared SQLite connection pattern that
  is not production-concurrency safe.
- The app can fall back to an in-memory seeded demo database.
- Upstream authentication supports only `auth_mode="none"`.
- Invocation has no idempotency or safe retry contract.
- Gateway and SDK response parsing lack a pre-parse response byte cap.
- Secret and security scans are advisory rather than blocking.
- Permission expiration is accepted as arbitrary text.
- Production-like load, concurrency, SSRF, real-upstream, and standalone SDK
  behavioral tests are still missing.

Validation performed:

- `230 passed` for `tests/test_tool_gateway_*.py`.
- `92 passed` for SDK remediation/package tests in `product-platform`.
- `84 passed` for selected runtime/auth/decision/forwarding/audit tests.
- Standalone SDK smoke test passed.
- SDK wheel built and installed successfully.
- Product-platform wheel built successfully.
- `compileall` passed for standalone SDK.
- Local `mypy` and `ruff` execution could not run because those tools were not
  installed.
- SDK `validate_release.py --skip-twine-check` failed locally because release
  extras were not installed.

## Prior Review Summary And Challenge

Prior file reviewed:

- `docs/product-platform-worktree/execution-logs/06-tool-gateway-logs/13-sdk-review-remediation.md`

Previously reported issues included:

- SDK discovery used the admin `/api/v1/tools` surface instead of
  gateway-scoped discovery.
- Discovery responses exposed internal fields.
- SDK lacked strong config, payload, URL, header, and response validation.
- SDK did not paginate `get_tool`.
- Token providers and error handling could expose sensitive values.
- No `EnvironmentTokenProvider`, `list_all_tools`, `clear_tool_cache`,
  `py.typed`, retry support, or async SDK.
- Tool definition typing did not match the gateway-safe response.
- Base URL validation allowed dangerous URL forms.
- Numeric and boolean config validation was loose.
- Discovery retries lacked `Retry-After` and jitter support.
- Standalone package did not exist or was incomplete.
- Credential scopes needed resource binding.
- Cache needed token partitioning.
- Package build and release validation were incomplete.

Claimed fixes included:

- New gateway discovery route `/api/v1/gateway/tools`.
- Gateway-safe `GatewayToolDefinitionResponse`.
- SDK validation for payloads, headers, base URLs, limits, token providers, and
  JSON shapes.
- Pagination, discovery retries, `Retry-After`, jitter, and
  token-fingerprinted cache keys.
- Redacted token repr and error diagnostics.
- Standalone `ophanix-tool-gateway-sdk` package.
- Compatibility re-export through `product_platform.tool_gateway`.
- Resource-bound credential scopes.
- Async client and token provider.
- Release validation and README expansion.

Claimed validation evidence included:

- SDK/package tests.
- Tool Gateway tests.
- Wheel build checks.
- Import smoke tests.
- Compile checks.

Scores assigned in the requested prior log:

- No explicit numeric scores were assigned in `13-sdk-review-remediation.md`.
- A later `14-sdk-production-readiness-audit.md` mentions older 8.x scores, but
  that file is not the requested review log and contains stale claims
  contradicted by current repository state.

Suspicious or under-evidenced prior conclusions:

- The prior remediation log gives too much credit for SDK-local hardening while
  under-reviewing server runtime behavior.
- Resource-bound scopes are implemented for enforcement, but issuance-time
  resource validation remains weak.
- Retry support exists for discovery, but invocation idempotency and retry
  semantics are still missing.
- Release validation exists, but local execution failed without release extras
  and provenance/tag cleanliness is not enforced.
- Gateway-safe discovery does not remove all runtime attack-surface concerns.
- Test counts are real, but mostly in-process and do not prove concurrency,
  load, SSRF resistance, real upstream behavior, or distributed deployment
  behavior.

Areas not deeply reviewed before:

- Gateway server runtime under production traffic.
- SSRF and upstream URL trust boundaries.
- Hidden/debug runtime endpoints.
- SQLite connection and transaction concurrency.
- CI security gate behavior.
- Dependency maintenance automation.
- Release provenance.
- Documentation contradictions.
- Standalone SDK test independence.
- Adoption path for protected upstream services.

## Repository Surface Reviewed

Relevant structure reviewed:

- `packages/ophanix-tool-gateway-sdk/`
  - `pyproject.toml`
  - `README.md`
  - `SECURITY.md`
  - `CHANGELOG.md`
  - `src/ophanix_tool_gateway/sdk.py`
  - `src/ophanix_tool_gateway/__init__.py`
  - `src/ophanix_tool_gateway/py.typed`
  - `tests/test_package_smoke.py`
  - `scripts/validate_release.py`
- `packages/product-platform/`
  - `src/ophanix_tool_gateway/*`
  - `src/product_platform/tool_gateway/*`
  - `src/product_platform/api/app.py`
  - `src/product_platform/api/settings.py`
  - `src/product_platform/db/*`
  - `src/product_platform/db/migrations/0003*`, `0050*` through `0055*`
  - `tests/test_tool_gateway_*.py`
  - `examples/tool-gateway-direct-http/*`
  - `README.md`
- Repository automation:
  - `.github/workflows/ci.yml`
  - `.github/workflows/publish.yml`
  - `.github/workflows/secret-scanning.yml`
  - `.github/workflows/security-scan.yml`
  - `.github/dependabot.yml`

## Exhaustive Issue Register

Each issue includes ID, title, category, severity, confidence, evidence,
production/DX/security impact, prior status, recommended remediation,
validation, and scoring impact.

### SDK-AUDIT-001 - Hidden principal probe endpoint exposes credential context

- Category: Security/API.
- Severity: High.
- Confidence: High.
- File or area: `packages/product-platform/src/product_platform/api/app.py:3027-3038`,
  `packages/product-platform/src/product_platform/tool_gateway/auth.py:45-54`.
- Evidence: `/api/v1/gateway/principal-probe` returns `GatewayPrincipal`,
  including credential ID, scopes, scope grants, tenant ID, agent ID, and
  request ID. It is hidden from OpenAPI but still callable.
- Why it matters: Any valid gateway bearer token holder can inspect credential
  scope structure and authorization context.
- Root cause: Debug/test endpoint left active in runtime app.
- Production-readiness impact: Exposes unnecessary attack surface and
  reconnaissance data.
- DX impact: Creates an undocumented runtime endpoint consumers may discover and
  rely on.
- Security or reliability impact: Information disclosure.
- Mentioned in prior review log: No.
- Previous fix claimed: No.
- Previous fix sufficient: Not applicable.
- Recommended remediation: Remove the endpoint or hard-gate it by environment
  and admin-only authorization, and return only minimal non-sensitive data.
- Suggested validation: Production-mode route table test and HTTP test must
  prove the endpoint is unavailable or admin-only.
- Should affect scoring: Yes.

### SDK-AUDIT-002 - Upstream URL validation permits loopback and DNS-private SSRF

- Category: Security/SSRF.
- Severity: Critical.
- Confidence: High.
- File or area: `packages/product-platform/src/product_platform/tool_gateway/models.py:458-477`,
  `models.py:512-538`.
- Evidence: URL validation permits loopback hosts and only checks IP literals.
  It does not resolve hostnames before deciding whether a target is private,
  loopback, link-local, or otherwise forbidden.
- Why it matters: A configured tool upstream can target local services, private
  network services, sidecars, admin ports, or DNS names that resolve to internal
  addresses.
- Root cause: Server-side URL validation is incomplete and explicitly treats
  loopback as allowed.
- Production-readiness impact: Material blocker for running the gateway in
  production network environments.
- DX impact: Documentation suggests safety that the code does not fully provide.
- Security or reliability impact: SSRF and lateral movement risk.
- Mentioned in prior review log: The prior log claimed URL hardening generally,
  but not this server-side SSRF boundary.
- Previous fix claimed: Partial URL validation.
- Previous fix sufficient: No.
- Recommended remediation: Block loopback, private, link-local, multicast,
  reserved, and metadata targets by default; resolve DNS and validate all
  resolved addresses; prevent DNS rebinding; add explicit allowlist mode for
  trusted private targets.
- Suggested validation: Tests for `localhost`, `127.0.0.1`, IPv6 loopback,
  private DNS, rebinding simulation, metadata hostnames, and redirects.
- Should affect scoring: Yes. This caps security and reliability at 5.

### SDK-AUDIT-003 - Blocking upstream HTTP calls run inside async endpoint

- Category: Runtime/Reliability.
- Severity: High.
- Confidence: High.
- File or area: `packages/product-platform/src/product_platform/api/app.py:3070-3405`,
  `packages/product-platform/src/product_platform/tool_gateway/invocation.py:79-146`.
- Evidence: The invocation endpoint is async, but `HttpToolInvocationExecutor`
  uses synchronous `httpx.Client.request()`.
- Why it matters: Slow upstream calls can block the event loop and degrade
  unrelated requests.
- Root cause: Sync executor reused in async web path.
- Production-readiness impact: Availability and latency risk under load.
- DX impact: Consumers see unpredictable latency and timeouts.
- Security or reliability impact: Event-loop starvation and exhaustion risk.
- Mentioned in prior review log: No.
- Previous fix claimed: Async SDK was claimed, but server runtime async was not.
- Previous fix sufficient: No.
- Recommended remediation: Use `httpx.AsyncClient` and await upstream calls, or
  isolate synchronous calls in a bounded worker pool.
- Suggested validation: Concurrent load test with slow upstreams proves unrelated
  requests remain responsive.
- Should affect scoring: Yes.

### SDK-AUDIT-004 - Shared SQLite connection and transaction handling are not production-safe

- Category: Runtime/Reliability.
- Severity: High.
- Confidence: High.
- File or area: `packages/product-platform/src/product_platform/db/connection.py:12-37`,
  `packages/product-platform/src/product_platform/db/migrator.py:49`.
- Evidence: The DB layer caches a single SQLite connection and uses `BEGIN`
  without an application lock. The connection is opened with
  `check_same_thread=False`.
- Why it matters: Concurrent requests can interleave transactions, hit
  `database is locked`, or corrupt logical operation boundaries.
- Root cause: Local/dev SQLite pattern used in runtime path.
- Production-readiness impact: Serious incident risk under concurrent traffic.
- DX impact: Failures are nondeterministic and hard to reproduce.
- Security or reliability impact: Availability and data consistency risk.
- Mentioned in prior review log: No.
- Previous fix claimed: No.
- Previous fix sufficient: Not applicable.
- Recommended remediation: Use per-request/session DB connections with a real
  production database and pooling, or serialize SQLite only in explicit dev mode.
- Suggested validation: Parallel invocation/auth/audit stress tests.
- Should affect scoring: Yes.

### SDK-AUDIT-005 - App can fall back to an in-memory seeded demo database

- Category: Runtime/Deployment.
- Severity: High.
- Confidence: High.
- File or area: `packages/product-platform/src/product_platform/api/app.py:945-954`.
- Evidence: `_audit_database()` creates `sqlite3.connect(":memory:")`, migrates,
  and seeds demo data when no DB is injected.
- Why it matters: A misconfigured deployment can start successfully with
  non-persistent demo state.
- Root cause: Demo/test fallback remains in runtime app construction.
- Production-readiness impact: Data loss and demo-data exposure risk.
- DX impact: Misconfiguration looks like a working service.
- Security or reliability impact: Persistence and integrity failure.
- Mentioned in prior review log: No.
- Previous fix claimed: No.
- Previous fix sufficient: Not applicable.
- Recommended remediation: Fail startup outside explicit test/dev mode if no
  configured database is available.
- Suggested validation: Production-mode startup without DB must fail.
- Should affect scoring: Yes.

### SDK-AUDIT-006 - Upstream authentication supports only auth_mode="none"

- Category: Security/Adoption.
- Severity: High.
- Confidence: High.
- File or area: `packages/product-platform/src/product_platform/tool_gateway/models.py:15`,
  `models.py:199-206`, `invocation.py:123-128`.
- Evidence: Supported upstream auth modes are limited to `{"none"}` and the
  executor rejects any other mode.
- Why it matters: Production teams usually need to call protected upstream
  services.
- Root cause: Upstream auth model was introduced before auth implementations.
- Production-readiness impact: Major adoption blocker for real production
  integrations.
- DX impact: Forces teams into unauthenticated services, sidecars, or custom
  workarounds.
- Security or reliability impact: Encourages unsafe network designs.
- Mentioned in prior review log: No.
- Previous fix claimed: No.
- Previous fix sufficient: Not applicable.
- Recommended remediation: Implement secret-backed bearer/API-key/mTLS or signed
  upstream auth modes with rotation and redaction.
- Suggested validation: Integration tests for each supported upstream auth mode.
- Should affect scoring: Yes.

### SDK-AUDIT-007 - Tool invocation lacks idempotency and safe retry contract

- Category: Reliability/API.
- Severity: High.
- Confidence: High.
- File or area: `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py:330-402`,
  `packages/product-platform/src/product_platform/api/app.py:3070-3405`.
- Evidence: Discovery has retries, but invocation has no idempotency key,
  dedupe, retry classification, or documented safe retry contract.
- Why it matters: Consumers cannot safely retry after timeout or partial
  failure, especially for mutating tools.
- Root cause: Invocation reliability semantics were deferred.
- Production-readiness impact: Duplicate side effects or lost operations.
- DX impact: Callers must invent their own idempotency model.
- Security or reliability impact: Reliability and correctness risk.
- Mentioned in prior review log: The prior log focused on discovery retries.
- Previous fix claimed: Discovery retry support only.
- Previous fix sufficient: No.
- Recommended remediation: Add idempotency keys, server-side dedupe, retryable
  error taxonomy, and docs.
- Suggested validation: Timeout-after-upstream-success and duplicate-key replay
  tests.
- Should affect scoring: Yes.

### SDK-AUDIT-008 - Gateway and SDK parse response bodies without pre-parse byte cap

- Category: Reliability/Security.
- Severity: High.
- Confidence: High.
- File or area: `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py:1285-1295`,
  `packages/product-platform/src/product_platform/tool_gateway/invocation.py:224-231`,
  `packages/product-platform/src/product_platform/tool_gateway/response.py:16-58`.
- Evidence: SDK and executor call `response.json()` before a hard byte limit is
  enforced. Policy size checks happen after parsing.
- Why it matters: Large JSON responses can consume memory and CPU before being
  blocked.
- Root cause: Response size controls are post-parse or text-fallback-only.
- Production-readiness impact: Availability risk from oversized upstream or
  gateway responses.
- DX impact: Failures may be process-level rather than structured errors.
- Security or reliability impact: Memory DoS risk.
- Mentioned in prior review log: Prior payload limits were claimed, not
  response pre-parse caps.
- Previous fix claimed: Partial validation hardening.
- Previous fix sufficient: No.
- Recommended remediation: Stream or cap response bytes before JSON parsing;
  enforce content-length and read limits.
- Suggested validation: Large JSON upstream/gateway response must fail
  boundedly.
- Should affect scoring: Yes.

### SDK-AUDIT-009 - Secret and security scans are advisory, not blocking

- Category: CI/Supply Chain.
- Severity: High.
- Confidence: High.
- File or area: `.github/workflows/secret-scanning.yml`,
  `.github/workflows/security-scan.yml`.
- Evidence: Gitleaks/security-scan steps use `continue-on-error` or warning-only
  behavior.
- Why it matters: Secrets or vulnerabilities can merge while checks appear to
  exist.
- Root cause: Security workflows are configured as advisory.
- Production-readiness impact: Weak release governance.
- DX impact: Maintainers can misread advisory checks as enforcement.
- Security or reliability impact: Credential and dependency exposure risk.
- Mentioned in prior review log: No.
- Previous fix claimed: No.
- Previous fix sufficient: Not applicable.
- Recommended remediation: Make scanners blocking with explicit baseline and
  allowlist process.
- Suggested validation: Seeded test secret must fail CI.
- Should affect scoring: Yes.

### SDK-AUDIT-010 - Permission expiration is accepted as arbitrary text

- Category: Authorization/Data Integrity.
- Severity: High.
- Confidence: High.
- File or area: `packages/product-platform/src/product_platform/tool_gateway/models.py:323-361`.
- Evidence: `expires_at` validators only strip strings. Authorization storage
  and queries rely on text values.
- Why it matters: Malformed expiration values can cause grants to expire
  incorrectly or not at all.
- Root cause: Missing datetime parsing and canonical storage.
- Production-readiness impact: Authorization correctness risk.
- DX impact: Hard-to-debug access behavior.
- Security or reliability impact: Stale or invalid grants may be honored.
- Mentioned in prior review log: No.
- Previous fix claimed: No.
- Previous fix sufficient: Not applicable.
- Recommended remediation: Parse timezone-aware datetimes at the API boundary
  and store canonical ISO or epoch values.
- Suggested validation: Malformed, timezone, past, and future expiration tests.
- Should affect scoring: Yes.

### SDK-AUDIT-011 - Gateway token hashes use plain SHA-256 without pepper

- Category: Security/Credential Storage.
- Severity: Medium.
- Confidence: High.
- File or area: `packages/product-platform/src/product_platform/agents/credentials.py:25-28`,
  `packages/product-platform/src/product_platform/tool_gateway/auth.py:102-105`.
- Evidence: Credential tokens are hashed using deterministic SHA-256.
- Why it matters: Database compromise enables offline guessing if token entropy
  is weak or fixture-like tokens leak.
- Root cause: Fast lookup hash used without server-side secret hardening.
- Production-readiness impact: Credential storage hardening gap.
- DX impact: Rotation and storage guarantees are not clear.
- Security or reliability impact: Credential compromise blast-radius risk.
- Mentioned in prior review log: Token redaction was discussed, not storage
  hardening.
- Previous fix claimed: No sufficient fix.
- Previous fix sufficient: No.
- Recommended remediation: Use HMAC with a server-side pepper for lookup, require
  high-entropy generated tokens, and document rotation.
- Suggested validation: Migration and verification tests for peppered hashes.
- Should affect scoring: Yes.

### SDK-AUDIT-012 - Runtime rate limiter is process-local and unbounded

- Category: Reliability/Security.
- Severity: Medium.
- Confidence: High.
- File or area: `packages/product-platform/src/product_platform/api/app.py:666-690`,
  `app.py:749`.
- Evidence: Rate limit counters live in an in-memory dict with no distributed
  coordination or pruning.
- Why it matters: Multi-worker deployments are not protected and high-cardinality
  keys can grow memory.
- Root cause: Local limiter used as runtime protection.
- Production-readiness impact: Weak abuse protection.
- DX impact: README caveat exists, but runtime behavior still looks protective.
- Security or reliability impact: Brute-force and memory pressure risk.
- Mentioned in prior review log: No.
- Previous fix claimed: No.
- Previous fix sufficient: Not applicable.
- Recommended remediation: Use a distributed limiter or clearly dev-only limiter
  with bounded eviction.
- Suggested validation: Multi-worker and high-cardinality tests.
- Should affect scoring: Yes.

### SDK-AUDIT-013 - Correlation and request IDs are caller-controllable

- Category: Audit Integrity.
- Severity: Medium.
- Confidence: High.
- File or area: `packages/product-platform/src/product_platform/api/app.py:623-630`,
  `app.py:782-808`, `packages/product-platform/src/product_platform/tool_gateway/invocation.py:19-32`.
- Evidence: Request/correlation IDs are accepted from headers/body without strict
  length or format validation.
- Why it matters: Callers can spoof, collide, or inject noisy audit identifiers.
- Root cause: Caller-provided IDs are treated as trace IDs without strong
  normalization.
- Production-readiness impact: Weak audit integrity.
- DX impact: Trace correlation can become unreliable.
- Security or reliability impact: Forensic ambiguity.
- Mentioned in prior review log: No.
- Previous fix claimed: No.
- Previous fix sufficient: Not applicable.
- Recommended remediation: Generate authoritative server request IDs, store
  caller IDs separately, and validate length/charset.
- Suggested validation: Oversized, control-character, and collision tests.
- Should affect scoring: Yes.

### SDK-AUDIT-014 - Allow decisions are persisted before schema validation

- Category: Audit/Correctness.
- Severity: Medium.
- Confidence: High.
- File or area: `packages/product-platform/src/product_platform/api/app.py:3092-3158`.
- Evidence: Policy decision evaluation and persistence happen before tool input
  schema validation.
- Why it matters: Audit can show an allowed decision for a request that never
  became a valid invocation.
- Root cause: Authz decision and executable action lifecycle are ordered
  incorrectly.
- Production-readiness impact: Audit trail inconsistency.
- DX impact: Operators may misread invalid requests as allowed invocations.
- Security or reliability impact: Forensic ambiguity.
- Mentioned in prior review log: No.
- Previous fix claimed: No.
- Previous fix sufficient: Not applicable.
- Recommended remediation: Validate schema before persisting allow decisions, or
  persist an explicit validation-failed action.
- Suggested validation: Invalid payload should produce coherent decision/action
  records.
- Should affect scoring: Yes.

### SDK-AUDIT-015 - Response policy status appears ignored

- Category: Runtime/Security.
- Severity: Medium.
- Confidence: High.
- File or area: `packages/product-platform/src/product_platform/tool_gateway/response.py:16-58`,
  response policy repository path.
- Evidence: Runtime applies a response policy without checking whether its
  lifecycle status is active.
- Why it matters: Disabled or draft policies may still redact, block, or expose
  responses.
- Root cause: Policy lifecycle metadata is not enforced at runtime.
- Production-readiness impact: Admin intent and runtime behavior can diverge.
- DX impact: Confusing policy management.
- Security or reliability impact: Wrong data exposure or blocking behavior.
- Mentioned in prior review log: No.
- Previous fix claimed: No.
- Previous fix sufficient: Not applicable.
- Recommended remediation: Enforce active status in repository lookup or runtime
  policy processing.
- Suggested validation: Disabled policy must not affect a response.
- Should affect scoring: Yes.

### SDK-AUDIT-016 - Failed upstream response bodies can be returned to agents

- Category: Security/Data Exposure.
- Severity: Medium.
- Confidence: High.
- File or area: `packages/product-platform/src/product_platform/api/app.py:3321-3363`,
  `packages/product-platform/src/product_platform/tool_gateway/invocation.py:161-175`.
- Evidence: Failed execution responses include serialized execution output and
  upstream error details.
- Why it matters: Upstream stack traces or sensitive error bodies can reach SDK
  consumers.
- Root cause: Failure payloads are treated similarly to success payloads.
- Production-readiness impact: Sensitive error data leakage risk.
- DX impact: Error shape is inconsistent and may be noisy.
- Security or reliability impact: Data exposure.
- Mentioned in prior review log: Prior SDK error redaction does not cover this.
- Previous fix claimed: Partial error redaction.
- Previous fix sufficient: No.
- Recommended remediation: Hide failed upstream bodies by default and expose only
  sanitized diagnostics.
- Suggested validation: Upstream 500 containing a secret must not return that
  secret.
- Should affect scoring: Yes.

### SDK-AUDIT-017 - HTTP 3xx upstream responses are treated as success

- Category: Runtime Correctness.
- Severity: Medium.
- Confidence: High.
- File or area: `packages/product-platform/src/product_platform/tool_gateway/invocation.py:160-164`.
- Evidence: Success is defined as `200 <= status_code < 400`.
- Why it matters: Redirects can be reported as successful tool execution.
- Root cause: Broad HTTP success range.
- Production-readiness impact: Incorrect execution status.
- DX impact: Tool authors receive surprising behavior.
- Security or reliability impact: Redirect confusion and incomplete execution
  risk.
- Mentioned in prior review log: No.
- Previous fix claimed: No.
- Previous fix sufficient: Not applicable.
- Recommended remediation: Treat only expected 2xx responses as success unless
  redirect behavior is explicit.
- Suggested validation: 301, 302, and 307 upstream tests.
- Should affect scoring: Yes.

### SDK-AUDIT-018 - GET and DELETE payloads are serialized into query parameters

- Category: Security/API Ergonomics.
- Severity: Medium.
- Confidence: High.
- File or area: `packages/product-platform/src/product_platform/tool_gateway/invocation.py:202-221`,
  `invocation.py:234-238`.
- Evidence: GET/DELETE requests send the whole payload as query params, and path
  params are not removed from the query after substitution.
- Why it matters: Sensitive data can land in URLs, logs, caches, proxies, and
  duplicated path/query locations.
- Root cause: Generic payload-to-HTTP mapping.
- Production-readiness impact: Unsafe default mapping for sensitive data.
- DX impact: Tool authors need hidden knowledge of mapping rules.
- Security or reliability impact: Data exposure and upstream ambiguity.
- Mentioned in prior review log: No.
- Previous fix claimed: No.
- Previous fix sufficient: Not applicable.
- Recommended remediation: Use schema-driven parameter placement and reject
  sensitive fields in query parameters.
- Suggested validation: Path params are not duplicated; secret-like fields are
  rejected for query placement.
- Should affect scoring: Yes.

### SDK-AUDIT-019 - Redaction regexes are not sufficiently ReDoS-safe

- Category: Security/Reliability.
- Severity: Medium.
- Confidence: Medium.
- File or area: `packages/product-platform/src/product_platform/tool_gateway/response.py:73-77`,
  `response.py:80-128`, `response.py:156-166`.
- Evidence: User-provided regexes are compiled and applied over runtime strings.
  Validation blocks only a narrow set of nested-quantifier patterns.
- Why it matters: Pathological regex patterns can create CPU spikes.
- Root cause: Arbitrary regex execution in response processing.
- Production-readiness impact: Policy-driven DoS risk.
- DX impact: Policy authors receive incomplete safety feedback.
- Security or reliability impact: ReDoS risk.
- Mentioned in prior review log: No.
- Previous fix claimed: No.
- Previous fix sufficient: Not applicable.
- Recommended remediation: Use safe-regex constraints, timeouts, or a restricted
  pattern language.
- Suggested validation: Known catastrophic regex patterns must fail validation or
  execute within a hard bound.
- Should affect scoring: Yes.

### SDK-AUDIT-020 - Payload and audit summaries redact by key, not by value

- Category: Data Protection.
- Severity: Medium.
- Confidence: High.
- File or area: `packages/product-platform/src/product_platform/tool_gateway/decision.py:499-550`.
- Evidence: Summary redaction checks key names such as token/password/secret but
  does not redact secret-looking values under innocuous keys.
- Why it matters: Tokens or PII under names like `notes` or `message` can enter
  audit summaries.
- Root cause: Key-only heuristic redaction.
- Production-readiness impact: Sensitive data retention risk.
- DX impact: Users may overtrust audit redaction.
- Security or reliability impact: Data leakage and compliance risk.
- Mentioned in prior review log: Prior redaction focused SDK errors.
- Previous fix claimed: Partial redaction.
- Previous fix sufficient: No.
- Recommended remediation: Add value-pattern redaction and schema-driven
  sensitive hints.
- Suggested validation: Secret-looking values under non-sensitive keys must be
  redacted.
- Should affect scoring: Yes.

### SDK-AUDIT-021 - Credential scope issuance does not validate resource references

- Category: Authorization.
- Severity: Medium.
- Confidence: High.
- File or area: `packages/product-platform/src/product_platform/agents/credentials.py:597-618`.
- Evidence: Scope validation checks scope names against approved capabilities
  but does not validate `resource_type` or `resource_id` references.
- Why it matters: Typoed, stale, or unintended resource grants can be issued.
- Root cause: Resource-bound enforcement was added without complete issuance
  validation.
- Production-readiness impact: Authorization drift.
- DX impact: Broken grants are hard to diagnose.
- Security or reliability impact: Access-control ambiguity.
- Mentioned in prior review log: Resource-bound scopes were claimed.
- Previous fix claimed: Yes.
- Previous fix sufficient: Partial only.
- Recommended remediation: Validate resource references against tenant-owned
  resources during credential issuance.
- Suggested validation: Invalid tool/resource grants must be rejected.
- Should affect scoring: Yes.

### SDK-AUDIT-022 - Credential scope uniqueness can be bypassed for NULL resource IDs

- Category: Data Integrity/Authz.
- Severity: Low.
- Confidence: High.
- File or area: `packages/product-platform/src/product_platform/db/migrations/0003_agent_credentials.up.sql:36-44`.
- Evidence: The unique constraint includes nullable `resource_id`; SQLite treats
  NULLs as distinct.
- Why it matters: Duplicate wildcard scope rows can accumulate.
- Root cause: Nullable column in uniqueness constraint.
- Production-readiness impact: Policy data ambiguity.
- DX impact: Confusing credential inspection.
- Security or reliability impact: Low authorization data integrity risk.
- Mentioned in prior review log: No.
- Previous fix claimed: No.
- Previous fix sufficient: Not applicable.
- Recommended remediation: Use a sentinel value or partial unique indexes.
- Suggested validation: Duplicate wildcard insert must fail.
- Should affect scoring: Minor.

### SDK-AUDIT-023 - Runtime latency type mismatch between DB and models

- Category: Correctness/Portability.
- Severity: Low.
- Confidence: High.
- File or area: `packages/product-platform/src/product_platform/db/migrations/0055_tool_runtime_actions.up.sql`,
  runtime audit and invocation models.
- Evidence: DB stores `latency_ms INTEGER`; code uses floating-point latency.
- Why it matters: Precision can be lost or behavior can vary on stricter
  databases.
- Root cause: Schema/model drift.
- Production-readiness impact: Low observability accuracy risk.
- DX impact: Inconsistent typing.
- Security or reliability impact: Minor reliability/metrics issue.
- Mentioned in prior review log: No.
- Previous fix claimed: No.
- Previous fix sufficient: Not applicable.
- Recommended remediation: Align schema and model type.
- Suggested validation: Fractional latency persistence test.
- Should affect scoring: Minor.

### SDK-AUDIT-024 - SDK does not extract top-level gateway error codes

- Category: SDK DX/Error Handling.
- Severity: Medium.
- Confidence: High.
- File or area: `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py:1259-1278`,
  gateway API error handlers.
- Evidence: SDK checks nested `error.code` or `reason_code`, but not top-level
  `code`.
- Why it matters: Consumers lose machine-readable diagnostics for some gateway
  errors.
- Root cause: SDK and server error schemas are not fully aligned.
- Production-readiness impact: Weaker automated error handling.
- DX impact: Harder exception branching and troubleshooting.
- Security or reliability impact: Retry/auth handling ambiguity.
- Mentioned in prior review log: Prior claimed structured diagnostics.
- Previous fix claimed: Yes.
- Previous fix sufficient: No.
- Recommended remediation: Parse every documented error shape consistently.
- Suggested validation: 401, 422, and 500 gateway error code tests.
- Should affect scoring: Yes.

### SDK-AUDIT-025 - SDK maps every invocation HTTP 403 to ToolDeniedError

- Category: SDK Correctness/DX.
- Severity: Medium.
- Confidence: High.
- File or area: `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py:373-383`,
  `sdk.py:1246-1256`.
- Evidence: `call_tool()` raises `ToolDeniedError` for any HTTP 403 response.
- Why it matters: Proxy, WAF, generic gateway, or malformed 403 responses are
  incorrectly presented as policy denials.
- Root cause: Status-code-only classification.
- Production-readiness impact: Incorrect automated handling.
- DX impact: Misleading remediation path.
- Security or reliability impact: Wrong retry/escalation behavior.
- Mentioned in prior review log: Prior introduced denied errors.
- Previous fix claimed: Yes.
- Previous fix sufficient: Partial only.
- Recommended remediation: Require structured denial reason before raising
  `ToolDeniedError`; otherwise raise generic gateway error.
- Suggested validation: Generic 403 body test.
- Should affect scoring: Yes.

### SDK-AUDIT-026 - SDK cache returns mutable nested schema data

- Category: SDK Correctness.
- Severity: Medium.
- Confidence: High.
- File or area: `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py:626-637`,
  `sdk.py:1224-1243`.
- Evidence: Cached `ToolDefinition` instances expose mutable nested
  `input_schema`, `output_schema`, and shallow raw mappings.
- Why it matters: One consumer can mutate cached schema and affect later calls.
- Root cause: Shallow immutability.
- Production-readiness impact: Incorrect discovery data can leak across calls.
- DX impact: Surprising shared state.
- Security or reliability impact: Incorrect validation/display behavior.
- Mentioned in prior review log: Cache partitioning was claimed, not immutable
  cache data.
- Previous fix claimed: Partial.
- Previous fix sufficient: No.
- Recommended remediation: Deep-copy on return or deep-freeze cached structures.
- Suggested validation: Mutate returned schema, fetch again, assert unchanged.
- Should affect scoring: Yes.

### SDK-AUDIT-027 - SDK payload validation has no cycle protection

- Category: SDK Correctness.
- Severity: Low.
- Confidence: High.
- File or area: `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py:1423-1455`.
- Evidence: `_validate_json_value()` recursively walks mappings/lists without a
  visited set.
- Why it matters: Self-referential payloads raise `RecursionError` instead of a
  clean validation error.
- Root cause: Recursive validation without cycle detection.
- Production-readiness impact: Low local caller crash risk.
- DX impact: Poor error message.
- Security or reliability impact: Local reliability issue.
- Mentioned in prior review log: Payload validation was claimed.
- Previous fix claimed: Yes.
- Previous fix sufficient: Partial only.
- Recommended remediation: Track object IDs or pre-serialize safely.
- Suggested validation: Cyclic payload test.
- Should affect scoring: Minor.

### SDK-AUDIT-028 - SDK discovery caches are unbounded

- Category: SDK Reliability.
- Severity: Low.
- Confidence: High.
- File or area: `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py:314-319`,
  `sdk.py:483-499`.
- Evidence: Cache maps are TTL-based but have no size bound.
- Why it matters: Long-lived processes with many tokens/query variants can grow
  memory.
- Root cause: TTL cache without max entries.
- Production-readiness impact: Low memory pressure risk.
- DX impact: No cache sizing control.
- Security or reliability impact: Low reliability issue.
- Mentioned in prior review log: Cache partitioning was claimed.
- Previous fix claimed: Yes.
- Previous fix sufficient: Partial only.
- Recommended remediation: Use bounded LRU or configurable max cache entries.
- Suggested validation: Many-token cache eviction test.
- Should affect scoring: Minor.

### SDK-AUDIT-029 - list_tools(status="active") exposes a misleading parameter

- Category: SDK API Ergonomics.
- Severity: Low.
- Confidence: High.
- File or area: `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py:404-416`,
  `sdk.py:1162-1185`.
- Evidence: `status` accepts only `active` and is not sent to the server.
- Why it matters: Callers may expect inactive listing or server-side filtering.
- Root cause: Internal API shape leaked into gateway-safe SDK.
- Production-readiness impact: Low API clarity issue.
- DX impact: Confusing public API.
- Security or reliability impact: Low.
- Mentioned in prior review log: Active-only discovery was claimed.
- Previous fix claimed: Yes.
- Previous fix sufficient: Mostly, but API remains awkward.
- Recommended remediation: Remove the parameter or document it as fixed
  active-only.
- Suggested validation: Docs and signature review.
- Should affect scoring: Minor.

### SDK-AUDIT-030 - SDK event hook exceptions are swallowed silently

- Category: SDK Observability.
- Severity: Low.
- Confidence: High.
- File or area: `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py:642-648`
  and async equivalent.
- Evidence: `_emit_event()` catches all exceptions and returns.
- Why it matters: Telemetry/instrumentation failures disappear.
- Root cause: Defensive hook isolation without optional reporting.
- Production-readiness impact: Observability gap.
- DX impact: Debugging instrumentation is difficult.
- Security or reliability impact: Low observability issue.
- Mentioned in prior review log: No.
- Previous fix claimed: No.
- Previous fix sufficient: Not applicable.
- Recommended remediation: Add optional hook error logger or debug callback.
- Suggested validation: Hook exception is observable when logger is configured.
- Should affect scoring: Minor.

### SDK-AUDIT-031 - SDK errors do not expose retry metadata

- Category: SDK Reliability/DX.
- Severity: Low.
- Confidence: Medium.
- File or area: SDK error classes and retry-after parsing path.
- Evidence: `Retry-After` is used internally for discovery retry, but public
  exceptions do not consistently expose retry-after/status/header metadata.
- Why it matters: Consumers cannot make informed retry decisions.
- Root cause: Retry metadata is internal-only.
- Production-readiness impact: Retry behavior is harder to implement correctly.
- DX impact: Manual retry policies are under-informed.
- Security or reliability impact: Retry storm or under-retry risk.
- Mentioned in prior review log: Retry-after support was claimed.
- Previous fix claimed: Yes.
- Previous fix sufficient: Partial only.
- Recommended remediation: Include status, retry-after, request ID, and
  correlation ID consistently on exceptions.
- Suggested validation: 429/503 exception metadata tests.
- Should affect scoring: Minor to medium.

### SDK-AUDIT-032 - Direct HTTP callers bypass SDK payload hardening

- Category: API/Security.
- Severity: Medium.
- Confidence: Medium.
- File or area: `packages/product-platform/src/product_platform/tool_gateway/invocation.py:19-32`,
  SDK payload validation path.
- Evidence: Server accepts `payload: dict[str, Any]`; SDK enforces stricter
  finite/depth/item/string constraints.
- Why it matters: Non-SDK clients can send payloads the SDK would reject.
- Root cause: Validation is not centralized at the server boundary.
- Production-readiness impact: Direct HTTP behavior can diverge from SDK
  behavior.
- DX impact: Different clients see different validation rules.
- Security or reliability impact: Malformed payload edge-case risk.
- Mentioned in prior review log: SDK validation was claimed.
- Previous fix claimed: Yes.
- Previous fix sufficient: No for direct HTTP clients.
- Recommended remediation: Move core payload constraints to the server too.
- Suggested validation: Direct HTTP tests for NaN, deep, list-heavy, and
  string-heavy payloads.
- Should affect scoring: Yes.

### SDK-AUDIT-033 - Standalone SDK package has only a smoke test

- Category: Testing.
- Severity: Medium.
- Confidence: High.
- File or area: `packages/ophanix-tool-gateway-sdk/tests/test_package_smoke.py`.
- Evidence: Standalone SDK tests only check imports/exports. Behavioral SDK
  tests live under product-platform.
- Why it matters: Standalone package can drift or regress without its own local
  test suite catching behavior.
- Root cause: Tests were not moved with the package.
- Production-readiness impact: Release confidence gap.
- DX impact: Contributors get weak package-local feedback.
- Security or reliability impact: Regression risk.
- Mentioned in prior review log: Package smoke tests were claimed.
- Previous fix claimed: Yes.
- Previous fix sufficient: No.
- Recommended remediation: Move or duplicate SDK behavioral tests into the
  standalone package.
- Suggested validation: Standalone suite covers sync, async, errors, cache,
  payload validation, retries, and packaging.
- Should affect scoring: Yes.

### SDK-AUDIT-034 - No convincing production-like concurrency/load/SSRF integration tests

- Category: Testing/Reliability.
- Severity: Medium.
- Confidence: High.
- File or area: Tool Gateway test suite.
- Evidence: Current tests are broad but primarily in-process with `TestClient`,
  fake HTTP clients, and mock transports. They do not prove multi-worker,
  deployed, real-upstream, load, SSRF, or memory-limit behavior.
- Why it matters: The highest-risk runtime issues can survive unit/in-process
  coverage.
- Root cause: System tests were not added alongside runtime features.
- Production-readiness impact: High residual production uncertainty.
- DX impact: Adopters discover problems late.
- Security or reliability impact: Concurrency, SSRF, and memory risks remain
  under-tested.
- Mentioned in prior review log: Test counts were claimed.
- Previous fix claimed: Partial.
- Previous fix sufficient: No.
- Recommended remediation: Add async load tests, real upstream service tests,
  SSRF suites, and multi-worker tests.
- Suggested validation: CI job running these tests.
- Should affect scoring: Yes.

### SDK-AUDIT-035 - CI matrix appears to test SDK on unsupported Python 3.10

- Category: CI/Packaging.
- Severity: Medium.
- Confidence: High.
- File or area: `.github/workflows/ci.yml`,
  `packages/ophanix-tool-gateway-sdk/pyproject.toml`.
- Evidence: SDK requires Python `>=3.11`, while CI matrix includes 3.10 and does
  not exclude the SDK package from 3.10.
- Why it matters: CI can fail for unsupported interpreter or produce noisy
  signal.
- Root cause: Matrix/package support drift.
- Production-readiness impact: Release pipeline instability.
- DX impact: Confusing support policy.
- Security or reliability impact: Indirect reliability issue.
- Mentioned in prior review log: No.
- Previous fix claimed: No.
- Previous fix sufficient: Not applicable.
- Recommended remediation: Exclude SDK from Python 3.10 or lower the package
  requirement only if genuinely supported.
- Suggested validation: CI matrix expansion check.
- Should affect scoring: Yes.

### SDK-AUDIT-036 - Dependabot omits product-platform and standalone SDK Python packages

- Category: Supply Chain.
- Severity: Medium.
- Confidence: High.
- File or area: `.github/dependabot.yml`.
- Evidence: Dependabot pip directories do not include `packages/product-platform`
  or `packages/ophanix-tool-gateway-sdk`.
- Why it matters: Vulnerable dependencies may not receive automated update PRs.
- Root cause: New packages were not added to dependency maintenance config.
- Production-readiness impact: Patch latency.
- DX impact: Manual dependency maintenance burden.
- Security or reliability impact: Supply-chain risk.
- Mentioned in prior review log: No.
- Previous fix claimed: No.
- Previous fix sufficient: Not applicable.
- Recommended remediation: Add both package directories to Dependabot config.
- Suggested validation: Dependabot config validation.
- Should affect scoring: Yes.

### SDK-AUDIT-037 - Product-platform wheel lacks included license file

- Category: Packaging/Compliance.
- Severity: Low.
- Confidence: High.
- File or area: `packages/product-platform/pyproject.toml`, built wheel
  metadata.
- Evidence: Product-platform uses `license = {text = "MIT"}` and the built wheel
  did not include `License-File` metadata.
- Why it matters: Downstream compliance scanners may flag incomplete license
  metadata.
- Root cause: Package-level license file is not included in wheel config.
- Production-readiness impact: Procurement/compliance friction.
- DX impact: Installation review friction.
- Security or reliability impact: None directly.
- Mentioned in prior review log: No.
- Previous fix claimed: No.
- Previous fix sufficient: Not applicable.
- Recommended remediation: Include a license file using modern packaging
  metadata.
- Suggested validation: Wheel metadata contains `License-File`.
- Should affect scoring: Minor.

### SDK-AUDIT-038 - Local database artifacts exist in product-platform package directory

- Category: Repo Hygiene/Packaging.
- Severity: Low.
- Confidence: High.
- File or area: `packages/product-platform/ophanix_product.db`,
  `packages/product-platform/ophanix_product.db.backup.20260509152042`.
- Evidence: Local DB files exist in the package directory. `git ls-files`
  showed they are not tracked and the wheel build excluded them.
- Why it matters: Runtime artifacts in package roots can accidentally leak if
  packaging rules change.
- Root cause: Local runtime data generated beside package metadata.
- Production-readiness impact: Low packaging hygiene risk.
- DX impact: Noisy workspace.
- Security or reliability impact: Low accidental data exposure risk.
- Mentioned in prior review log: Later V1 audit overclaimed current packaging
  impact.
- Previous fix claimed: Exclusion currently works.
- Previous fix sufficient: Mostly for wheel, but source-tree hygiene remains.
- Recommended remediation: Move runtime DB outside package tree and keep
  sdist/wheel exclusion tests.
- Suggested validation: sdist and wheel content tests exclude DB files.
- Should affect scoring: Minor.

### SDK-AUDIT-039 - Release validator does not enforce clean worktree or tag/version match

- Category: Release.
- Severity: Low.
- Confidence: Medium.
- File or area: `packages/ophanix-tool-gateway-sdk/scripts/validate_release.py`.
- Evidence: Validator checks build/install/twine/pip-audit markers, but not git
  state, tag alignment, or release provenance expectations.
- Why it matters: Dirty or mismatched releases remain possible.
- Root cause: Artifact validation is separate from release governance.
- Production-readiness impact: Provenance gap.
- DX impact: Maintainers rely on convention.
- Security or reliability impact: Supply-chain/release integrity gap.
- Mentioned in prior review log: Release validation was claimed.
- Previous fix claimed: Yes.
- Previous fix sufficient: Partial only.
- Recommended remediation: Add strict release mode with clean worktree, tag, and
  version checks.
- Suggested validation: Dirty tree and version mismatch tests.
- Should affect scoring: Minor.

### SDK-AUDIT-040 - Product-platform README has stale test instructions

- Category: Documentation/DX.
- Severity: Low.
- Confidence: High.
- File or area: `packages/product-platform/README.md`.
- Evidence: README says to run tests via `unittest`, while project config and
  current validation use pytest.
- Why it matters: Contributors may run the wrong command.
- Root cause: Documentation drift.
- Production-readiness impact: Low.
- DX impact: Setup friction.
- Security or reliability impact: Indirect.
- Mentioned in prior review log: No.
- Previous fix claimed: No.
- Previous fix sufficient: Not applicable.
- Recommended remediation: Update README commands.
- Suggested validation: Documentation command smoke test.
- Should affect scoring: Minor.

### SDK-AUDIT-041 - Documentation understates upstream URL and SSRF risk

- Category: Documentation/Security.
- Severity: Medium.
- Confidence: High.
- File or area: `packages/product-platform/README.md`.
- Evidence: Docs say private non-loopback IPs are rejected, but do not warn that
  loopback is allowed and DNS is not resolved.
- Why it matters: Operators may overtrust SSRF protection.
- Root cause: Documentation mirrors incomplete validation.
- Production-readiness impact: Unsafe deployment assumptions.
- DX impact: Misleading security model.
- Security or reliability impact: Material SSRF risk.
- Mentioned in prior review log: URL hardening was claimed.
- Previous fix claimed: Partial.
- Previous fix sufficient: No.
- Recommended remediation: Fix validation first, then document exact trust
  boundary and allowlist behavior.
- Suggested validation: Docs match SSRF tests.
- Should affect scoring: Yes.

### SDK-AUDIT-042 - SDK SECURITY.md is minimal

- Category: Documentation/Security Process.
- Severity: Low.
- Confidence: High.
- File or area: `packages/ophanix-tool-gateway-sdk/SECURITY.md`.
- Evidence: Security policy exists but lacks full supported versions,
  disclosure SLA, scope, and detailed contact/process information.
- Why it matters: External users need a clear vulnerability reporting path.
- Root cause: Placeholder-level security process doc.
- Production-readiness impact: Slower disclosure handling.
- DX impact: Adoption friction.
- Security or reliability impact: Security-process gap.
- Mentioned in prior review log: No.
- Previous fix claimed: No.
- Previous fix sufficient: Not applicable.
- Recommended remediation: Add complete security policy.
- Suggested validation: Release checklist includes security policy review.
- Should affect scoring: Minor.

### SDK-AUDIT-043 - Deterministic local fixture tokens appear in docs/examples

- Category: Security/DX.
- Severity: Low.
- Confidence: High.
- File or area: `packages/product-platform/examples/tool-gateway-direct-http/README.md`
  and example paths.
- Evidence: Docs include deterministic local fixture tokens with local-only
  warnings.
- Why it matters: Tokens can confuse scanners or be copied into non-local setups.
- Root cause: Demo convenience.
- Production-readiness impact: Low if warnings are followed.
- DX impact: Convenience with footgun potential.
- Security or reliability impact: Low credential confusion risk.
- Mentioned in prior review log: No.
- Previous fix claimed: No.
- Previous fix sufficient: Not applicable.
- Recommended remediation: Mark more aggressively as fixtures and isolate under
  test/demo naming.
- Suggested validation: Scanner allowlist plus docs warning check.
- Should affect scoring: Minor.

### SDK-AUDIT-044 - Local release validation has dependency friction

- Category: Release/DX.
- Severity: Low.
- Confidence: High.
- File or area: `packages/ophanix-tool-gateway-sdk/scripts/validate_release.py`.
- Evidence: `validate_release.py --skip-twine-check` failed locally with
  "Install release extras first".
- Why it matters: Maintainers may skip validation if setup is cumbersome.
- Root cause: Release tooling depends on optional extras and does not bootstrap.
- Production-readiness impact: Indirect release confidence gap.
- DX impact: Maintainer friction.
- Security or reliability impact: Indirect.
- Mentioned in prior review log: Release validation was claimed.
- Previous fix claimed: Yes.
- Previous fix sufficient: Operationally partial.
- Recommended remediation: Add clearer preflight or self-contained runner.
- Suggested validation: Clean environment release validation run.
- Should affect scoring: Minor.

### SDK-AUDIT-045 - Actual publishing path is opaque in repo

- Category: Release/Adoption.
- Severity: Medium.
- Confidence: Medium.
- File or area: `.github/workflows/publish.yml` and release docs.
- Evidence: GitHub workflow builds/signs/attests, but comments indicate actual
  PyPI publishing should occur through an Azure DevOps pipeline not visible in
  this repo.
- Why it matters: External reviewers cannot verify full publish controls from
  the repository.
- Root cause: Split release system.
- Production-readiness impact: Provenance and supply-chain review gap.
- DX impact: Release ownership unclear.
- Security or reliability impact: Supply-chain trust gap.
- Mentioned in prior review log: Buildability was claimed, not full publishing.
- Previous fix claimed: Partial.
- Previous fix sufficient: No.
- Recommended remediation: Document or include publishing pipeline policy,
  trusted publishing, and rollback.
- Suggested validation: Dry-run release documentation and artifact provenance
  check.
- Should affect scoring: Yes.

### SDK-AUDIT-046 - SDK source is duplicated between standalone package and product-platform

- Category: Maintainability/Release.
- Severity: Medium.
- Confidence: High.
- File or area: `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/*`,
  `packages/product-platform/src/ophanix_tool_gateway/*`.
- Evidence: The copies are currently byte-identical, but both copies exist.
- Why it matters: Future fixes can land in one package and not the other.
- Root cause: Compatibility packaging strategy copied source.
- Production-readiness impact: Drift risk.
- DX impact: Contributors may patch the wrong copy.
- Security or reliability impact: Security fixes can be missed in one
  distribution.
- Mentioned in prior review log: Compatibility packaging was claimed.
- Previous fix claimed: Yes.
- Previous fix sufficient: Partial only.
- Recommended remediation: Use one source of truth or enforce byte-for-byte
  equality in CI.
- Suggested validation: CI fails if copies differ.
- Should affect scoring: Yes.

### SDK-AUDIT-047 - API docs and OpenAPI appear enabled unconditionally

- Category: Security/Deployment.
- Severity: Low.
- Confidence: High.
- File or area: `packages/product-platform/src/product_platform/api/app.py:733-739`.
- Evidence: FastAPI docs and OpenAPI URLs are configured directly.
- Why it matters: Production route inventory may be exposed if not blocked
  upstream.
- Root cause: Dev-friendly defaults.
- Production-readiness impact: Reconnaissance risk.
- DX impact: Convenient locally, ambiguous in production.
- Security or reliability impact: Low information exposure risk.
- Mentioned in prior review log: No.
- Previous fix claimed: No.
- Previous fix sufficient: Not applicable.
- Recommended remediation: Environment-gate docs or require explicit enablement.
- Suggested validation: Production-mode docs return 404.
- Should affect scoring: Minor.

### SDK-AUDIT-048 - Development defaults are not fail-closed

- Category: Security/Deployment.
- Severity: Medium.
- Confidence: High.
- File or area: `packages/product-platform/src/product_platform/api/settings.py`.
- Evidence: Defaults include `session_secret = "dev-secret-change-me"` and
  default dev login values.
- Why it matters: Production accidentally running with dev/default config is
  unsafe.
- Root cause: Local-first defaults without production startup guard.
- Production-readiness impact: Deployment hardening gap.
- DX impact: Easy local start, risky deployment.
- Security or reliability impact: Session/auth risk.
- Mentioned in prior review log: No.
- Previous fix claimed: No.
- Previous fix sufficient: Not applicable.
- Recommended remediation: Fail startup in production if default secrets or
  login values remain.
- Suggested validation: Production config test rejects default values.
- Should affect scoring: Yes.

### SDK-AUDIT-049 - Bearer token parsing is permissive

- Category: Security/Auth.
- Severity: Low.
- Confidence: Medium.
- File or area: `packages/product-platform/src/product_platform/tool_gateway/auth.py:74-99`.
- Evidence: Bearer token parser strips and accepts broad token strings.
- Why it matters: Malformed headers may be accepted inconsistently with
  proxies/standards.
- Root cause: Simple parser.
- Production-readiness impact: Low auth-boundary ambiguity.
- DX impact: Edge-case confusion.
- Security or reliability impact: Low.
- Mentioned in prior review log: No.
- Previous fix claimed: No.
- Previous fix sufficient: Not applicable.
- Recommended remediation: Enforce a documented token format and reject
  whitespace/control characters.
- Suggested validation: Malformed bearer header tests.
- Should affect scoring: Minor.

### SDK-AUDIT-050 - Public SDK remains pre-1.0/beta for production adoption

- Category: API Stability/DX.
- Severity: Low.
- Confidence: High.
- File or area: `packages/ophanix-tool-gateway-sdk/pyproject.toml`.
- Evidence: SDK version is `0.1.0` and classifiers mark it as Beta.
- Why it matters: External teams lack strong compatibility and support signals.
- Root cause: Early package lifecycle.
- Production-readiness impact: Adoption hesitation.
- DX impact: Breaking-change anxiety.
- Security or reliability impact: None directly.
- Mentioned in prior review log: Standalone package was claimed.
- Previous fix claimed: Yes.
- Previous fix sufficient: Package exists, but stability policy does not.
- Recommended remediation: Publish compatibility policy, semver commitments, and
  migration notes.
- Suggested validation: Release checklist includes changelog and compatibility
  review.
- Should affect scoring: Minor.

## Issues Grouped By Category

Security, authentication, and data exposure:

- `SDK-AUDIT-001`, `SDK-AUDIT-002`, `SDK-AUDIT-006`,
  `SDK-AUDIT-009`, `SDK-AUDIT-010`, `SDK-AUDIT-011`,
  `SDK-AUDIT-013`, `SDK-AUDIT-016`, `SDK-AUDIT-018`,
  `SDK-AUDIT-019`, `SDK-AUDIT-020`, `SDK-AUDIT-021`,
  `SDK-AUDIT-041`, `SDK-AUDIT-042`, `SDK-AUDIT-043`,
  `SDK-AUDIT-047`, `SDK-AUDIT-048`, `SDK-AUDIT-049`.

Runtime reliability and correctness:

- `SDK-AUDIT-003`, `SDK-AUDIT-004`, `SDK-AUDIT-005`,
  `SDK-AUDIT-007`, `SDK-AUDIT-008`, `SDK-AUDIT-012`,
  `SDK-AUDIT-014`, `SDK-AUDIT-015`, `SDK-AUDIT-017`,
  `SDK-AUDIT-022`, `SDK-AUDIT-023`, `SDK-AUDIT-032`,
  `SDK-AUDIT-034`.

SDK API and developer experience:

- `SDK-AUDIT-024`, `SDK-AUDIT-025`, `SDK-AUDIT-026`,
  `SDK-AUDIT-027`, `SDK-AUDIT-028`, `SDK-AUDIT-029`,
  `SDK-AUDIT-030`, `SDK-AUDIT-031`, `SDK-AUDIT-050`.

Testing:

- `SDK-AUDIT-033`, `SDK-AUDIT-034`.

Packaging, release, and CI:

- `SDK-AUDIT-035`, `SDK-AUDIT-036`, `SDK-AUDIT-037`,
  `SDK-AUDIT-038`, `SDK-AUDIT-039`, `SDK-AUDIT-044`,
  `SDK-AUDIT-045`, `SDK-AUDIT-046`.

Documentation and adoption:

- `SDK-AUDIT-040`, `SDK-AUDIT-041`, `SDK-AUDIT-042`,
  `SDK-AUDIT-043`, `SDK-AUDIT-045`, `SDK-AUDIT-050`.

## Critical And High-Severity Blockers

Critical:

- `SDK-AUDIT-002` - SSRF boundary allows loopback and DNS-private upstream
  targets.

High:

- `SDK-AUDIT-001` - Principal probe leaks credential context.
- `SDK-AUDIT-003` - Blocking upstream HTTP in async endpoint.
- `SDK-AUDIT-004` - Shared SQLite connection/transaction model.
- `SDK-AUDIT-005` - In-memory seeded DB fallback.
- `SDK-AUDIT-006` - Upstream auth only supports `none`.
- `SDK-AUDIT-007` - No idempotency/retry contract for invocation.
- `SDK-AUDIT-008` - No pre-parse response byte cap.
- `SDK-AUDIT-009` - Non-blocking security scans.
- `SDK-AUDIT-010` - Arbitrary string permission expirations.

## Medium-Severity Production Risks

Medium issues that should be fixed before broad production adoption:

- `SDK-AUDIT-011`, `SDK-AUDIT-012`, `SDK-AUDIT-013`,
  `SDK-AUDIT-014`, `SDK-AUDIT-015`, `SDK-AUDIT-016`,
  `SDK-AUDIT-017`, `SDK-AUDIT-018`, `SDK-AUDIT-019`,
  `SDK-AUDIT-020`, `SDK-AUDIT-021`, `SDK-AUDIT-024`,
  `SDK-AUDIT-025`, `SDK-AUDIT-026`, `SDK-AUDIT-032`,
  `SDK-AUDIT-033`, `SDK-AUDIT-034`, `SDK-AUDIT-035`,
  `SDK-AUDIT-036`, `SDK-AUDIT-041`, `SDK-AUDIT-045`,
  `SDK-AUDIT-046`, `SDK-AUDIT-048`.

## Low-Severity And Nit-Level Issues

Lower-severity issues:

- `SDK-AUDIT-022`, `SDK-AUDIT-023`, `SDK-AUDIT-027`,
  `SDK-AUDIT-028`, `SDK-AUDIT-029`, `SDK-AUDIT-030`,
  `SDK-AUDIT-031`, `SDK-AUDIT-037`, `SDK-AUDIT-038`,
  `SDK-AUDIT-039`, `SDK-AUDIT-040`, `SDK-AUDIT-042`,
  `SDK-AUDIT-043`, `SDK-AUDIT-044`, `SDK-AUDIT-047`,
  `SDK-AUDIT-049`, `SDK-AUDIT-050`.

## Prior Findings Status Table

| Prior finding or fix claim | Current status | Sufficient? | Related issues |
| --- | --- | --- | --- |
| Discovery moved to `/api/v1/gateway/tools` | Implemented and tests pass | Mostly | `SDK-AUDIT-029` |
| Gateway-safe discovery shape | Implemented | Mostly | None major |
| SDK config and payload validation | Implemented in SDK | Partial | `SDK-AUDIT-027`, `SDK-AUDIT-032` |
| HTTPS-by-default SDK base URL handling | Implemented in SDK | Mostly | Server SSRF remains: `SDK-AUDIT-002` |
| `get_tool` pagination | Implemented | Yes | None |
| Token repr and error redaction | Implemented | Partial | `SDK-AUDIT-016`, `SDK-AUDIT-020`, `SDK-AUDIT-024` |
| Discovery retries, `Retry-After`, jitter | Implemented for discovery | Partial | `SDK-AUDIT-007`, `SDK-AUDIT-031` |
| Env token provider, `list_all_tools`, cache clearing | Implemented | Mostly | `SDK-AUDIT-028` |
| `py.typed` | Present in SDK and product-platform package | Yes | None |
| Standalone SDK package | Builds and imports | Partial | `SDK-AUDIT-033`, `SDK-AUDIT-046`, `SDK-AUDIT-050` |
| Resource-bound credential scopes | Enforcement present | Partial | `SDK-AUDIT-021`, `SDK-AUDIT-022` |
| Cache partitioned by token fingerprint | Implemented | Partial | `SDK-AUDIT-026`, `SDK-AUDIT-028` |
| Async SDK | Implemented | SDK yes, server no | `SDK-AUDIT-003` |
| Release validation | Script exists; wheel validates | Partial | `SDK-AUDIT-039`, `SDK-AUDIT-044`, `SDK-AUDIT-045` |
| Expanded README | Exists | Partial | `SDK-AUDIT-040`, `SDK-AUDIT-041`, `SDK-AUDIT-042` |

## Scoring Matrix

### Implementation Quality

- Current score: 6 / 10.
- Prior score from requested log: Not assigned.
- Whether score should be upheld, raised, or lowered: New strict score. If
  compared to later stale 8.x notes, it should be lowered.
- Exact reasons: Strong unit coverage and successful wheel builds are offset by
  blocking runtime I/O, SQLite concurrency risk, audit ordering problems,
  response-size gaps, duplicated SDK source, and weak standalone SDK tests.
- Score cap caused by unresolved issues: 6.
- What must be fixed to reach the next score: Fix `SDK-AUDIT-003`,
  `SDK-AUDIT-004`, `SDK-AUDIT-005`, `SDK-AUDIT-008`,
  `SDK-AUDIT-033`, and `SDK-AUDIT-034`.
- What must be fixed to reach 8: Add production-like integration/load tests,
  idempotency, response caps, and source drift guard.
- What must be fixed to reach 9: Prove production deployment behavior under
  concurrency and failure, with mature release validation.

### Ease Of Use

- Current score: 6 / 10.
- Prior score from requested log: Not assigned.
- Whether score should be upheld, raised, or lowered: New strict score. If
  compared to optimistic prior narrative, it should be lowered.
- Exact reasons: SDK API is usable and documented, but upstream auth is missing,
  error classification loses detail, docs are stale/incomplete in places, direct
  HTTP behavior differs from SDK behavior, and release/adoption path is unclear.
- Score cap caused by unresolved issues: 7, pulled down to 6 by missing upstream
  auth and misleading errors/docs.
- What must be fixed to reach the next score: Fix `SDK-AUDIT-006`,
  `SDK-AUDIT-024`, `SDK-AUDIT-025`, `SDK-AUDIT-040`, and
  `SDK-AUDIT-041`.
- What must be fixed to reach 8: Complete auth modes, examples for production
  credentials, clean error taxonomy, and standalone SDK behavioral tests.
- What must be fixed to reach 9: Stable semver policy, migration guides,
  production quickstart, and complete troubleshooting matrix.

### Security And Reliability

- Current score: 5 / 10.
- Prior score from requested log: Not assigned.
- Whether score should be upheld, raised, or lowered: New strict score. If
  compared to later stale 8.x notes, it should be strongly lowered.
- Exact reasons: SSRF gap, hidden principal probe, blocking I/O, SQLite runtime
  model, non-blocking security scans, weak response caps, process-local limiter,
  unsalted token hashes, and weak audit redaction.
- Score cap caused by unresolved issues: 5 because of one critical and multiple
  high security/reliability issues.
- What must be fixed to reach the next score: Fix `SDK-AUDIT-001`,
  `SDK-AUDIT-002`, `SDK-AUDIT-003`, `SDK-AUDIT-004`,
  `SDK-AUDIT-005`, `SDK-AUDIT-008`, `SDK-AUDIT-009`, and
  `SDK-AUDIT-010`.
- What must be fixed to reach 8: Add distributed rate limiting, protected
  upstream auth, idempotency, response streaming/caps, robust audit redaction,
  and concurrency tests.
- What must be fixed to reach 9: Formal threat model, security-gated CI,
  fuzz/property tests, and documented operational hardening.

## Score Cap Explanation

The security and reliability score cannot exceed 5 while `SDK-AUDIT-002`
exists. SSRF against loopback/private-by-DNS targets is a production-class
vulnerability for a gateway whose job is to broker tool calls.

Implementation quality cannot exceed 6 while the gateway uses blocking upstream
I/O in an async endpoint, has shared SQLite transaction concerns, lacks
pre-parse response caps, and lacks production-like concurrency tests.

Ease of use cannot exceed 7, and currently lands at 6, because a production
adopter cannot configure protected upstream auth, cannot rely on crisp SDK error
classification, and must reconcile stale or incomplete docs.

## Required Fixes To Reach Production Readiness

Minimum production-readiness fixes:

1. Remove or hard-gate the principal probe endpoint.
2. Redesign upstream URL SSRF protection with DNS resolution,
   loopback/private-address blocking, and explicit allowlists.
3. Replace sync upstream HTTP calls in async request flow.
4. Remove production fallback to in-memory demo DB.
5. Fix DB connection and transaction model for concurrent use.
6. Add response byte caps before JSON parsing.
7. Make secret and security scans blocking.
8. Validate permission expiration as real datetimes.
9. Add protected upstream auth modes.
10. Add invocation idempotency semantics.
11. Add production-like integration, load, concurrency, and SSRF tests.
12. Fix SDK error classification and top-level error code parsing.

## Required Fixes To Reach 8 Out Of 10

To justify 8:

- All critical and high issues fixed.
- Medium security/reliability issues fixed or explicitly mitigated.
- Standalone SDK has full behavioral test coverage.
- CI includes blocking security scans and dependency automation for the SDK and
  product-platform packages.
- Release process is reproducible and documented.
- Docs accurately describe production setup, auth, rate limits, SSRF
  boundaries, retries, idempotency, and error handling.
- Server and SDK behavior are consistent for validation, errors, request IDs,
  and payload constraints.

## Required Fixes To Reach 9 Out Of 10

To justify 9:

- Formal threat model and security review artifacts.
- Mature upstream auth with rotation and secret storage.
- Distributed rate limiting and production observability.
- Load-tested async gateway runtime.
- Strong audit integrity model.
- Proven release provenance and trusted publishing.
- Backward-compatibility policy and migration guides.
- Fuzz/property tests for URL parsing, payload validation, redaction, and error
  parsing.
- No meaningful unresolved medium issues.

## Recommended Remediation Order

1. Fix `SDK-AUDIT-002`, `SDK-AUDIT-001`, `SDK-AUDIT-008`, and
   `SDK-AUDIT-009` first because they are security-sensitive.
2. Fix `SDK-AUDIT-003`, `SDK-AUDIT-004`, and `SDK-AUDIT-005` because they
   affect runtime availability and correctness.
3. Fix `SDK-AUDIT-006`, `SDK-AUDIT-007`, and `SDK-AUDIT-010` to make
   production integrations safe.
4. Fix `SDK-AUDIT-014`, `SDK-AUDIT-015`, `SDK-AUDIT-016`,
   `SDK-AUDIT-018`, `SDK-AUDIT-019`, `SDK-AUDIT-020`, and
   `SDK-AUDIT-021` to strengthen policy and audit behavior.
5. Fix SDK API issues `SDK-AUDIT-024`, `SDK-AUDIT-025`,
   `SDK-AUDIT-026`, `SDK-AUDIT-027`, `SDK-AUDIT-028`, and
   `SDK-AUDIT-031`.
6. Add test coverage for `SDK-AUDIT-033` and `SDK-AUDIT-034`.
7. Clean up CI, release, and documentation issues `SDK-AUDIT-035` through
   `SDK-AUDIT-046`.
8. Address remaining low-severity polish before public production positioning.

## Validation Plan

Required validation suite:

- SSRF tests for loopback, private IPs, IPv6, DNS-to-private, redirects, and
  rebinding.
- Async load test with slow upstreams proving event loop remains responsive.
- Multi-request DB concurrency tests.
- Large response tests proving pre-parse byte limits.
- Authz tests for malformed expiration, expired grants, resource-bound grants,
  and duplicate wildcard scopes.
- Upstream auth integration tests.
- Idempotency replay and timeout-after-success tests.
- SDK tests for top-level error codes, generic 403, cache immutability, cyclic
  payloads, retry metadata, and async parity.
- Standalone SDK package-local behavioral test suite.
- Wheel and sdist content tests.
- CI tests proving security scans fail the build.
- Documentation command smoke tests.

## Final Strict Assessment

The current repo is not production-ready for broad external SDK or Tool Gateway
adoption.

The SDK itself is usable in controlled environments and the packaging state is
better than some stale prior notes suggest. But production readiness must include
the runtime gateway, security posture, release pipeline, docs, and tests. On
that full standard, the remaining SSRF exposure, hidden probe endpoint, blocking
runtime I/O, DB concurrency model, missing upstream auth, missing idempotency,
weak response caps, and advisory-only security scans cap the system well below
generally production-ready.

Strict final scores:

- Implementation quality: 6 / 10.
- Ease of use: 6 / 10.
- Security and reliability: 5 / 10.
