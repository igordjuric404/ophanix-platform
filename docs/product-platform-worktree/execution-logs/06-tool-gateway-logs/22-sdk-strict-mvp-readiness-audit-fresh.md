# Tool Gateway SDK Strict MVP Readiness Audit

Date: 2026-05-12

## 1. Executive Summary

The current Tool Gateway SDK is a credible controlled MVP for technically competent early adopters, but it is not yet a low-friction or broadly safe external SDK. The strongest positive evidence is that the standalone SDK has a dedicated package, typed public exports, sync and async clients, HTTPS-by-default URL validation, strict payload validation, response-size caps for built-in clients, idempotency-gated invocation retries, discovery retries, compatibility probing, redacted diagnostic errors, a release validator, and live gateway integration tests.

The strongest negative evidence is that adoption still depends on fragile repository and release assumptions: the product-platform package depends on the standalone SDK from the package index while also carrying an unshipped compatibility source copy; the Docker build installs product-platform without first installing the local standalone SDK; release validation is optional for dependency audit, strict git state, and index install verification; documentation contains commands using `python` in cloud docs even though this audit environment only has `python3`; generated caches and build artifacts are present in the workspace; and direct HTTP/server integration paths remain easier to misuse than the SDK path.

Strict MVP verdict: credible MVP for internal pilots and design partners under operator control. Not ready for unsupervised external adoption.

Scores:

- Implementation quality: 6/10
- Ease of use: 6/10
- Security and reliability: 6/10

## 2. Repository Surface Reviewed

Relevant SDK, runtime, packaging, tests, docs, and release files reviewed:

- `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/__init__.py`
- `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py`
- `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/py.typed`
- `packages/ophanix-tool-gateway-sdk/pyproject.toml`
- `packages/ophanix-tool-gateway-sdk/README.md`
- `packages/ophanix-tool-gateway-sdk/API_REFERENCE.md`
- `packages/ophanix-tool-gateway-sdk/MIGRATION.md`
- `packages/ophanix-tool-gateway-sdk/CHANGELOG.md`
- `packages/ophanix-tool-gateway-sdk/SECURITY.md`
- `packages/ophanix-tool-gateway-sdk/examples/async_worker_example.py`
- `packages/ophanix-tool-gateway-sdk/examples/langgraph_node_example.py`
- `packages/ophanix-tool-gateway-sdk/scripts/validate_release.py`
- `packages/ophanix-tool-gateway-sdk/tests/test_sdk_behavior.py`
- `packages/ophanix-tool-gateway-sdk/tests/test_package_smoke.py`
- `packages/product-platform/src/ophanix_tool_gateway/*`
- `packages/product-platform/src/product_platform/tool_gateway/sdk.py`
- `packages/product-platform/src/product_platform/tool_gateway/auth.py`
- `packages/product-platform/src/product_platform/tool_gateway/invocation.py`
- `packages/product-platform/src/product_platform/tool_gateway/pagination.py`
- `packages/product-platform/src/product_platform/tool_gateway/repository.py`
- `packages/product-platform/src/product_platform/tool_gateway/response.py`
- `packages/product-platform/src/product_platform/tool_gateway/runtime_audit.py`
- `packages/product-platform/src/product_platform/api/app.py`
- `packages/product-platform/src/product_platform/api/settings.py`
- `packages/product-platform/src/product_platform/agents/credentials.py`
- `packages/product-platform/pyproject.toml`
- `packages/product-platform/README.md`
- `packages/product-platform/LOCAL_DEMO.md`
- `packages/product-platform/examples/tool-gateway-direct-http/*`
- `packages/product-platform/deploy/cloud/*`
- `packages/product-platform/tests/test_tool_gateway_sdk_*.py`
- `packages/product-platform/tests/test_tool_gateway_installed_sdk_contract.py`
- `packages/product-platform/tests/test_tool_gateway_auth_*.py`
- `packages/product-platform/tests/test_tool_gateway_invocation_*.py`
- `packages/product-platform/tests/test_tool_gateway_forwarding_*.py`
- `packages/product-platform/tests/test_tool_gateway_runtime_audit_*.py`

Validation commands run:

- `python3 -m pytest packages/ophanix-tool-gateway-sdk/tests -q`: 39 passed.
- `python3 -m build packages/ophanix-tool-gateway-sdk`: passed.
- `cd packages/ophanix-tool-gateway-sdk && python3 -m mypy src/ophanix_tool_gateway`: passed.
- `cd packages/ophanix-tool-gateway-sdk && python3 scripts/validate_release.py`: passed.
- `python3 -m pytest packages/product-platform/tests/test_tool_gateway_sdk_phase1.py packages/product-platform/tests/test_tool_gateway_sdk_phase2.py packages/product-platform/tests/test_tool_gateway_sdk_phase3.py packages/product-platform/tests/test_tool_gateway_sdk_package.py packages/product-platform/tests/test_tool_gateway_installed_sdk_contract.py -q`: 103 passed.
- `cd packages/product-platform && python3 -m mypy src/product_platform/tool_gateway src/ophanix_tool_gateway`: passed.
- `cd packages/product-platform && python3 -m build`: passed.

Observed environment fact:

- `python` is not available in this audit shell; `python3` is available.

## 3. Exhaustive Issue Register

### SDK-AUDIT-001

Title: Product-platform wheel excludes the compatibility SDK source while retaining it in the source tree.

Category: Packaging and release

Severity: Medium

Confidence: High

File path or area: `packages/product-platform/pyproject.toml:63-76`, `packages/product-platform/src/ophanix_tool_gateway`

Evidence: `pyproject.toml` excludes `/src/ophanix_tool_gateway` and wheel packages only `src/product_platform`, while the repository still carries `src/ophanix_tool_gateway` as a parity copy.

Why it matters: Local source-tree imports and installed-wheel imports can differ. A developer testing with `PYTHONPATH=src` can unknowingly validate a package layout that product-platform consumers will not receive.

Root cause or likely root cause: Transitional extraction from embedded SDK to standalone package.

Impact on MVP readiness: Does not block controlled MVP usage, but it creates a packaging trap and raises confidence risk.

Impact on developer experience, if applicable: Source-level debugging can disagree with installed behavior.

Impact on security or reliability, if applicable: Stale local copies could hide patched security behavior if parity checks are skipped.

Recommended remediation: Remove the unshipped product-platform SDK source copy or automate generation from the standalone package with a clearly documented compatibility strategy.

Suggested validation or test: Keep the existing parity test and add an installed product-platform wheel test that imports `product_platform.tool_gateway` without `PYTHONPATH=src`.

Should affect scoring: Yes.

### SDK-AUDIT-002

Title: Product-platform installation depends on an external SDK package even for local monorepo builds.

Category: Packaging and release

Severity: Medium

Confidence: High

File path or area: `packages/product-platform/pyproject.toml:15-25`, `packages/product-platform/deploy/cloud/Dockerfile.api:17-20`

Evidence: `ophanix-product-platform` depends on `ophanix-tool-gateway-sdk>=0.1.0,<1.0`; Dockerfile installs `./packages/product-platform` but does not install `./packages/ophanix-tool-gateway-sdk` first.

Why it matters: A clean build can silently resolve the SDK from the package index rather than the monorepo checkout. If the local platform and released SDK drift, the image may not contain the code under review.

Root cause or likely root cause: Standalone packaging was added without a monorepo-local dependency override in deployment builds.

Impact on MVP readiness: Controlled deployments can work if the exact SDK is already published, but reproducibility is weak.

Impact on developer experience, if applicable: Developers may see different behavior locally, in CI, and in Docker.

Impact on security or reliability, if applicable: Security fixes in the repo are not guaranteed to land in images unless the package index has the same version.

Recommended remediation: In monorepo Docker and CI builds, install the local SDK wheel or pin a verified package hash/version built from the same commit.

Suggested validation or test: Build Docker images with network disabled after local wheel creation, or assert installed `ophanix_tool_gateway.__version__` and source provenance in the image smoke test.

Should affect scoring: Yes.

### SDK-AUDIT-003

Title: Product-platform and standalone SDK both declare version `0.1.0`, creating ambiguous provenance.

Category: Packaging and release

Severity: Low

Confidence: High

File path or area: `packages/product-platform/pyproject.toml:5-7`, `packages/ophanix-tool-gateway-sdk/pyproject.toml:5-7`

Evidence: Both packages use version `0.1.0`.

Why it matters: When debugging SDK/platform compatibility, the same semver value on two packages makes logs and support reports less precise.

Root cause or likely root cause: Initial MVP versioning across packages.

Impact on MVP readiness: Acceptable for MVP, but weak for support.

Impact on developer experience, if applicable: Users can report "0.1.0" without making clear whether they mean platform or SDK.

Impact on security or reliability, if applicable: Patch provenance is less clear during incident response.

Recommended remediation: Use package-qualified version logging and release manifests that bind SDK version, platform version, and git SHA.

Suggested validation or test: Add a startup/readiness field and SDK support command that prints both package names and versions.

Should affect scoring: Yes, lightly.

### SDK-AUDIT-004

Title: Release validator makes dependency audit optional.

Category: Security

Severity: Medium

Confidence: High

File path or area: `packages/ophanix-tool-gateway-sdk/scripts/validate_release.py:43-46`, `packages/ophanix-tool-gateway-sdk/pyproject.toml:44-46`

Evidence: `--require-dependency-audit` is an optional flag. The default release validation passed without running `pip-audit`.

Why it matters: The SDK is small, but its only runtime dependency is HTTP transport code. Shipping without mandatory dependency audit weakens security confidence.

Root cause or likely root cause: Release script supports fast local validation and stricter release validation with optional flags.

Impact on MVP readiness: Acceptable for internal MVP if CI enforces the strict mode; not proven by this repo state.

Impact on developer experience, if applicable: Maintainers can accidentally publish from a weaker path.

Impact on security or reliability, if applicable: Known vulnerable dependency versions may slip through.

Recommended remediation: Make dependency audit required in release CI or fail publish workflow unless `validate_release.py --require-dependency-audit` passes.

Suggested validation or test: Add CI job evidence or workflow check invoking strict release validation.

Should affect scoring: Yes.

### SDK-AUDIT-005

Title: Release validator does not require strict git/tag provenance by default.

Category: Packaging and release

Severity: Medium

Confidence: High

File path or area: `packages/ophanix-tool-gateway-sdk/scripts/validate_release.py:47-55`

Evidence: `--strict-git` is optional. The default validation can build artifacts from a dirty or untagged tree.

Why it matters: MVP design partners need reproducible artifacts. Building from dirty state makes it difficult to prove what code was shipped.

Root cause or likely root cause: Local developer convenience.

Impact on MVP readiness: Controlled MVP can proceed, but release credibility is capped.

Impact on developer experience, if applicable: Support cannot reliably map package behavior to source.

Impact on security or reliability, if applicable: Incident remediation cannot prove artifact provenance.

Recommended remediation: Enforce strict git/tag validation in publish CI and write the git SHA into release metadata.

Suggested validation or test: Publish workflow should fail when `git status --porcelain` is non-empty or tag does not match package version.

Should affect scoring: Yes.

### SDK-AUDIT-006

Title: Release validator does not verify package-index install by default.

Category: Packaging and release

Severity: Low

Confidence: High

File path or area: `packages/ophanix-tool-gateway-sdk/scripts/validate_release.py:56-62`, `packages/ophanix-tool-gateway-sdk/README.md:492`

Evidence: `--verify-index-install` is optional.

Why it matters: A wheel that builds locally can still fail for real consumers if index metadata, package name normalization, or dependency resolution differs.

Root cause or likely root cause: Separation between pre-publish artifact validation and post-publish verification.

Impact on MVP readiness: Not a blocker, but it reduces confidence in installation readiness.

Impact on developer experience, if applicable: Consumers may discover packaging problems first.

Impact on security or reliability, if applicable: Wrong index or package version may be installed.

Recommended remediation: Make index-install verification part of release completion.

Suggested validation or test: CI should create a fresh venv and install the exact released version from the intended index.

Should affect scoring: Yes, lightly.

### SDK-AUDIT-007

Title: SDK public API is still pre-1.0 and explicitly unstable.

Category: Public API

Severity: Medium

Confidence: High

File path or area: `packages/ophanix-tool-gateway-sdk/API_REFERENCE.md:1-4`, `packages/ophanix-tool-gateway-sdk/pyproject.toml:6-7`

Evidence: API reference says the supported public surface is for the `0.x` line; package version is `0.1.0`.

Why it matters: Early adopters can use it, but should expect breaking changes. That is acceptable for MVP only if migration support is active and explicit.

Root cause or likely root cause: MVP-stage package.

Impact on MVP readiness: Does not block MVP, but caps ease-of-use and confidence.

Impact on developer experience, if applicable: Consumers need to pin versions and expect migration work.

Impact on security or reliability, if applicable: None direct.

Recommended remediation: Define a compatibility policy for 0.x, publish deprecation windows, and add contract tests across supported gateway versions.

Suggested validation or test: Add API snapshot tests that fail on accidental export or signature changes.

Should affect scoring: Yes.

### SDK-AUDIT-008

Title: `allow_buffered_custom_http_client` is exposed but intentionally ignored.

Category: Public API

Severity: Low

Confidence: High

File path or area: `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py:343`, `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py:2007-2044`

Evidence: Config contains `allow_buffered_custom_http_client`, but validators assign it to `_` and still reject clients without `stream()`.

Why it matters: A public option that never enables the named behavior is confusing even when documented as compatibility-only.

Root cause or likely root cause: Backward compatibility after hardening response caps.

Impact on MVP readiness: Acceptable shortcut, but it is API clutter.

Impact on developer experience, if applicable: Users may set the flag expecting it to work.

Impact on security or reliability, if applicable: The fail-closed behavior is safer than honoring it.

Recommended remediation: Deprecate and remove the option before 1.0, or rename it to an internal compatibility marker.

Suggested validation or test: Add a warning test when the option is set to `True`.

Should affect scoring: Yes, lightly.

### SDK-AUDIT-009

Title: `ToolGatewayClientConfig` cannot carry `base_url` or `token_provider`.

Category: Public API

Severity: Low

Confidence: High

File path or area: `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py:323-344`, `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py:434-470`

Evidence: `from_config()` still requires `base_url` and `token_provider` separately.

Why it matters: A class named client config looks like it might be complete configuration, but it only holds tuning knobs.

Root cause or likely root cause: Desire to keep secrets and environment-specific values separate.

Impact on MVP readiness: Acceptable MVP ergonomics issue.

Impact on developer experience, if applicable: Onboarding friction and minor confusion.

Impact on security or reliability, if applicable: Separating token provider is safer, but base URL omission is less obvious.

Recommended remediation: Rename to `ToolGatewayClientOptions` or document the split more prominently in constructor examples.

Suggested validation or test: Add a docs lint/example that shows `from_config()` with required separate values.

Should affect scoring: Yes, lightly.

### SDK-AUDIT-010

Title: Compatibility check is advisory and not enforced before calls.

Category: Runtime behavior

Severity: Medium

Confidence: High

File path or area: `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py:570-697`, `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py:795-818`

Evidence: `call_tool()` does not call `check_compatibility()` or fail on contract mismatch; docs show consumers doing it manually.

Why it matters: A consumer can skip the check and hit confusing runtime failures after a gateway contract change.

Root cause or likely root cause: Avoiding extra network calls and preserving thin-client behavior.

Impact on MVP readiness: Acceptable in controlled MVP but fragile for external adoption.

Impact on developer experience, if applicable: Contract mismatches become late failures.

Impact on security or reliability, if applicable: Unsupported contracts can produce unsafe assumptions about retries, responses, or errors.

Recommended remediation: Add optional `require_compatible=True` startup validation or a cached lazy compatibility guard.

Suggested validation or test: Test that clients can fail fast when configured to require compatibility.

Should affect scoring: Yes.

### SDK-AUDIT-011

Title: Non-JSON error responses are represented as successful parsed dictionaries before status handling.

Category: Runtime behavior

Severity: Low

Confidence: High

File path or area: `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py:2357-2372`, `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py:2409-2412`

Evidence: `_response_data()` returns an `error` dictionary for non-JSON bodies; `_mapping_response()` wraps non-dict values as `result`.

Why it matters: It is safe enough for errors, but it blurs transport/protocol failure with gateway-provided JSON error contracts.

Root cause or likely root cause: Keep error handling uniform.

Impact on MVP readiness: Acceptable.

Impact on developer experience, if applicable: Debug output may look like a gateway error when the server returned HTML/text.

Impact on security or reliability, if applicable: Body excerpts are sanitized and capped, limiting risk.

Recommended remediation: Add a distinct exception code path for non-JSON HTTP errors versus gateway JSON errors.

Suggested validation or test: Assert non-JSON `500` exposes `code="non_json_response"` rather than a generic HTTP code path.

Should affect scoring: Yes, lightly.

### SDK-AUDIT-012

Title: SDK returns full raw successful response snapshots that may include sensitive tool payloads.

Category: Security

Severity: Medium

Confidence: High

File path or area: `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py:2115-2134`, `packages/ophanix-tool-gateway-sdk/API_REFERENCE.md:115-120`

Evidence: `ToolCallResult.raw` is the immutable full response; docs warn not to log it unless classified safe.

Why it matters: The SDK protects exception diagnostics, but successful raw results can still be accidentally logged by consumers.

Root cause or likely root cause: Diagnostic convenience and response transparency.

Impact on MVP readiness: Acceptable for controlled adopters, risky for broader adoption.

Impact on developer experience, if applicable: Convenient debugging but easy misuse.

Impact on security or reliability, if applicable: Possible PII/secret exposure in application logs.

Recommended remediation: Add an opt-in `include_raw_response` flag defaulting to false, or provide redacted raw diagnostics separately.

Suggested validation or test: Test that default successful results do not expose raw payloads when the flag is disabled.

Should affect scoring: Yes.

### SDK-AUDIT-013

Title: Event hook schema is untyped at runtime and not versioned.

Category: Public API

Severity: Low

Confidence: High

File path or area: `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py:129-140`, `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py:1848-1856`

Evidence: Events are generic mappings with string event names; no event schema object or version field is emitted.

Why it matters: Observability integrations can break silently if event fields change.

Root cause or likely root cause: Lightweight MVP telemetry design.

Impact on MVP readiness: Acceptable.

Impact on developer experience, if applicable: Consumers must inspect docs or source.

Impact on security or reliability, if applicable: Monitoring may become inconsistent.

Recommended remediation: Add typed event dataclasses or include `schema_version`.

Suggested validation or test: Add snapshot tests for event payload keys.

Should affect scoring: Yes, lightly.

### SDK-AUDIT-014

Title: Discovery cache has no server-driven invalidation.

Category: Reliability

Severity: Medium

Confidence: High

File path or area: `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py:331-332`, `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py:786-793`

Evidence: Cache is process-local TTL with manual `clear_tool_cache()`.

Why it matters: Permission revocation or tool contract changes can remain invisible until TTL expires when consumers enable caching.

Root cause or likely root cause: MVP-local cache without ETag/version invalidation.

Impact on MVP readiness: Controlled MVP can keep caching disabled by default; broader use needs invalidation.

Impact on developer experience, if applicable: Users may not know when to clear cache.

Impact on security or reliability, if applicable: Revoked tools may still be visible locally, though actual invocation should still be server-authorized.

Recommended remediation: Add gateway discovery version/ETag, cache validation, or revocation-aware cache hints.

Suggested validation or test: Integration test permission revocation with `cache_tools=True` and verify invocation remains denied while discovery invalidates promptly.

Should affect scoring: Yes.

### SDK-AUDIT-015

Title: `get_tool()` fallback to offset pagination can miss concurrent catalog changes on older gateways.

Category: Reliability

Severity: Low

Confidence: Medium

File path or area: `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py:830-859`

Evidence: Cursor pagination is attempted first, but if unsupported the SDK falls back to offset pagination.

Why it matters: Offset pagination is unstable when tool catalogs change during scanning.

Root cause or likely root cause: Backward compatibility with older gateway list responses.

Impact on MVP readiness: Acceptable for small controlled catalogs.

Impact on developer experience, if applicable: Rare missing tools can require retries/source debugging.

Impact on security or reliability, if applicable: Inconsistent discovery under churn.

Recommended remediation: Require cursor pagination for SDK-supported gateways or expose a warning when falling back.

Suggested validation or test: Simulate offset pagination with an inserted/deleted tool between pages.

Should affect scoring: Yes, lightly.

### SDK-AUDIT-016

Title: Retry policy is intentionally narrow but not tool-contract aware.

Category: Reliability

Severity: Medium

Confidence: High

File path or area: `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py:601-660`, `packages/ophanix-tool-gateway-sdk/API_REFERENCE.md:155-165`

Evidence: Invocation retries are gated only by presence of `idempotency_key`, not by per-tool idempotency metadata.

Why it matters: Some tools may not be safely repeatable even with a key if upstream side effects are not actually deduplicated correctly.

Root cause or likely root cause: Gateway idempotency envelope exists but tool-specific idempotency semantics are not modeled in discovery.

Impact on MVP readiness: Acceptable for controlled tools where operators validate semantics.

Impact on developer experience, if applicable: Consumers may over-trust `idempotency_key`.

Impact on security or reliability, if applicable: Duplicate side effects remain possible if upstream/gateway idempotency assumptions are wrong.

Recommended remediation: Add tool metadata that declares retry/idempotency safety and have SDK respect it.

Suggested validation or test: Contract test a non-idempotent tool definition and ensure SDK does not retry even with a key.

Should affect scoring: Yes.

### SDK-AUDIT-017

Title: Runtime request body cap is server-side setting, but SDK docs do not prove matching defaults across gateway and SDK.

Category: Cross-file consistency

Severity: Low

Confidence: Medium

File path or area: `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py:108`, `packages/product-platform/README.md:109`

Evidence: SDK default max payload is `1_000_000`; product docs describe server body cap default `1000000`. No shared constant or contract test proves they stay aligned.

Why it matters: If one side changes, consumers can pass SDK validation but get server rejection, or vice versa.

Root cause or likely root cause: Separate SDK and server constants.

Impact on MVP readiness: Acceptable now, but brittle.

Impact on developer experience, if applicable: Confusing payload-size failures.

Impact on security or reliability, if applicable: Size caps are safety controls and should remain consistent.

Recommended remediation: Expose limits from capabilities endpoint and let SDK default to gateway-advertised caps.

Suggested validation or test: Test `GatewayCapabilitiesResponse` includes payload/response caps and SDK honors them.

Should affect scoring: Yes, lightly.

### SDK-AUDIT-018

Title: Direct HTTP examples require callers to recreate critical SDK safeguards.

Category: Developer experience

Severity: Medium

Confidence: High

File path or area: `packages/product-platform/examples/tool-gateway-direct-http/README.md:8-19`, `packages/product-platform/README.md:142`

Evidence: Direct HTTP docs explicitly state callers must implement token refresh, payload validation, timeouts, caps, retry policy, redaction, compatibility probing, idempotency-key generation, and typed errors.

Why it matters: The example exists in the same product surface and can be copied by early adopters despite being materially less safe than the SDK.

Root cause or likely root cause: Need to document raw HTTP contract for non-Python consumers.

Impact on MVP readiness: Not a blocker, but it creates adoption risk.

Impact on developer experience, if applicable: Developers can choose the harder path and then hit avoidable bugs.

Impact on security or reliability, if applicable: Missing safeguards can expose tokens, retry unsafe calls, or accept oversized/malformed responses.

Recommended remediation: Move direct HTTP examples behind a stronger warning and provide generated clients or a minimal reusable helper per language.

Suggested validation or test: Add docs test that direct HTTP example sets timeout, idempotency key, and response-size cap.

Should affect scoring: Yes.

### SDK-AUDIT-019

Title: Cloud deployment docs use `python`, while local validation environment only provides `python3`.

Category: Developer experience

Severity: Low

Confidence: High

File path or area: `packages/product-platform/deploy/cloud/observability.yml:10`, `packages/product-platform/deploy/cloud/PILOT_READINESS.md:11-12`, `packages/product-platform/deploy/cloud/backup-restore.md:14`

Evidence: Cloud docs/config use commands such as `python -m product_platform.cli`; audit shell returned `zsh:1: command not found: python`.

Why it matters: Small but real onboarding friction in environments that do not alias Python 3 as `python`.

Root cause or likely root cause: Mixed Python command conventions.

Impact on MVP readiness: Low.

Impact on developer experience, if applicable: First-run commands fail.

Impact on security or reliability, if applicable: Health/worker commands may fail in minimal images if `python` is absent.

Recommended remediation: Standardize docs and runtime commands on `python3` or prove container images provide `python`.

Suggested validation or test: Smoke container command resolution for every documented CLI command.

Should affect scoring: Yes, lightly.

### SDK-AUDIT-020

Title: Generated caches and build artifacts are present in the repository workspace.

Category: Maintainability

Severity: Low

Confidence: High

File path or area: `packages/ophanix-tool-gateway-sdk/.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `__pycache__`, `dist`; `packages/product-platform/.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `__pycache__`

Evidence: `find` shows cache directories and built `dist` artifacts under package roots.

Why it matters: Even if ignored by git, their presence makes repo scanning noisy and increases the chance of stale artifacts being mistaken for source evidence.

Root cause or likely root cause: Local validation artifacts kept in the workspace.

Impact on MVP readiness: Not functional blocker.

Impact on developer experience, if applicable: Search results and audit surface are polluted.

Impact on security or reliability, if applicable: Stale build artifacts can be accidentally uploaded outside the intended release path.

Recommended remediation: Clean generated artifacts before handoff and ensure `.gitignore`/CI prevents artifact commits.

Suggested validation or test: Add a cleanliness check in release CI for cache/build artifacts.

Should affect scoring: Yes, lightly.

### SDK-AUDIT-021

Title: Product-platform mypy configuration weakens type assurance for SDK-adjacent code.

Category: Testing

Severity: Low

Confidence: High

File path or area: `packages/product-platform/pyproject.toml:99-104`

Evidence: Product-platform mypy sets `ignore_missing_imports = true` and `follow_imports = "skip"`.

Why it matters: Type validation around SDK compatibility shims and gateway runtime can miss dependency/API drift.

Root cause or likely root cause: Large application surface with external dependencies.

Impact on MVP readiness: Acceptable, but reduces proof.

Impact on developer experience, if applicable: Type errors may surface only at runtime.

Impact on security or reliability, if applicable: Runtime path bugs can hide behind skipped imports.

Recommended remediation: Keep strict mypy for standalone SDK and add targeted stricter config for product-platform gateway modules.

Suggested validation or test: Run mypy with stricter import following for `product_platform.tool_gateway` in CI.

Should affect scoring: Yes, lightly.

### SDK-AUDIT-022

Title: Standalone SDK tests are fewer than product-platform compatibility tests.

Category: Testing

Severity: Medium

Confidence: High

File path or area: `packages/ophanix-tool-gateway-sdk/tests`, `packages/product-platform/tests/test_tool_gateway_sdk_phase*.py`

Evidence: Standalone SDK test run collected 39 tests; product-platform SDK-related run collected 103 tests, many targeting compatibility copy and live contract behavior.

Why it matters: The package that external users install has a thinner self-contained test suite than the monorepo integration surface.

Root cause or likely root cause: Tests accumulated in product-platform before extraction.

Impact on MVP readiness: Not a blocker because integration tests exist, but standalone package confidence is weaker.

Impact on developer experience, if applicable: SDK contributors may run only package-local tests and miss behavior covered elsewhere.

Impact on security or reliability, if applicable: Release package regressions could pass local SDK tests but fail product integration.

Recommended remediation: Move or duplicate critical SDK behavior tests into the standalone package test suite.

Suggested validation or test: Standalone package tests should cover all public API validation, retry, redaction, cache, async, packaging, and live-contract mocks.

Should affect scoring: Yes.

### SDK-AUDIT-023

Title: Live gateway contract test depends on local wheel install but not published package install.

Category: Testing

Severity: Low

Confidence: High

File path or area: `packages/product-platform/tests/test_tool_gateway_installed_sdk_contract.py`

Evidence: Tests install/use the standalone root from the local repository path; release script has optional index install verification.

Why it matters: This proves local wheel behavior, not that consumers can install the released package from the intended index.

Root cause or likely root cause: Pre-release local validation.

Impact on MVP readiness: Acceptable for internal MVP.

Impact on developer experience, if applicable: Index packaging defects may be found late.

Impact on security or reliability, if applicable: Wrong package source can undermine provenance.

Recommended remediation: Add post-publish smoke against the actual index package.

Suggested validation or test: Fresh venv, `pip install ophanix-tool-gateway-sdk==<version>`, run live contract smoke.

Should affect scoring: Yes, lightly.

### SDK-AUDIT-024

Title: Response redaction is best-effort and explicitly not a substitute for safe logging.

Category: Security

Severity: Medium

Confidence: High

File path or area: `packages/ophanix-tool-gateway-sdk/SECURITY.md:50-56`, `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py:142-188`

Evidence: Security docs state diagnostic redaction is best-effort. Code uses key-name and regex heuristics.

Why it matters: Consumers can overestimate redaction coverage, especially for domain-specific PII or secrets in arbitrary strings.

Root cause or likely root cause: Generic SDK cannot know every sensitive field.

Impact on MVP readiness: Acceptable with explicit warning for controlled pilots.

Impact on developer experience, if applicable: Requires consumers to design logging carefully.

Impact on security or reliability, if applicable: Residual data exposure risk.

Recommended remediation: Provide structured logging guidance and optional custom redactor hook.

Suggested validation or test: Add tests for representative domain-sensitive fields and custom redactor behavior.

Should affect scoring: Yes.

### SDK-AUDIT-025

Title: Token provider has no first-class rotation or refresh abstraction.

Category: Public API

Severity: Low

Confidence: High

File path or area: `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py:195-268`, `packages/ophanix-tool-gateway-sdk/README.md:303-314`

Evidence: Public providers are static token and environment token; README shows a custom cached provider example.

Why it matters: Early adopters must implement refresh/rotation patterns themselves.

Root cause or likely root cause: SDK does not mint tokens and keeps auth provider minimal.

Impact on MVP readiness: Acceptable.

Impact on developer experience, if applicable: Additional source-level integration work.

Impact on security or reliability, if applicable: Stale tokens can cause avoidable authentication failures.

Recommended remediation: Add documented provider patterns for secret managers and rotating credentials.

Suggested validation or test: Example provider tests for token refresh on 401 or expiry hints.

Should affect scoring: Yes, lightly.

### SDK-AUDIT-026

Title: Base URL allows explicit non-local insecure HTTP opt-in.

Category: Security

Severity: Medium

Confidence: High

File path or area: `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py:1983-2004`

Evidence: Non-local `http://` is rejected unless `allow_insecure_http=True`.

Why it matters: This is a necessary escape hatch for internal networks, but it can expose bearer tokens if used outside a protected channel.

Root cause or likely root cause: Support for internal/dev deployments without TLS.

Impact on MVP readiness: Acceptable temporary MVP risk if docs are followed.

Impact on developer experience, if applicable: Clear opt-in.

Impact on security or reliability, if applicable: High-risk if copied to external environments.

Recommended remediation: Emit a warning when enabled and document environment-specific guardrails.

Suggested validation or test: Test warning/log emission for non-local insecure HTTP.

Should affect scoring: Yes.

### SDK-AUDIT-027

Title: Retry-After support is capped, but there is no total retry budget cap across calls.

Category: Reliability

Severity: Low

Confidence: Medium

File path or area: `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py:1763-1801`

Evidence: Per-sleep caps exist for discovery and invocation retries; total application-level retry budget is left to callers.

Why it matters: Many workers can still create aggregate retry pressure under outages.

Root cause or likely root cause: SDK-level per-call resilience, not fleet-level rate control.

Impact on MVP readiness: Acceptable for controlled pilots.

Impact on developer experience, if applicable: Operators must configure worker-level concurrency and backpressure.

Impact on security or reliability, if applicable: Thundering herd risk under moderate usage.

Recommended remediation: Document concurrency/backpressure patterns and expose optional retry budget/circuit hook.

Suggested validation or test: Simulate many SDK clients receiving 429/503 and verify bounded aggregate behavior in sample worker.

Should affect scoring: Yes, lightly.

### SDK-AUDIT-028

Title: Compatibility version comparison is simplistic.

Category: Runtime behavior

Severity: Low

Confidence: High

File path or area: `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py:2181-2198`

Evidence: `_version_parts()` extracts leading numeric dot-separated parts via regex rather than using PEP 440 parsing.

Why it matters: Pre-releases, local versions, and nonstandard version strings may compare incorrectly.

Root cause or likely root cause: Avoiding a packaging dependency.

Impact on MVP readiness: Acceptable if versions are simple.

Impact on developer experience, if applicable: Confusing compatibility failures for pre-release builds.

Impact on security or reliability, if applicable: Could allow or reject the wrong SDK version in edge cases.

Recommended remediation: Use `packaging.version.Version` or constrain gateway `min_sdk_version` format.

Suggested validation or test: Add version comparison tests for `0.1.0rc1`, `0.1.0+local`, and malformed strings.

Should affect scoring: Yes, lightly.

### SDK-AUDIT-029

Title: Successful response validation does not validate the shape of `result`.

Category: Runtime behavior

Severity: Low

Confidence: High

File path or area: `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py:2115-2134`

Evidence: `_tool_call_result()` validates required envelope strings and optional decision mapping, but `result` is accepted as any value.

Why it matters: The SDK cannot guarantee schema correctness to consumers; they must validate tool-specific output themselves.

Root cause or likely root cause: Tool-specific result schemas are dynamic.

Impact on MVP readiness: Acceptable if documented, but not fully type-safe.

Impact on developer experience, if applicable: Consumers may assume typed result safety that is not provided.

Impact on security or reliability, if applicable: Malformed upstream output can propagate.

Recommended remediation: Expose optional output-schema validation on the SDK using discovered tool definitions.

Suggested validation or test: Add an SDK helper test that validates result body against `output_schema_json`.

Should affect scoring: Yes, lightly.

### SDK-AUDIT-030

Title: Server idempotency response persistence failure leaves outcome reconciliation to humans.

Category: Reliability

Severity: Medium

Confidence: High

File path or area: `packages/product-platform/src/product_platform/api/app.py:3714-3773`

Evidence: If replay response persistence fails after execution, the server returns `idempotency_persistence_failed` and says the outcome is unknown.

Why it matters: This is the correct fail-safe behavior, but it means MVP adopters still need operational reconciliation paths.

Root cause or likely root cause: Idempotency storage is separate from upstream execution and cannot be atomic across arbitrary upstreams.

Impact on MVP readiness: Acceptable for internal pilots with runbooks; risky for external self-serve use.

Impact on developer experience, if applicable: Requires source-level or operational understanding to recover.

Impact on security or reliability, if applicable: Duplicate or lost side effects can occur if callers choose the wrong recovery action.

Recommended remediation: Provide a reconciliation endpoint/runbook keyed by request ID/correlation ID and tool-specific operation identifiers.

Suggested validation or test: Fault-inject idempotency persistence failure and verify documented recovery steps.

Should affect scoring: Yes.

### SDK-AUDIT-031

Title: Denied calls do not store idempotency replay records.

Category: Reliability

Severity: Low

Confidence: High

File path or area: `packages/product-platform/src/product_platform/api/app.py:3497-3537`, `packages/product-platform/src/product_platform/api/app.py:3575-3667`

Evidence: Policy denial returns before `begin_invocation()` is called.

Why it matters: Repeating a denied request with the same idempotency key will re-evaluate policy rather than replay the first denial.

Root cause or likely root cause: Idempotency is applied after policy decision and schema validation.

Impact on MVP readiness: Usually acceptable; denial has no upstream side effect.

Impact on developer experience, if applicable: Idempotency behavior is not uniform for all outcomes.

Impact on security or reliability, if applicable: Policy changes can make a repeated request with the same key behave differently.

Recommended remediation: Document that idempotency applies to allowed execution attempts, or record denials as replayable outcomes.

Suggested validation or test: Test repeated denied invocation with same key before/after permission change.

Should affect scoring: Yes, lightly.

### SDK-AUDIT-032

Title: Schema validation failures do not store idempotency replay records.

Category: Reliability

Severity: Low

Confidence: High

File path or area: `packages/product-platform/src/product_platform/api/app.py:3546-3575`, `packages/product-platform/src/product_platform/api/app.py:3575-3667`

Evidence: Input schema validation failure returns before idempotency begin.

Why it matters: The same key can be reused after fixing payload shape without an idempotency conflict. That may be desirable, but it is not made explicit.

Root cause or likely root cause: Idempotency protects upstream execution, not pre-execution validation.

Impact on MVP readiness: Acceptable.

Impact on developer experience, if applicable: Inconsistent mental model.

Impact on security or reliability, if applicable: Low.

Recommended remediation: Document exact idempotency lifecycle boundaries.

Suggested validation or test: Add server and SDK docs/tests for validation failure plus key reuse.

Should affect scoring: Yes, lightly.

### SDK-AUDIT-033

Title: Standalone package does not include repository-level CI workflow evidence in its own directory.

Category: Testing

Severity: Low

Confidence: Medium

File path or area: `packages/ophanix-tool-gateway-sdk`

Evidence: Package contains tests and release script, but no package-local workflow file. CI may exist elsewhere, but package-local evidence is absent from the reviewed surface.

Why it matters: External contributors cannot easily see what is required before release.

Root cause or likely root cause: Monorepo-level workflows.

Impact on MVP readiness: Low.

Impact on developer experience, if applicable: Harder to self-validate.

Impact on security or reliability, if applicable: Release gates may be invisible.

Recommended remediation: Add a package README section or workflow reference listing exact CI gates.

Suggested validation or test: CI badge or documented job names that include tests, mypy, build, twine, pip-audit, and installed-wheel smoke.

Should affect scoring: Yes, lightly.

### SDK-AUDIT-034

Title: Docs overstate publish status without repository evidence of release provenance.

Category: Documentation

Severity: Low

Confidence: Medium

File path or area: `packages/ophanix-tool-gateway-sdk/README.md:5-14`

Evidence: README says the package is published on PyPI, while this audit only proved local build and release validation.

Why it matters: Published status alone does not prove current source equals published package.

Root cause or likely root cause: Documentation written for expected release path.

Impact on MVP readiness: Low unless package is not actually published or is stale.

Impact on developer experience, if applicable: Users may install a version that does not match docs/source.

Impact on security or reliability, if applicable: Provenance ambiguity.

Recommended remediation: Link to release checksums, package version, and source tag.

Suggested validation or test: Add release manifest URL and verify-index-install output to release notes.

Should affect scoring: Yes, lightly.

### SDK-AUDIT-035

Title: Gateway capabilities response does not appear to advertise operational limits or retry policy.

Category: Public API

Severity: Medium

Confidence: Medium

File path or area: `packages/product-platform/src/product_platform/api/app.py:3444-3455`, `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py:795-818`

Evidence: Capabilities endpoint returns `GatewayCapabilitiesResponse()` with default contract fields; SDK uses hard-coded local defaults for caps and retry behavior.

Why it matters: SDK consumers cannot discover actual server limits, retention windows, max body size, max response size, or retry/idempotency policy.

Root cause or likely root cause: Minimal compatibility endpoint.

Impact on MVP readiness: Acceptable for controlled pilots with matching defaults, but fragile for varied deployments.

Impact on developer experience, if applicable: Operators must read docs or config rather than code-discover limits.

Impact on security or reliability, if applicable: Clients may exceed server limits or under-provision retry behavior.

Recommended remediation: Extend capabilities response with limits, feature flags, and idempotency TTL/retention.

Suggested validation or test: SDK compatibility test asserts advertised limits are consumed or surfaced.

Should affect scoring: Yes.

## 4. Issues Grouped By Category

Public API:

- SDK-AUDIT-007, SDK-AUDIT-008, SDK-AUDIT-009, SDK-AUDIT-010, SDK-AUDIT-013, SDK-AUDIT-025, SDK-AUDIT-035

Runtime behavior:

- SDK-AUDIT-010, SDK-AUDIT-011, SDK-AUDIT-028, SDK-AUDIT-029

Security:

- SDK-AUDIT-004, SDK-AUDIT-012, SDK-AUDIT-024, SDK-AUDIT-026

Reliability:

- SDK-AUDIT-014, SDK-AUDIT-015, SDK-AUDIT-016, SDK-AUDIT-027, SDK-AUDIT-030, SDK-AUDIT-031, SDK-AUDIT-032, SDK-AUDIT-035

Developer experience:

- SDK-AUDIT-009, SDK-AUDIT-018, SDK-AUDIT-019, SDK-AUDIT-025, SDK-AUDIT-033, SDK-AUDIT-034

Testing:

- SDK-AUDIT-021, SDK-AUDIT-022, SDK-AUDIT-023, SDK-AUDIT-033

Packaging and release:

- SDK-AUDIT-001, SDK-AUDIT-002, SDK-AUDIT-003, SDK-AUDIT-005, SDK-AUDIT-006, SDK-AUDIT-020, SDK-AUDIT-034

Documentation:

- SDK-AUDIT-018, SDK-AUDIT-019, SDK-AUDIT-031, SDK-AUDIT-032, SDK-AUDIT-034

Cross-file consistency:

- SDK-AUDIT-001, SDK-AUDIT-002, SDK-AUDIT-017, SDK-AUDIT-019, SDK-AUDIT-035

## 5. Critical And High-Severity Blockers

No Critical or High issues were proven in the current SDK surface.

That absence does not mean production readiness. It means the reviewed current state has no directly proven unsafe secret exposure, unusable package build failure, missing authentication enforcement, or fundamental SDK non-functionality.

## 6. Medium-Severity MVP Risks

- SDK-AUDIT-001: unshipped compatibility source copy creates source/install divergence risk.
- SDK-AUDIT-002: local monorepo builds can resolve SDK from external index.
- SDK-AUDIT-004: dependency audit optional in release validation.
- SDK-AUDIT-005: strict git/tag provenance optional in release validation.
- SDK-AUDIT-007: pre-1.0 API instability.
- SDK-AUDIT-010: compatibility check not enforced before calls.
- SDK-AUDIT-012: successful raw responses can contain sensitive payloads.
- SDK-AUDIT-014: discovery cache lacks invalidation.
- SDK-AUDIT-016: retry policy is not tool-contract aware.
- SDK-AUDIT-018: direct HTTP examples require consumers to recreate safeguards.
- SDK-AUDIT-022: standalone SDK tests are thinner than product-platform SDK tests.
- SDK-AUDIT-024: redaction is best-effort.
- SDK-AUDIT-026: non-local insecure HTTP opt-in remains available.
- SDK-AUDIT-030: idempotency persistence failures require operational reconciliation.
- SDK-AUDIT-035: capabilities endpoint does not advertise operational limits.

## 7. Low-Severity And Nit-Level Issues

- SDK-AUDIT-003, SDK-AUDIT-006, SDK-AUDIT-008, SDK-AUDIT-009, SDK-AUDIT-011, SDK-AUDIT-013, SDK-AUDIT-015, SDK-AUDIT-017, SDK-AUDIT-019, SDK-AUDIT-020, SDK-AUDIT-021, SDK-AUDIT-023, SDK-AUDIT-025, SDK-AUDIT-027, SDK-AUDIT-028, SDK-AUDIT-029, SDK-AUDIT-031, SDK-AUDIT-032, SDK-AUDIT-033, SDK-AUDIT-034

## 8. Scoring Matrix

Implementation quality: 6/10

Exact reasons:

- Positive: sync/async SDKs exist; strict input validation exists; response-size caps exist for built-in clients; idempotency-gated invocation retries exist; discovery pagination and retry exist; mypy passed; build passed; standalone and product SDK tests passed.
- Negative: source/package boundary is still transitional; capabilities do not advertise limits; standalone package tests are not as broad as product-platform tests; compatibility check is advisory; release provenance enforcement is optional.

Score cap caused by unresolved issues: capped at 6 by SDK-AUDIT-001, SDK-AUDIT-002, SDK-AUDIT-010, SDK-AUDIT-022, SDK-AUDIT-035.

What must be fixed to reach next score: resolve package/source divergence, make local deployment install exact local SDK, and move critical product SDK tests into the standalone package.

What must be fixed to reach 7: add enforced or opt-in compatibility guard, capabilities limit advertisement, and release CI evidence for strict build/test gates.

What must be fixed to reach 8: add stronger contract-version testing across gateway versions, tool-aware retry metadata, and provenance-pinned release artifacts.

Ease of use: 6/10

Exact reasons:

- Positive: README, API reference, migration notes, examples, typed errors, environment token provider, context managers, and clear sync/async examples exist.
- Negative: direct HTTP examples create an attractive unsafe path; cloud docs use `python`; config naming is partially confusing; users must manually understand compatibility checks, token rotation, idempotency boundaries, and raw-response logging.

Score cap caused by unresolved issues: capped at 6 by SDK-AUDIT-008, SDK-AUDIT-009, SDK-AUDIT-018, SDK-AUDIT-019, SDK-AUDIT-025, SDK-AUDIT-031, SDK-AUDIT-032.

What must be fixed to reach next score: standardize commands, reduce confusing public options, strengthen quickstart around compatibility and idempotency boundaries.

What must be fixed to reach 7: provide an end-to-end onboarding path that issues a credential, invokes a tool, handles denial, handles retry, and shows safe logging without source-level debugging.

What must be fixed to reach 8: provide generated/direct clients or safe helpers for non-Python callers and publish operational runbooks for common failures.

Security and reliability: 6/10

Exact reasons:

- Positive: HTTPS default, token shape validation, no proxy trust by default, error diagnostic redaction, server auth, permission-filtered discovery, payload caps, response caps, idempotency storage, retry-after handling, rate/circuit controls in product-platform docs/code.
- Negative: dependency audit/provenance gates are optional; redaction and raw success data remain risky; insecure HTTP opt-in is available; discovery cache invalidation is manual; idempotency persistence failure requires reconciliation; capabilities do not surface runtime limits.

Score cap caused by unresolved issues: capped at 6 by SDK-AUDIT-004, SDK-AUDIT-005, SDK-AUDIT-012, SDK-AUDIT-014, SDK-AUDIT-016, SDK-AUDIT-024, SDK-AUDIT-026, SDK-AUDIT-030.

What must be fixed to reach next score: enforce release security gates, add stronger safe logging defaults, and document/test operational reconciliation.

What must be fixed to reach 7: capabilities must advertise limits and idempotency settings; release CI must require dependency audit and strict provenance; cache/revocation behavior must be clearer.

What must be fixed to reach 8: add tool-aware retry semantics, structured redaction hooks, fleet-level retry/backpressure guidance, and post-publish verification.

## 9. Score Cap Explanation

Implementation cannot exceed 6 because package/release boundaries are not fully coherent and the standalone package does not independently prove all behavior that product-platform tests prove.

Ease of use cannot exceed 6 because a competent engineer can adopt the SDK in a few hours, but only if they read multiple docs and avoid the direct HTTP trap. Hidden concepts remain: token issuance, compatibility checks, idempotency boundaries, raw logging risk, and runtime limit alignment.

Security and reliability cannot exceed 6 because the core safeguards are real, but release security gates, raw-success logging, manual cache invalidation, insecure opt-in, and idempotency reconciliation are not yet sufficiently hard to support unsupervised external use.

## 10. Required Fixes To Reach MVP Readiness

The repo already reaches controlled MVP readiness if the adopting team is internal or closely supported.

Minimum required before broader MVP rollout:

1. Ensure Docker/CI installs the exact local standalone SDK artifact or a hash-pinned released SDK built from the same source.
2. Enforce release validation with tests, mypy, build, twine check, dependency audit, strict git/tag state, and installed-wheel smoke.
3. Move critical SDK tests into the standalone package.
4. Document idempotency lifecycle boundaries and reconciliation steps.
5. Add a clear warning or safer defaults for `ToolCallResult.raw`.
6. Standardize `python3` versus `python` commands or prove the images provide `python`.

## 11. Required Fixes To Reach 7 Out Of 10

1. Resolve source/package duplication and provenance ambiguity.
2. Add optional enforced compatibility checking or a lazy compatibility guard.
3. Extend capabilities endpoint with runtime limits, feature flags, and idempotency TTL/retention.
4. Add standalone SDK tests for all validation, retry, redaction, cache, async, package, and live-contract behavior.
5. Add release CI evidence that strict validation is mandatory.
6. Make direct HTTP examples visibly secondary to SDK usage and add safer generated/non-Python client guidance.

## 12. Required Fixes To Reach 8 Out Of 10

1. Add tool-contract-aware retry/idempotency metadata and SDK enforcement.
2. Add server-driven cache invalidation or discovery ETags/versioning.
3. Provide first-class token rotation/secret-manager provider examples with tests.
4. Add structured custom redaction hooks and safer raw-response defaults.
5. Add post-publish index install validation and release provenance artifacts.
6. Add cross-version gateway/SDK contract test matrix.
7. Add operational load/backpressure guidance and tests for retry behavior under throttling.

## 13. Recommended Remediation Order

1. Fix packaging/install determinism: SDK local wheel in Docker/CI, remove or formalize duplicate source, provenance-pinned releases.
2. Strengthen release gates: mandatory dependency audit, strict git/tag, installed-wheel smoke, post-publish install verification.
3. Improve standalone test coverage by moving product SDK tests into standalone package.
4. Extend `/api/v1/gateway/capabilities` with limits and feature flags.
5. Add compatibility guard option in SDK.
6. Clarify and test idempotency boundaries and reconciliation.
7. Reduce raw-response logging risk and add custom redaction hooks.
8. Clean docs and examples: `python3`, direct HTTP warnings, token rotation provider patterns.
9. Add cache invalidation/versioning.
10. Add tool-aware retry metadata.

## 14. Validation Plan

Package validation:

- Build standalone SDK wheel and sdist.
- Install wheel into a fresh venv with no repo `PYTHONPATH`.
- Run standalone tests against installed wheel.
- Run `twine check`.
- Run `pip-audit` on runtime dependencies.
- Verify `py.typed`, README, API reference, migration notes, changelog, security policy, examples, and license are in the sdist.

Product/platform validation:

- Build product-platform wheel in a clean environment.
- Install product-platform and local SDK wheel together.
- Verify `product_platform.tool_gateway` compatibility exports work without source-tree `src/ophanix_tool_gateway`.
- Build Docker images with local SDK artifact or hash-pinned SDK.
- Run live gateway SDK contract test against Dockerized API.

Runtime validation:

- Auth failure, denial, schema validation, upstream success, upstream failure, non-JSON upstream, response too large, timeout, 429, 503, retry-after, idempotency replay, idempotency conflict, in-progress, stale, and persistence failure.
- Cache enabled plus permission revocation.
- Cursor pagination with owner-team filter and catalog churn.

Security validation:

- Token never appears in repr, event hooks, error messages, response diagnostics, runtime audit records, or logs.
- Raw successful response logging risk is documented or disabled by default.
- Non-local HTTP opt-in produces a warning.
- Dependency audit and provenance checks are mandatory before publish.

DX validation:

- Follow README quickstart from a fresh venv.
- Follow local demo from a clean checkout.
- Follow cloud pilot commands in the target container image.
- Confirm all docs use commands available in the image or host.

## 15. Final Strict MVP Assessment

This is a functional, credible MVP for controlled adoption. It is not a paper design: the SDK builds, types, tests, and can call the live product-platform gateway contract. The core runtime posture is substantially safer than a thin HTTP wrapper.

It is still too fragile for broad external adoption. The main blockers are not one catastrophic code defect; they are accumulated release, packaging, provenance, documentation, and operational edge risks. Before wider rollout, make the artifact path deterministic, enforce strict release gates, move critical tests into the standalone package, surface server limits through capabilities, and reduce the chances that adopters misuse raw responses, direct HTTP examples, or idempotency recovery.

## 16. Iterative Remediation Pass 1

Date: 2026-05-12

Scope: SDK public API, runtime compatibility behavior, safe diagnostic defaults, capabilities metadata, local Docker install determinism, cloud command documentation, standalone/product SDK parity, tests, builds, mypy, and release validation.

### Fixes Implemented

SDK-AUDIT-002: Product-platform installation depends on an external SDK package even for local monorepo builds.

- Root cause: Cloud and demo Dockerfiles copied and installed `product-platform` without copying/installing the local standalone SDK package first. The product package declares `ophanix-tool-gateway-sdk>=0.1.0,<1.0`, so container builds could resolve a package-index artifact that did not match the checkout.
- Fix: Updated `packages/product-platform/deploy/cloud/Dockerfile.api`, `packages/product-platform/deploy/cloud/Dockerfile.worker`, and `packages/product-platform/Dockerfile.demo` to copy `packages/ophanix-tool-gateway-sdk` and install it before `packages/product-platform`.
- Impact: Local container builds now evaluate the SDK source in the checkout instead of silently depending on an external index copy.
- Validation: Added `test_cloud_dockerfiles_install_local_tool_gateway_sdk_before_product_platform` in `packages/product-platform/tests/test_tool_gateway_sdk_package.py`; full Tool Gateway suite passed.
- Status: Resolved for current Docker build paths.

SDK-AUDIT-008: `allow_buffered_custom_http_client` is exposed but intentionally ignored.

- Root cause: The compatibility option remained in the public constructor/config but did not communicate that buffered clients are no longer accepted.
- Fix: The option now emits a `DeprecationWarning` when enabled, while validation continues to reject custom clients without `stream()` so response-size caps cannot be bypassed.
- Impact: Existing callers get an actionable migration signal instead of a silent no-op.
- Validation: Added standalone SDK test proving the warning and stream requirement.
- Status: Resolved as a compatibility/deprecation issue; the field still exists for `0.1.x` compatibility.

SDK-AUDIT-009: `ToolGatewayClientConfig` cannot carry `base_url` or `token_provider`.

- Root cause: The name read like a complete client configuration even though endpoint and credentials are intentionally runtime inputs.
- Fix: Added `ToolGatewayClientOptions = ToolGatewayClientConfig` alias and exported it from standalone and product compatibility namespaces.
- Impact: New consumers can use the clearer "options" name without breaking existing imports.
- Validation: Added standalone and product export assertions.
- Status: Partially resolved. The original class name remains for compatibility, so some naming ambiguity remains until a future breaking release.

SDK-AUDIT-010: Compatibility check is advisory and not enforced before calls.

- Root cause: `check_compatibility()` was available but callers had to remember to invoke it and handle incompatibility manually.
- Fix: Added `require_compatible_gateway` option to sync and async clients/config. When enabled, the SDK probes `/api/v1/gateway/capabilities` once before `call_tool`, `list_tools`, `list_all_tools`, or `get_tool`, caches a successful check, and fails closed with `ToolGatewayError` on contract or minimum-version mismatch.
- Impact: Strict adopters can prevent accidental calls against incompatible gateways without adding custom wrapper code.
- Validation: Added tests for one-time compatibility probing and fail-before-invocation behavior.
- Status: Resolved as an opt-in MVP guard. Not made default to avoid breaking existing `0.1.x` callers.

SDK-AUDIT-012: SDK returns full raw successful response snapshots that may include sensitive tool payloads.

- Root cause: `ToolCallResult.raw` stored the complete success body, including arbitrary upstream `result` payloads.
- Fix: Added `include_raw_response=False` default. Successful `ToolCallResult.raw` now retains only diagnostic metadata (`request_id`, `correlation_id`, `tool_name`, `reason_code`, `decision`) unless callers explicitly opt in.
- Impact: Safer default for logs, telemetry, and object retention; callers still have an explicit escape hatch when they control data retention.
- Validation: Added tests proving `result` is omitted by default and included only when `include_raw_response=True`.
- Status: Resolved for successful SDK responses.

SDK-AUDIT-013: Event hook schema is untyped at runtime and not versioned.

- Root cause: Hook events had names and fields but no runtime schema identifier.
- Fix: Added `TELEMETRY_SCHEMA_VERSION = "tool-gateway-sdk.telemetry.v1"` and inject `schema_version` into emitted events.
- Impact: Downstream telemetry consumers can version parsing and dashboards safely.
- Validation: Added event hook assertion for schema version.
- Status: Resolved at SDK runtime level.

SDK-AUDIT-019: Cloud deployment docs use `python`, while local validation environment only provides `python3`.

- Root cause: Cloud docs mixed generic `python` commands with repo docs that otherwise use `python3`.
- Fix: Updated cloud pilot, backup/restore, and observability command references to `python3`.
- Impact: Fewer setup failures in environments where only `python3` is available.
- Validation: Documentation diff reviewed; build/test validation unaffected.
- Status: Resolved for reviewed cloud docs. CI workflows still use `python` inside setup-python environments where that executable is provided.

SDK-AUDIT-028: Compatibility version comparison is simplistic.

- Root cause: Version comparison parsed only leading numeric components, which mishandled valid PEP 440 versions.
- Fix: Switched compatibility comparison to `packaging.version.Version` and added `packaging>=23,<26` as a runtime dependency for the standalone SDK and product-platform source-tree compatibility path.
- Impact: Gateway `min_sdk_version` checks now follow Python packaging semantics for pre-releases, post-releases, and local versions.
- Validation: Standalone mypy, SDK tests, build, and release validator passed with the new dependency.
- Status: Resolved.

SDK-AUDIT-035: Gateway capabilities response does not appear to advertise operational limits or retry policy.

- Root cause: `/api/v1/gateway/capabilities` returned only contract version, minimum SDK version, and package name.
- Fix: Extended `GatewayCapabilitiesResponse` with payload/response caps, discovery page size, pagination modes, idempotency support and TTL/retention, retryable status code lists, rate-limit settings, and circuit-breaker settings. The endpoint now fills settings-backed values from `resolved_settings`.
- Impact: SDKs and operators can discover the gateway's core operational envelope without source-level inspection.
- Validation: Product remediation test asserts the new fields; SDK compatibility test parses surfaced limits and feature metadata.
- Status: Resolved for current MVP metadata. Future work can add per-tool retry/idempotency metadata.

### Partially Mitigated Issues

SDK-AUDIT-001: Product-platform wheel excludes the compatibility SDK source while retaining it in the source tree.

- Remediation this pass: Synced the product-platform source-tree copy with the standalone SDK and kept the byte-for-byte parity test.
- Remaining concern: The repository still has a transitional source-tree copy that is intentionally excluded from the product wheel. This is coherent if treated strictly as a local compatibility copy, but it remains a maintenance footgun.
- Status: Partially mitigated, not fully resolved.

SDK-AUDIT-004: Release validator makes dependency audit optional.

- Remediation this pass: Ran SDK and product release validators with `--require-dependency-audit`; current CI/publish workflows already invoke required dependency-audit mode for SDK/product release validation paths.
- Remaining concern: The validator CLI still allows non-audited local runs by default, and `pip-audit` skipped the local unpublished package names while auditing resolvable dependencies.
- Status: Partially resolved operationally; CLI default remains permissive.

SDK-AUDIT-005: Release validator does not require strict git/tag provenance by default.

- Remediation this pass: Confirmed release workflow uses strict git/tag validation for release events.
- Remaining concern: Local validation still defaults to non-strict mode; this dirty remediation worktree could not pass strict-git mode by design.
- Status: Partially resolved in release workflow, not defaulted in CLI.

SDK-AUDIT-018: Direct HTTP examples require callers to recreate critical SDK safeguards.

- Remediation this pass: Product and SDK docs now more clearly identify the SDK as the safer production path, and SDK defaults reduce one major raw-response logging risk.
- Remaining concern: Direct HTTP examples remain available and still rely on consumers to reproduce SDK-level behavior in non-Python clients.
- Status: Partially mitigated, not resolved.

SDK-AUDIT-022: Standalone SDK tests are fewer than product-platform compatibility tests.

- Remediation this pass: Standalone SDK tests increased from 39 to 44 and now cover compatibility enforcement, raw response privacy, event schema versioning, insecure HTTP warning, and deprecated buffered-client option behavior.
- Remaining concern: Standalone tests still do not fully subsume the 325 product Tool Gateway tests or all installed-wheel live gateway behavior.
- Status: Partially mitigated.

SDK-AUDIT-026: Base URL allows explicit non-local insecure HTTP opt-in.

- Remediation this pass: Non-local `http://` with `allow_insecure_http=True` now emits a `RuntimeWarning`.
- Remaining concern: The opt-in remains available for test networks and therefore remains unsafe if misused.
- Status: Partially mitigated, intentionally not removed in `0.1.x`.

### Left Unresolved

- SDK-AUDIT-003: Version/provenance ambiguity remains because both packages still declare `0.1.0`; release process evidence, not code edits, must ultimately disambiguate artifacts.
- SDK-AUDIT-006: Package-index install verification remains optional and was not run because this local package version is not guaranteed to exist on the index during remediation.
- SDK-AUDIT-007: Pre-1.0 API instability remains by definition.
- SDK-AUDIT-011: Non-JSON error response handling remains an acceptable but imperfect MVP behavior.
- SDK-AUDIT-014: Discovery cache still has no server-driven invalidation, ETag, or version token.
- SDK-AUDIT-015: Offset fallback can still miss catalog churn on older gateways.
- SDK-AUDIT-016: Retry policy is still not tool-contract aware.
- SDK-AUDIT-017: Runtime cap alignment is improved through capabilities, but not automatically enforced from server-advertised limits in client config.
- SDK-AUDIT-020: Workspace build artifacts/caches still exist after validation runs and should be cleaned or ignored by repository hygiene policy.
- SDK-AUDIT-021: Product-platform mypy still uses weaker settings for SDK-adjacent source than the standalone SDK.
- SDK-AUDIT-023: Live contract tests still validate local wheel behavior, not post-publish package-index installation.
- SDK-AUDIT-024: Redaction remains best-effort and not a substitute for safe logging.
- SDK-AUDIT-025: No first-class token rotation/refresh provider abstraction was added.
- SDK-AUDIT-027: Retry settings still do not include a cross-call total retry budget.
- SDK-AUDIT-029: The SDK still does not validate arbitrary `result` payload shape beyond preserving it as caller-owned data.
- SDK-AUDIT-030: Idempotency persistence failure still requires operator reconciliation.
- SDK-AUDIT-031: Denied calls still do not store idempotency replay records.
- SDK-AUDIT-032: Schema validation failures still do not store idempotency replay records.
- SDK-AUDIT-033: Standalone package still relies on repository-level workflow evidence rather than a package-local CI declaration.
- SDK-AUDIT-034: Release provenance remains process-dependent until artifacts are actually published with provenance and post-publish verification.

### Validation Run

- `python3 -m pytest packages/ophanix-tool-gateway-sdk/tests -q`: passed, 44 tests.
- `python3 -m pytest packages/product-platform/tests/test_tool_gateway_sdk_package.py packages/product-platform/tests/test_tool_gateway_sdk_remediation.py -q`: passed, 12 tests.
- `python3 -m mypy src/ophanix_tool_gateway` from `packages/ophanix-tool-gateway-sdk`: passed.
- `python3 -m mypy src/product_platform/tool_gateway src/ophanix_tool_gateway` from `packages/product-platform`: passed.
- `ruff check src tests scripts --select E,F,W --ignore E501` from `packages/ophanix-tool-gateway-sdk`: passed.
- `ruff check src tests --select E,F,W --ignore E501` from `packages/product-platform`: passed.
- `python3 -m pytest $(rg --files packages/product-platform/tests | rg 'test_tool_gateway.*\\.py') -q`: passed, 325 tests, 5 warnings. Warnings were deprecation/runtime warnings from dependency stack and intentional non-local insecure HTTP opt-in tests.
- `python3 -m build` from `packages/ophanix-tool-gateway-sdk`: passed.
- `python3 -m build` from `packages/product-platform`: passed.
- `python3 scripts/validate_release.py --out-dir /tmp/ophanix-sdk-remediation-release --require-dependency-audit` from `packages/ophanix-tool-gateway-sdk`: passed; dependency audit reported the local unpublished package name as skipped/not found on PyPI.
- `python3 scripts/validate_release.py --out-dir /tmp/ophanix-product-remediation-release-2 --require-dependency-audit` from `packages/product-platform`: passed; dependency audit reported the local unpublished package name as skipped/not found on PyPI.

### Post-Pass Score Reassessment

Implementation quality: 7/10.

- Reason: The SDK now has safer raw-response defaults, opt-in compatibility enforcement, PEP 440 version checks, richer capabilities metadata, deterministic local Docker SDK installation, expanded standalone tests, passing mypy, passing builds, passing release validators, and a broad 325-test Tool Gateway regression pass.
- Score cap: Capped at 7 by unresolved cache invalidation, tool-aware retry metadata, package-index verification, and incomplete standalone parity with product gateway tests.

Ease of use: 7/10.

- Reason: The API now exposes the clearer `ToolGatewayClientOptions` alias, warns on dangerous insecure HTTP and deprecated buffered-client compatibility settings, documents raw-response retention, and standardizes reviewed cloud commands to `python3`.
- Score cap: Capped at 7 by remaining direct-HTTP footguns, no first-class token rotation provider, and process-heavy release/provenance docs.

Security and reliability: 7/10.

- Reason: The biggest proven security issue, successful raw payload retention in `ToolCallResult.raw`, now has a safer default; compatibility can fail closed; gateway limits are discoverable; non-local insecure HTTP opt-in emits a runtime warning; and dependency-audit-required release validation was exercised.
- Score cap: Capped at 7 by best-effort redaction, retained insecure HTTP opt-in, manual cache invalidation, unresolved idempotency reconciliation, and lack of tool-aware retry contracts.

### Next Remediation Order

1. Add server-driven discovery invalidation or cache validators.
2. Add tool-contract metadata for retryability/idempotency and have the SDK honor it.
3. Add first-class token refresh/rotation provider examples with tests.
4. Decide whether the product source-tree compatibility copy should be removed, generated, or formalized as a checked parity artifact.
5. Add post-publish package-index install verification to the release workflow after publish.
6. Add custom redaction hooks or structured payload-classification support.
7. Define operational reconciliation workflow/tests for idempotency persistence failures.
