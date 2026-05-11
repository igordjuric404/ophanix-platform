# Tool Gateway SDK Production Readiness Audit V4

Date: 2026-05-11

Scope: strict production-readiness audit of the current `ophanix-platform` repository, focused on the standalone Python Tool Gateway SDK, the vendored compatibility SDK, the product-platform gateway runtime that the SDK depends on, tests, documentation, packaging, CI, and release readiness.

This audit intentionally does not implement fixes. It treats `docs/product-platform-worktree/execution-logs/06-tool-gateway-logs/13-sdk-review-remediation.md` as prior context and prior evidence only. All conclusions below are based on a fresh repository pass.

## 1. Executive Summary

Current strict scores:

| Area | Current score | Prior latest score in `13-sdk-review-remediation.md` | Direction | Strict assessment |
| --- | ---: | ---: | --- | --- |
| Implementation quality | 6 / 10 | 6 / 10 | Upheld | The SDK client itself is materially better than early reviews, and the product gateway test suite is broad. The score remains capped by server-side production architecture gaps: SQLite-only persistence, in-memory secret storage, no invocation idempotency, no distributed runtime limiting, no live installed-wheel-to-running-gateway contract test, and no load or multi-worker proof. |
| Ease of use | 6 / 10 | 8 / 10 | Lowered | The client API is usable, but external adoption is still slowed by unpublished/unclear package publication, beta status, missing generated API docs, local test setup requiring `PYTHONPATH` or installation, unclear real secret-manager setup, no end-to-end onboarding proof, and a gateway runtime that still requires substantial operational caveats. |
| Security and reliability | 5 / 10 | 6 / 10 | Lowered | Multiple high-severity production risks remain: SQLite production posture, in-memory demo secret provider, process-local limiter, missing idempotency/replay protection, DNS-rebinding residual SSRF risk, unresolved-host bypass, no retention policy for runtime/audit data, and no production-like failure/load validation. |

The repository is not production-ready for broad external SDK adoption. It is functional and tested for many unit/in-process paths, but production readiness requires stronger server runtime guarantees, release proof, operational controls, and adoption documentation than the current repository provides.

No critical issue is proven in the current state, but several high-severity issues combine to cap security/reliability at 5 and implementation quality at 6.

## 2. Prior Review Summary And Challenge

### 2.1 Previously Reported Non-Deferred Issues

The requested prior log reported these non-deferred issues across the SDK and gateway contract:

- SDK discovery originally called the operator `/api/v1/tools` route with gateway bearer credentials instead of an agent-safe gateway discovery route.
- Gateway discovery initially returned an operator-facing tool model with tenant/creator fields.
- SDK input validation was too weak: non-string tool names, non-JSON payloads, malformed successful responses, and non-local plain HTTP could pass too far into runtime.
- `get_tool()` searched only the first discovery page.
- `StaticTokenProvider` and SDK error diagnostics could leak tokens or sensitive response text through representations and exception messages.
- Discovery ergonomics lacked environment token provider, `list_all_tools()`, explicit cache invalidation, typed package marker, and discovery retries.
- Boundary hardening was incomplete for strict JSON payloads, base URL userinfo/query/fragment, header control characters, limit/offset validation, and numeric config validation.
- Discovery retries ignored `Retry-After`.
- The SDK was embedded in the product package rather than distributed as a lightweight standalone package.
- Resource-bound gateway credential scopes, cache partitioning, async SDK parity, package smoke tests, API docs, security policy, changelog, release validation, and CI/package workflows were missing or incomplete.
- Runtime/gateway gaps later recorded in the same log included SSRF controls, request/response caps, upstream auth, rate limiting, failed-response redaction, CORS production guards, SQLite/default production posture, DB artifacts, migration issues, and production adoption documentation.

Deferred or explicitly accepted items in the prior log, such as idempotency and production-like load validation, are not counted as "previously reported fixes" here, but they remain live production-readiness issues in this audit.

### 2.2 Fixes Claimed

The prior log claimed the following fixes:

- Added `GET /api/v1/gateway/tools` protected by `GatewayPrincipal`.
- Added gateway-safe discovery response shape and filtering to active/callable tools.
- Added SDK runtime validation for config, payloads, responses, HTTPS defaults, strict JSON, header values, numeric values, and retry configuration.
- Added generic/redacted SDK exception messages and redacted diagnostics.
- Added `EnvironmentTokenProvider`, `list_all_tools()`, `clear_tool_cache()`, discovery retries with bounded exponential backoff and `Retry-After`, and `py.typed`.
- Extracted the standalone `ophanix_tool_gateway` package and kept product compatibility exports.
- Added async SDK client and sync/async parity tests.
- Added package smoke tests, API reference, README, security policy, changelog, release validator, CI matrix, dependency audit wiring, and publish workflow.
- Added resource-bound gateway scopes, cache fingerprint partitioning, upstream auth support, explicit query allowlists, body/response caps, response policy hardening, rate limiting, production startup checks, CORS guard, and additional migration/test coverage.

### 2.3 Validation Evidence Claimed

The prior log claimed repeated validation using focused SDK tests, product Tool Gateway tests, full product tests, type checks, compile checks, package builds, release validators, dependency audit paths, `git diff --check`, and parity checks between standalone and vendored SDK sources. Earlier counts in the log grew from 30 SDK tests and 653 product tests to later claims of 774 full product tests.

Fresh validation in this audit:

- `PYTHONPATH=src python3 -m pytest tests -q --tb=short` in `packages/ophanix-tool-gateway-sdk`: 10 passed.
- `python3 -m pytest tests -q --tb=short` in `packages/ophanix-tool-gateway-sdk` without `PYTHONPATH`: failed with `ModuleNotFoundError: No module named 'ophanix_tool_gateway'`.
- `PYTHONPATH=src python3 -m pytest tests/test_tool_gateway_*.py -q --tb=short` in `packages/product-platform`: 273 passed.
- `python3 -m pytest tests/test_tool_gateway_*.py` in `packages/product-platform` without `PYTHONPATH`: failed with `ModuleNotFoundError: No module named 'product_platform'`.
- `PYTHONPATH=src python3 -m pytest tests -q --tb=short` in `packages/product-platform`: 774 passed.
- SDK `ruff`, SDK `mypy`, product gateway `ruff`, product gateway `mypy`, and targeted `compileall`: passed.
- Standalone SDK release validator with `--skip-twine-check`: passed.
- Product-platform release validator with `--skip-twine-check`: passed.
- SDK release validator with `--skip-twine-check --require-dependency-audit`: failed locally because the `[security]` extra was not installed. CI installs it, so this is local validation incomplete rather than proof of a vulnerability.
- Standalone/vendored SDK parity check using `cmp`: passed.
- Production SQLite probe with explicit `allow_sqlite_in_production=True`: application startup allowed SQLite.

### 2.4 Scores Assigned In The Prior Log

The prior log contains several score rounds as remediation continued:

- Early strict SDK-only scores: implementation `7.8/10`, ease of use `8.0/10`, security/reliability `8.1/10`.
- Later SDK/package scores: implementation `8.1/10`, ease of use `8.3/10`, security/reliability `8.3/10`.
- Later broader audit/remediation score: implementation `7.5/10`, ease of use `8.0/10`, security/reliability `7.5/10`.
- Later V2-style score: implementation `7/10`, ease of use `7/10`, security/reliability `6/10`.
- Latest score table visible in `13-sdk-review-remediation.md`: implementation `6/10`, ease of use `8/10`, security/reliability `6/10`.

This audit uses the latest visible prior table only for comparison, not as an anchor.

### 2.5 Suspicious, Under-Evidenced, Too Lenient, Or Too Strict Prior Conclusions

- The SDK-local scores became too generous when they were implicitly applied to the broader production gateway. A client SDK cannot be production-ready if its required server runtime is not production-ready.
- The prior ease-of-use score of `8/10` is too lenient because package publication is still a handoff, real secret-manager setup is not wired, the package is still beta, local test setup fails without install/PYTHONPATH, and no external onboarding proof exists.
- The prior security/reliability score of `6/10` is still slightly too lenient for broad adoption because high-severity runtime risks remain simultaneously: SQLite, in-memory secret provider, process-local rate limiting, missing idempotency, DNS-rebinding residual SSRF risk, and missing load/multi-worker evidence.
- Prior claims around release readiness are under-evidenced because workflows validate artifacts and attest them, but do not publish to an index, do not enforce SDK `--strict-git`, and were not run in this audit environment.
- Prior claims around rate limiting are too optimistic: the implemented limiter is explicitly process-local and can be exhausted by distinct authorization keys.
- Prior claims around upstream auth fixed a major gap, but the production secret provider backing that auth remains demo/in-memory in this repo.
- Prior claims around SSRF controls are directionally correct but too optimistic; DNS validation at configuration time is not sufficient against DNS rebinding or network-layer egress mistakes.
- A few earlier V3 conclusions are now too strict: the manual health route wiring and long DB transaction across upstream invocation appear to have been remediated in the current code and should not be carried forward as live findings.

### 2.6 Areas Not Deeply Reviewed Before

- Real production secret-provider wiring behind `secret_manager_ref`.
- Multi-process and multi-worker behavior of rate limiting, cache state, SQLite, and in-memory secrets.
- DNS rebinding/time-of-use behavior for upstream targets.
- Live installed-wheel SDK against a running gateway service.
- Package publication to an actual internal or public index.
- Operational data retention for runtime action logs and response summaries.
- Production runbook completeness: backup/restore, token rotation, incident response, load testing, SLOs, and failure drills.
- Local contributor flow without editable installs or `PYTHONPATH`.
- Interaction between runtime limiter key exhaustion and unauthenticated/invalid tokens.

## 3. Repository Surface Reviewed

### Pass 1: Repository Map

Relevant SDK package files:

- `packages/ophanix-tool-gateway-sdk/pyproject.toml`
- `packages/ophanix-tool-gateway-sdk/README.md`
- `packages/ophanix-tool-gateway-sdk/API_REFERENCE.md`
- `packages/ophanix-tool-gateway-sdk/SECURITY.md`
- `packages/ophanix-tool-gateway-sdk/CHANGELOG.md`
- `packages/ophanix-tool-gateway-sdk/scripts/validate_release.py`
- `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/__init__.py`
- `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py`
- `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/py.typed`
- `packages/ophanix-tool-gateway-sdk/tests/test_package_smoke.py`
- `packages/ophanix-tool-gateway-sdk/tests/test_sdk_behavior.py`

Relevant vendored compatibility SDK files:

- `packages/product-platform/src/ophanix_tool_gateway/__init__.py`
- `packages/product-platform/src/ophanix_tool_gateway/sdk.py`
- `packages/product-platform/src/ophanix_tool_gateway/py.typed`

Relevant product gateway runtime files:

- `packages/product-platform/src/product_platform/api/app.py`
- `packages/product-platform/src/product_platform/api/settings.py`
- `packages/product-platform/src/product_platform/api/dependencies.py`
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
- `packages/product-platform/src/product_platform/tool_gateway/sdk.py`
- `packages/product-platform/src/product_platform/agents/credentials.py`
- `packages/product-platform/src/product_platform/integrations/secrets.py`
- `packages/product-platform/src/product_platform/db/connection.py`
- `packages/product-platform/src/product_platform/db/migrator.py`
- `packages/product-platform/src/product_platform/db/migrations/*.py`

Relevant tests:

- `packages/product-platform/tests/test_tool_gateway_auth*.py`
- `packages/product-platform/tests/test_tool_gateway_decision.py`
- `packages/product-platform/tests/test_tool_gateway_direct_http_examples.py`
- `packages/product-platform/tests/test_tool_gateway_forwarding.py`
- `packages/product-platform/tests/test_tool_gateway_invocation.py`
- `packages/product-platform/tests/test_tool_gateway_permissions.py`
- `packages/product-platform/tests/test_tool_gateway_registry*.py`
- `packages/product-platform/tests/test_tool_gateway_response.py`
- `packages/product-platform/tests/test_tool_gateway_runtime_audit.py`
- `packages/product-platform/tests/test_tool_gateway_sdk*.py`
- `packages/product-platform/tests/test_tool_gateway_upstream*.py`
- Full `packages/product-platform/tests` suite for cross-impact validation.

Relevant packaging, build, CI, and release files:

- `packages/product-platform/pyproject.toml`
- `packages/product-platform/scripts/validate_release.py`
- `.github/workflows/ci.yml`
- `.github/workflows/publish.yml`
- `.github/dependabot.yml`
- `.github/actions/guard-dependencies/action.yml`
- `docs/internal/pypi-publishing.md`
- `docs/product-platform-worktree/execution-logs/06-tool-gateway-logs/*.md`

## 4. Exhaustive Issue Register

### SDK-AUDIT-001: Product gateway persistence remains SQLite-only

- Category: Runtime architecture / persistence
- Severity: High
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/db/migrator.py`, `packages/product-platform/src/product_platform/db/connection.py`, `packages/product-platform/README.md`
- Evidence: `migrator.py` only supports `sqlite:///` URLs and opens a single SQLite connection; `connection.py` serializes transactions with an `RLock`; the README states the runtime remains SQLite-backed and broad production adoption requires an external managed production database layer.
- Why it matters: A production SDK depends on the gateway being reliable under real concurrent traffic. SQLite with a shared process-local connection is not a broad production persistence strategy for multi-worker service traffic, migrations, backups, or failover.
- Root cause or likely root cause: The product-platform runtime still uses a local/demo persistence architecture.
- Impact on production readiness: High. This caps implementation quality and reliability.
- Impact on developer experience, if applicable: External adopters must design around an unresolved server persistence story.
- Impact on security or reliability, if applicable: Reliability risk from lock contention, single-node state, backup/restore gaps, and multi-worker inconsistency.
- Whether it was mentioned in the prior review log: Yes.
- Whether a previous fix claimed to address it: Partially. Production startup guard and transaction-scope work were claimed.
- Whether that previous fix is sufficient: No.
- Recommended remediation: Add a production database backend with pooling, migrations, backup/restore runbook, and deployment guidance. Treat SQLite as local/test only.
- Suggested validation or test: Run the gateway with the production DB backend under multi-worker load, migration apply/rollback tests, transaction contention tests, and backup/restore drills.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-002: Production startup still permits SQLite through an escape hatch

- Category: Runtime configuration / production safety
- Severity: High
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/api/app.py`, `packages/product-platform/src/product_platform/api/settings.py`
- Evidence: `_validate_production_settings()` rejects SQLite only when `allow_sqlite_in_production` is false. A fresh probe with `Settings(environment="production", database_url="sqlite:///prod.db", allow_sqlite_in_production=True, gateway_token_hash_pepper="pepper")` allowed app startup.
- Why it matters: The production guard can be bypassed by a single environment flag. That makes a high-risk local storage mode an accepted production state rather than a hard development-only constraint.
- Root cause or likely root cause: Compatibility/demo flexibility was preserved inside the production configuration path.
- Impact on production readiness: High. A misconfigured deployment can pass startup while using a non-production persistence layer.
- Impact on developer experience, if applicable: Documentation says the runtime remains SQLite-backed, so adopters may be unsure whether the escape hatch is supported or only tolerated.
- Impact on security or reliability, if applicable: Reliability risk from local disk, single-node state, locking, and weak operational guarantees.
- Whether it was mentioned in the prior review log: Yes.
- Whether a previous fix claimed to address it: Yes, through production startup validation.
- Whether that previous fix is sufficient: No.
- Recommended remediation: Remove or heavily restrict the production SQLite escape hatch. If it must exist for internal demos, require a separate non-production environment classification.
- Suggested validation or test: Add a production-settings test asserting all SQLite URLs fail in production regardless of opt-in unless an explicit test-only override is injected.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-003: Upstream secret provider is still an in-memory demo provider by default

- Category: Security / secret management
- Severity: High
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/integrations/secrets.py`, `packages/product-platform/src/product_platform/api/app.py`, `packages/product-platform/src/product_platform/api/settings.py`
- Evidence: `DemoLocalSecretProvider` stores secrets in an in-memory dictionary. `_secret_provider()` in `app.py` returns `DEFAULT_SECRET_PROVIDER`. `Settings.secret_manager_ref` exists but is not wired into a real provider selection path.
- Why it matters: Upstream bearer/API-key auth relies on a secret provider. A process-local demo provider loses secrets on restart, is not shared across workers, and is not auditable like a managed secret store.
- Root cause or likely root cause: The abstraction exists, but production provider integration was not implemented.
- Impact on production readiness: High. Protected upstream targets cannot be operated safely at scale without a real secret manager.
- Impact on developer experience, if applicable: Operators see `secret_manager_ref` and `secret_ref` concepts but do not get a working production setup path in code.
- Impact on security or reliability, if applicable: Secret availability, rotation, auditability, and separation of duties are weak.
- Whether it was mentioned in the prior review log: Partially. Upstream auth was reviewed, but this provider wiring gap was not deeply reviewed.
- Whether a previous fix claimed to address it: Upstream auth was claimed fixed.
- Whether that previous fix is sufficient: No. Auth mode support is incomplete without a production secret backend.
- Recommended remediation: Implement managed secret-provider backends, select them from settings, fail production startup without one, and document secret lifecycle/rotation.
- Suggested validation or test: Add production startup tests requiring a non-demo provider; integration tests against the configured provider; restart/multi-worker secret retrieval tests.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-004: No invocation idempotency or replay-protection contract

- Category: Reliability / API contract
- Severity: High
- Confidence: High
- File path or area: SDK README, product README, `packages/product-platform/src/product_platform/api/app.py`, invocation route
- Evidence: Documentation explicitly says tool invocations are not retried automatically because the server contract does not provide idempotency keys. No `Idempotency-Key` contract exists in the invocation route.
- Why it matters: Agents and network clients will see timeouts and uncertain failures. Without idempotency, callers cannot safely retry mutating tools and cannot distinguish "not executed" from "executed but response lost."
- Root cause or likely root cause: Invocation persistence records runtime actions but does not expose a deduplication/replay API contract.
- Impact on production readiness: High. This blocks robust production retry behavior.
- Impact on developer experience, if applicable: SDK users must build their own idempotency or avoid retries, which is fragile.
- Impact on security or reliability, if applicable: Duplicate mutations, lost operations, and inconsistent external side effects are likely under network failure.
- Whether it was mentioned in the prior review log: Yes.
- Whether a previous fix claimed to address it: No; it was repeatedly deferred or accepted as remaining risk.
- Whether that previous fix is sufficient: No.
- Recommended remediation: Add idempotency key schema, request hashing, replay result semantics, conflict handling, TTL, and SDK support.
- Suggested validation or test: Integration tests for timeout-after-upstream-success, duplicate key replay, payload mismatch conflict, concurrent duplicate calls, and SDK retry behavior.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-005: Runtime rate limiting is process-local and not production-distributed

- Category: Reliability / abuse resistance
- Severity: High
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/api/app.py`, `packages/product-platform/README.md`
- Evidence: `_tool_gateway_rate_limit_exceeded()` stores counters in `app.state.tool_gateway_rate_limits` guarded by a process-local `threading.Lock`. The README states production deployments should still enforce global edge limits because the built-in limiter is process-local.
- Why it matters: Multi-process or multi-node deployments multiply the effective limit and cannot enforce global quotas or tenant/credential limits.
- Root cause or likely root cause: A lightweight in-process guard was implemented instead of a distributed limiter.
- Impact on production readiness: High. This is not adequate as the only production abuse-control layer.
- Impact on developer experience, if applicable: Operators must infer and deploy an additional limiter.
- Impact on security or reliability, if applicable: Abuse, cost spikes, upstream pressure, and denial-of-service are still possible.
- Whether it was mentioned in the prior review log: Yes.
- Whether a previous fix claimed to address it: Yes, a lightweight in-process limiter was added.
- Whether that previous fix is sufficient: No.
- Recommended remediation: Add a distributed rate-limit backend or make gateway startup require documented ingress/edge enforcement in production.
- Suggested validation or test: Multi-worker tests proving aggregate limits, credential/tenant quotas, and limiter behavior under restart.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-006: Rate limiter can be exhausted by distinct invalid authorization keys

- Category: Reliability / abuse resistance
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/api/app.py`, `packages/product-platform/tests/test_tool_gateway_auth_phase3.py`
- Evidence: The limiter keys on a SHA-256 digest of the raw `Authorization` header before authentication. The regression test with `tool_gateway_rate_limit_max_keys=1` proves a second distinct invalid token receives `429` after the first invalid token consumes the only key slot.
- Why it matters: Attackers can generate many invalid authorization values to fill the limiter key map and deny service to new legitimate credentials when `max_keys` is reached.
- Root cause or likely root cause: Limiting occurs before authentication and uses caller-controlled key cardinality.
- Impact on production readiness: Medium. Defaults reduce but do not eliminate the issue.
- Impact on developer experience, if applicable: Operators may tune `max_keys` without realizing invalid-token traffic can consume the budget.
- Impact on security or reliability, if applicable: Denial-of-service risk.
- Whether it was mentioned in the prior review log: No, not specifically.
- Whether a previous fix claimed to address it: No.
- Whether that previous fix is sufficient: Not applicable.
- Recommended remediation: Separate unauthenticated limiter keys from authenticated credential keys, enforce IP/edge limits first, and avoid letting invalid bearer strings consume unbounded credential buckets.
- Suggested validation or test: Abuse tests with many invalid tokens plus a legitimate credential under constrained and default `max_keys`.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-007: Gateway rate-limit responses omit `Retry-After`

- Category: Reliability / protocol ergonomics
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/api/app.py`
- Evidence: The middleware returns `429` with code `TOOL_GATEWAY_RATE_LIMITED` but does not set `Retry-After`. SDK retry logic can honor `Retry-After`, but the gateway limiter does not emit it.
- Why it matters: Clients cannot coordinate backoff with the gateway's configured window and may retry too aggressively or too conservatively.
- Root cause or likely root cause: The limiter returns a generic error response without exposing window state.
- Impact on production readiness: Medium.
- Impact on developer experience, if applicable: SDK consumers receive less actionable throttling feedback.
- Impact on security or reliability, if applicable: Poor backpressure behavior during spikes.
- Whether it was mentioned in the prior review log: No.
- Whether a previous fix claimed to address it: Discovery `Retry-After` support was added in the SDK.
- Whether that previous fix is sufficient: No, because the server limiter does not provide the signal.
- Recommended remediation: Include `Retry-After` and optionally structured limit headers for runtime limiter responses.
- Suggested validation or test: Assert `429` responses include `Retry-After` matching the remaining window, and that SDK discovery honors it against the real gateway.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-008: SSRF defenses remain vulnerable to DNS rebinding and time-of-use changes

- Category: Security / SSRF
- Severity: High
- Confidence: Medium
- File path or area: `packages/product-platform/src/product_platform/tool_gateway/models.py`, `packages/product-platform/src/product_platform/tool_gateway/invocation.py`
- Evidence: URL validation rejects forbidden hostnames, IP literals, and DNS resolutions at validation time. Invocation revalidates the URL shape, but there is no connection-time IP pinning, resolver control, network egress allowlist, or post-resolution enforcement in the HTTP client.
- Why it matters: DNS names can change after validation or between resolution and connect. Application-layer URL validation alone is not a complete SSRF boundary.
- Root cause or likely root cause: SSRF mitigation relies on static validation instead of runtime egress enforcement.
- Impact on production readiness: High for any deployment that lets operators configure upstream targets with DNS names.
- Impact on developer experience, if applicable: Docs mention egress controls, but implementation cannot prove the protection.
- Impact on security or reliability, if applicable: Potential access to internal metadata, private services, or unintended networks if infrastructure egress controls are absent or misconfigured.
- Whether it was mentioned in the prior review log: Yes, as residual infrastructure risk.
- Whether a previous fix claimed to address it: Yes, SSRF URL validation was added.
- Whether that previous fix is sufficient: No.
- Recommended remediation: Add network-layer egress policy, DNS pinning or controlled resolver enforcement, and production deployment requirements that fail closed without egress controls.
- Suggested validation or test: DNS rebinding integration test and deployment-level egress tests blocking metadata/private IP ranges at connect time.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-009: Unresolved upstream hosts can be allowed in production by environment variable

- Category: Security / configuration
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/tool_gateway/models.py`
- Evidence: `_allow_unresolved_upstream_hosts()` returns true for local/test and also when `OPHANIX_ALLOW_UNRESOLVED_UPSTREAM_HOSTS=true`; there is no production guard in that helper.
- Why it matters: A production deployment can bypass DNS validation for upstream targets, weakening SSRF defense and enabling typos or private DNS surprises to reach runtime.
- Root cause or likely root cause: A local/test escape hatch was made environment-driven without production scoping.
- Impact on production readiness: Medium.
- Impact on developer experience, if applicable: Teams may use the variable to work around private DNS issues instead of configuring safe egress.
- Impact on security or reliability, if applicable: Weakens fail-closed URL validation and can produce runtime failures.
- Whether it was mentioned in the prior review log: No.
- Whether a previous fix claimed to address it: No.
- Whether that previous fix is sufficient: Not applicable.
- Recommended remediation: Forbid unresolved-host bypass in production, or require an explicit allowlist and network egress policy.
- Suggested validation or test: Production settings test asserting unresolved-host bypass is rejected.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-010: Real secret-manager setup is not documented or enforced enough for upstream auth

- Category: Security / developer experience
- Severity: Medium
- Confidence: High
- File path or area: Product README, `settings.py`, `integrations/secrets.py`
- Evidence: Documentation tells users to use `secret_ref`, but the implementation defaults to an in-memory provider and does not describe a concrete production provider configuration path.
- Why it matters: Operators can configure bearer/API-key upstream auth in a way that passes tests but fails after restart or across workers.
- Root cause or likely root cause: Product docs describe the abstraction but not an implemented production backend.
- Impact on production readiness: Medium to high depending deployment.
- Impact on developer experience, if applicable: Adoption path is confusing for teams that need protected upstreams.
- Impact on security or reliability, if applicable: Secret loss, inconsistent retrieval, and rotation gaps.
- Whether it was mentioned in the prior review log: Partially.
- Whether a previous fix claimed to address it: Upstream auth docs were claimed improved.
- Whether that previous fix is sufficient: No.
- Recommended remediation: Provide a working production secret-provider integration and setup guide.
- Suggested validation or test: End-to-end test storing and retrieving an upstream secret through the configured production provider.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-011: Legacy unpeppered gateway token hash acceptance can be enabled in production

- Category: Security / credential storage
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/agents/credentials.py`, `packages/product-platform/src/product_platform/api/app.py`
- Evidence: `credential_token_hash_candidates()` can include legacy SHA-256 hashes when `OPHANIX_GATEWAY_TOKEN_HASH_ACCEPT_LEGACY=true`. Production startup requires `gateway_token_hash_pepper` but does not appear to reject legacy acceptance.
- Why it matters: Legacy unsalted lookup hashes should be migration-only and time-bound. Leaving acceptance enabled expands the blast radius of a DB dump.
- Root cause or likely root cause: Backward compatibility migration switch is not guarded by production policy.
- Impact on production readiness: Medium.
- Impact on developer experience, if applicable: Operators may not understand when legacy acceptance should be removed.
- Impact on security or reliability, if applicable: Increased offline token verification risk for old hashes.
- Whether it was mentioned in the prior review log: Yes, token hashing was discussed.
- Whether a previous fix claimed to address it: Token peppering and docs were claimed.
- Whether that previous fix is sufficient: Partially. Production can still opt into legacy acceptance.
- Recommended remediation: Add startup warning/failure in production when legacy acceptance is enabled, plus migration metrics and a sunset date.
- Suggested validation or test: Production config test rejecting `OPHANIX_GATEWAY_TOKEN_HASH_ACCEPT_LEGACY=true`.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-012: Runtime response storage can persist sensitive upstream data

- Category: Security / data handling
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/tool_gateway/response.py`, `packages/product-platform/src/product_platform/api/app.py`
- Evidence: Response policies can store full response bodies after policy processing. Redaction is policy- and pattern-dependent, and policy-disabled paths bypass redaction entirely.
- Why it matters: Upstream payloads can contain PII, secrets, tokens, or regulated data. Persisting them in SQLite audit tables creates retention and breach exposure.
- Root cause or likely root cause: Audit/debuggability is prioritized without a strict data-minimization default for all paths.
- Impact on production readiness: Medium.
- Impact on developer experience, if applicable: Operators must understand subtle response policy settings to avoid over-collection.
- Impact on security or reliability, if applicable: Data leakage and compliance risk.
- Whether it was mentioned in the prior review log: Yes, response storage semantics were discussed.
- Whether a previous fix claimed to address it: Partially. Redaction and storage semantics were improved.
- Whether that previous fix is sufficient: No.
- Recommended remediation: Make storage opt-in with stricter defaults, add retention/TTL, encrypt sensitive audit fields, and document data classification.
- Suggested validation or test: Tests proving secrets/PII are not persisted by default and that disabled policies cannot store raw sensitive bodies unintentionally.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-013: Disabled response policy bypasses validation and redaction

- Category: Security / response handling
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/tool_gateway/response.py`
- Evidence: `process_tool_execution_response()` returns a completed decision with the original execution body when `policy is None`.
- Why it matters: Turning off a policy disables redaction, response-size policy checks, schema validation, and field exposure rules. In a gateway product, the safe baseline should be explicit and hard to bypass.
- Root cause or likely root cause: "No policy" is treated as "allow everything" instead of "minimal safe default."
- Impact on production readiness: Medium.
- Impact on developer experience, if applicable: Operators may not realize policy absence changes security posture so dramatically.
- Impact on security or reliability, if applicable: Data leakage and schema drift risk.
- Whether it was mentioned in the prior review log: Partially.
- Whether a previous fix claimed to address it: Response policy hardening was claimed.
- Whether that previous fix is sufficient: No.
- Recommended remediation: Apply a safe default response policy when none exists, or require an explicit privileged override to disable processing.
- Suggested validation or test: Tests for no-policy behavior proving redaction/size defaults still apply.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-014: Runtime audit summaries are not PII-aware and have no retention policy

- Category: Security / privacy / operations
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/tool_gateway/runtime_audit.py`, repository/runtime action tables
- Evidence: Payload summarization redacts secret-like keys and values, but not general PII or business-sensitive identifiers. No TTL or retention mechanism for runtime actions/events was found.
- Why it matters: Agent payloads and tool responses can include personal or regulated data even when they do not look like tokens or passwords.
- Root cause or likely root cause: Audit logging focuses on secret redaction, not broader data minimization and retention.
- Impact on production readiness: Medium.
- Impact on developer experience, if applicable: Teams lack clear guidance on what data is recorded and for how long.
- Impact on security or reliability, if applicable: Privacy/compliance exposure.
- Whether it was mentioned in the prior review log: No, not deeply.
- Whether a previous fix claimed to address it: No.
- Whether that previous fix is sufficient: Not applicable.
- Recommended remediation: Add data classification, configurable retention, deletion jobs, audit encryption, and PII minimization.
- Suggested validation or test: Tests for retention cleanup and payload summaries with PII-like fields.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-015: Offset pagination can miss or duplicate tools during concurrent changes

- Category: API correctness / runtime behavior
- Severity: Medium
- Confidence: High
- File path or area: SDK `list_all_tools()` and `get_tool()`, repository list methods
- Evidence: SDK pagination advances by `offset += len(page)` while server ordering is mutable by `updated_at`/`id`. Concurrent creates/updates/deactivations can shift rows between pages.
- Why it matters: Discovery can miss callable tools or return duplicates in active environments.
- Root cause or likely root cause: Offset pagination was chosen instead of cursor pagination over a stable snapshot or stable cursor.
- Impact on production readiness: Medium.
- Impact on developer experience, if applicable: Agents may see nondeterministic discovery results.
- Impact on security or reliability, if applicable: Reliability risk for discovery and tool lookup.
- Whether it was mentioned in the prior review log: Pagination was mentioned, but this concurrency issue was not fixed.
- Whether a previous fix claimed to address it: `get_tool()` first-page behavior was fixed.
- Whether that previous fix is sufficient: No.
- Recommended remediation: Add cursor pagination with stable sort keys and de-duplication in SDK helpers.
- Suggested validation or test: Simulate concurrent tool update/create between pages and assert no miss/duplicate under cursor pagination.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-016: No background health-check scheduler for upstream targets

- Category: Reliability / operations
- Severity: Medium
- Confidence: Medium
- File path or area: `packages/product-platform/src/product_platform/tool_gateway/health.py`, `packages/product-platform/src/product_platform/api/app.py`
- Evidence: Health checker code and a manual health route exist, and targets store interval/status fields. No background worker or scheduler was found that periodically checks targets according to `interval_seconds`.
- Why it matters: Health state can become stale and manual checks do not provide automated degradation detection.
- Root cause or likely root cause: Health check model and route were implemented before operational scheduling.
- Impact on production readiness: Medium.
- Impact on developer experience, if applicable: Operators may assume configured health intervals are active.
- Impact on security or reliability, if applicable: Reliability risk from stale healthy/unhealthy status.
- Whether it was mentioned in the prior review log: Earlier health bugs were mentioned, but this scheduler gap was not deeply reviewed.
- Whether a previous fix claimed to address it: Manual health route wiring was fixed.
- Whether that previous fix is sufficient: No.
- Recommended remediation: Add a scheduler/worker for target health checks or remove interval semantics until implemented.
- Suggested validation or test: Time-driven integration test proving health checks run automatically and update state.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-017: Invocation fail-closed health behavior can rely on stale unhealthy state

- Category: Reliability / runtime behavior
- Severity: Medium
- Confidence: Medium
- File path or area: `packages/product-platform/src/product_platform/tool_gateway/invocation.py`, app invocation path
- Evidence: Invocation rejects targets when preloaded status is `unhealthy`; no freshness threshold around `last_checked_at` was found in the invocation path.
- Why it matters: A transient failure can keep a tool blocked until someone manually refreshes health, especially without a background scheduler.
- Root cause or likely root cause: Status value is checked without staleness semantics.
- Impact on production readiness: Medium.
- Impact on developer experience, if applicable: Operators may see confusing denials after the upstream has recovered.
- Impact on security or reliability, if applicable: Availability risk.
- Whether it was mentioned in the prior review log: No.
- Whether a previous fix claimed to address it: No.
- Whether that previous fix is sufficient: Not applicable.
- Recommended remediation: Add freshness thresholds, automatic recheck behavior, and clear error metadata.
- Suggested validation or test: Test invocation behavior for stale unhealthy status, recovered upstream, and background refresh.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-018: No upstream circuit breaker or adaptive backpressure

- Category: Reliability / resilience
- Severity: Medium
- Confidence: Medium
- File path or area: Invocation executor and gateway app runtime
- Evidence: Runtime has timeouts, health status, and process-local request limiting, but no circuit breaker, failure-window tracking, or adaptive per-upstream backpressure was found.
- Why it matters: A degraded upstream can consume gateway resources and produce repeated failures until manual health state changes.
- Root cause or likely root cause: Minimal direct HTTP executor rather than full resilience layer.
- Impact on production readiness: Medium.
- Impact on developer experience, if applicable: Operators must handle per-upstream failure control outside the product.
- Impact on security or reliability, if applicable: Reliability and cascading-failure risk.
- Whether it was mentioned in the prior review log: Partially, as degraded-service behavior and rate-limit concerns.
- Whether a previous fix claimed to address it: No.
- Whether that previous fix is sufficient: Not applicable.
- Recommended remediation: Add per-upstream circuit breaker/failure budgets and explicit recovery semantics.
- Suggested validation or test: Failure-storm tests against a slow/failing upstream and assertions that gateway resource use remains bounded.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-019: Standalone SDK local tests fail without installation or `PYTHONPATH`

- Category: Developer experience / testing
- Severity: Low
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/pyproject.toml`, SDK tests
- Evidence: Running `python3 -m pytest tests -q --tb=short` from the SDK package failed with `ModuleNotFoundError: No module named 'ophanix_tool_gateway'`. The same command passed with `PYTHONPATH=src`.
- Why it matters: A new contributor following common pytest habits hits import errors unless they install the package or set `PYTHONPATH`.
- Root cause or likely root cause: Pytest config lacks a `pythonpath = ["src"]` entry and docs emphasize release installs more than contributor test setup.
- Impact on production readiness: Low.
- Impact on developer experience, if applicable: Contributor friction and confusing local validation.
- Impact on security or reliability, if applicable: Indirect, by making validation easier to skip.
- Whether it was mentioned in the prior review log: No.
- Whether a previous fix claimed to address it: No.
- Whether that previous fix is sufficient: Not applicable.
- Recommended remediation: Add pytest pythonpath config or document editable install as the required local flow.
- Suggested validation or test: Run `python3 -m pytest tests` from a clean checkout without manual `PYTHONPATH`.
- Whether it should affect scoring: Slightly.

### SDK-AUDIT-020: Product-platform local tests fail without installation or `PYTHONPATH`

- Category: Developer experience / testing
- Severity: Low
- Confidence: High
- File path or area: `packages/product-platform/pyproject.toml`, product tests
- Evidence: Running `python3 -m pytest tests/test_tool_gateway_*.py` from the product package failed with `ModuleNotFoundError: No module named 'product_platform'`. The same tests passed with `PYTHONPATH=src`.
- Why it matters: New contributors get a broken default test command for the exact gateway tests they are likely to run.
- Root cause or likely root cause: Pytest config lacks source path configuration.
- Impact on production readiness: Low.
- Impact on developer experience, if applicable: Local validation friction.
- Impact on security or reliability, if applicable: Indirect.
- Whether it was mentioned in the prior review log: No.
- Whether a previous fix claimed to address it: No.
- Whether that previous fix is sufficient: Not applicable.
- Recommended remediation: Add pytest pythonpath config, standardize editable-install docs, or use a task runner command everywhere.
- Suggested validation or test: Run focused and full pytest commands from a clean checkout without manual `PYTHONPATH`.
- Whether it should affect scoring: Slightly.

### SDK-AUDIT-021: Standalone SDK package has very thin independent test coverage

- Category: Testing
- Severity: Medium
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/tests`
- Evidence: The standalone SDK package currently has 10 passing tests. Much deeper SDK behavior coverage lives in product-platform compatibility tests.
- Why it matters: The independently distributed package should prove its own behavior without relying on a larger product test suite.
- Root cause or likely root cause: The SDK originated inside product-platform and was extracted later.
- Impact on production readiness: Medium.
- Impact on developer experience, if applicable: Maintainers must know to run product tests to validate SDK behavior.
- Impact on security or reliability, if applicable: Regression risk if standalone package evolves separately.
- Whether it was mentioned in the prior review log: Partially, as package smoke/release tests.
- Whether a previous fix claimed to address it: Standalone smoke tests were added.
- Whether that previous fix is sufficient: No.
- Recommended remediation: Move or duplicate core SDK behavior tests into the standalone package and keep product compatibility tests as integration coverage.
- Suggested validation or test: Standalone SDK suite covering validation, retries, redaction, async/sync parity, custom clients, cache behavior, and close semantics.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-022: No live installed-wheel SDK to running-gateway contract test

- Category: Testing / integration
- Severity: High
- Confidence: High
- File path or area: CI, SDK tests, product tests
- Evidence: Existing tests are in-process or use fake clients. No CI test installs the built SDK wheel, starts the product gateway as a service, issues a real credential, and exercises discovery/invocation over HTTP.
- Why it matters: Packaging, import paths, auth headers, FastAPI routing, gateway runtime, and SDK behavior can all pass in isolation while failing in a real consumer setup.
- Root cause or likely root cause: Package extraction and runtime tests were validated separately.
- Impact on production readiness: High.
- Impact on developer experience, if applicable: External adopters become the first true integration test.
- Impact on security or reliability, if applicable: Contract drift and release regression risk.
- Whether it was mentioned in the prior review log: Yes, as a known/deferred score cap.
- Whether a previous fix claimed to address it: No.
- Whether that previous fix is sufficient: No.
- Recommended remediation: Add a CI job that builds the wheel, installs it into a clean venv, starts the gateway, seeds credentials/tools, and runs SDK calls over HTTP.
- Suggested validation or test: Live wheel-to-gateway discovery, invocation, denial, 401, 429, malformed response, and timeout tests.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-023: No production-like load, concurrency, or multi-worker validation

- Category: Testing / reliability
- Severity: High
- Confidence: High
- File path or area: Test suite, CI workflows
- Evidence: The suite has many unit/in-process tests but no evidence of multi-worker gateway execution, SQLite contention tests, distributed limiter tests, or sustained load tests.
- Why it matters: The highest remaining risks only appear under concurrency: DB locks, in-memory limiter bypass, in-memory secret inconsistency, duplicate invocations, and upstream pressure.
- Root cause or likely root cause: CI focuses on deterministic unit/regression tests.
- Impact on production readiness: High.
- Impact on developer experience, if applicable: Operators lack capacity guidance and performance expectations.
- Impact on security or reliability, if applicable: Reliability incidents are plausible under real traffic.
- Whether it was mentioned in the prior review log: Yes.
- Whether a previous fix claimed to address it: No, it was deferred.
- Whether that previous fix is sufficient: No.
- Recommended remediation: Add load, stress, and multi-worker tests with a production-like database and upstream mock service.
- Suggested validation or test: Run N workers, concurrent discovery/invocation, rate-limit abuse, DB migration/load, upstream timeout/failure storms, and restart scenarios.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-024: Product mypy coverage is narrow and configured to skip imports

- Category: Maintainability / testing
- Severity: Low
- Confidence: High
- File path or area: `packages/product-platform/pyproject.toml`, `.github/workflows/ci.yml`
- Evidence: Product mypy config targets selected gateway paths and uses `ignore_missing_imports=true` and `follow_imports=skip`.
- Why it matters: Type regressions outside selected files or behind imports may be missed.
- Root cause or likely root cause: Pragmatic mypy rollout over a larger codebase.
- Impact on production readiness: Low to medium.
- Impact on developer experience, if applicable: Maintainers may overestimate type-safety coverage.
- Impact on security or reliability, if applicable: Indirect correctness risk.
- Whether it was mentioned in the prior review log: No.
- Whether a previous fix claimed to address it: No.
- Whether that previous fix is sufficient: Not applicable.
- Recommended remediation: Expand typed coverage gradually, remove `follow_imports=skip` for gateway-critical modules, and track a mypy strictness plan.
- Suggested validation or test: CI fails on type regressions in gateway dependencies, not only gateway leaf files.
- Whether it should affect scoring: Slightly.

### SDK-AUDIT-025: Release strict-git validation is not enforced in CI or publish workflow

- Category: Packaging / release
- Severity: Medium
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/scripts/validate_release.py`, `.github/workflows/ci.yml`, `.github/workflows/publish.yml`
- Evidence: The SDK validator has `--strict-git`, but CI/publish invocations do not pass it.
- Why it matters: Release validation can pass without proving the package version matches a clean tagged state.
- Root cause or likely root cause: Strict mode was added for local/manual use but not adopted in automation.
- Impact on production readiness: Medium.
- Impact on developer experience, if applicable: Release managers have to know which optional flag matters.
- Impact on security or reliability, if applicable: Supply-chain and provenance risk.
- Whether it was mentioned in the prior review log: Partially.
- Whether a previous fix claimed to address it: Release validator and CI wiring were claimed.
- Whether that previous fix is sufficient: No.
- Recommended remediation: Require `--strict-git` on release/tag builds and fail publication if the worktree/version/tag is inconsistent.
- Suggested validation or test: Release workflow dry-run from a tag and from an inconsistent version to prove enforcement.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-026: Publish workflow validates artifacts but does not publish to an index

- Category: Packaging / release
- Severity: Medium
- Confidence: High
- File path or area: `.github/workflows/publish.yml`, `docs/internal/pypi-publishing.md`
- Evidence: The workflow builds, validates, attests, and uploads artifacts, but comments and docs state PyPI/internal-index upload happens through separate approval/handoff. No actual trusted-publishing upload step exists.
- Why it matters: `pip install ophanix-tool-gateway-sdk` is not proven by repository automation. External adopters cannot rely on a complete release path from source to index.
- Root cause or likely root cause: Artifact handoff process is separated from package build validation.
- Impact on production readiness: Medium.
- Impact on developer experience, if applicable: Install instructions are conditional and may fail depending on index state.
- Impact on security or reliability, if applicable: Manual release handoffs are more error-prone.
- Whether it was mentioned in the prior review log: Yes.
- Whether a previous fix claimed to address it: Publish workflow and internal docs were added.
- Whether that previous fix is sufficient: No.
- Recommended remediation: Add trusted publishing to the target package index or document and automate the internal promotion pipeline with verifiable evidence.
- Suggested validation or test: Release dry-run proving package appears in the configured index and can be installed in a clean environment.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-027: Workflow dispatch package selector does not limit Python package matrix

- Category: CI / release ergonomics
- Severity: Low
- Confidence: Medium
- File path or area: `.github/workflows/publish.yml`
- Evidence: The workflow has a `package` input, but the Python build matrix still enumerates product-platform and the standalone SDK rather than selecting only the requested Python package.
- Why it matters: Manual release runs can build more artifacts than expected, increasing confusion and release review burden.
- Root cause or likely root cause: Matrix was extended without fully wiring the dispatch selector.
- Impact on production readiness: Low.
- Impact on developer experience, if applicable: Release operator friction.
- Impact on security or reliability, if applicable: Low supply-chain process risk from unintended artifacts.
- Whether it was mentioned in the prior review log: No.
- Whether a previous fix claimed to address it: No.
- Whether that previous fix is sufficient: Not applicable.
- Recommended remediation: Filter the matrix by workflow input or make the input semantics explicit.
- Suggested validation or test: Workflow dry-runs for `product-platform`, `ophanix-tool-gateway-sdk`, and `all`.
- Whether it should affect scoring: Slightly.

### SDK-AUDIT-028: SDK remains beta/pre-1.0 with no explicit compatibility matrix

- Category: API stability / documentation
- Severity: Medium
- Confidence: High
- File path or area: SDK `pyproject.toml`, SDK README, SDK changelog
- Evidence: Package version is `0.1.0` and classifier is beta. Docs do not provide a gateway-server compatibility matrix.
- Why it matters: External production teams need to know what server versions a client supports and what breaking-change policy applies.
- Root cause or likely root cause: Early SDK distribution stage.
- Impact on production readiness: Medium.
- Impact on developer experience, if applicable: Adopters cannot plan upgrades confidently.
- Impact on security or reliability, if applicable: Contract drift can break runtime calls.
- Whether it was mentioned in the prior review log: Yes, as beta/stability cap.
- Whether a previous fix claimed to address it: Docs and changelog were added.
- Whether that previous fix is sufficient: No.
- Recommended remediation: Add version compatibility matrix, semver policy, deprecation policy, and migration guide.
- Suggested validation or test: Contract tests asserting SDK version compatibility with gateway API versions.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-029: API reference omits the deprecated `status` parameter that the SDK still accepts

- Category: Documentation / API consistency
- Severity: Low
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/API_REFERENCE.md`, SDK `sdk.py`
- Evidence: SDK `list_tools()` still accepts `status: Literal["active"] | None` with a deprecation warning. API reference lists `list_tools(owner_team, limit, offset)` and omits `status`.
- Why it matters: Deprecated compatibility parameters should still be documented clearly until removed, especially if downstream users see type hints or warnings.
- Root cause or likely root cause: Docs describe preferred API, not the complete compatibility surface.
- Impact on production readiness: Low.
- Impact on developer experience, if applicable: Confusing warnings and incomplete reference docs.
- Impact on security or reliability, if applicable: None direct.
- Whether it was mentioned in the prior review log: No.
- Whether a previous fix claimed to address it: API reference was added.
- Whether that previous fix is sufficient: No.
- Recommended remediation: Document deprecated parameters in a compatibility/deprecations section with removal target.
- Suggested validation or test: Docs check comparing public signatures to API reference.
- Whether it should affect scoring: Slightly.

### SDK-AUDIT-030: SDK does not reject accidental `Bearer ` token prefixes early

- Category: Developer experience / auth input validation
- Severity: Low
- Confidence: High
- File path or area: SDK token providers and auth header construction
- Evidence: SDK docs say providers return the raw token. Header text validation rejects control characters but not a token string like `Bearer abc`, so the SDK can send `Authorization: Bearer Bearer abc`; server auth will reject later.
- Why it matters: A common integration mistake produces a less helpful server-side 401 instead of a local validation error.
- Root cause or likely root cause: Token validation is intentionally permissive at the SDK boundary.
- Impact on production readiness: Low.
- Impact on developer experience, if applicable: Slower auth debugging.
- Impact on security or reliability, if applicable: Minor, from ambiguous auth failures.
- Whether it was mentioned in the prior review log: No.
- Whether a previous fix claimed to address it: No.
- Whether that previous fix is sufficient: Not applicable.
- Recommended remediation: Reject tokens beginning with `Bearer ` or containing whitespace, with a clear message.
- Suggested validation or test: SDK tests for prefixed/whitespace tokens.
- Whether it should affect scoring: Slightly.

### SDK-AUDIT-031: SDK cache fingerprint uses unsalted SHA-256 of the bearer token

- Category: Security / diagnostics
- Severity: Low
- Confidence: High
- File path or area: SDK `_auth_context()`
- Evidence: Cache key material uses `hashlib.sha256(token.encode()).hexdigest()`.
- Why it matters: The value is internal and not logged by default, but if memory or debug state is dumped it is an offline-verifiable token fingerprint.
- Root cause or likely root cause: Stable token partitioning was implemented without a process-local salt/HMAC.
- Impact on production readiness: Low.
- Impact on developer experience, if applicable: None direct.
- Impact on security or reliability, if applicable: Low token-correlation risk.
- Whether it was mentioned in the prior review log: Cache partitioning was mentioned; this residual was not.
- Whether a previous fix claimed to address it: Cache partitioning fix was claimed.
- Whether that previous fix is sufficient: Mostly, but not ideal.
- Recommended remediation: Use a process-local random salt or keyed HMAC for SDK cache fingerprints.
- Suggested validation or test: Assert cache partitioning still works and fingerprints cannot be recomputed without process secret.
- Whether it should affect scoring: Slightly.

### SDK-AUDIT-032: SDK `get_tool()` not-found error includes caller-supplied lookup text

- Category: Security / logging hygiene
- Severity: Low
- Confidence: High
- File path or area: SDK `get_tool()`
- Evidence: The not-found path raises `Tool not found: {normalized_tool_name}`.
- Why it matters: If callers accidentally pass sensitive text as a tool name, logs can retain it.
- Root cause or likely root cause: Helpful error message includes raw lookup value.
- Impact on production readiness: Low.
- Impact on developer experience, if applicable: Error is helpful, but could be safer with redaction/truncation.
- Impact on security or reliability, if applicable: Low accidental log exposure risk.
- Whether it was mentioned in the prior review log: No.
- Whether a previous fix claimed to address it: Error message redaction was improved elsewhere.
- Whether that previous fix is sufficient: Partially.
- Recommended remediation: Truncate and sanitize lookup values in exception messages.
- Suggested validation or test: Error-message test with token-like lookup string.
- Whether it should affect scoring: Slightly.

### SDK-AUDIT-033: SDK clients have no explicit closed-state guard

- Category: Runtime behavior / developer experience
- Severity: Low
- Confidence: Medium
- File path or area: SDK `close()` and request methods
- Evidence: `close()` delegates to the underlying client, but request methods do not appear to check a `_closed` flag before using the client.
- Why it matters: Calls after close may surface HTTPX-specific runtime errors rather than deterministic SDK-owned errors.
- Root cause or likely root cause: Lifecycle is delegated to HTTPX.
- Impact on production readiness: Low.
- Impact on developer experience, if applicable: Confusing lifecycle errors in long-running agent processes.
- Impact on security or reliability, if applicable: Minor reliability/debuggability risk.
- Whether it was mentioned in the prior review log: No.
- Whether a previous fix claimed to address it: Resource cleanup was improved, but not closed-state errors.
- Whether that previous fix is sufficient: Partially.
- Recommended remediation: Track closed state and raise `ToolGatewayError` or `RuntimeError` with a stable message.
- Suggested validation or test: Sync and async calls after `close()` produce deterministic errors.
- Whether it should affect scoring: Slightly.

### SDK-AUDIT-034: Sync and async SDK paths still duplicate substantial logic

- Category: Maintainability
- Severity: Low
- Confidence: High
- File path or area: SDK `sdk.py`
- Evidence: Sync and async clients have mirrored constructors, auth context, discovery, invocation, and parsing paths.
- Why it matters: Duplicated behavior can drift during future fixes, especially around security-sensitive validation and retries.
- Root cause or likely root cause: Separate sync/async ergonomics were implemented directly in one file.
- Impact on production readiness: Low to medium over time.
- Impact on developer experience, if applicable: Maintainers must change two paths for many features.
- Impact on security or reliability, if applicable: Drift risk.
- Whether it was mentioned in the prior review log: Yes.
- Whether a previous fix claimed to address it: Some shared validation helpers were added.
- Whether that previous fix is sufficient: Partially, but duplication remains.
- Recommended remediation: Extract shared request/response normalization and config logic; keep transport-specific boundaries small.
- Suggested validation or test: Mutation tests or parity tests that force sync/async behavior equality for every public method.
- Whether it should affect scoring: Slightly.

### SDK-AUDIT-035: Injected custom HTTP clients can bypass streaming response caps

- Category: Reliability / integration safety
- Severity: Medium
- Confidence: High
- File path or area: SDK transport helpers, product README
- Evidence: README states custom executors or injected HTTP clients must provide equivalent streaming limits. SDK fallback for clients without `stream()` necessarily sees materialized responses.
- Why it matters: Large or malicious responses can be loaded before SDK size caps are applied when a custom client does not support streaming.
- Root cause or likely root cause: SDK supports broad custom client injection without requiring the streaming interface.
- Impact on production readiness: Medium for custom integrations.
- Impact on developer experience, if applicable: Consumers may not understand the safety contract of custom clients.
- Impact on security or reliability, if applicable: Memory pressure and denial-of-service risk.
- Whether it was mentioned in the prior review log: Yes, response cap concerns were discussed.
- Whether a previous fix claimed to address it: Streaming caps were added for default clients.
- Whether that previous fix is sufficient: Partially.
- Recommended remediation: Require `stream()` for custom clients in production mode or expose an explicit unsafe opt-in.
- Suggested validation or test: Custom client tests proving large responses fail before full materialization or are rejected at construction.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-036: SDK event hook failures are swallowed

- Category: Observability / developer experience
- Severity: Low
- Confidence: High
- File path or area: SDK event hook dispatch
- Evidence: Event hook exceptions are caught and logged at debug level so SDK calls continue.
- Why it matters: This protects primary calls, but telemetry/monitoring failures can silently hide production visibility gaps.
- Root cause or likely root cause: Hooks are intentionally best-effort.
- Impact on production readiness: Low.
- Impact on developer experience, if applicable: Users may think telemetry is active when hook delivery is failing.
- Impact on security or reliability, if applicable: Observability reliability risk.
- Whether it was mentioned in the prior review log: No.
- Whether a previous fix claimed to address it: Telemetry hooks were documented.
- Whether that previous fix is sufficient: Partially.
- Recommended remediation: Add optional strict hook mode or error counter callback.
- Suggested validation or test: Hook-failure tests proving counters/logs are visible.
- Whether it should affect scoring: Slightly.

### SDK-AUDIT-037: Wildcard tool credential scopes are supported without strong operational guardrails

- Category: Authorization / least privilege
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/tool_gateway/auth.py`, credential models
- Evidence: `GatewayPrincipal.allows_tool_scope()` allows wildcard tool scope when `resource_id` is `None`.
- Why it matters: A single credential can authorize broad tool discovery/invocation if combined with agent permissions. That may be necessary for some agents, but production use needs explicit issuance controls and audit.
- Root cause or likely root cause: Flexible credential scope model.
- Impact on production readiness: Medium.
- Impact on developer experience, if applicable: Credential scope semantics are powerful but easy to over-grant.
- Impact on security or reliability, if applicable: Excess privilege blast radius.
- Whether it was mentioned in the prior review log: Resource-bound scopes were discussed.
- Whether a previous fix claimed to address it: Resource-bound scope support was added.
- Whether that previous fix is sufficient: Partially.
- Recommended remediation: Require explicit admin confirmation for wildcard tool scopes, add issuance audit flags, and document least-privilege defaults.
- Suggested validation or test: Tests and admin workflows distinguishing wildcard from resource-bound grants.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-038: Credential scope issuance does not verify referenced tool existence or required-scope match

- Category: Authorization / developer experience
- Severity: Medium
- Confidence: Medium
- File path or area: `packages/product-platform/src/product_platform/agents/credentials.py`, credential scope models, repository permission grants
- Evidence: Scope requests allow `resource_type="tool"` and optional `resource_id`; invocation later checks tool/permission/scope compatibility, but issuance-time verification against a real tool was not found.
- Why it matters: Operators can issue credentials that are broader than intended or credentials that never work, with failure deferred to runtime.
- Root cause or likely root cause: Credential issuance is generic across agent/claim/tool resources.
- Impact on production readiness: Medium.
- Impact on developer experience, if applicable: Confusing 403/denied behavior after apparently successful credential creation.
- Impact on security or reliability, if applicable: Least-privilege and authorization-management risk.
- Whether it was mentioned in the prior review log: Partially.
- Whether a previous fix claimed to address it: Resource scope validation was improved.
- Whether that previous fix is sufficient: No.
- Recommended remediation: Validate tool resource IDs and required scopes during credential issuance, or make wildcard creation a separate privileged path.
- Suggested validation or test: Credential issuance tests for nonexistent tool, wrong required scope, wildcard scope, and renamed/deactivated tools.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-039: Agent-tool permission grants defer required-scope mismatch to runtime

- Category: Authorization / operations
- Severity: Medium
- Confidence: Medium
- File path or area: `packages/product-platform/src/product_platform/tool_gateway/repository.py`, `decision.py`
- Evidence: Permission grant paths create agent-tool permissions, while decision-time checks enforce required scope compatibility. Grant-time required-scope validation was not evident.
- Why it matters: Invalid permissions can be stored and only fail at invocation time.
- Root cause or likely root cause: Authorization correctness is centralized in decision evaluation rather than write-time validation.
- Impact on production readiness: Medium.
- Impact on developer experience, if applicable: Operators see successful grants that later deny.
- Impact on security or reliability, if applicable: Operational correctness risk; less direct security risk because runtime denies.
- Whether it was mentioned in the prior review log: Partially.
- Whether a previous fix claimed to address it: Decision-layer scope checks were improved.
- Whether that previous fix is sufficient: Partially.
- Recommended remediation: Enforce required-scope consistency at grant time and provide migration cleanup for invalid grants.
- Suggested validation or test: Grant APIs reject mismatched scope before runtime.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-040: Upstream auth header prefix validation is permissive

- Category: Security / input validation
- Severity: Low
- Confidence: Medium
- File path or area: `packages/product-platform/src/product_platform/tool_gateway/models.py`, `invocation.py`
- Evidence: `header_prefix` rejects line breaks but otherwise permits arbitrary text that is concatenated with the secret for header output.
- Why it matters: Invalid or surprising auth schemes can be configured and sent to upstreams. CRLF injection is blocked, but the allowed grammar is broader than necessary.
- Root cause or likely root cause: Flexible upstream header customization.
- Impact on production readiness: Low.
- Impact on developer experience, if applicable: Misconfiguration can produce confusing upstream 401s.
- Impact on security or reliability, if applicable: Low header misuse risk.
- Whether it was mentioned in the prior review log: No.
- Whether a previous fix claimed to address it: Upstream auth was added.
- Whether that previous fix is sufficient: Mostly, but validation can tighten.
- Recommended remediation: Restrict `header_prefix` to a conservative token pattern plus optional trailing space.
- Suggested validation or test: Reject prefixes with tabs, multiple header-like tokens, leading/trailing surprises, and very long values.
- Whether it should affect scoring: Slightly.

### SDK-AUDIT-041: URL validation depends on DNS resolution at configuration time

- Category: Reliability / developer experience
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/tool_gateway/models.py`
- Evidence: Upstream URL validation attempts to resolve hostnames and rejects forbidden address ranges based on current DNS results unless unresolved-host bypass is allowed.
- Why it matters: Private DNS, split-horizon DNS, CI environments, and transient resolver failures can block legitimate target registration. The unsafe workaround is to allow unresolved hosts.
- Root cause or likely root cause: SSRF controls are implemented in application validation rather than infrastructure egress policy.
- Impact on production readiness: Medium.
- Impact on developer experience, if applicable: Operators may hit registration failures unrelated to actual runtime reachability.
- Impact on security or reliability, if applicable: Reliability risk and pressure to weaken SSRF settings.
- Whether it was mentioned in the prior review log: Partially.
- Whether a previous fix claimed to address it: SSRF DNS validation was added.
- Whether that previous fix is sufficient: Partially.
- Recommended remediation: Pair application validation with explicit allowlists and runtime egress controls; document private DNS setup.
- Suggested validation or test: Tests for split-horizon/private DNS deployment and safe allowlist behavior.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-042: OAuth, mTLS, and dynamic per-tenant upstream auth are not implemented

- Category: Feature completeness / adoption
- Severity: Medium
- Confidence: High
- File path or area: Product README, upstream auth models
- Evidence: README states OAuth and dynamic per-tenant upstream auth remain future product work. Supported modes are `none`, `bearer`, and `api_key`.
- Why it matters: Many production upstreams require OAuth client credentials, mTLS, short-lived tokens, or per-tenant delegated auth.
- Root cause or likely root cause: Initial upstream auth implementation covers static secret modes only.
- Impact on production readiness: Medium for teams with modern upstream auth requirements.
- Impact on developer experience, if applicable: Adopters may need custom middleware or cannot use the gateway for protected upstreams.
- Impact on security or reliability, if applicable: Teams may overuse static secrets where short-lived credentials are expected.
- Whether it was mentioned in the prior review log: Yes, earlier as unsupported upstream auth; partially fixed.
- Whether a previous fix claimed to address it: Bearer/API-key upstream auth was added.
- Whether that previous fix is sufficient: Partially.
- Recommended remediation: Add OAuth/mTLS/dynamic credential provider support with rotation and caching semantics.
- Suggested validation or test: Integration tests for OAuth token refresh, mTLS client certs, and tenant-scoped credential selection.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-043: Query allowlists reduce risk but do not cap URL/path expansion separately

- Category: Runtime behavior / input validation
- Severity: Low
- Confidence: Medium
- File path or area: `packages/product-platform/src/product_platform/tool_gateway/invocation.py`
- Evidence: Request payload size is capped, and GET/DELETE query allowlists reject credential-like keys. Path parameters and query values are stringified from payload values, but no separate final URL length cap was found.
- Why it matters: Large allowed scalar values can create overly long URLs or upstream/proxy failures even when the JSON payload is under the body cap.
- Root cause or likely root cause: Body-size limits were implemented separately from constructed URL limits.
- Impact on production readiness: Low.
- Impact on developer experience, if applicable: Upstream 414/400 errors may be confusing.
- Impact on security or reliability, if applicable: Minor reliability/DoS risk.
- Whether it was mentioned in the prior review log: Query allowlists were mentioned; URL length was not.
- Whether a previous fix claimed to address it: Query allowlists were added.
- Whether that previous fix is sufficient: Partially.
- Recommended remediation: Add configurable final URL length cap and per-parameter length validation.
- Suggested validation or test: Invocation tests with large path/query values.
- Whether it should affect scoring: Slightly.

### SDK-AUDIT-044: SDK raises built-in `ValueError` for many boundary errors instead of SDK-specific exceptions

- Category: Public API / developer experience
- Severity: Low
- Confidence: High
- File path or area: SDK validation helpers
- Evidence: Public constructors and methods raise `ValueError` for invalid configuration and input validation, while network/gateway failures use SDK-specific error types.
- Why it matters: Consumers must catch both SDK errors and built-in validation errors, and validation failures are less discoverable in the SDK error hierarchy.
- Root cause or likely root cause: Pythonic local validation style.
- Impact on production readiness: Low.
- Impact on developer experience, if applicable: Slightly less ergonomic error handling.
- Impact on security or reliability, if applicable: None direct.
- Whether it was mentioned in the prior review log: No.
- Whether a previous fix claimed to address it: Error typing was improved for gateway errors.
- Whether that previous fix is sufficient: Partially.
- Recommended remediation: Add `ToolGatewayConfigurationError` or `ToolGatewayValidationError` subclasses while preserving `ValueError` compatibility if needed.
- Suggested validation or test: Public API error taxonomy tests.
- Whether it should affect scoring: Slightly.

### SDK-AUDIT-045: SDK redaction is pattern-based and incomplete by design

- Category: Security / logging
- Severity: Medium
- Confidence: High
- File path or area: SDK error redaction helpers
- Evidence: Redaction covers bearer tokens, common `token=`, `secret=`, password, and API-key patterns. Arbitrary secrets, domain identifiers, and PII not matching those patterns can remain in diagnostic data.
- Why it matters: SDK exceptions are a common log sink. Pattern-based redaction should be treated as best-effort, not a guarantee.
- Root cause or likely root cause: Generic SDK cannot know all sensitive domain fields.
- Impact on production readiness: Medium.
- Impact on developer experience, if applicable: Users may overtrust sanitized diagnostics.
- Impact on security or reliability, if applicable: Accidental log exposure risk.
- Whether it was mentioned in the prior review log: Yes.
- Whether a previous fix claimed to address it: Redaction was expanded.
- Whether that previous fix is sufficient: Partially.
- Recommended remediation: Document redaction limits prominently and let consumers configure custom redactors or disable response-body diagnostics.
- Suggested validation or test: Tests for common JWT/API-key/PII shapes and custom redaction hooks.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-046: Response redaction defaults are not domain-PII aware

- Category: Security / privacy
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/tool_gateway/response.py`
- Evidence: Default redaction focuses on secret-like keys/patterns, not domain-specific PII such as names, addresses, emails in arbitrary nested payload fields, claim/customer IDs, or regulated attributes.
- Why it matters: A production tool gateway will commonly process personal or business-sensitive data that is not a secret token.
- Root cause or likely root cause: Generic response policy model lacks data-classification rules.
- Impact on production readiness: Medium.
- Impact on developer experience, if applicable: Operators must design every response policy correctly.
- Impact on security or reliability, if applicable: Privacy/compliance risk.
- Whether it was mentioned in the prior review log: Partially.
- Whether a previous fix claimed to address it: Redaction rules were improved.
- Whether that previous fix is sufficient: No.
- Recommended remediation: Add built-in PII classifiers/presets, policy templates, and strict defaults for storage/logging.
- Suggested validation or test: Response-policy tests with representative PII payloads.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-047: No formal threat model is present for the Tool Gateway trust boundaries

- Category: Security / documentation
- Severity: Medium
- Confidence: High
- File path or area: Repository docs
- Evidence: README and security policy cover setup and reporting, but no formal threat model was found for agent credentials, upstream targets, secret refs, SSRF, audit storage, and external SDK consumers.
- Why it matters: This code crosses multiple trust boundaries: external agents, product users, upstream HTTP services, credentials, and persisted audit logs.
- Root cause or likely root cause: Remediation focused on code/test fixes, not threat-model documentation.
- Impact on production readiness: Medium.
- Impact on developer experience, if applicable: Security reviewers at adopting teams lack a single review artifact.
- Impact on security or reliability, if applicable: Missed design assumptions and inconsistent controls.
- Whether it was mentioned in the prior review log: As a 9/10 requirement, not as completed.
- Whether a previous fix claimed to address it: No.
- Whether that previous fix is sufficient: Not applicable.
- Recommended remediation: Write and maintain a threat model with assets, actors, trust boundaries, abuse cases, controls, and residual risks.
- Suggested validation or test: Security review sign-off requiring threat model updates for gateway changes.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-048: No operational runbook for gateway production incidents

- Category: Operations / documentation
- Severity: Medium
- Confidence: High
- File path or area: Product and SDK docs
- Evidence: Docs include setup and release notes, but no runbook was found for token compromise, secret rotation, upstream outage, stuck unhealthy targets, rate-limit spikes, DB restore, or audit-data deletion.
- Why it matters: Production readiness includes incident response and operational procedures, not only code paths.
- Root cause or likely root cause: The project is still in product/test hardening rather than operations hardening.
- Impact on production readiness: Medium.
- Impact on developer experience, if applicable: External adopters must create their own operational model.
- Impact on security or reliability, if applicable: Slower incident response and recovery.
- Whether it was mentioned in the prior review log: Partially, as production checklist/runbook gaps.
- Whether a previous fix claimed to address it: Production checklist was added.
- Whether that previous fix is sufficient: No.
- Recommended remediation: Add runbooks for credential rotation, limiter tuning, upstream failure, DB backup/restore, audit retention, and release rollback.
- Suggested validation or test: Tabletop incident exercises and docs review.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-049: Changelog does not reflect the breadth of security/runtime remediation

- Category: Documentation / release
- Severity: Low
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/CHANGELOG.md`
- Evidence: The SDK changelog is minimal relative to the many security, retry, validation, async, packaging, and compatibility changes described in remediation logs.
- Why it matters: External adopters use changelogs to assess upgrade risk and security-relevant changes.
- Root cause or likely root cause: Changelog was created as package metadata, not maintained as a detailed release artifact.
- Impact on production readiness: Low.
- Impact on developer experience, if applicable: Upgrade planning is harder.
- Impact on security or reliability, if applicable: Security-relevant changes are less visible.
- Whether it was mentioned in the prior review log: Changelog addition was mentioned.
- Whether a previous fix claimed to address it: Yes.
- Whether that previous fix is sufficient: No.
- Recommended remediation: Expand changelog entries with security, behavior, compatibility, and migration notes.
- Suggested validation or test: Release checklist requiring changelog coverage for public API/security changes.
- Whether it should affect scoring: Slightly.

### SDK-AUDIT-050: Package install docs reference PyPI before publication is proven

- Category: Documentation / packaging
- Severity: Medium
- Confidence: High
- File path or area: SDK README, publish workflow, internal publishing docs
- Evidence: SDK README starts with `pip install ophanix-tool-gateway-sdk` but immediately qualifies that the package may not be published to the configured index yet. Publish workflow does not publish to an index.
- Why it matters: A first-time external adopter may try the primary command and fail.
- Root cause or likely root cause: Docs anticipate package publication before repository automation proves it.
- Impact on production readiness: Medium.
- Impact on developer experience, if applicable: First-run install friction.
- Impact on security or reliability, if applicable: Users may install from local paths or ad hoc artifacts.
- Whether it was mentioned in the prior review log: Yes.
- Whether a previous fix claimed to address it: Docs were clarified.
- Whether that previous fix is sufficient: Partially.
- Recommended remediation: Either publish the package and verify install, or make local/internal install the primary documented path until publication is complete.
- Suggested validation or test: Clean-environment `pip install` from the documented index.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-051: Stale execution-log docs can contradict current package/API story

- Category: Documentation consistency
- Severity: Low
- Confidence: Medium
- File path or area: `docs/product-platform-worktree/execution-logs/06-tool-gateway-logs/*.md`
- Evidence: Historical execution logs still describe older package placement and previous scores. They are logs, but they live alongside current audit/remediation context and can be mistaken for current guidance.
- Why it matters: Long remediation trails make it easy for future reviewers to anchor on outdated conclusions.
- Root cause or likely root cause: Execution logs are append-only and not clearly separated from current docs.
- Impact on production readiness: Low.
- Impact on developer experience, if applicable: Review and onboarding confusion.
- Impact on security or reliability, if applicable: Indirect, from stale assumptions.
- Whether it was mentioned in the prior review log: Not applicable.
- Whether a previous fix claimed to address it: No.
- Whether that previous fix is sufficient: Not applicable.
- Recommended remediation: Add an index that marks superseded logs and points to the latest authoritative status.
- Suggested validation or test: Docs lint/check for "current status" links.
- Whether it should affect scoring: Slightly.

### SDK-AUDIT-052: Product package still vendors the SDK source, creating release/source ownership risk

- Category: Packaging / maintainability
- Severity: Low
- Confidence: High
- File path or area: `packages/product-platform/src/ophanix_tool_gateway`, standalone SDK package
- Evidence: The same SDK namespace exists in both the standalone package and product-platform. A parity check currently passes, but the source still has to be kept in sync.
- Why it matters: Duplicated distribution ownership can drift if parity validation is skipped or not enforced in every relevant workflow.
- Root cause or likely root cause: Compatibility import needs after SDK extraction.
- Impact on production readiness: Low to medium.
- Impact on developer experience, if applicable: Maintainers must know which copy is authoritative.
- Impact on security or reliability, if applicable: Drift could reintroduce fixed SDK bugs in one package.
- Whether it was mentioned in the prior review log: Yes.
- Whether a previous fix claimed to address it: Parity checks and compatibility exports were added.
- Whether that previous fix is sufficient: Partially.
- Recommended remediation: Make one source canonical through packaging/import dependency or enforce parity in all CI/release paths.
- Suggested validation or test: CI parity check failing on any difference between standalone and vendored files.
- Whether it should affect scoring: Slightly.

### SDK-AUDIT-053: Security dependency audit path is not fully reproducible from the default local validation flow

- Category: Supply chain / validation
- Severity: Low
- Confidence: High
- File path or area: SDK release validator, SDK README
- Evidence: `python3 scripts/validate_release.py --skip-twine-check --require-dependency-audit` failed locally until `[security]` extras are installed. The README does document installing security extras.
- Why it matters: Optional environment preparation makes local release validation easier to run incompletely.
- Root cause or likely root cause: Security tooling is an optional extra rather than bootstrapped by the validator.
- Impact on production readiness: Low.
- Impact on developer experience, if applicable: Release validators can fail with a setup error instead of self-installing/checking tools.
- Impact on security or reliability, if applicable: Indirect supply-chain validation risk.
- Whether it was mentioned in the prior review log: Yes, dependency audit was a recurring topic.
- Whether a previous fix claimed to address it: CI installs security extras and validator can require audit.
- Whether that previous fix is sufficient: Mostly for CI, not ideal locally.
- Recommended remediation: Make release validation command self-contained via a pinned tool environment or clearer `make release-check` wrapper.
- Suggested validation or test: Fresh venv release validation succeeds with one documented command.
- Whether it should affect scoring: Slightly.

### SDK-AUDIT-054: CI security scanning is present but not enough to prove package-level advisory coverage before publication

- Category: Supply chain / release
- Severity: Medium
- Confidence: Medium
- File path or area: `.github/workflows/ci.yml`, SDK release validator
- Evidence: CI runs dependency audit tooling, but unpublished local packages cannot be matched as published advisory subjects; previous logs acknowledge local package advisory matching remains unavailable before publication.
- Why it matters: Internal package vulnerabilities or accidental dependency confusion issues may not be covered by generic dependency audit.
- Root cause or likely root cause: Advisory ecosystems work best for published package coordinates.
- Impact on production readiness: Medium.
- Impact on developer experience, if applicable: Security status can look stronger than it is.
- Impact on security or reliability, if applicable: Supply-chain risk.
- Whether it was mentioned in the prior review log: Yes.
- Whether a previous fix claimed to address it: Dependency audit and dependency-confusion checks were added.
- Whether that previous fix is sufficient: Partially.
- Recommended remediation: Publish to the intended index, add internal advisory scanning, SBOM review, and dependency confusion checks for package coordinates.
- Suggested validation or test: Audited SBOM and package-index install scan from the published artifact.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-055: Direct HTTP examples and seed helpers use deterministic local tokens

- Category: Security / examples
- Severity: Low
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/tool_gateway/direct_http_examples.py`, tests/docs
- Evidence: Local examples/fixtures rely on deterministic tokens for repeatable demos and tests, with documentation warnings.
- Why it matters: Fixture tokens sometimes get copied into non-test environments.
- Root cause or likely root cause: Developer-friendly local demo setup.
- Impact on production readiness: Low.
- Impact on developer experience, if applicable: Useful locally but requires clear boundaries.
- Impact on security or reliability, if applicable: Low if docs are followed; higher if copied.
- Whether it was mentioned in the prior review log: Yes, fixture token warnings were discussed.
- Whether a previous fix claimed to address it: Docs warn about local-only tokens.
- Whether that previous fix is sufficient: Mostly.
- Recommended remediation: Make fixture token names unmistakably unsafe and add runtime guards preventing fixture tokens in production.
- Suggested validation or test: Production startup/use rejects known fixture token values.
- Whether it should affect scoring: Slightly.

### SDK-AUDIT-056: No final URL/domain allowlist for upstream invocation

- Category: Security / governance
- Severity: Medium
- Confidence: Medium
- File path or area: Upstream target models and invocation executor
- Evidence: Upstream URL validation blocks forbidden hosts/ranges but no organization/environment allowlist for approved domains or target categories was found in the gateway runtime.
- Why it matters: Production environments often need explicit outbound allowlists, not only blocklists.
- Root cause or likely root cause: Initial SSRF mitigation uses deny rules rather than positive policy.
- Impact on production readiness: Medium.
- Impact on developer experience, if applicable: Security teams may need to enforce policy outside the product.
- Impact on security or reliability, if applicable: SSRF and governance risk.
- Whether it was mentioned in the prior review log: Partially.
- Whether a previous fix claimed to address it: SSRF validation was added.
- Whether that previous fix is sufficient: No for strict production environments.
- Recommended remediation: Add configurable per-environment upstream domain allowlists and require them in production.
- Suggested validation or test: Tests rejecting unapproved external domains even when they pass generic SSRF checks.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-057: Gateway discovery exposes callable tool catalog to wildcard credentials

- Category: Security / information disclosure
- Severity: Low
- Confidence: Medium
- File path or area: Gateway discovery route and auth principal scope checks
- Evidence: Discovery returns active callable tools for the credential. Wildcard tool-scope credentials can therefore enumerate the callable catalog available to the associated agent/permissions.
- Why it matters: Tool names/descriptions/schemas may reveal internal capabilities or business workflows.
- Root cause or likely root cause: Discovery is designed for agent ergonomics and follows authorization filters.
- Impact on production readiness: Low to medium depending catalog sensitivity.
- Impact on developer experience, if applicable: Discovery is useful, but needs least-privilege credential practices.
- Impact on security or reliability, if applicable: Information disclosure risk from overbroad credentials.
- Whether it was mentioned in the prior review log: Gateway-safe discovery shape was discussed.
- Whether a previous fix claimed to address it: Discovery narrowed operator fields.
- Whether that previous fix is sufficient: Mostly, but wildcard scope remains a governance risk.
- Recommended remediation: Document catalog sensitivity, restrict wildcard issuance, and optionally add per-tool discovery visibility controls.
- Suggested validation or test: Tests for resource-bound credentials seeing only intended tool definitions.
- Whether it should affect scoring: Slightly.

### SDK-AUDIT-058: Built artifacts are validated, but release evidence is not archived in a reviewable manifest

- Category: Release / governance
- Severity: Low
- Confidence: Medium
- File path or area: `.github/workflows/publish.yml`, release docs
- Evidence: Workflow uploads artifacts and attestations, but no single release manifest tying commit, package versions, hashes, validator output, dependency audit, and install test was found.
- Why it matters: Production adopters and auditors need an easy way to verify exactly what was released.
- Root cause or likely root cause: Release workflow is artifact-oriented, not manifest-oriented.
- Impact on production readiness: Low.
- Impact on developer experience, if applicable: Release review is more manual.
- Impact on security or reliability, if applicable: Supply-chain traceability gap.
- Whether it was mentioned in the prior review log: Partially.
- Whether a previous fix claimed to address it: Provenance/attestation support was added.
- Whether that previous fix is sufficient: Partially.
- Recommended remediation: Generate and archive a release manifest per package.
- Suggested validation or test: Release workflow artifact includes manifest with hashes, commands, and audit outputs.
- Whether it should affect scoring: Slightly.

### SDK-AUDIT-059: No consumer-facing migration guide for compatibility import removal

- Category: Documentation / API lifecycle
- Severity: Low
- Confidence: High
- File path or area: SDK README, product compatibility exports
- Evidence: Docs prefer `ophanix_tool_gateway`, while compatibility shims remain. No removal timeline or migration guide was found.
- Why it matters: Existing users of `product_platform.tool_gateway.sdk` need a clear path before compatibility is removed.
- Root cause or likely root cause: Compatibility was preserved during extraction without a lifecycle document.
- Impact on production readiness: Low.
- Impact on developer experience, if applicable: Upgrade uncertainty.
- Impact on security or reliability, if applicable: None direct.
- Whether it was mentioned in the prior review log: Partially.
- Whether a previous fix claimed to address it: Compatibility exports were added.
- Whether that previous fix is sufficient: Partially.
- Recommended remediation: Add migration guide and deprecation/removal timeline.
- Suggested validation or test: Docs coverage check for deprecated public imports.
- Whether it should affect scoring: Slightly.

### SDK-AUDIT-060: Production readiness depends on external ingress limits that are documented but not verified

- Category: Reliability / operations
- Severity: Medium
- Confidence: High
- File path or area: Product README, deployment/CI
- Evidence: README says production deployments should enforce global edge rate limits and request-size limits at ingress because the built-in limiter is process-local. No deployment validation or infrastructure test proves those controls exist.
- Why it matters: Documented external dependencies are still production dependencies. Without verification, deployments can silently omit them.
- Root cause or likely root cause: Runtime package has no infrastructure-as-code or deployment conformance checks in this repo.
- Impact on production readiness: Medium.
- Impact on developer experience, if applicable: Adopters must translate prose into infrastructure.
- Impact on security or reliability, if applicable: Abuse and large-request risk if ingress controls are absent.
- Whether it was mentioned in the prior review log: Yes, as ingress/rate-limit caveat.
- Whether a previous fix claimed to address it: Documentation was added.
- Whether that previous fix is sufficient: No.
- Recommended remediation: Provide deployment templates or conformance checks that assert ingress limits are configured.
- Suggested validation or test: Environment smoke test proving edge body/rate limits are active before gateway traffic reaches the app.
- Whether it should affect scoring: Yes.

## 5. Issues Grouped By Category

Runtime architecture and reliability:

- SDK-AUDIT-001, SDK-AUDIT-002, SDK-AUDIT-004, SDK-AUDIT-005, SDK-AUDIT-006, SDK-AUDIT-007, SDK-AUDIT-015, SDK-AUDIT-016, SDK-AUDIT-017, SDK-AUDIT-018, SDK-AUDIT-023, SDK-AUDIT-035, SDK-AUDIT-041, SDK-AUDIT-043, SDK-AUDIT-060

Security, authorization, and data handling:

- SDK-AUDIT-003, SDK-AUDIT-008, SDK-AUDIT-009, SDK-AUDIT-010, SDK-AUDIT-011, SDK-AUDIT-012, SDK-AUDIT-013, SDK-AUDIT-014, SDK-AUDIT-031, SDK-AUDIT-032, SDK-AUDIT-037, SDK-AUDIT-038, SDK-AUDIT-039, SDK-AUDIT-040, SDK-AUDIT-045, SDK-AUDIT-046, SDK-AUDIT-047, SDK-AUDIT-055, SDK-AUDIT-056, SDK-AUDIT-057

Public API and developer experience:

- SDK-AUDIT-019, SDK-AUDIT-020, SDK-AUDIT-028, SDK-AUDIT-029, SDK-AUDIT-030, SDK-AUDIT-033, SDK-AUDIT-036, SDK-AUDIT-044, SDK-AUDIT-048, SDK-AUDIT-049, SDK-AUDIT-050, SDK-AUDIT-051, SDK-AUDIT-059

Testing:

- SDK-AUDIT-021, SDK-AUDIT-022, SDK-AUDIT-023, SDK-AUDIT-024, SDK-AUDIT-053

Packaging, CI, and release:

- SDK-AUDIT-025, SDK-AUDIT-026, SDK-AUDIT-027, SDK-AUDIT-052, SDK-AUDIT-054, SDK-AUDIT-058

## 6. Critical And High-Severity Blockers

No critical issue is proven by this audit.

High-severity blockers:

- SDK-AUDIT-001: Product gateway persistence remains SQLite-only.
- SDK-AUDIT-002: Production startup still permits SQLite through an escape hatch.
- SDK-AUDIT-003: Upstream secret provider is still an in-memory demo provider by default.
- SDK-AUDIT-004: No invocation idempotency or replay-protection contract.
- SDK-AUDIT-005: Runtime rate limiting is process-local and not production-distributed.
- SDK-AUDIT-008: SSRF defenses remain vulnerable to DNS rebinding and time-of-use changes.
- SDK-AUDIT-022: No live installed-wheel SDK to running-gateway contract test.
- SDK-AUDIT-023: No production-like load, concurrency, or multi-worker validation.

## 7. Medium-Severity Production Risks

- SDK-AUDIT-006: Rate limiter can be exhausted by distinct invalid authorization keys.
- SDK-AUDIT-007: Gateway rate-limit responses omit `Retry-After`.
- SDK-AUDIT-009: Unresolved upstream hosts can be allowed in production by environment variable.
- SDK-AUDIT-010: Real secret-manager setup is not documented or enforced enough for upstream auth.
- SDK-AUDIT-011: Legacy unpeppered gateway token hash acceptance can be enabled in production.
- SDK-AUDIT-012: Runtime response storage can persist sensitive upstream data.
- SDK-AUDIT-013: Disabled response policy bypasses validation and redaction.
- SDK-AUDIT-014: Runtime audit summaries are not PII-aware and have no retention policy.
- SDK-AUDIT-015: Offset pagination can miss or duplicate tools during concurrent changes.
- SDK-AUDIT-016: No background health-check scheduler for upstream targets.
- SDK-AUDIT-017: Invocation fail-closed health behavior can rely on stale unhealthy state.
- SDK-AUDIT-018: No upstream circuit breaker or adaptive backpressure.
- SDK-AUDIT-021: Standalone SDK package has very thin independent test coverage.
- SDK-AUDIT-026: Publish workflow validates artifacts but does not publish to an index.
- SDK-AUDIT-028: SDK remains beta/pre-1.0 with no explicit compatibility matrix.
- SDK-AUDIT-035: Injected custom HTTP clients can bypass streaming response caps.
- SDK-AUDIT-037: Wildcard tool credential scopes are supported without strong operational guardrails.
- SDK-AUDIT-038: Credential scope issuance does not verify referenced tool existence or required-scope match.
- SDK-AUDIT-039: Agent-tool permission grants defer required-scope mismatch to runtime.
- SDK-AUDIT-041: URL validation depends on DNS resolution at configuration time.
- SDK-AUDIT-042: OAuth, mTLS, and dynamic per-tenant upstream auth are not implemented.
- SDK-AUDIT-045: SDK redaction is pattern-based and incomplete by design.
- SDK-AUDIT-046: Response redaction defaults are not domain-PII aware.
- SDK-AUDIT-047: No formal threat model is present for the Tool Gateway trust boundaries.
- SDK-AUDIT-048: No operational runbook for gateway production incidents.
- SDK-AUDIT-050: Package install docs reference PyPI before publication is proven.
- SDK-AUDIT-054: CI security scanning is present but not enough to prove package-level advisory coverage before publication.
- SDK-AUDIT-056: No final URL/domain allowlist for upstream invocation.
- SDK-AUDIT-060: Production readiness depends on external ingress limits that are documented but not verified.

## 8. Low-Severity And Nit-Level Issues

- SDK-AUDIT-019: Standalone SDK local tests fail without installation or `PYTHONPATH`.
- SDK-AUDIT-020: Product-platform local tests fail without installation or `PYTHONPATH`.
- SDK-AUDIT-024: Product mypy coverage is narrow and configured to skip imports.
- SDK-AUDIT-027: Workflow dispatch package selector does not limit Python package matrix.
- SDK-AUDIT-029: API reference omits the deprecated `status` parameter that the SDK still accepts.
- SDK-AUDIT-030: SDK does not reject accidental `Bearer ` token prefixes early.
- SDK-AUDIT-031: SDK cache fingerprint uses unsalted SHA-256 of the bearer token.
- SDK-AUDIT-032: SDK `get_tool()` not-found error includes caller-supplied lookup text.
- SDK-AUDIT-033: SDK clients have no explicit closed-state guard.
- SDK-AUDIT-034: Sync and async SDK paths still duplicate substantial logic.
- SDK-AUDIT-036: SDK event hook failures are swallowed.
- SDK-AUDIT-040: Upstream auth header prefix validation is permissive.
- SDK-AUDIT-043: Query allowlists reduce risk but do not cap URL/path expansion separately.
- SDK-AUDIT-044: SDK raises built-in `ValueError` for many boundary errors instead of SDK-specific exceptions.
- SDK-AUDIT-049: Changelog does not reflect the breadth of security/runtime remediation.
- SDK-AUDIT-051: Stale execution-log docs can contradict current package/API story.
- SDK-AUDIT-052: Product package still vendors the SDK source, creating release/source ownership risk.
- SDK-AUDIT-053: Security dependency audit path is not fully reproducible from the default local validation flow.
- SDK-AUDIT-055: Direct HTTP examples and seed helpers use deterministic local tokens.
- SDK-AUDIT-057: Gateway discovery exposes callable tool catalog to wildcard credentials.
- SDK-AUDIT-058: Built artifacts are validated, but release evidence is not archived in a reviewable manifest.
- SDK-AUDIT-059: No consumer-facing migration guide for compatibility import removal.

## 9. Prior Findings Status Table

| Prior finding area | Current status | Challenge |
| --- | --- | --- |
| SDK discovery used operator route | Fixed | Gateway discovery route exists and SDK uses it. |
| Gateway discovery exposed operator fields | Fixed | Gateway response shape is narrower. Catalog sensitivity remains for wildcard credentials. |
| SDK weak input/response validation | Mostly fixed | Residual issues remain around token prefix validation, custom clients, and validation error taxonomy. |
| `get_tool()` first-page-only | Fixed for basic scale | Offset pagination remains unstable under concurrent changes. |
| Token repr and exception leakage | Improved | Redaction is pattern-based and incomplete by design. |
| Environment provider/list-all/cache invalidation/py.typed missing | Fixed | Standalone package tests remain thin. |
| Discovery retries missing `Retry-After` | SDK fixed | Gateway limiter itself omits `Retry-After`. |
| Standalone package missing | Fixed structurally | Publication to index is not automated/proven. |
| Async SDK missing | Fixed | Duplicated sync/async logic remains maintainability risk. |
| Resource-bound credential scopes missing | Improved | Wildcard issuance and issuance-time validation still need guardrails. |
| Upstream auth unsupported | Partially fixed | Static bearer/API-key modes exist, but real secret provider, OAuth, mTLS, and dynamic auth remain gaps. |
| SSRF controls missing | Improved | DNS rebinding, unresolved-host bypass, and lack of allowlist/egress proof remain. |
| Rate limiting missing | Partially fixed | In-process limiter is not distributed, can be key-exhausted, and omits `Retry-After`. |
| Runtime body/response caps missing | Improved | Custom clients can bypass streaming caps; ingress controls are external and unverified. |
| Production defaults weak | Improved | SQLite can still be allowed in production, and secret provider remains demo by default. |
| Failed-response leakage/response policy | Improved | Disabled policy and storage/PII retention remain risks. |
| Package/release validation missing | Improved | Strict-git not enforced, index publish absent, manifest/advisory evidence incomplete. |
| Load/multi-worker validation missing | Still open | This remains a major score cap. |
| Idempotency missing | Still open | This remains a major score cap. |

## 10. Scoring Matrix

| Score area | Current score | Prior latest score | Uphold/raise/lower | Exact reasons | Score cap | Next score requires | Reach 8 requires | Reach 9 requires |
| --- | ---: | ---: | --- | --- | ---: | --- | --- | --- |
| Implementation quality | 6 / 10 | 6 / 10 | Upheld | The SDK and gateway pass broad unit/in-process suites, release validators build artifacts, and several earlier correctness bugs are fixed. Implementation remains capped by SQLite-only persistence, demo secret provider, missing idempotency, no live wheel-to-gateway test, no load/multi-worker proof, offset pagination instability, and duplicated SDK source/logic. | 6 | Production DB plan, live contract test, idempotency design, real secret provider. | Production DB/pooling, idempotency API, distributed limiter, automatic health scheduler, cursor pagination, strong standalone SDK tests. | Mature modular architecture, proven live/load tests, enforced single source of SDK truth, release manifests, only minor residual issues. |
| Ease of use | 6 / 10 | 8 / 10 | Lowered | The SDK API is usable and documented, but external adoption still hits beta status, unpublished package path, missing compatibility matrix, incomplete API reference/deprecation docs, local test import failures, no real secret-manager setup guide, and no production runbook. | 6 | Fix install/publish story, local test setup, secret-manager guide, compatibility/deprecation docs. | Published package, generated/reference-complete docs, end-to-end quickstart against running gateway, stable compatibility matrix, runbooks. | GA-level docs, migration guides, examples for major auth modes, proven external onboarding, semver/deprecation discipline. |
| Security and reliability | 5 / 10 | 6 / 10 | Lowered | High risks remain across persistence, secret management, SSRF, rate limiting, idempotency, response/audit data retention, and production-like validation. Passing tests do not prove multi-worker or adversarial runtime behavior. | 5 | Remove production SQLite path, wire real secret provider, add idempotency, strengthen SSRF/egress controls, add distributed limiter plan. | Enforced production DB, idempotency/replay, distributed rate limits, runtime egress allowlists, retention/PII policy, load/failure testing. | Formal threat model, chaos/failure tests, managed secrets with rotation, SBOM/advisory coverage, operational SLOs/runbooks, low-only residual risks. |

## 11. Score Cap Explanation

Implementation quality cannot exceed 6 while the gateway runtime still depends on SQLite and in-memory/demo secret storage, lacks idempotency, lacks a live installed-wheel contract test, and lacks production-like load/multi-worker evidence.

Ease of use cannot exceed 6 because the happy-path SDK API is not enough for external production adoption. The install path is not proven through actual index publication, local tests fail without setup tweaks, real secret-manager configuration is not implemented/documented, and there is no complete compatibility/stability story.

Security and reliability cannot exceed 5 because multiple high-severity risks remain simultaneously. A single one of SQLite production posture, process-local limiter, missing idempotency, in-memory secret provider, or SSRF DNS-rebinding residual risk would cap the score. Together they make a 6+ security/reliability score too generous for broad production adoption.

Adversarial score-6-or-lower case: The strongest evidence is that the SDK depends on a server runtime that is not production-grade: SQLite-only, local secret provider, process-local rate limiting, no idempotency, no distributed/load validation, and incomplete operational controls. The repository proves many unit paths, but not production behavior.

Adversarial score-8-or-higher case: To justify 8+, the repo would need a real production DB backend, managed secret provider, idempotency contract, distributed/edge limiter proof, egress allowlist/SSRF runtime enforcement, live installed-wheel gateway integration, package publication proof, load/multi-worker tests, and clear runbooks. The current repo does not contain that evidence.

## 12. Required Fixes To Reach Production Readiness

Production readiness requires at minimum:

- Replace or augment SQLite with a production database backend, pooling, migrations, backups, restore tests, and multi-worker validation.
- Remove the production SQLite escape hatch or make it impossible in real production deployments.
- Wire a real secret manager and fail production startup when the demo provider is active.
- Add invocation idempotency/replay semantics and SDK support.
- Add distributed or enforced edge rate limiting, including `Retry-After` and protection against invalid-token key exhaustion.
- Strengthen SSRF controls with runtime egress enforcement, allowlists, and DNS-rebinding tests.
- Add retention, minimization, and encryption policy for runtime actions, audit events, and stored responses.
- Add live installed-wheel-to-running-gateway CI tests.
- Add production-like load, concurrency, multi-worker, and degraded-upstream tests.
- Complete release publication proof and strict release validation.

## 13. Required Fixes To Reach 8 Out Of 10

To reach 8, the repo must also provide:

- Published SDK package installable from the documented index.
- Generated or signature-complete API docs, deprecation policy, and SDK/gateway compatibility matrix.
- Cursor pagination or stable snapshot semantics for discovery.
- Automatic health checking or removal of misleading interval semantics.
- OAuth/mTLS/dynamic upstream auth roadmap or implementation for common production upstreams.
- PII-aware response/audit policies with safe defaults.
- End-to-end onboarding guide that creates credentials, configures secrets, starts the gateway, installs the SDK, and invokes a tool over real HTTP.
- CI parity enforcement for standalone and vendored SDK source.

## 14. Required Fixes To Reach 9 Out Of 10

To reach 9, the repo must demonstrate:

- Formal threat model and security review for all gateway trust boundaries.
- Chaos/failure tests for upstream timeouts, gateway restarts, DB failover, secret-provider outages, limiter backend outages, and duplicate invocation races.
- Full release manifest including hashes, SBOM, dependency audit, provenance, install verification, and advisory coverage.
- Mature production runbooks for token compromise, rotation, outage response, rollback, backup/restore, and audit deletion.
- Stable semver/GA policy with migration guides and compatibility tests.
- Strong observability story with metrics, traces, audit events, hook failure visibility, and SLO dashboards.
- Only low-severity residual issues.

## 15. Recommended Remediation Order

1. Fix production runtime foundations: production DB backend, remove SQLite production escape hatch, real secret provider.
2. Add invocation idempotency/replay semantics and live wheel-to-gateway contract test.
3. Replace process-local rate limiting with distributed/edge-enforced limits and add `Retry-After`.
4. Strengthen SSRF controls with egress allowlists, production guardrails, and DNS-rebinding tests.
5. Add retention/minimization/encryption policy for runtime and response audit data.
6. Add load, multi-worker, restart, and degraded-upstream validation.
7. Complete package publication automation, strict release validation, and release manifests.
8. Improve SDK standalone coverage, local test ergonomics, API docs, compatibility matrix, and migration docs.
9. Add threat model, runbooks, and production onboarding guide.
10. Clean up low-severity API, docs, and maintainability issues.

## 16. Validation Plan

Recommended validation after remediation:

- Unit: SDK sync/async parity, validation taxonomy, token validation, redaction, cache partitioning, close-state behavior.
- Integration: installed SDK wheel against running gateway over HTTP with real credential issuance, discovery, invocation, denial, malformed response, timeout, and rate-limit flows.
- Security: SSRF DNS rebinding test, unresolved-host production rejection, wildcard credential issuance controls, response/audit PII persistence checks, legacy token hash rejection.
- Reliability: multi-worker limiter tests, DB contention/load tests, idempotency duplicate/replay tests, upstream outage/circuit-breaker tests, background health scheduler tests.
- Packaging: clean venv `pip install` from documented index, import/type-check smoke, wheel/sdist content audit, strict-git release validation, SBOM/advisory audit.
- Operations: backup/restore drill, token rotation drill, secret-provider outage drill, rate-limit spike drill, unhealthy-target recovery drill.

Validation commands run during this audit:

- `PYTHONPATH=src python3 -m pytest tests -q --tb=short` in SDK package: passed, 10 tests.
- `python3 -m pytest tests -q --tb=short` in SDK package without `PYTHONPATH`: failed with import error.
- `PYTHONPATH=src python3 -m pytest tests/test_tool_gateway_*.py -q --tb=short` in product package: passed, 273 tests.
- `python3 -m pytest tests/test_tool_gateway_*.py` in product package without `PYTHONPATH`: failed with import errors.
- `PYTHONPATH=src python3 -m pytest tests -q --tb=short` in product package: passed, 774 tests.
- SDK and product gateway `ruff`: passed.
- SDK and product gateway `mypy`: passed.
- Targeted `compileall`: passed.
- SDK and product release validators with `--skip-twine-check`: passed.
- SDK dependency-audit release validation: not completed locally because security extras were not installed.
- Standalone/vendored SDK parity: passed.

## 17. Final Strict Assessment

The current SDK client surface is usable, typed, and much safer than the initial implementation described in the prior log. The repository also has broad product-platform tests and artifact validation. That is real progress.

It is still not enough for broad production readiness. The SDK is coupled to a gateway runtime whose production persistence, secret management, rate limiting, idempotency, SSRF enforcement, operational data handling, and production-like validation are not strong enough. The ease-of-use story is also not an 8 while package publication, real secret-manager setup, local validation ergonomics, compatibility policy, and onboarding proof remain incomplete.

Strict final scores:

- Implementation quality: 6 / 10.
- Ease of use: 6 / 10.
- Security and reliability: 5 / 10.

The next review should not raise these scores unless the repository itself proves the runtime and release risks are resolved through code, tests, packaging automation, documentation, and operational validation.
