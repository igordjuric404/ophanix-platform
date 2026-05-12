# Strict MVP Readiness Audit: Tool Gateway SDK And Product Gateway

Date: 2026-05-12

Scope: fresh strict MVP-readiness audit of the Ophanix Tool Gateway SDK package, its product-platform compatibility copy, gateway HTTP contract, relevant tests, docs, packaging, CI, and release workflow evidence.

Source context reviewed first: `docs/product-platform-worktree/execution-logs/06-tool-gateway-logs/13-sdk-review-remediation.md`.

Important reviewer constraints:

- No fixes were implemented during this audit.
- Prior remediation claims were treated as untrusted until checked against current code, tests, docs, and package metadata.
- Load balancing was not treated as an MVP flaw. Process-local controls are only flagged where they create recovery, restart, or perimeter assumptions that adopters must understand.
- Publication to PyPI was not treated as missing. The package may be published; this audit only flags repository evidence gaps that remain relevant after publication.

## 1. Executive Summary

Strict result: the SDK is a credible controlled MVP for internal teams or closely supported design partners, but it is not a clean 8/10 production pilot and should not be described as production-ready.

The current repository is much stronger than the prior early remediation state. The SDK has a standalone package, sync and async clients, secure URL defaults, strict token and payload validation, bounded response handling, idempotency-key support, retries only for idempotent invocation attempts, a capabilities endpoint, release validators, CI coverage, and a substantial product-platform gateway test suite. Fresh validation passed for SDK tests, product gateway tests, mypy, and local package build validators.

The remaining blockers are not cosmetic. The most important risks are: stuck `in_progress` idempotency records with no expiry or recovery path; full internal policy decision objects returned to agents on allowed/upstream-error invocation responses; no true installed-wheel-to-running-network-gateway test; duplicate ownership of the `ophanix_tool_gateway` top-level package by both product-platform and standalone SDK distributions; indefinite retention of idempotent replay response bodies; and compatibility checks that ignore `min_sdk_version`.

Scores assigned in this audit:

| Category | Current score | Prior score from log | Direction | MVP interpretation |
| --- | ---: | ---: | --- | --- |
| Implementation quality | 7.0/10 | 8.1/10 | Lowered | Credible MVP implementation, but capped by idempotency recovery, duplicate package ownership, limited real-network validation, and single-file complexity. |
| Ease of use | 7.0/10 | 8.3/10 | Lowered | Usable by competent engineers, but credential issuance, examples, API knobs, stale install wording, and source-level assumptions still slow onboarding. |
| Security and reliability | 6.5/10 | 8.3/10 | Lowered | Functional but fragile MVP security/reliability posture. Controlled adoption is realistic; broad external adoption needs fixes. |

No critical issue was proven. Two high-severity issues are strong MVP blockers for broader adoption: idempotency recovery and agent-facing policy decision exposure. Several medium issues collectively cap security/reliability below 7.

## 2. Prior Review Summary And Challenge

### Previously Reported Issues, Ignoring Deferred Items

The remediation log reported these implemented or fixed issues:

- SDK discovery used product-user `/api/v1/tools` instead of an agent-safe gateway discovery route.
- Gateway discovery initially returned operator-facing tool fields.
- SDK input validation, response validation, and non-local HTTP defaults were weak.
- `get_tool()` only searched the first discovery page.
- `StaticTokenProvider` exposed token material in `repr`, and exceptions could retain raw response bodies.
- No environment token provider, no `list_all_tools()`, and weak discovery ergonomics.
- Payload validation allowed non-strict JSON shapes and unsafe URL construction.
- Numeric configuration accepted non-finite values and bool-like non-bools.
- Discovery retries ignored `Retry-After`.
- SDK was embedded in product-platform only.
- Credential resource binding was flattened to scope strings.
- Discovery cache initially crossed credential contexts.
- No async SDK.
- Standalone package buildability and docs were thin.
- Response contract validation was incomplete.
- Error redaction missed common secret patterns.
- Release validation was ad hoc.
- Sync and async client configuration validation was duplicated.
- Later Pass 21 table claimed remediation for CI coverage, package publishing workflow inclusion, DB artifact removal, release validation, type checking, auth-route allowlist, authz-before-schema, upstream SSRF hardening, response-policy-on-failure, `store_full_response`, rate limiting, body-size limits, CORS guardrails, token entropy documentation, and docs/governance gaps.

### Fixes Claimed

The log claimed fixes including:

- `GET /api/v1/gateway/tools` and `GET /api/v1/gateway/capabilities`.
- `GatewayToolDefinitionResponse`.
- Standalone package `ophanix-tool-gateway-sdk` with `ophanix_tool_gateway` namespace.
- Compatibility exports from `product_platform.tool_gateway`.
- Strict client-side URL, token, payload, and response parsing.
- Sync and async clients.
- `ToolGatewayClientConfig`.
- Environment and static token providers.
- Idempotency key support and idempotent invocation retries.
- Credential-partitioned discovery cache.
- Runtime gateway idempotency persistence.
- Gateway request body cap.
- Process-local rate limiter and circuit breaker.
- Upstream URL and response policy controls.
- Release validation scripts and CI/publish workflow integration.
- Security, changelog, README, migration, API reference, and publishing docs.

### Validation Evidence Claimed

The prior log claimed multiple unittest suites, product-platform test runs, compile checks, wheel and sdist builds, release validator runs, dependency audit attempts, and static review of CI/publish workflows. Later local validation in this audit independently ran current pytest, mypy, and package validators instead of trusting those older counts.

### Scores Assigned In Prior Log

The latest explicit scoring section in `13-sdk-review-remediation.md` assigned:

- Implementation quality: 8.1/10.
- Ease of use: 8.3/10.
- Security/reliability: 8.3/10.

Earlier strict scores in the same log included 7.8/10 implementation, 8.0/10 DX, and 8.1/10 security/reliability.

### Suspicious, Under-Evidenced, Too Lenient, Or Too Strict Conclusions

- Too lenient: 8.3 security/reliability did not account for stuck idempotency records with no expiry/recovery, agent-facing internal decision objects, and indefinite idempotency response retention.
- Too lenient: production-candidate language overweights SDK-local hardening and underweights gateway runtime recovery behavior.
- Too lenient: release confidence did not sufficiently account for duplicate top-level package ownership between `ophanix-product-platform` and `ophanix-tool-gateway-sdk`.
- Too lenient: installed-wheel evidence was mostly import smoke and TestClient adapter coverage, not a true network gateway process.
- Too lenient: `check_compatibility()` existence was credited even though the SDK ignores `min_sdk_version`.
- Under-evidenced: CI/publish workflow existence was credited without proving the exact PyPI artifact corresponds to the validated artifact. Publication itself is not disputed, but repository evidence does not close the provenance loop.
- Too strict or stale: older concerns about no async SDK, no idempotency key support, no standalone package, no SDK release validation, missing compatibility exports, broad auth bypass, failed response policy bypass, and missing rate limiting are no longer current as originally described.

### Areas Not Deeply Reviewed Before

- Idempotency failure recovery after process crash, timeout, or killed request.
- Data retention for idempotency replay bodies.
- Agent-facing invocation response shape, especially the `decision` object.
- Actual package namespace conflict when both product-platform and standalone SDK are installed.
- Real installed wheel against an actual running ASGI/HTTP server.
- Compatibility semantics beyond same contract string.
- Operational effect of process restarts on rate limiter and circuit breaker.
- DNS rebinding and infrastructure egress assumptions for upstream forwarding.
- Direct HTTP example copy-paste risk.
- Publication provenance after the GitHub workflow handoff.

## 3. Repository Surface Reviewed

### Repository Map

Relevant SDK package surface:

- `packages/ophanix-tool-gateway-sdk/pyproject.toml`
- `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/__init__.py`
- `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py`
- `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/py.typed`
- `packages/ophanix-tool-gateway-sdk/tests/test_sdk_behavior.py`
- `packages/ophanix-tool-gateway-sdk/tests/test_package_smoke.py`
- `packages/ophanix-tool-gateway-sdk/scripts/validate_release.py`
- `packages/ophanix-tool-gateway-sdk/README.md`
- `packages/ophanix-tool-gateway-sdk/API_REFERENCE.md`
- `packages/ophanix-tool-gateway-sdk/MIGRATION.md`
- `packages/ophanix-tool-gateway-sdk/CHANGELOG.md`
- `packages/ophanix-tool-gateway-sdk/SECURITY.md`
- `packages/ophanix-tool-gateway-sdk/examples/async_worker_example.py`

Relevant product-platform gateway and compatibility surface:

- `packages/product-platform/pyproject.toml`
- `packages/product-platform/src/ophanix_tool_gateway/__init__.py`
- `packages/product-platform/src/ophanix_tool_gateway/sdk.py`
- `packages/product-platform/src/product_platform/tool_gateway/__init__.py`
- `packages/product-platform/src/product_platform/tool_gateway/sdk.py`
- `packages/product-platform/src/product_platform/tool_gateway/auth.py`
- `packages/product-platform/src/product_platform/tool_gateway/decision.py`
- `packages/product-platform/src/product_platform/tool_gateway/invocation.py`
- `packages/product-platform/src/product_platform/tool_gateway/models.py`
- `packages/product-platform/src/product_platform/tool_gateway/repository.py`
- `packages/product-platform/src/product_platform/tool_gateway/response.py`
- `packages/product-platform/src/product_platform/tool_gateway/runtime_audit.py`
- `packages/product-platform/src/product_platform/tool_gateway/schemas.py`
- `packages/product-platform/src/product_platform/tool_gateway/health.py`
- `packages/product-platform/src/product_platform/api/app.py`
- `packages/product-platform/src/product_platform/api/settings.py`
- `packages/product-platform/src/product_platform/agents/credentials.py`
- `packages/product-platform/src/product_platform/db/migrations/0050_*` through `0059_*`
- `packages/product-platform/scripts/validate_release.py`
- `packages/product-platform/README.md`

Relevant tests:

- `packages/product-platform/tests/test_tool_gateway_auth_phase*.py`
- `packages/product-platform/tests/test_tool_gateway_decision_phase*.py`
- `packages/product-platform/tests/test_tool_gateway_direct_http_examples_phase*.py`
- `packages/product-platform/tests/test_tool_gateway_forwarding_phase*.py`
- `packages/product-platform/tests/test_tool_gateway_installed_sdk_contract.py`
- `packages/product-platform/tests/test_tool_gateway_invocation_phase*.py`
- `packages/product-platform/tests/test_tool_gateway_permissions_phase*.py`
- `packages/product-platform/tests/test_tool_gateway_registry_phase*.py`
- `packages/product-platform/tests/test_tool_gateway_response_phase*.py`
- `packages/product-platform/tests/test_tool_gateway_runtime_audit_phase*.py`
- `packages/product-platform/tests/test_tool_gateway_sdk_package.py`
- `packages/product-platform/tests/test_tool_gateway_sdk_phase*.py`
- `packages/product-platform/tests/test_tool_gateway_sdk_remediation.py`
- `packages/product-platform/tests/test_tool_gateway_upstream_phase*.py`

Relevant docs, examples, CI, release, and governance:

- `docs/product-platform-worktree/execution-logs/06-tool-gateway-logs/13-sdk-review-remediation.md`
- `docs/product-platform-worktree/execution-logs/06-tool-gateway-logs/18-sdk-mvp-readiness-audit.md`
- `docs/internal/pypi-publishing.md`
- `.github/workflows/ci.yml`
- `.github/workflows/publish.yml`
- `.github/workflows/weekly-security-audit.yml`
- `.github/dependabot.yml`
- `.github/CODEOWNERS`
- `packages/product-platform/examples/tool-gateway-direct-http/*`

### Validation Performed During This Audit

- `python3 -m pytest tests -q --tb=short` in `packages/ophanix-tool-gateway-sdk`: passed, 27 tests.
- `python3 -m pytest tests/test_tool_gateway_*.py -q --tb=short` in `packages/product-platform`: passed, 296 tests.
- `python3 scripts/validate_release.py --out-dir /tmp/ophanix-sdk-audit-current --skip-twine-check` in SDK package: passed, wheel and sdist built. `twine check` was intentionally skipped only in this local audit command.
- `python3 scripts/validate_release.py --out-dir /tmp/ophanix-product-audit-current --skip-twine-check` in product-platform: passed, wheel and sdist built. `twine check` was intentionally skipped only in this local audit command.
- `python3 -m mypy src/ophanix_tool_gateway` in SDK package: passed.
- `python3 -m mypy src/product_platform/tool_gateway src/ophanix_tool_gateway` in product-platform: passed.
- `git status --short`: clean.
- Generated/cache files are present as ignored workspace files under package trees, but no tracked SDK generated files were found.

## 4. Exhaustive Issue Register

### SDK-AUDIT-001: Idempotency `in_progress` Records Have No Expiry Or Recovery

- Category: Runtime behavior / reliability
- Severity: High
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/tool_gateway/runtime_audit.py`; `packages/product-platform/src/product_platform/db/migrations/0059_tool_gateway_idempotency.up.sql`; `packages/product-platform/src/product_platform/api/app.py`
- Evidence: `begin_invocation()` inserts records with `status = "in_progress"` at `runtime_audit.py:400-470`. `_validated_existing()` raises `ToolInvocationIdempotencyInProgressError` whenever status is not `completed` at `runtime_audit.py:553-562`. The migration stores `created_at` and `updated_at` but no lease, expiry, heartbeat, or terminal failure status at `0059_tool_gateway_idempotency.up.sql:1-28`. The API returns repeated 409 `idempotency_in_progress` at `app.py:3540-3560`.
- Why it matters: If a request starts an idempotent operation and the process crashes, the executor is cancelled, or the completion update fails, the caller's idempotency key can be permanently unusable for that credential/tool/payload.
- Root cause or likely root cause: Idempotency was implemented as replay storage, not as a leased operation lifecycle with stale-record recovery.
- Impact on MVP readiness: Blocks comfortable MVP adoption for workflows where callers rely on idempotency to reconcile unknown outcomes.
- Impact on developer experience, if applicable: A caller can follow the docs, use an idempotency key correctly, and still be stuck with a permanent 409 that requires source or database-level debugging.
- Impact on security or reliability, if applicable: Reliability risk. It undermines the retry safety story for exactly the failure mode idempotency is supposed to handle.
- Whether it was mentioned in the prior review log: Not as this specific failure mode. Prior logs discussed missing idempotency and then claimed idempotency support.
- Whether a previous fix claimed to address it: Partially. Pass 21 claimed idempotency support, but not stale recovery.
- Whether that previous fix is sufficient: No.
- Recommended remediation: Add an idempotency lease/expiry, stale-record transition, operator cleanup command, and explicit behavior for "unknown outcome after stale in_progress". Consider statuses such as `failed_unknown`, `expired`, and `completed`.
- Suggested validation or test: Add a repository and API test that seeds an old `in_progress` record and proves retry either recovers, returns a documented terminal status, or allows a safe takeover according to the chosen semantics.
- Whether it should affect scoring: Yes. Caps security/reliability at 6.5 and implementation below 8.

### SDK-AUDIT-002: Allowed Invocation Responses Expose Full Internal Policy Decision Objects To Agents

- Category: Security / API contract
- Severity: High
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/tool_gateway/decision.py`; `packages/product-platform/src/product_platform/tool_gateway/invocation.py`; `packages/product-platform/src/product_platform/api/app.py`; SDK result parsing
- Evidence: `ToolPolicyDecisionResult` includes `organization_id`, `environment_id`, `agent_id`, `tool_id`, `permission_id`, `reason_message`, `matched_policy_id`, `request_id`, `correlation_id`, and `payload_summary` at `decision.py:114-130`. `ToolInvocationResponse` includes `decision` at `invocation.py:103-112`. Allowed and upstream-error responses pass `decision=decision` at `app.py:3669-3677`, `app.py:3699-3710`, `app.py:3758-3766`, `app.py:3804-3816`, and `app.py:3847-3855`. Tests assert `payload["decision"]["permission_id"]` at `test_tool_gateway_invocation_phase3.py:153-158`.
- Why it matters: Denied responses were hardened to coarse `tool_call_denied`, but allowed and upstream-error responses still return internal IDs and policy metadata that agents do not need.
- Root cause or likely root cause: The persisted internal decision model is reused directly in the external invocation response envelope.
- Impact on MVP readiness: Concerning for early external design partners. Internal teams can tolerate it if they understand the contract, but it is not least-privilege.
- Impact on developer experience, if applicable: Consumers may start depending on internal decision fields, making future narrowing a breaking API change.
- Impact on security or reliability, if applicable: Information exposure risk. It leaks tenant/environment/permission/policy internals and potentially redacted-but-still-internal payload summaries.
- Whether it was mentioned in the prior review log: Prior review addressed discovery exposure and denial reason exposure, but not allowed invocation decision exposure.
- Whether a previous fix claimed to address it: No direct fix.
- Whether that previous fix is sufficient: No.
- Recommended remediation: Introduce an agent-facing `GatewayInvocationDecisionSummary` with only stable public fields such as `decision="allow"` and `reason_code="allowed"`, or omit `decision` entirely from successful responses.
- Suggested validation or test: Add API and SDK contract tests proving successful and upstream-error invocation responses do not include `organization_id`, `environment_id`, `permission_id`, `matched_policy_id`, or `reason_message`.
- Whether it should affect scoring: Yes. Caps security/reliability below 7 for external MVP use.

### SDK-AUDIT-003: No True Installed-Wheel-To-Running-Network-Gateway Test

- Category: Testing / integration
- Severity: High
- Confidence: High
- File path or area: `packages/product-platform/tests/test_tool_gateway_installed_sdk_contract.py`; CI
- Evidence: The installed-wheel test builds and installs the SDK wheel, but calls the FastAPI app through a custom `_TestClientGatewayHTTPClient` using `fastapi.testclient.TestClient` at `test_tool_gateway_installed_sdk_contract.py:133-151` and `test_tool_gateway_installed_sdk_contract.py:164-201`. It does not start a real ASGI server, open a socket, exercise HTTPX network behavior, or verify proxy/TLS/runtime server behavior.
- Why it matters: A package can pass in-process tests while still failing in a real installed SDK to running gateway setup due to server startup, routing, headers, URL formation, streaming, timeout, or dependency issues.
- Root cause or likely root cause: The contract test optimizes for deterministic in-process speed and avoids a server lifecycle harness.
- Impact on MVP readiness: For a controlled MVP it is acceptable if operators test manually, but it is a serious gap for claiming a robust external SDK.
- Impact on developer experience, if applicable: Early adopters may become the first real end-to-end testers.
- Impact on security or reliability, if applicable: Reliability validation gap.
- Whether it was mentioned in the prior review log: Yes. Prior Pass 21 marked a true running-gateway contract test as deferred.
- Whether a previous fix claimed to address it: Partially. Installed-wheel smoke and TestClient contract coverage were added.
- Whether that previous fix is sufficient: No, not for this specific end-to-end behavior.
- Recommended remediation: Add CI that builds the wheel, installs it into a clean venv, starts product-platform on localhost with migrated/seeded data, and runs the installed SDK over real HTTP.
- Suggested validation or test: One sync and one async smoke path: compatibility probe, discovery, allowed invocation, denied invocation, idempotent replay, and response cap over an actual port.
- Whether it should affect scoring: Yes. Caps implementation quality below 8.

### SDK-AUDIT-004: Product-Platform And Standalone SDK Both Ship The Same Top-Level `ophanix_tool_gateway` Package

- Category: Packaging / release
- Severity: High
- Confidence: High
- File path or area: `packages/product-platform/pyproject.toml`; `packages/ophanix-tool-gateway-sdk/pyproject.toml`; product-platform compatibility namespace
- Evidence: Product-platform wheel target includes `packages = ["src/product_platform", "src/ophanix_tool_gateway"]` at `packages/product-platform/pyproject.toml:72-74`. The standalone SDK wheel also packages `src/ophanix_tool_gateway` at `packages/ophanix-tool-gateway-sdk/pyproject.toml:48-50`.
- Why it matters: Installing both distributions into one environment creates duplicate ownership of the same import package. Whichever distribution was installed last can shadow the other, and security/bugfix updates to the standalone SDK may not take effect if product-platform overwrites the same top-level package.
- Root cause or likely root cause: Compatibility imports were preserved by physically shipping a copied SDK namespace inside product-platform instead of depending on the standalone package or using only `product_platform.tool_gateway` shims.
- Impact on MVP readiness: Internal environments can manage this deliberately, but external consumers can hit confusing import/version behavior.
- Impact on developer experience, if applicable: Debugging "which package provided `ophanix_tool_gateway`" can require inspecting installed distributions and sys.path.
- Impact on security or reliability, if applicable: Security patch rollout risk if patched SDK and product-platform copies diverge or install order shadows the patched code.
- Whether it was mentioned in the prior review log: The prior log mentioned compatibility exports and vendored/copy parity, but treated it as acceptable after parity checks.
- Whether a previous fix claimed to address it: Yes, parity checks were added.
- Whether that previous fix is sufficient: Partially. Parity checks reduce source drift before release but do not solve duplicate distribution ownership.
- Recommended remediation: Make product-platform depend on `ophanix-tool-gateway-sdk` for the top-level package, or remove `src/ophanix_tool_gateway` from the product-platform wheel and keep only `product_platform.tool_gateway` re-export shims.
- Suggested validation or test: Build both wheels, install in both orders into clean venvs, assert a single distribution owns `ophanix_tool_gateway`, and verify `SDK_VERSION` and file path are predictable.
- Whether it should affect scoring: Yes. Caps packaging confidence and implementation quality.

### SDK-AUDIT-005: Idempotency Replay Stores Public Response Bodies Indefinitely

- Category: Security / privacy / reliability
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/tool_gateway/runtime_audit.py`; migration `0059_tool_gateway_idempotency.up.sql`; response policy
- Evidence: `complete_invocation()` stores `response_body_json` for replay at `runtime_audit.py:472-509`. The migration has no retention, expiry, purge marker, or size beyond text storage at `0059_tool_gateway_idempotency.up.sql:1-28`. The stored body is the public response envelope, which can include `result`, `decision`, and error details depending on response policy.
- Why it matters: Replay data may contain customer payload or upstream result data. The absence of retention policy means a safety feature becomes an unbounded data store.
- Root cause or likely root cause: Idempotency was implemented as correctness storage without a retention lifecycle.
- Impact on MVP readiness: Acceptable for very controlled pilots with known data classes, but risky for broader design partners handling sensitive tool responses.
- Impact on developer experience, if applicable: Operators need undocumented cleanup practices.
- Impact on security or reliability, if applicable: Data retention and storage growth risk.
- Whether it was mentioned in the prior review log: Not specifically.
- Whether a previous fix claimed to address it: No.
- Whether that previous fix is sufficient: No.
- Recommended remediation: Add configurable retention, cleanup job/CLI, and explicit docs for what is stored. Consider storing only response hashes plus replay bodies for short TTL.
- Suggested validation or test: Seed old completed records and verify cleanup removes or redacts `response_body_json` while preserving audit invariants.
- Whether it should affect scoring: Yes. Medium security/reliability score reducer.

### SDK-AUDIT-006: Compatibility Probe Ignores `min_sdk_version`

- Category: Public API / compatibility
- Severity: Medium
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py`; `packages/product-platform/src/product_platform/tool_gateway/models.py`
- Evidence: Gateway capabilities include `min_sdk_version: str = "0.1.0"` at `models.py:164-170`. SDK `_gateway_compatibility()` sets `compatible` solely by comparing `gateway_contract_version == SDK_GATEWAY_CONTRACT_VERSION` at `sdk.py:1871-1881`; it records but does not enforce or evaluate `min_sdk_version`.
- Why it matters: During MVP iteration, the gateway can declare that older SDK versions are no longer acceptable, but the SDK will still report `compatible=True` as long as the contract string is unchanged.
- Root cause or likely root cause: Compatibility was modeled as a contract-string probe, not a version-range negotiation.
- Impact on MVP readiness: Concerning API instability risk. It can cause subtle runtime breakage after gateway upgrades.
- Impact on developer experience, if applicable: Developers may trust `compatible=True` and then hit errors later.
- Impact on security or reliability, if applicable: Reliability and rollout risk.
- Whether it was mentioned in the prior review log: Compatibility probe was added and credited, but this missing semantic check was not called out.
- Whether a previous fix claimed to address it: Partially. The probe exists.
- Whether that previous fix is sufficient: No.
- Recommended remediation: Parse and compare SDK package version against `min_sdk_version`; expose a reason when incompatible.
- Suggested validation or test: Mock capabilities with `min_sdk_version` greater than the installed SDK and assert `compatible=False` plus a useful diagnostic.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-007: Process-Local Rate Limiting Is Not A Complete Gateway Protection Boundary

- Category: Reliability / security
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/api/app.py`
- Evidence: Rate-limit state is stored in `app.state.tool_gateway_rate_limits` and `app.state.tool_gateway_rate_limit_overflow_limits` at `app.py:1023-1026`. `_tool_gateway_rate_limit_result()` keeps counters in those in-memory dicts at `app.py:792-845`.
- Why it matters: This is not a load-balancing complaint. For low-traffic MVP usage, process-local may be acceptable. The issue is that counters reset on restart and are not a durable perimeter if multiple worker processes or a separate ingress path are used.
- Root cause or likely root cause: MVP-friendly in-process control was added instead of an edge or shared limiter.
- Impact on MVP readiness: Acceptable only if the deployment has a single process or an explicit external ingress limit.
- Impact on developer experience, if applicable: Operators must know this is a local guard, not a complete rate-limit system.
- Impact on security or reliability, if applicable: Abuse and burst-control risk under restarts or multi-process deployments.
- Whether it was mentioned in the prior review log: Yes. Prior logs recognized in-process limits as not a distributed replacement.
- Whether a previous fix claimed to address it: Yes, rate limiting was added.
- Whether that previous fix is sufficient: Partially for MVP, not sufficient as a general external control.
- Recommended remediation: Document required ingress assumptions and add optional Redis/shared limiter or gateway-edge integration for external pilots.
- Suggested validation or test: Add deployment docs and a restart/multi-instance test plan showing expected behavior and external protection.
- Whether it should affect scoring: Yes, but it should not be treated as a high blocker for low-traffic pilots.

### SDK-AUDIT-008: Process-Local Circuit Breaker Loses State On Restart And Across Workers

- Category: Reliability
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/tool_gateway/invocation.py`; `packages/product-platform/src/product_platform/api/app.py`
- Evidence: `InMemoryToolGatewayCircuitBreaker` stores `_state` in a process-local dict at `invocation.py:148-199`. The app creates one instance in `app.state` at `app.py:1027-1030`.
- Why it matters: Circuit breaking is meant to prevent repeated calls to a failing upstream. A restart or separate worker starts with no failure memory.
- Root cause or likely root cause: Simple MVP in-memory implementation.
- Impact on MVP readiness: Acceptable for controlled pilots with low traffic, but fragile during upstream incidents.
- Impact on developer experience, if applicable: Operators may assume circuit state is shared or durable when it is not.
- Impact on security or reliability, if applicable: Reliability risk during degraded upstream behavior.
- Whether it was mentioned in the prior review log: The prior log mentioned circuit breaker work, but not this as a current score reducer.
- Whether a previous fix claimed to address it: Yes, a circuit breaker was added.
- Whether that previous fix is sufficient: Partially.
- Recommended remediation: Document the scope clearly and add optional shared state or ingress-level upstream protection for broader deployment.
- Suggested validation or test: Add tests or docs showing restart behavior and multi-worker assumptions.
- Whether it should affect scoring: Yes, medium reliability cap.

### SDK-AUDIT-009: Offset Pagination Can Miss Or Duplicate Tools Under Catalog Churn

- Category: Runtime behavior / API design
- Severity: Medium
- Confidence: Medium
- File path or area: SDK discovery helpers; product gateway discovery route
- Evidence: The gateway route accepts `limit` and `offset` at `app.py:3344-3348`. SDK `list_all_tools()` increments `offset += page_size` until a short page at `sdk.py:623-662` and async mirrors this at `sdk.py:1253-1292`.
- Why it matters: If tool visibility changes between pages, offset pagination can skip or duplicate entries. The SDK dedupes duplicates but cannot recover skipped rows.
- Root cause or likely root cause: MVP list endpoint uses offset pagination instead of a stable cursor/snapshot.
- Impact on MVP readiness: Acceptable for small, stable catalogs. Risky for active teams editing tools during discovery.
- Impact on developer experience, if applicable: Developers may see intermittent missing tools and blame SDK caching or permissions.
- Impact on security or reliability, if applicable: Reliability issue, not a security flaw.
- Whether it was mentioned in the prior review log: Earlier logs addressed first-page-only `get_tool()` but not churn-safe pagination.
- Whether a previous fix claimed to address it: Pagination was fixed for static catalogs.
- Whether that previous fix is sufficient: Partially.
- Recommended remediation: Add cursor pagination or document discovery consistency limits. Consider ordering by immutable ID plus cursor.
- Suggested validation or test: Simulate insertion/deletion between pages and assert either documented behavior or cursor stability.
- Whether it should affect scoring: Yes, modestly.

### SDK-AUDIT-010: Opt-In Discovery Cache Can Serve Stale Authorization Or Contract Data

- Category: Reliability / DX
- Severity: Medium
- Confidence: High
- File path or area: SDK cache behavior and README
- Evidence: `ToolGatewayClientConfig.cache_tools` defaults to false, but when enabled defaults to `cache_ttl_seconds = 300.0` at `sdk.py:230-249`. README documents stale data can be served for up to TTL at `README.md:370-371`.
- Why it matters: Credential revocation, permission changes, or tool contract changes may not be observed until TTL expires or the caller manually clears the cache.
- Root cause or likely root cause: Process-local cache optimizes discovery latency without server-driven invalidation.
- Impact on MVP readiness: Acceptable because it is opt-in and documented. Still a meaningful risk for early adopters who turn it on.
- Impact on developer experience, if applicable: Hidden stale authorization symptoms can be confusing.
- Impact on security or reliability, if applicable: Stale discovery can overstate currently callable tools, though invocation should still enforce policy server-side.
- Whether it was mentioned in the prior review log: Yes, cache partitioning and TTL were discussed.
- Whether a previous fix claimed to address it: Yes, credential partitioning and TTL were added.
- Whether that previous fix is sufficient: Mostly, but stale-data behavior remains an accepted MVP tradeoff.
- Recommended remediation: Keep default off, document revocation workflows, and consider gateway ETag/version invalidation.
- Suggested validation or test: Add docs and tests proving invocation denies stale-discovered tools after permission revocation.
- Whether it should affect scoring: Yes, low-to-medium.

### SDK-AUDIT-011: Response Policy Can Be Disabled And Then Redaction/Visibility Controls Are Bypassed

- Category: Security / response handling
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/tool_gateway/response.py`; response policy model/tests
- Evidence: `process_tool_execution_response()` returns the original execution unchanged if policy status is not `active` at `response.py:26-31`. Tests explicitly confirm a disabled policy leaves `{"token": "secret"}` exposed and `exposed_to_agent=True` at `test_tool_gateway_response_phase3.py:70-85`. The policy model allows `status` values `active` and `disabled` at `models.py:494-502`.
- Why it matters: A single policy toggle disables redaction, max response policy, output validation, and exposure controls for that tool.
- Root cause or likely root cause: Policy status is implemented as a full bypass rather than a mode switch for individual controls.
- Impact on MVP readiness: Acceptable only if operators understand that disabling policy means "raw passthrough".
- Impact on developer experience, if applicable: Operators might disable a policy to work around validation and accidentally disable redaction.
- Impact on security or reliability, if applicable: Data exposure risk from operator misconfiguration.
- Whether it was mentioned in the prior review log: Failed-response policy and redaction were discussed, but disabled-policy bypass as an operational risk was not emphasized.
- Whether a previous fix claimed to address it: Partially. Policy application was improved.
- Whether that previous fix is sufficient: Not for this configuration-risk case.
- Recommended remediation: Split "policy disabled" into explicit controls, add guardrails/warnings, or forbid disabling redaction/exposure safeguards in production.
- Suggested validation or test: Production setting test that rejects disabled response policies for externally exposed tools unless an explicit override is present.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-012: Upstream SSRF Protection Still Relies On DNS-Time Checks And Infrastructure Egress Controls

- Category: Security
- Severity: Medium
- Confidence: Medium
- File path or area: `packages/product-platform/src/product_platform/tool_gateway/models.py`; upstream invocation
- Evidence: `validate_http_url()` checks scheme, credentials, query/fragment, forbidden hostnames, DNS resolution, and allowlist at `models.py:522-546`. `_hostname_resolves_to_forbidden_address()` uses `socket.getaddrinfo()` at `models.py:725-740`, but the HTTP client later connects independently.
- Why it matters: DNS rebinding or resolver differences between validation and connect time can still route to forbidden networks. The app has good application-level controls, but it does not pin the resolved IP for the connection.
- Root cause or likely root cause: Application-layer SSRF checks are used without network egress policy enforcement in this repo.
- Impact on MVP readiness: Acceptable for controlled environments with egress controls and allowlisted hosts; not enough for unsupervised external tool registration.
- Impact on developer experience, if applicable: Operators may overestimate the SSRF guarantee.
- Impact on security or reliability, if applicable: Residual SSRF risk.
- Whether it was mentioned in the prior review log: Prior log said SSRF was substantially reduced and noted infrastructure-level residual risk.
- Whether a previous fix claimed to address it: Yes, URL validation and allowlists were added.
- Whether that previous fix is sufficient: Partially.
- Recommended remediation: Document required egress policy, pin/connect to resolved safe IP where feasible, or use an outbound proxy that enforces destination policy.
- Suggested validation or test: Add an integration test with a fake resolver/rebinding harness or document why egress proxy enforcement is required for external deployments.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-013: Local/Test Unresolved Upstream Hosts Are Allowed By Default

- Category: Security / configuration / DX
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/tool_gateway/models.py`; production validation
- Evidence: `_allow_unresolved_upstream_hosts()` returns true for `development`, `dev`, `local`, and `test` by default at `models.py:743-752`. Production rejects unresolved upstream hosts only when `OPHANIX_ALLOW_UNRESOLVED_UPSTREAM_HOSTS` is set at `app.py:736-740`.
- Why it matters: Local demos can pass with fake or unresolved upstream hosts, then fail at production startup or invocation. This is useful for tests but can hide deployment-readiness issues.
- Root cause or likely root cause: Test ergonomics and local demos were prioritized.
- Impact on MVP readiness: Acceptable shortcut for local MVP development, but should be explicit in setup docs.
- Impact on developer experience, if applicable: A competent engineer may be surprised by environment-specific behavior.
- Impact on security or reliability, if applicable: Reliability/config drift risk, not a production security flaw if production validation is kept.
- Whether it was mentioned in the prior review log: Not specifically.
- Whether a previous fix claimed to address it: No direct fix.
- Whether that previous fix is sufficient: Not applicable.
- Recommended remediation: Document local/test unresolved-host behavior near upstream target setup and add a "production parity" validation command.
- Suggested validation or test: Add a test or CLI dry run that validates upstream targets with production semantics before rollout.
- Whether it should affect scoring: Yes, modest DX/reliability reducer.

### SDK-AUDIT-014: SDK Payload Validator Has No Explicit Depth Limit

- Category: Runtime behavior / reliability
- Severity: Medium
- Confidence: Medium
- File path or area: `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py`; product server invocation validation
- Evidence: SDK `_validate_json_value()` recurses through dicts and lists with cycle detection but no depth cap at `sdk.py:2322-2347`. The server has `MAX_INVOCATION_PAYLOAD_DEPTH = 50` at `invocation.py:22-25` and validates depth at request model level.
- Why it matters: Extremely deep caller payloads can cause Python recursion errors or poor error quality in the SDK instead of a deterministic `ToolGatewayValidationError`.
- Root cause or likely root cause: SDK validation implemented strict JSON shape and cycle checks but did not mirror the server depth limit.
- Impact on MVP readiness: Low likelihood for normal use, but it is a correctness and resilience gap.
- Impact on developer experience, if applicable: Bad inputs may produce surprising low-level exceptions.
- Impact on security or reliability, if applicable: Local process reliability risk if untrusted code constructs SDK payloads.
- Whether it was mentioned in the prior review log: Prior log discussed payload validation broadly, not depth parity.
- Whether a previous fix claimed to address it: Partially.
- Whether that previous fix is sufficient: No for depth.
- Recommended remediation: Add SDK `max_payload_depth` or a fixed cap aligned to the gateway.
- Suggested validation or test: Construct a nested payload deeper than the cap and assert a clean `ToolGatewayValidationError`.
- Whether it should affect scoring: Yes, small implementation/reliability reducer.

### SDK-AUDIT-015: Standalone SDK Test Suite Is Thin Relative To The Product-Platform Mirror Suite

- Category: Testing
- Severity: Medium
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/tests`; `packages/product-platform/tests/test_tool_gateway_sdk_phase*.py`
- Evidence: Standalone package has 488 lines of SDK tests and 27 tests passed locally. Product-platform has a much larger mirrored Tool Gateway suite, including SDK phase/remediation tests, and 296 gateway tests passed locally. `wc -l` showed `sdk.py` at 2480 lines and product gateway tests at 11688 total lines.
- Why it matters: The canonical published package should prove most of its behavior locally, not rely primarily on another package's test tree.
- Root cause or likely root cause: The SDK originated inside product-platform and much behavior coverage remains there.
- Impact on MVP readiness: Current CI appears to run both packages for relevant changes, so this is not an immediate blocker. It is still a packaging/test ownership weakness.
- Impact on developer experience, if applicable: External contributors or package consumers may run only the standalone tests and get a false sense of coverage.
- Impact on security or reliability, if applicable: Test gap risk if CI path filters or local validation drift.
- Whether it was mentioned in the prior review log: Yes, package-local tests were originally missing and then expanded.
- Whether a previous fix claimed to address it: Yes, standalone tests and CI were added.
- Whether that previous fix is sufficient: Partially.
- Recommended remediation: Move or duplicate critical SDK behavior tests into the standalone package, especially async, cache, idempotency, response cap, auth error, and compatibility cases.
- Suggested validation or test: Standalone package test suite should fail if any public SDK behavior regresses, independent of product-platform tests.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-016: Product-Platform Release Validator Is Weaker Than The SDK Validator

- Category: Packaging / release
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/scripts/validate_release.py`; SDK validator
- Evidence: SDK validator supports `--require-dependency-audit` and `--strict-git` at `packages/ophanix-tool-gateway-sdk/scripts/validate_release.py:45-58`, validates vendored parity at `scripts/validate_release.py:252-262`, and can audit runtime deps at `scripts/validate_release.py:265-284`. Product validator has no dependency-audit or strict-git options at `packages/product-platform/scripts/validate_release.py:35-80`.
- Why it matters: Product-platform ships the compatibility SDK namespace and the gateway server. Its release validator should have at least equivalent guardrails for the relevant gateway surface.
- Root cause or likely root cause: The SDK validator was hardened more deeply than the broader product package validator.
- Impact on MVP readiness: Does not block SDK MVP by itself, but weakens confidence in product-platform artifacts used with the SDK.
- Impact on developer experience, if applicable: Release owners have inconsistent commands and guarantees across packages.
- Impact on security or reliability, if applicable: Supply-chain/release process risk.
- Whether it was mentioned in the prior review log: Product validator work was claimed, but parity with SDK validator was not closed.
- Whether a previous fix claimed to address it: Partially.
- Whether that previous fix is sufficient: No.
- Recommended remediation: Add product validator `--require-dependency-audit`, `--strict-git`, parity checks, and relevant gateway contract smoke tests.
- Suggested validation or test: Run both validators in strict mode in CI and publish workflow.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-017: Local Validator SBOMs List Artifact Files, Not Runtime Dependency Components

- Category: Packaging / supply chain
- Severity: Medium
- Confidence: High
- File path or area: SDK and product validator scripts; publish workflow
- Evidence: SDK `_write_minimal_sbom()` creates CycloneDX components only for artifact files at `packages/ophanix-tool-gateway-sdk/scripts/validate_release.py:326-350`. Product validator mirrors this at `packages/product-platform/scripts/validate_release.py:234-258`. Publish workflow separately uses Anchore SBOM for SDK/product at `.github/workflows/publish.yml:102-110`.
- Why it matters: The local release manifest may look like an SBOM gate, but it does not enumerate runtime dependencies such as `httpx`. CI publish SBOM helps, but local validation evidence is weaker.
- Root cause or likely root cause: Minimal SBOM was added as artifact provenance metadata rather than full dependency inventory.
- Impact on MVP readiness: Acceptable if CI/publish SBOM is the source of truth. Misleading if local validator output is treated as complete SBOM evidence.
- Impact on developer experience, if applicable: Release owners may over-credit the local SBOM.
- Impact on security or reliability, if applicable: Supply-chain evidence gap.
- Whether it was mentioned in the prior review log: Prior log credited local CycloneDX SBOMs and publish SBOMs.
- Whether a previous fix claimed to address it: Yes.
- Whether that previous fix is sufficient: Partially.
- Recommended remediation: Rename local SBOM to artifact manifest or generate a true dependency SBOM during validator execution.
- Suggested validation or test: Assert the generated SBOM includes runtime dependencies, or document that only publish workflow SBOM is complete.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-018: Runtime Dependencies Are Broadly Ranged And Not Locked For Reproducible Consumer Resolution

- Category: Packaging / supply chain
- Severity: Medium
- Confidence: High
- File path or area: SDK and product `pyproject.toml`; CI
- Evidence: SDK runtime dependency is `httpx>=0.27.0,<1.0` at `packages/ophanix-tool-gateway-sdk/pyproject.toml:15-17`. Product dependencies similarly use broad ranges at `packages/product-platform/pyproject.toml:15-24`. CI audits the current resolved environment but does not define a lock or min/max compatibility matrix.
- Why it matters: Future dependency releases inside allowed ranges can change behavior or introduce vulnerabilities that were not tested with the published package.
- Root cause or likely root cause: Library packages avoid strict pins for consumer compatibility, but no constraints/testing strategy is documented.
- Impact on MVP readiness: Acceptable MVP shortcut, but it caps supply-chain confidence.
- Impact on developer experience, if applicable: Consumers may hit resolver differences that maintainers did not test.
- Impact on security or reliability, if applicable: Supply-chain and runtime compatibility risk.
- Whether it was mentioned in the prior review log: Yes, broad dependency ranges were previously listed.
- Whether a previous fix claimed to address it: Partially through dependency audit.
- Whether that previous fix is sufficient: No.
- Recommended remediation: Add min/max dependency CI jobs, a constraints file for tested release resolution, and docs explaining library dependency policy.
- Suggested validation or test: Run SDK tests with minimum supported `httpx` and latest allowed `httpx` in CI.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-019: Credential Issuance Docs Still Depend On An Opaque Operator Token Step

- Category: Documentation / developer experience
- Severity: Medium
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/README.md`
- Evidence: The local issuance flow asks users to export `OPHANIX_OPERATOR_TOKEN="<operator-api-token-from-your-local-login-or-admin-flow>"` at `README.md:288-300`, then says endpoint names may differ in private operator builds at `README.md:313-316`.
- Why it matters: The SDK consumes tokens but cannot be evaluated unless an adopter can get one. The current docs still leave the most important setup step as an exercise.
- Root cause or likely root cause: Token issuance spans product auth/operator flows that are outside the SDK package.
- Impact on MVP readiness: Slows onboarding. A competent engineer can probably solve it internally, but external design partners may need hand-holding.
- Impact on developer experience, if applicable: High. First-run success depends on hidden auth context.
- Impact on security or reliability, if applicable: Security risk if users improvise weak local fixture tokens or paste operator tokens into unsafe places.
- Whether it was mentioned in the prior review log: Yes, token issuance/setup was flagged and partially documented.
- Whether a previous fix claimed to address it: Yes.
- Whether that previous fix is sufficient: Partially.
- Recommended remediation: Provide a complete local token issuance quickstart, including how to obtain the operator token safely, expected response shape, and copy-paste path from raw token to `OPHANIX_GATEWAY_TOKEN`.
- Suggested validation or test: Fresh-environment docs test where a new engineer follows the README without source-code lookup.
- Whether it should affect scoring: Yes, caps ease of use.

### SDK-AUDIT-020: Direct HTTP Python Example Omits SDK Safeguards In Code

- Category: Documentation / examples / security
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/examples/tool-gateway-direct-http/direct_http_requests_example.py`; direct HTTP README
- Evidence: The Python direct HTTP example builds URLs with `base_url.rstrip("/")`, uses raw `requests.post`, calls `response.json()` directly, has no SDK base URL policy, no strict payload validation, no response-size cap, no compatibility check, no retry policy, and returns raw JSON at `direct_http_requests_example.py:34-68`. The README warns direct callers must implement these controls at `README.md:7-14`.
- Why it matters: Examples get copied. The README warning helps, but the code remains less safe than the SDK.
- Root cause or likely root cause: The example exists to demonstrate the public HTTP contract, not to be a production helper.
- Impact on MVP readiness: Acceptable for local demo, but it can undermine SDK adoption and create risky integrations.
- Impact on developer experience, if applicable: Users may pick the shortest code path and miss controls.
- Impact on security or reliability, if applicable: Potential unsafe defaults if copied outside local use.
- Whether it was mentioned in the prior review log: Yes, direct HTTP example safety was flagged and warnings were added.
- Whether a previous fix claimed to address it: Yes, README warnings.
- Whether that previous fix is sufficient: Partially.
- Recommended remediation: Rename code clearly as local-only demo, add visible runtime warning, or implement minimal URL/response/error safeguards.
- Suggested validation or test: Example test asserting non-JSON responses, oversized bodies, and unsafe non-local HTTP fail safely if the example is intended beyond demo.
- Whether it should affect scoring: Yes, mainly DX/security.

### SDK-AUDIT-021: Deprecated `list_tools(status=...)` Remains In The Public API

- Category: Public API / DX
- Severity: Low
- Confidence: High
- File path or area: SDK sync/async clients and docs
- Evidence: Sync `list_tools()` accepts `status: Literal["active"] | None` and emits `DeprecationWarning` when provided at `sdk.py:602-621`. Async mirrors this at `sdk.py:1232-1251`. README says compatibility shims such as `list_tools(status="active")` may be removed at `README.md:318-323`.
- Why it matters: It suggests status filtering exists even though gateway discovery returns active callable tools only.
- Root cause or likely root cause: Backward compatibility with earlier internal API.
- Impact on MVP readiness: Acceptable MVP wart, but it is API instability.
- Impact on developer experience, if applicable: Minor confusion and possible warnings in test suites.
- Impact on security or reliability, if applicable: None material.
- Whether it was mentioned in the prior review log: Yes.
- Whether a previous fix claimed to address it: Yes, narrowed to `active` and warning.
- Whether that previous fix is sufficient: Yes for MVP, but not polished.
- Recommended remediation: Remove in the next pre-1.0 breaking cleanup or move status filtering to an explicit future gateway API.
- Suggested validation or test: Keep deprecation test until removal, then add migration note.
- Whether it should affect scoring: Yes, low DX/API reducer.

### SDK-AUDIT-022: `raw` And `decision` Fields Encourage Dependence On Unstable Internal Shapes

- Category: Public API / maintainability
- Severity: Medium
- Confidence: High
- File path or area: SDK dataclasses and response parsing
- Evidence: `ToolCallResult` exposes `decision: dict[str, Any] | None` and `raw` at `sdk.py:188-199`. `ToolDefinition` exposes `raw` at `sdk.py:201-214`. `_tool_call_result()` stores optional decision mappings and raw response body at `sdk.py:1827-1846`; `_tool_definition()` stores raw body at `sdk.py:1849-1868`.
- Why it matters: These fields are useful escape hatches, but consumers can start depending on unstable server internals, making future contract narrowing painful.
- Root cause or likely root cause: SDK preserves forwards-compatible access to extra fields.
- Impact on MVP readiness: Acceptable shortcut for beta, but should be clearly marked as unstable.
- Impact on developer experience, if applicable: Short-term helpful, long-term migration risk.
- Impact on security or reliability, if applicable: Security risk when `raw` contains internal fields that should not become public API.
- Whether it was mentioned in the prior review log: Related raw-field immutability was mentioned, but not the API dependency risk.
- Whether a previous fix claimed to address it: Partially, raw mappings were made immutable.
- Whether that previous fix is sufficient: No for stability.
- Recommended remediation: Document `raw` and `decision` as diagnostic/unstable, and avoid exposing internal server-only fields in gateway responses.
- Suggested validation or test: Contract snapshot test for exact public fields plus docs stating unsupported fields.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-023: Event Hook Contract Is Stringly Typed, Unversioned, And Sync-Only

- Category: Observability / API ergonomics
- Severity: Low
- Confidence: High
- File path or area: SDK event hook implementation and docs
- Evidence: `TelemetryEventHook = Callable[[Mapping[str, Any]], None]` at `sdk.py:98`. `_emit_event()` passes `MappingProxyType(dict(event))` and swallows hook exceptions by default at `sdk.py:956-965`. README lists event names/fields at `README.md:255-265`. Async client uses the same sync hook type.
- Why it matters: Observability consumers must parse string names and untyped dict fields. Async runtimes cannot `await` hooks without wrapping.
- Root cause or likely root cause: Minimal MVP callback design.
- Impact on MVP readiness: Acceptable MVP shortcut.
- Impact on developer experience, if applicable: Minor friction for typed consumers and async agent frameworks.
- Impact on security or reliability, if applicable: Minimal; swallowed exceptions are safe by default.
- Whether it was mentioned in the prior review log: Telemetry hook was credited, but limitations remain.
- Whether a previous fix claimed to address it: Yes, hook added.
- Whether that previous fix is sufficient: Yes for MVP, not for a polished SDK.
- Recommended remediation: Add typed event dataclasses or Literals, a schema version, and optional async hook support.
- Suggested validation or test: Type-check sample event hook integrations and async hook behavior.
- Whether it should affect scoring: Yes, low DX reducer.

### SDK-AUDIT-024: Async Client Uses `threading.RLock` In Async Methods

- Category: Async runtime / maintainability
- Severity: Low
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py`
- Evidence: Sync and async clients both use `self._cache_lock = threading.RLock()` (`sdk.py:451` and mirrored async constructor) and async methods call synchronous cache methods such as `_cached_tool()` and `clear_tool_cache()` around `sdk.py:1293-1300` and `sdk.py:1327-1336`.
- Why it matters: The lock scope is short and likely fine for MVP, but blocking locks inside event loops are not ideal if hooks or future cache work grows.
- Root cause or likely root cause: Shared sync/async cache implementation.
- Impact on MVP readiness: Acceptable.
- Impact on developer experience, if applicable: Low.
- Impact on security or reliability, if applicable: Low async latency risk under heavy shared-client use.
- Whether it was mentioned in the prior review log: Sync/async duplication and cache thread-safety were mentioned generally.
- Whether a previous fix claimed to address it: No.
- Whether that previous fix is sufficient: Not applicable.
- Recommended remediation: Use separate async cache lock or keep cache operations strictly bounded and document client-sharing expectations.
- Suggested validation or test: Async concurrency stress test with cache enabled.
- Whether it should affect scoring: Yes, low maintainability/reliability reducer.

### SDK-AUDIT-025: Custom HTTP Client Protocol Is Runtime-Checked But Not Formally Modeled

- Category: API extensibility / DX
- Severity: Low
- Confidence: High
- File path or area: SDK HTTP client validation and README
- Evidence: Constructors accept `http_client: httpx.Client | None` or `httpx.AsyncClient | None`, but runtime validators inspect required methods and require streaming support by default. README says custom clients must expose `stream()` unless `allow_buffered_custom_http_client=True` at `README.md:90-94` and `README.md:374-375`.
- Why it matters: A custom compatible client can fail constructor checks because the SDK expects particular methods (`get`, `post`, `close`/`aclose`, `stream`) even when actual request paths mainly use streaming helpers.
- Root cause or likely root cause: Runtime structural checks were added without defining a public Protocol type.
- Impact on MVP readiness: Acceptable, but source-level debugging may be required for custom transports.
- Impact on developer experience, if applicable: Integrators using custom instrumentation/proxy clients may need adapters.
- Impact on security or reliability, if applicable: Low; strict checks protect response caps by default.
- Whether it was mentioned in the prior review log: Injected client validation was fixed and credited.
- Whether a previous fix claimed to address it: Yes.
- Whether that previous fix is sufficient: Mostly for safety, not ideal for ergonomics.
- Recommended remediation: Export `SyncGatewayHttpClient` and `AsyncGatewayHttpClient` Protocols and document method requirements.
- Suggested validation or test: Type-check and runtime-test a documented custom client adapter.
- Whether it should affect scoring: Yes, low DX reducer.

### SDK-AUDIT-026: Buffered Custom HTTP Client Opt-In Can Bypass Response-Size Enforcement

- Category: Reliability / security
- Severity: Medium
- Confidence: High
- File path or area: SDK custom client path and README
- Evidence: `allow_buffered_custom_http_client` defaults false in config at `sdk.py:249`. README warns to set it only when the injected client enforces equivalent response-size limits at `README.md:90-94` and `README.md:374-375`.
- Why it matters: The escape hatch is necessary for extensibility, but if a consumer sets it casually, the SDK may receive already-buffered oversized responses from a custom client.
- Root cause or likely root cause: Extensibility tradeoff.
- Impact on MVP readiness: Acceptable as documented opt-in, but important for SDK consumers integrating custom transports.
- Impact on developer experience, if applicable: A developer may set the flag to silence constructor errors without understanding the safety consequence.
- Impact on security or reliability, if applicable: Memory exhaustion and data exposure risk.
- Whether it was mentioned in the prior review log: Custom client streaming requirement was credited.
- Whether a previous fix claimed to address it: Yes.
- Whether that previous fix is sufficient: Mostly, because default is safe.
- Recommended remediation: Require an explicit callable/adapter that enforces size caps, or add a louder warning in exception text/docs.
- Suggested validation or test: Example custom client adapter that enforces caps before buffering.
- Whether it should affect scoring: Yes, medium/low.

### SDK-AUDIT-027: `EnvironmentTokenProvider` Re-Reads Environment Variables On Every Request

- Category: API behavior / DX
- Severity: Low
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py`; README
- Evidence: `EnvironmentTokenProvider.get_token()` calls `os.environ.get(env_var)` each time at `sdk.py:174-185`. README says env provider reads on each request and suggests custom caching for high-throughput agents at `README.md:240-253`.
- Why it matters: This enables rotation, but the behavior is implicit in code and can surprise consumers expecting a captured token at client creation.
- Root cause or likely root cause: Simple provider design.
- Impact on MVP readiness: Acceptable.
- Impact on developer experience, if applicable: Minor surprise and potential per-request env dependency.
- Impact on security or reliability, if applicable: Low. Can help rotation; can also change authorization context mid-process if env changes.
- Whether it was mentioned in the prior review log: Environment token provider was added and credited.
- Whether a previous fix claimed to address it: Yes.
- Whether that previous fix is sufficient: Yes for MVP.
- Recommended remediation: Make docs clearer that the provider is dynamic and add a `CachedTokenProvider` utility if common.
- Suggested validation or test: Test/example showing env rotation behavior intentionally changes credential context.
- Whether it should affect scoring: Low.

### SDK-AUDIT-028: README Install Wording Is Stale Now That The Package Is Published

- Category: Documentation / DX
- Severity: Low
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/README.md`
- Evidence: README says "When the package is published to your configured Python index" at `README.md:5-14`. The user provided context that the package is published to PyPI.
- Why it matters: This wording makes the package sound not yet published, reducing confidence and creating unnecessary ambiguity.
- Root cause or likely root cause: Docs were written before or during publication.
- Impact on MVP readiness: Minor polish issue.
- Impact on developer experience, if applicable: Minor confusion.
- Impact on security or reliability, if applicable: None.
- Whether it was mentioned in the prior review log: Prior log discussed publication/install docs.
- Whether a previous fix claimed to address it: Partially.
- Whether that previous fix is sufficient: No, wording is stale after publication.
- Recommended remediation: Change install section to "Install from PyPI" and keep internal wheel fallback as a secondary path.
- Suggested validation or test: Docs lint/review against current package publication state.
- Whether it should affect scoring: Yes, low DX.

### SDK-AUDIT-029: No Framework-Specific Adoption Examples

- Category: Documentation / examples
- Severity: Low
- Confidence: High
- File path or area: SDK README/examples
- Evidence: SDK examples show direct sync and async usage, plus `examples/async_worker_example.py`, but no LangChain, LangGraph, OpenAI Agents, FastAPI worker, Celery, or queue-based integration example was found in the SDK package.
- Why it matters: Early adopters often integrate SDK calls into existing agent runtimes, not standalone scripts.
- Root cause or likely root cause: MVP docs focus on core HTTP SDK usage.
- Impact on MVP readiness: Does not block a competent engineer, but slows onboarding.
- Impact on developer experience, if applicable: Moderate friction for real agent integration.
- Impact on security or reliability, if applicable: Missing framework examples can cause ad hoc retry/token/error handling.
- Whether it was mentioned in the prior review log: Richer examples were noted as a remaining cap.
- Whether a previous fix claimed to address it: Docs were expanded, but not framework examples.
- Whether that previous fix is sufficient: Partially.
- Recommended remediation: Add one sync worker and one async framework example showing token provider, compatibility probe, idempotency, denied handling, and correlation IDs.
- Suggested validation or test: Run examples in CI using a mock transport or local gateway fixture.
- Whether it should affect scoring: Yes, ease-of-use cap.

### SDK-AUDIT-030: Constructor Configuration Surface Is Large For A First MVP Integration

- Category: API ergonomics / DX
- Severity: Low
- Confidence: High
- File path or area: SDK constructors, `ToolGatewayClientConfig`, README
- Evidence: `ToolGatewayClientConfig` exposes timeout, payload/response caps, cache, insecure HTTP, user agent, discovery retries, invocation retries, jitter, buffered custom clients, and event hook failure behavior at `sdk.py:229-250`. README lists many constructor options at `README.md:81-118`.
- Why it matters: The knobs are mostly justified, but first-time users may not know which values to change.
- Root cause or likely root cause: Safety and resiliency controls are exposed directly rather than layered into profiles.
- Impact on MVP readiness: Acceptable. Defaults appear usable, but onboarding docs should be more opinionated.
- Impact on developer experience, if applicable: Some users may need source or maintainer guidance for recommended settings.
- Impact on security or reliability, if applicable: Misconfiguration risk for `allow_insecure_http`, retry counts, and buffered custom clients.
- Whether it was mentioned in the prior review log: Shared config and docs were discussed.
- Whether a previous fix claimed to address it: Yes, config object and docs.
- Whether that previous fix is sufficient: Mostly for MVP, not polished.
- Recommended remediation: Add "recommended configs" for local dev, internal pilot, and external design partner.
- Suggested validation or test: Docs review with a new integrator following only the recommended profile.
- Whether it should affect scoring: Low.

### SDK-AUDIT-031: Diagnostic Redaction Remains Best-Effort And Can Miss Arbitrary PII In Free Text

- Category: Security / privacy
- Severity: Medium
- Confidence: High
- File path or area: SDK error sanitization; response redaction docs
- Evidence: SDK redacts common key names and text assignment patterns at `sdk.py:99-147` and sanitizes response bodies at `sdk.py:2350-2375` onward. README explicitly describes common keys only at `README.md:266-268`.
- Why it matters: Pattern-based redaction is never complete. A free-text error field can include sensitive data without a matching key or assignment pattern.
- Root cause or likely root cause: SDK uses deterministic lightweight redaction instead of a DLP system.
- Impact on MVP readiness: Acceptable if documented as best-effort and callers do not log sensitive payloads blindly.
- Impact on developer experience, if applicable: Developers may overtrust sanitized `response_body`.
- Impact on security or reliability, if applicable: Data exposure in logs.
- Whether it was mentioned in the prior review log: Yes. Prior log says redaction remains pattern-based.
- Whether a previous fix claimed to address it: Yes, redaction was broadened.
- Whether that previous fix is sufficient: Partially.
- Recommended remediation: Strengthen docs and add logging guidance that sanitized diagnostics are not a privacy guarantee. Consider opt-in stricter diagnostic suppression.
- Suggested validation or test: Add tests for free-text PII examples and decide whether to redact or document as out of scope.
- Whether it should affect scoring: Yes, security/reliability cap.

### SDK-AUDIT-032: Redaction Regex Safety Heuristics Are Helpful But Not A Complete ReDoS Defense

- Category: Security / reliability
- Severity: Low
- Confidence: Medium
- File path or area: `packages/product-platform/src/product_platform/tool_gateway/response.py`; `models.py`
- Evidence: Redaction regexes are compiled and cached at `response.py:83-97`; validators reject obvious nested/unbounded patterns and cap length at `response.py:180-196` and `models.py:699-711`.
- Why it matters: Regex safety heuristics can miss expensive patterns accepted by Python's regex engine.
- Root cause or likely root cause: Lightweight validation instead of a safe-regex engine or timeout.
- Impact on MVP readiness: Acceptable for trusted operators. Riskier if untrusted users can write response policies.
- Impact on developer experience, if applicable: Operators may not understand regex cost.
- Impact on security or reliability, if applicable: Potential response-time CPU spike.
- Whether it was mentioned in the prior review log: Regex validation was credited, residual risk mentioned generally.
- Whether a previous fix claimed to address it: Yes.
- Whether that previous fix is sufficient: Mostly for MVP with trusted operators.
- Recommended remediation: Keep policy authors trusted, document regex restrictions, or use a regex engine/timeouts with stronger guarantees.
- Suggested validation or test: Add pathological regex test cases and benchmark upper bounds.
- Whether it should affect scoring: Low.

### SDK-AUDIT-033: Custom Gateway Executors Can Return Or Raise Unsanitized Agent-Facing Messages

- Category: Extensibility / security
- Severity: Medium
- Confidence: Medium
- File path or area: `packages/product-platform/src/product_platform/api/app.py`; `ToolExecutionError`; extension point via `app.state.tool_gateway_executor`
- Evidence: The app uses `app.state.tool_gateway_executor` when present at `app.py:3634-3645`. If a custom executor raises `ToolExecutionError`, the response returns `{"code": exc.code, "message": exc.message}` at `app.py:3658-3687`. The default executor uses controlled messages, but the extension point can supply arbitrary `ToolExecutionError.message`.
- Why it matters: Trusted internal custom executors can accidentally put upstream details or secrets into agent-facing error messages.
- Root cause or likely root cause: Extensibility hook assumes custom executors are trusted and already sanitized.
- Impact on MVP readiness: Acceptable for controlled internal MVP, but should be documented for teams replacing the executor.
- Impact on developer experience, if applicable: Teams may not know which executor errors are safe to expose.
- Impact on security or reliability, if applicable: Data exposure risk from custom extension code.
- Whether it was mentioned in the prior review log: Not specifically.
- Whether a previous fix claimed to address it: No.
- Whether that previous fix is sufficient: Not applicable.
- Recommended remediation: Document `ToolExecutionError.message` as agent-facing and provide a sanitizer or safe constructor for executor authors.
- Suggested validation or test: Test a custom executor raising a message with token-like text and assert gateway sanitizes or rejects it.
- Whether it should affect scoring: Yes, modest security/DX reducer.

### SDK-AUDIT-034: Publication Provenance Depends On Manual Handoff Outside The GitHub Publish Workflow

- Category: Release / governance
- Severity: Medium
- Confidence: High
- File path or area: `.github/workflows/publish.yml`; `docs/internal/pypi-publishing.md`
- Evidence: Publish workflow says actual PyPI publishing is intentionally outside the build job at `.github/workflows/publish.yml:31-37`. The publishing runbook requires release owners to upload only validated artifacts and record evidence at `docs/internal/pypi-publishing.md:1-51`.
- Why it matters: The package may be published to PyPI, but the repository alone does not prove that the PyPI artifact was exactly the validated, signed, attested artifact unless release-ticket evidence is available.
- Root cause or likely root cause: Publishing is intentionally separated from GitHub build/attestation.
- Impact on MVP readiness: Acceptable for internal releases if the runbook is followed. Not enough to independently certify artifact provenance from repo state.
- Impact on developer experience, if applicable: External users cannot infer provenance solely from PyPI plus repository files.
- Impact on security or reliability, if applicable: Supply-chain governance risk.
- Whether it was mentioned in the prior review log: Prior log discussed release provenance as a remaining cap.
- Whether a previous fix claimed to address it: Yes, runbook and attestations.
- Whether that previous fix is sufficient: Partially.
- Recommended remediation: Use PyPI trusted publishing directly from the validated workflow or publish a signed release evidence bundle linked from release notes.
- Suggested validation or test: For a release, verify PyPI wheel hash matches the GitHub attested artifact and record the result in repo-visible release notes.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-035: `list_all_tools()` Has No Default Hard Total Cap

- Category: Reliability / API ergonomics
- Severity: Low
- Confidence: High
- File path or area: SDK discovery helpers
- Evidence: `list_all_tools(max_total: int | None = None)` defaults to no total cap at `sdk.py:623-629` and only raises `tool_discovery_too_large` when caller supplies `max_total` at `sdk.py:653-657`. Async mirrors this at `sdk.py:1253-1287`.
- Why it matters: A bad server, misconfigured tenant, or unexpectedly huge catalog can cause many requests and memory growth.
- Root cause or likely root cause: Convenience helper designed for normal MVP catalogs.
- Impact on MVP readiness: Acceptable given expected low volume, but callers should be nudged toward caps.
- Impact on developer experience, if applicable: Developers may not notice `max_total`.
- Impact on security or reliability, if applicable: Reliability risk in abnormal catalogs.
- Whether it was mentioned in the prior review log: `list_all_tools()` was added and credited; no default cap issue noted.
- Whether a previous fix claimed to address it: No direct fix.
- Whether that previous fix is sufficient: Not applicable.
- Recommended remediation: Add a conservative default `max_total`, a config default, or stronger docs recommending caps.
- Suggested validation or test: Simulate endless full pages and assert `max_total` or a default guard stops the loop.
- Whether it should affect scoring: Low.

### SDK-AUDIT-036: Token Character Grammar May Reject Future Legitimate Opaque Token Formats

- Category: API compatibility / auth
- Severity: Low
- Confidence: Medium
- File path or area: SDK token validation and gateway token parser
- Evidence: SDK token pattern is `^[A-Za-z0-9._~+/=-]+$` at `sdk.py:89-92`; gateway parser uses the same style at `auth.py:14-16`. Docs say raw tokens may contain only those characters at `README.md:29-31`.
- Why it matters: Current AgentMesh tokens use `secrets.token_urlsafe(32)` and fit this grammar, but future opaque issuers that use colons or other safe bearer-token characters will fail.
- Root cause or likely root cause: Tight token grammar chosen for log/header safety.
- Impact on MVP readiness: Acceptable because current issuer matches.
- Impact on developer experience, if applicable: Integrators using another issuer may hit validation errors.
- Impact on security or reliability, if applicable: Mostly compatibility risk, not a security weakness.
- Whether it was mentioned in the prior review log: Token validation was credited, not future format risk.
- Whether a previous fix claimed to address it: Yes, strict validation.
- Whether that previous fix is sufficient: Yes for current MVP issuer.
- Recommended remediation: Document issuer constraints and revisit grammar if external identity providers issue gateway tokens.
- Suggested validation or test: Contract test that Product Platform issued tokens always pass SDK and server validators.
- Whether it should affect scoring: Low.

### SDK-AUDIT-037: Workspace Contains Ignored Generated Cache Files In Package Trees

- Category: Repository hygiene
- Severity: Nit
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk`; `packages/product-platform/src/.../__pycache__`; test caches
- Evidence: `find` showed ignored `.mypy_cache`, `.pytest_cache`, `.ruff_cache`, and `__pycache__` files under SDK and product package trees. `git status --short` was clean, and release validators exclude cache artifacts.
- Why it matters: Not a release blocker, but it adds noise to audits and can hide accidental artifact inclusion if validators regress.
- Root cause or likely root cause: Local validation generated caches in package directories.
- Impact on MVP readiness: No direct impact.
- Impact on developer experience, if applicable: Minor repo navigation noise.
- Impact on security or reliability, if applicable: None while untracked and excluded.
- Whether it was mentioned in the prior review log: Prior log discussed excluding generated files from artifacts.
- Whether a previous fix claimed to address it: Yes, artifact denylist.
- Whether that previous fix is sufficient: Yes for publishing, not for local cleanliness.
- Recommended remediation: Optionally clean caches before release audits or add a documented cleanup command.
- Suggested validation or test: Keep artifact denylist checks in validators.
- Whether it should affect scoring: No material score effect.

### SDK-AUDIT-038: Changelog Is Minimal And Undated

- Category: Documentation / release governance
- Severity: Low
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/CHANGELOG.md`
- Evidence: Changelog only lists `## 0.1.0` with bullet features and no date, release link, or migration section at `CHANGELOG.md:1-25`.
- Why it matters: For a published SDK, adopters need a concise history of what changed and when, especially while the API is beta.
- Root cause or likely root cause: Initial package release had only one version.
- Impact on MVP readiness: Minor.
- Impact on developer experience, if applicable: Low; it reduces confidence in release cadence and upgrade tracking.
- Impact on security or reliability, if applicable: Security fix tracking would be harder if this remains minimal.
- Whether it was mentioned in the prior review log: Changelog absence was previously fixed by adding one.
- Whether a previous fix claimed to address it: Yes.
- Whether that previous fix is sufficient: Partially.
- Recommended remediation: Add release date, artifact hashes or release URL, compatibility note, and security-fix convention.
- Suggested validation or test: Release checklist requires changelog entry with date and compatibility notes.
- Whether it should affect scoring: Low.

## 5. Issues Grouped By Category

Public API and compatibility:

- SDK-AUDIT-006, SDK-AUDIT-021, SDK-AUDIT-022, SDK-AUDIT-023, SDK-AUDIT-025, SDK-AUDIT-027, SDK-AUDIT-030, SDK-AUDIT-036.

Runtime correctness and reliability:

- SDK-AUDIT-001, SDK-AUDIT-007, SDK-AUDIT-008, SDK-AUDIT-009, SDK-AUDIT-010, SDK-AUDIT-014, SDK-AUDIT-026, SDK-AUDIT-035.

Security and privacy:

- SDK-AUDIT-002, SDK-AUDIT-005, SDK-AUDIT-011, SDK-AUDIT-012, SDK-AUDIT-013, SDK-AUDIT-031, SDK-AUDIT-032, SDK-AUDIT-033.

Developer experience and documentation:

- SDK-AUDIT-019, SDK-AUDIT-020, SDK-AUDIT-028, SDK-AUDIT-029, SDK-AUDIT-030, SDK-AUDIT-038.

Testing:

- SDK-AUDIT-003, SDK-AUDIT-015.

Packaging, release, and supply chain:

- SDK-AUDIT-004, SDK-AUDIT-016, SDK-AUDIT-017, SDK-AUDIT-018, SDK-AUDIT-034, SDK-AUDIT-037, SDK-AUDIT-038.

## 6. Critical And High-Severity Blockers

No critical issue was proven in the current repository state.

High-severity blockers for broader adoption:

- SDK-AUDIT-001: idempotency `in_progress` records have no expiry or recovery.
- SDK-AUDIT-002: allowed invocation responses expose full internal policy decision objects.
- SDK-AUDIT-003: no true installed-wheel-to-running-network-gateway test.
- SDK-AUDIT-004: product-platform and standalone SDK both ship the same top-level `ophanix_tool_gateway` package.

These do not make the SDK unusable for a controlled internal MVP, but they are too substantial for an 8/10 production-pilot rating.

## 7. Medium-Severity MVP Risks

Medium risks:

- SDK-AUDIT-005: idempotency replay response body retention has no cleanup policy.
- SDK-AUDIT-006: compatibility probe ignores `min_sdk_version`.
- SDK-AUDIT-007: process-local rate limiter is not a complete protection boundary.
- SDK-AUDIT-008: process-local circuit breaker loses state on restart/across workers.
- SDK-AUDIT-009: offset pagination can miss or duplicate under catalog churn.
- SDK-AUDIT-010: opt-in discovery cache can serve stale auth/contract data.
- SDK-AUDIT-011: disabled response policies bypass redaction and visibility controls.
- SDK-AUDIT-012: upstream SSRF defense still depends on infrastructure egress controls.
- SDK-AUDIT-013: local/test unresolved upstream behavior can mask production failures.
- SDK-AUDIT-014: SDK payload validator lacks explicit depth cap.
- SDK-AUDIT-015: standalone SDK suite is thin compared with product-platform mirror coverage.
- SDK-AUDIT-016: product release validator is weaker than SDK validator.
- SDK-AUDIT-017: local validator SBOMs are artifact-only.
- SDK-AUDIT-018: dependency resolution is not reproducibly constrained/tested.
- SDK-AUDIT-019: credential issuance docs still contain opaque operator-token step.
- SDK-AUDIT-020: direct HTTP example code lacks SDK safeguards.
- SDK-AUDIT-022: `raw`/`decision` fields encourage unstable dependence.
- SDK-AUDIT-026: buffered custom HTTP client opt-in can bypass response-size enforcement.
- SDK-AUDIT-031: diagnostic redaction remains best-effort.
- SDK-AUDIT-033: custom executors can expose unsanitized messages.
- SDK-AUDIT-034: publication provenance depends on manual handoff evidence.

## 8. Low-Severity And Nit-Level Issues

Low and nit issues:

- SDK-AUDIT-021: deprecated `list_tools(status=...)` remains public.
- SDK-AUDIT-023: event hook is stringly typed, unversioned, and sync-only.
- SDK-AUDIT-024: async client uses `threading.RLock`.
- SDK-AUDIT-025: custom HTTP client protocol is not formally modeled.
- SDK-AUDIT-027: `EnvironmentTokenProvider` rereads env on every request.
- SDK-AUDIT-028: install wording is stale after publication.
- SDK-AUDIT-029: no framework-specific adoption examples.
- SDK-AUDIT-030: first-use config surface is broad.
- SDK-AUDIT-032: redaction regex heuristics are incomplete.
- SDK-AUDIT-035: `list_all_tools()` default has no hard total cap.
- SDK-AUDIT-036: strict token grammar may constrain future issuers.
- SDK-AUDIT-037: ignored generated cache files are present in package trees.
- SDK-AUDIT-038: changelog is minimal and undated.

## 9. Prior Findings Status Table

| Prior issue or claim | Current status | Challenge |
| --- | --- | --- |
| SDK discovery used `/api/v1/tools` with gateway token | Fixed | SDK uses `/api/v1/gateway/tools` and gateway route is gateway-authenticated. |
| Gateway discovery exposed operator fields | Mostly fixed | Discovery response is narrow; invocation response still exposes full decision object. |
| Weak SDK URL/token/payload validation | Mostly fixed | Strong current validation; payload depth cap still missing. |
| `get_tool()` first-page only | Fixed for static catalogs | Offset pagination can still miss under churn. |
| Token repr and exception body exposure | Mostly fixed | Redaction is broader but still best-effort. |
| Missing env token provider | Fixed | Dynamic env reread behavior should be clearer. |
| Manual pagination required | Fixed | `list_all_tools()` exists; no default total cap. |
| Discovery retry lacked `Retry-After` | Fixed | Covered in current SDK retry helpers. |
| SDK embedded only in product platform | Partially fixed | Standalone package exists, but duplicate top-level package ownership remains. |
| Resource-bound credential scopes flattened | Fixed | `GatewayPrincipal.scope_grants` and resource-aware checks are present. |
| Discovery cache crossed credentials | Fixed | Cache is credential-fingerprinted; staleness remains opt-in tradeoff. |
| No async SDK | Fixed | Async client exists; some async ergonomics remain rough. |
| Standalone package buildability/docs gaps | Mostly fixed | Validators and docs exist; docs still have onboarding and stale wording gaps. |
| No idempotency contract | Partially fixed | Idempotency exists, but stale `in_progress` recovery and retention are unresolved. |
| Broad gateway auth bypass | Fixed | Gateway runtime paths use explicit allowlist. |
| Invocation schema before authz / existence oracle | Fixed | Policy decision runs before schema validation; denied responses coarse. |
| Upstream URL validation weak | Mostly fixed | Stronger validation exists; DNS rebinding/egress residual remains. |
| Failed upstream responses bypass policy | Fixed | Response policy applies to failed and successful execution results. |
| `store_full_response` not honored | Fixed for runtime summaries | Idempotency replay still stores public response envelope. |
| No rate limiting | Partially fixed | Process-local limiter exists; deployment assumptions remain. |
| No request body limit | Fixed | Runtime body cap middleware exists. |
| CORS broad with credentials | Fixed for production guard | No current issue found. |
| Token entropy docs missing | Mostly fixed | Current issuer uses high-entropy tokens and docs warn about fixtures. |
| Direct HTTP example unsafe | Partially fixed | README warning exists; code remains thin. |
| Token issuance setup underdocumented | Partially fixed | Still depends on opaque operator token step. |
| Install docs assumed unpublished package | Stale | User confirms PyPI publication; README wording still conditional. |
| Changelog/security policy missing | Mostly fixed | Changelog exists but minimal/undated; security policy exists. |
| Broad dependency ranges | Still open | Dependency audit exists; reproducible range strategy is not closed. |
| Local validation not release-equivalent | Improved | CI/publish validators exist; PyPI upload provenance still depends on external handoff evidence. |

## 10. Scoring Matrix

### Implementation Quality

- Current score: 7.0/10.
- Prior score from review log: 8.1/10.
- Direction: Lowered.
- Exact reasons: Strong SDK structure and current validation pass, but idempotency recovery is incomplete, duplicate package ownership is risky, real-network contract validation is missing, `min_sdk_version` compatibility is ignored, and the SDK remains a large single-file implementation with mirrored sync/async paths.
- Score cap caused by unresolved issues: High issues SDK-AUDIT-001, SDK-AUDIT-003, and SDK-AUDIT-004 cap this at 7.
- What must be fixed to reach the next score: Add stale idempotency recovery, real installed-wheel network E2E, and package ownership cleanup.
- What must be fixed to reach 7: Current repo reaches 7 for implementation because core SDK/gateway behavior works and validation passes.
- What must be fixed to reach 8: Resolve high issues, add stronger standalone test ownership, and reduce duplicate package/source ownership risk.

### Ease Of Use

- Current score: 7.0/10.
- Prior score from review log: 8.3/10.
- Direction: Lowered.
- Exact reasons: README and API reference are useful, but credential issuance is not fully runnable, direct HTTP examples can be copied unsafely, install wording is stale, no framework-specific integration examples exist, and several public API fields are unstable or compatibility-oriented.
- Score cap caused by unresolved issues: SDK-AUDIT-019, SDK-AUDIT-020, SDK-AUDIT-021, SDK-AUDIT-022, SDK-AUDIT-028, SDK-AUDIT-029, and SDK-AUDIT-030 cap this near 7.
- What must be fixed to reach the next score: Make token issuance quickstart fully runnable and add framework examples.
- What must be fixed to reach 7: Current repo reaches 7 for a competent internal engineer.
- What must be fixed to reach 8: Complete first-run docs, clean stale wording, document stable/unstable fields, and provide tested integration examples.

### Security And Reliability

- Current score: 6.5/10.
- Prior score from review log: 8.3/10.
- Direction: Lowered.
- Exact reasons: Secure defaults are materially better than early versions, but idempotency recovery and retention, decision object exposure, process-local controls, DNS rebinding residuals, policy-disable bypass, best-effort redaction, and manual publication provenance prevent a stronger score.
- Score cap caused by unresolved issues: SDK-AUDIT-001 and SDK-AUDIT-002 cap this below 7 for external MVP use.
- What must be fixed to reach the next score: Add idempotency recovery, narrow agent-facing decision responses, add response retention cleanup, and document/enforce deployment perimeter assumptions.
- What must be fixed to reach 7: Fix SDK-AUDIT-001 or provide an explicit operator recovery path, and narrow the invocation decision envelope.
- What must be fixed to reach 8: Add shared/perimeter reliability controls, stronger egress enforcement evidence, real-network E2E, dependency/provenance evidence, and robust retention policy.

## 11. Score Cap Explanation

A single unresolved high reliability issue can cap the relevant score below 7. Here, SDK-AUDIT-001 directly weakens the idempotency and retry story. SDK-AUDIT-002 weakens least-privilege API exposure. SDK-AUDIT-003 prevents strong confidence that the published SDK and gateway work in a real process boundary. SDK-AUDIT-004 creates avoidable packaging ambiguity.

The repository proves enough current behavior to avoid a 4 or 5: tests pass, packages build, mypy passes, authz and discovery are materially fixed, and the SDK has real sync/async clients with safe defaults. But the unresolved high issues prevent an 8. The security/reliability score remains 6.5 because the system is functional but fragile around recovery and operational boundaries.

## 12. Required Fixes To Reach MVP Readiness

For a controlled internal MVP, the repository is already usable with guardrails:

- Single-process or explicitly rate-limited ingress.
- Trusted tool operators only.
- Known upstream hosts with infrastructure egress controls.
- Sensitive-data policy review for every exposed tool.
- Manual operator path for stuck idempotency records.
- Support engineer available for credential issuance.

For broader MVP readiness without heavy hand-holding, required fixes:

- SDK-AUDIT-001: recover or expire stale idempotency records.
- SDK-AUDIT-002: narrow agent-facing decision responses.
- SDK-AUDIT-003: add true installed-wheel network E2E.
- SDK-AUDIT-004: remove duplicate top-level package ownership.
- SDK-AUDIT-005: add idempotency replay retention/cleanup.
- SDK-AUDIT-019: make credential issuance docs runnable.

## 13. Required Fixes To Reach 7 Out Of 10

Implementation and ease of use are already at 7. Security/reliability needs:

- Fix stale `in_progress` idempotency recovery or document and implement an operator recovery CLI.
- Remove internal decision fields from agent-facing success/upstream-error responses.
- Add retention for idempotency replay bodies.
- Add deployment docs that explicitly state process-local rate limiter/circuit breaker assumptions.
- Make token issuance quickstart runnable enough for a new internal engineer.

## 14. Required Fixes To Reach 8 Out Of 10

To reach an 8 in this MVP-oriented rubric:

- Complete the 7/10 items.
- Add real installed-wheel-to-running-gateway E2E in CI for sync and async paths.
- Resolve package namespace ownership by depending on the standalone SDK or removing duplicate `ophanix_tool_gateway` from product-platform.
- Enforce `min_sdk_version` in compatibility checks.
- Add min/max dependency range tests or release constraints.
- Produce full dependency SBOMs in local validator or clearly rely on publish-workflow SBOM evidence.
- Add cursor or snapshot discovery pagination.
- Add framework examples and full first-run credential issuance docs.
- Add production-parity upstream validation docs/tests and egress policy requirements.

## 15. Recommended Remediation Order

1. Fix SDK-AUDIT-001 stale idempotency recovery.
2. Fix SDK-AUDIT-002 agent-facing decision exposure.
3. Fix SDK-AUDIT-004 duplicate top-level package ownership.
4. Add SDK-AUDIT-003 real installed-wheel running-gateway E2E.
5. Add SDK-AUDIT-005 idempotency response retention/cleanup.
6. Fix SDK-AUDIT-006 `min_sdk_version` compatibility semantics.
7. Update credential issuance docs and install wording.
8. Document process-local limiter/circuit assumptions and production egress requirements.
9. Expand standalone SDK tests and framework examples.
10. Harden release evidence: product validator parity, true dependency SBOM, dependency range CI, and PyPI artifact hash provenance.

## 16. Validation Plan

Validation to keep:

- SDK package tests with pytest.
- Product gateway `test_tool_gateway_*.py` suite.
- SDK mypy and product tool gateway mypy.
- SDK release validator with dependency audit and `twine check` in CI/publish.
- Product release validator.
- Artifact denylist checks for DB/cache/generated files.

Validation to add:

- Installed wheel against real running product-platform HTTP server.
- Async installed-wheel E2E.
- Stale idempotency recovery test.
- Idempotency retention/cleanup test.
- Agent-facing response-shape contract test that forbids internal decision fields.
- Package install-order test for product-platform plus standalone SDK.
- Compatibility test for unsupported `min_sdk_version`.
- Discovery churn test or cursor pagination tests.
- Production-parity upstream host validation test.
- Custom executor error sanitization test.
- Min/max dependency matrix for `httpx`.
- PyPI artifact hash/provenance verification for each release.

## 17. Final Strict MVP Assessment

The repository is a functional but fragile MVP, not a production-ready SDK/platform boundary.

It is credible for controlled internal teams and design partners if the operators control credentials, upstream tool registration, ingress limits, response policies, and rollout scope. It is not yet safe enough to hand to broader external adopters without support because the idempotency recovery story can fail permanently, the agent-facing invocation envelope exposes internal policy objects, package ownership is ambiguous when both distributions are installed, and end-to-end validation still stops short of a real running gateway process.

Final assessment: credible controlled MVP, with security/reliability below the threshold I would want before broader adoption.
