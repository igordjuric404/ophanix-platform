# Tool Gateway SDK Production Readiness Audit

Date: 2026-05-11

Scope: strict production-readiness audit of the Ophanix Tool Gateway SDK and the
relevant `ophanix-platform` repository surface: SDK API, server gateway runtime,
tests, packaging, release workflow, documentation, examples, CI, and adoption path.

This audit is intentionally adversarial. It records issues found in the current
repository state. It does not implement fixes.

## Executive Summary

Current strict scores:

| Category | Current score | Prior score | Direction |
| --- | ---: | ---: | --- |
| Implementation quality | 6.0 / 10 | 8.1 / 10 | Lower |
| Ease of use | 6.0 / 10 | 8.3 / 10 | Lower |
| Security and reliability | 5.0 / 10 | 8.3 / 10 | Lower |

The SDK implementation has improved substantially compared with the early
review state, and focused local tests pass. That is not enough to call the
current repository production-ready.

The strongest blockers are:

- The standalone SDK package, preferred SDK namespace, new SDK tests, and the
  prior remediation log are untracked in the current worktree.
- The visible CI and publish workflows do not include `product-platform` or
  `ophanix-tool-gateway-sdk`.
- The product-platform source distribution includes a local SQLite database and
  a database backup.
- Failed upstream responses bypass response policy redaction, size, and
  visibility controls.
- Upstream target URLs allow arbitrary `http` and `https` destinations without
  SSRF/private-network controls.
- Upstream `auth_mode` is modeled and accepted but not implemented.
- Gateway invocation validates tool schema and reveals tool existence before
  authorization/policy evaluation.
- Default runtime executor and health checker can create unclosed `httpx.Client`
  instances.
- Tests are broad but still miss several proven negative cases and are not
  enforced by the current CI/release path.

## Prior Review Summary And Challenge

Prior file reviewed:

- `docs/product-platform-worktree/execution-logs/06-tool-gateway-logs/13-sdk-review-remediation.md`

Previously reported issues included:

- SDK discovery used `/api/v1/tools` with gateway bearer token, but that endpoint
  required product-user auth.
- Gateway discovery returned an operator model exposing tenant/creator fields.
- SDK validation was weak for invalid tool names, non-JSON payloads, malformed
  responses, and non-local HTTP defaults.
- `get_tool` searched only the first discovery page.
- Token provider representation and exception bodies could expose sensitive
  material.
- Env token provider, `list_all_tools`, discovery retries, cache invalidation,
  and `py.typed` were missing.
- Strict JSON payload validation, finite number checks, base URL validation,
  retry-after handling, jitter, cache partitioning, structured resource-bound
  credential scopes, async SDK, package buildability, docs, release validation,
  optional mapping validation, `__version__`, and expanded redaction were later
  claimed as remediations.

Fixes claimed:

- Added `/api/v1/gateway/tools`.
- Added gateway-safe discovery response model.
- Added HTTPS-by-default SDK config with explicit insecure opt-in.
- Added stricter payload, header, base URL, timeout, retry, and response
  validation.
- Added env/static token providers and sanitized error diagnostics.
- Added discovery pagination and retries.
- Added opt-in discovery cache partitioned by credential fingerprint.
- Added async SDK client.
- Added standalone `ophanix_tool_gateway` namespace and package metadata.
- Added release validator for wheel/sdist shape.
- Expanded README documentation and examples.

Validation evidence claimed:

- SDK/package/remediation test suites passing.
- Tool Gateway test suites passing.
- Full product-platform test suite passing.
- Compile checks passing.
- Wheel and sdist build checks passing.
- Optional dependency audit passing.

Prior scores assigned:

- Implementation quality: 8.1 / 10
- Ease of use: 8.3 / 10
- Security and reliability: 8.3 / 10

Suspicious or under-evidenced conclusions:

- The prior scores are too optimistic because the visible CI and publish
  workflows do not include the product-platform package or the standalone SDK
  package.
- Prior validation was local and not proven as a release gate.
- The standalone SDK package is untracked and symlinked, so package extraction is
  not proven as committed production state.
- Server-side gateway behavior was underweighted, especially failed-response
  policy bypass, unclosed HTTP clients, upstream SSRF exposure, and
  authorization ordering.
- Redaction was over-credited; a colon-bearing bearer token still partially
  leaks in SDK diagnostic sanitization.
- Release validation was over-credited; it checks expected files but not unwanted
  files, license files, installed-wheel behavior, CI enforcement, or provenance.

Areas not deeply reviewed before:

- CI path filters and package matrices.
- Publish workflow coverage.
- Product-platform sdist contents.
- Upstream forwarding runtime.
- Failed upstream response policy handling.
- Health checker lifecycle.
- SSRF/private-network boundaries.
- Token issuance documentation.
- Package license/security/changelog metadata.
- Source-control state and adoption path.

## Repository Surface Reviewed

Relevant files and directories:

- `packages/product-platform/src/ophanix_tool_gateway/`
- `packages/product-platform/src/product_platform/tool_gateway/sdk.py`
- `packages/product-platform/src/product_platform/tool_gateway/__init__.py`
- `packages/ophanix-tool-gateway-sdk/`
- `packages/product-platform/src/product_platform/api/app.py`
- `packages/product-platform/src/product_platform/tool_gateway/auth.py`
- `packages/product-platform/src/product_platform/tool_gateway/decision.py`
- `packages/product-platform/src/product_platform/tool_gateway/health.py`
- `packages/product-platform/src/product_platform/tool_gateway/invocation.py`
- `packages/product-platform/src/product_platform/tool_gateway/models.py`
- `packages/product-platform/src/product_platform/tool_gateway/repository.py`
- `packages/product-platform/src/product_platform/tool_gateway/response.py`
- `packages/product-platform/src/product_platform/tool_gateway/runtime_audit.py`
- `packages/product-platform/src/product_platform/tool_gateway/schemas.py`
- `packages/product-platform/src/product_platform/db/migrations/0050-0055*`
- `packages/product-platform/tests/test_tool_gateway_*.py`
- `packages/product-platform/examples/tool-gateway-direct-http/`
- `packages/product-platform/README.md`
- `packages/ophanix-tool-gateway-sdk/README.md`
- `packages/product-platform/pyproject.toml`
- `packages/ophanix-tool-gateway-sdk/pyproject.toml`
- `.github/workflows/ci.yml`
- `.github/workflows/publish.yml`
- `.github/workflows/product-platform-images.yml`

Validation run during audit:

- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_sdk*.py' -v`
  - Result: 76 tests passed.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_*.py' -v`
  - Result: 199 tests passed.
- `python3 -m compileall -q packages/product-platform/src/ophanix_tool_gateway packages/product-platform/src/product_platform/tool_gateway packages/ophanix-tool-gateway-sdk/scripts`
  - Result: passed.
- `git diff --check`
  - Result: passed.
- `python scripts/validate_release.py --out-dir /tmp/ophanix-sdk-audit-release-rerun`
  - Result: passed.
- `python scripts/validate_release.py --out-dir /tmp/ophanix-sdk-audit-release-audit-rerun --require-dependency-audit`
  - Result: passed, but `pip-audit` skipped `ophanix-tool-gateway-sdk` because the package was not found on PyPI.
- Product-platform build:
  - Result: built wheel and sdist, but sdist included `ophanix_product.db` and `ophanix_product.db.backup.20260509152042`.

## Exhaustive Issue Register

### SDK-AUDIT-001: Untracked SDK Package And Namespace

- Category: Repository / release readiness
- Severity: Critical
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/`, `packages/product-platform/src/ophanix_tool_gateway/`, SDK tests, prior remediation log
- Evidence: `git status --short` shows `?? packages/ophanix-tool-gateway-sdk/`, `?? packages/product-platform/src/ophanix_tool_gateway/`, `?? packages/product-platform/tests/test_tool_gateway_sdk_package.py`, `?? packages/product-platform/tests/test_tool_gateway_sdk_remediation.py`, and the prior review log as untracked.
- Why it matters: A release built from tracked repository state would not contain the standalone SDK package or preferred namespace.
- Root cause or likely root cause: Remediation artifacts were created locally but not added to version control.
- Impact on production readiness: Critical release blocker; current repository state does not prove the SDK package exists in committed source.
- Impact on developer experience: External consumers may be told to install or import a package that is not shipped.
- Impact on security or reliability: Release process can omit security fixes and package validation.
- Mentioned in prior review log: Partially; standalone package was discussed.
- Previous fix claimed to address it: Yes, standalone package extraction was claimed.
- Previous fix sufficient: No. The current source-control state undermines the claim.
- Recommended remediation: Add intended files to version control or remove the claims; require a clean worktree before release.
- Suggested validation or test: CI job that fails when SDK package paths are untracked or when release runs from a dirty worktree.
- Should affect scoring: Yes.

### SDK-AUDIT-002: Prior Review Log Is Untracked

- Category: Governance / auditability
- Severity: Medium
- Confidence: High
- File path or area: `docs/product-platform-worktree/execution-logs/06-tool-gateway-logs/13-sdk-review-remediation.md`
- Evidence: `git status --short` shows the prior remediation log as untracked.
- Why it matters: The prior evidence trail cannot be treated as durable repository history.
- Root cause or likely root cause: Review/remediation notes were generated locally and not committed.
- Impact on production readiness: Weakens release governance and reviewer continuity.
- Impact on developer experience: Future maintainers cannot reconstruct why changes were accepted.
- Impact on security or reliability: Security and release evidence may be lost.
- Mentioned in prior review log: No.
- Previous fix claimed to address it: No.
- Previous fix sufficient: Not applicable.
- Recommended remediation: Commit audit evidence or move it to an approved durable evidence store.
- Suggested validation or test: Release checklist verifies required audit artifacts are tracked.
- Should affect scoring: Yes.

### SDK-AUDIT-003: CI Path Filters Exclude Product Platform And SDK

- Category: CI / release readiness
- Severity: Critical
- Confidence: High
- File path or area: `.github/workflows/ci.yml`
- Evidence: CI path filters list agent packages and shared paths but omit `packages/product-platform/**` and `packages/ophanix-tool-gateway-sdk/**`; Python matrices also omit both packages.
- Why it matters: SDK and gateway changes can merge without running their tests, lint, build, or package validation.
- Root cause or likely root cause: Product-platform and standalone SDK were added outside the existing CI package matrix.
- Impact on production readiness: Critical; local passing tests are not equivalent to protected CI gates.
- Impact on developer experience: Contributors may receive false confidence from unrelated CI passing.
- Impact on security or reliability: Security regressions can merge undetected.
- Mentioned in prior review log: Prior log said CI should guard the symlink/package boundary.
- Previous fix claimed to address it: No actual visible workflow fix.
- Previous fix sufficient: No.
- Recommended remediation: Add both packages to path filters, lint/test/build matrices, and SDK release validation jobs.
- Suggested validation or test: Modify an SDK file in a test PR and verify CI runs SDK tests and build.
- Should affect scoring: Yes.

### SDK-AUDIT-004: Publish Workflow Cannot Publish The SDK

- Category: Packaging / release
- Severity: Critical
- Confidence: High
- File path or area: `.github/workflows/publish.yml`
- Evidence: Manual package options and build matrix omit `ophanix-tool-gateway-sdk` and `product-platform`.
- Why it matters: The standalone SDK has no visible release lane.
- Root cause or likely root cause: Publish workflow was not updated when standalone package was introduced.
- Impact on production readiness: Critical; external adoption depends on a real published artifact.
- Impact on developer experience: `pip install ophanix-tool-gateway-sdk` may fail or never receive updates.
- Impact on security or reliability: Vulnerability fixes may not reach consumers through a controlled release path.
- Mentioned in prior review log: Release validation was mentioned, publish workflow was not adequately addressed.
- Previous fix claimed to address it: Partial local release validation only.
- Previous fix sufficient: No.
- Recommended remediation: Add SDK to publish workflow, artifact signing, provenance, and dry-run publish validation.
- Suggested validation or test: Publish workflow dry run creates SDK wheel/sdist artifacts and provenance.
- Should affect scoring: Yes.

### SDK-AUDIT-005: Product-Platform Sdist Includes Local SQLite Database Files

- Category: Packaging / data handling
- Severity: Critical
- Confidence: High
- File path or area: `packages/product-platform/ophanix_product.db`, `packages/product-platform/ophanix_product.db.backup.20260509152042`
- Evidence: Product-platform sdist contained `ophanix_product.db` and `ophanix_product.db.backup.20260509152042`; `ophanix_product.db` is tracked.
- Why it matters: Source distributions can leak local or demo data and install stale database state.
- Root cause or likely root cause: Missing package sdist include/exclude policy and tracked local DB file.
- Impact on production readiness: Critical packaging and data-exposure blocker.
- Impact on developer experience: Installed package includes confusing local state.
- Impact on security or reliability: Potential sensitive data exposure and unpredictable runtime behavior.
- Mentioned in prior review log: No.
- Previous fix claimed to address it: No.
- Previous fix sufficient: Not applicable.
- Recommended remediation: Remove DB files from version control, exclude `*.db*` from sdist/docker contexts, and regenerate artifacts.
- Suggested validation or test: Artifact denylist test fails if wheel/sdist includes `*.db*`, backups, secrets, or pycache.
- Should affect scoring: Yes.

### SDK-AUDIT-006: Standalone SDK Source Is A Symlink Into Product Platform

- Category: Packaging / maintainability
- Severity: High
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway`
- Evidence: The standalone package source path is a symlink to `../../product-platform/src/ophanix_tool_gateway`.
- Why it matters: Symlink packaging is fragile across build tools, operating systems, source archives, and review ownership boundaries.
- Root cause or likely root cause: Attempt to share one implementation between product-platform compatibility imports and standalone package.
- Impact on production readiness: High; package shape can silently break without CI coverage.
- Impact on developer experience: Contributors may edit through one path and miss package implications.
- Impact on security or reliability: Release artifacts may diverge from tested source shape.
- Mentioned in prior review log: Yes; prior log acknowledged symlink and said CI must guard it.
- Previous fix claimed to address it: Artifact validation was claimed.
- Previous fix sufficient: No, because CI/publish do not enforce it.
- Recommended remediation: Use a real shared package source or add cross-platform symlink artifact validation in CI.
- Suggested validation or test: Build wheel/sdist from clean checkout on Linux/macOS/Windows or replace symlink with owned source.
- Should affect scoring: Yes.

### SDK-AUDIT-007: Release Validator Checks Presence But Not Absence Or Installed Behavior

- Category: Packaging / release
- Severity: Medium
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/scripts/validate_release.py`
- Evidence: The validator checks only `__init__.py`, `sdk.py`, and `py.typed` presence plus `twine check`.
- Why it matters: Artifacts can include unwanted files, omit license metadata, or fail after installation while still passing.
- Root cause or likely root cause: Minimal artifact-shape validator.
- Impact on production readiness: Medium; release confidence is overstated.
- Impact on developer experience: Consumers can receive broken or noncompliant artifacts.
- Impact on security or reliability: Artifact leaks or missing metadata may go undetected.
- Mentioned in prior review log: Yes, release validator was claimed.
- Previous fix claimed to address it: Yes.
- Previous fix sufficient: No.
- Recommended remediation: Add denylist checks, installed-wheel import smoke, sdist install smoke, metadata/license validation, and package-size checks.
- Suggested validation or test: Validator fails on `*.db*`, `__pycache__`, missing license, broken installed import, or unexpected source roots.
- Should affect scoring: Yes.

### SDK-AUDIT-008: Standalone SDK Artifacts Omit Package-Local License File

- Category: Packaging / legal compliance
- Severity: Medium
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/pyproject.toml`, built wheel/sdist
- Evidence: Artifact listings contain no `LICENSE`; project declares `license = {text = "MIT"}` only.
- Why it matters: Downstream scanners and legal reviews often expect license files in distributed artifacts.
- Root cause or likely root cause: Package metadata was created without `license-files` or local license include.
- Impact on production readiness: Medium; can block enterprise adoption.
- Impact on developer experience: Consumers may see license warnings in compliance tooling.
- Impact on security or reliability: No direct runtime impact.
- Mentioned in prior review log: No.
- Previous fix claimed to address it: No.
- Previous fix sufficient: Not applicable.
- Recommended remediation: Include repository license in SDK wheel/sdist via `license-files`.
- Suggested validation or test: Release validator asserts license file in both artifacts.
- Should affect scoring: Yes.

### SDK-AUDIT-009: SDK Metadata Is Incomplete And Marked Alpha

- Category: Packaging / developer experience
- Severity: Medium
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/pyproject.toml`
- Evidence: Classifier says `Development Status :: 3 - Alpha`; metadata lacks authors, maintainers, URLs, project links, support/security contact, and Python 3.13 classifier.
- Why it matters: Production adopters receive mixed maturity signals and limited support information.
- Root cause or likely root cause: Initial scaffold-level metadata.
- Impact on production readiness: Medium; not publication-grade.
- Impact on developer experience: Harder to identify maintainers, docs, source, and support path.
- Impact on security or reliability: Security reporting path is unclear.
- Mentioned in prior review log: Package metadata was mentioned generally.
- Previous fix claimed to address it: Partial.
- Previous fix sufficient: No.
- Recommended remediation: Complete metadata or explicitly state pre-production status.
- Suggested validation or test: Metadata check in release validator.
- Should affect scoring: Yes.

### SDK-AUDIT-010: Standalone Package Test Configuration Points At Missing Tests

- Category: Testing / packaging
- Severity: Low
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/pyproject.toml`
- Evidence: `[tool.pytest.ini_options] testpaths = ["tests"]`, but the standalone package has no `tests/` directory.
- Why it matters: Running pytest in the package root can run nothing or confuse contributors.
- Root cause or likely root cause: Copied test config without package-local tests.
- Impact on production readiness: Low.
- Impact on developer experience: Confusing local validation path.
- Impact on security or reliability: Indirect; tests may be skipped.
- Mentioned in prior review log: No.
- Previous fix claimed to address it: No.
- Previous fix sufficient: Not applicable.
- Recommended remediation: Add package-local tests or remove/redirect test config.
- Suggested validation or test: `pytest` from standalone package root must run meaningful tests or fail with guidance.
- Should affect scoring: Yes, minor.

### SDK-AUDIT-011: Typed SDK Has No Type Checker Gate

- Category: Testing / typing
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/src/ophanix_tool_gateway/py.typed`, CI/config
- Evidence: `py.typed` exists, but no `mypy` or `pyright` config/gate was found for the SDK.
- Why it matters: Shipping `py.typed` promises usable public types, but that promise is not verified.
- Root cause or likely root cause: Type marker added without type-check workflow.
- Impact on production readiness: Medium.
- Impact on developer experience: Consumers may hit type-check failures or inaccurate hints.
- Impact on security or reliability: Type drift can hide runtime integration errors.
- Mentioned in prior review log: Prior log noted no type-checker run.
- Previous fix claimed to address it: No.
- Previous fix sufficient: No.
- Recommended remediation: Add mypy/pyright checks for SDK source and installed wheel usage examples.
- Suggested validation or test: CI type-checks public examples and Protocol implementations.
- Should affect scoring: Yes.

### SDK-AUDIT-012: No Installed-Wheel Plus Running-Gateway Contract Test

- Category: Testing / integration
- Severity: High
- Confidence: High
- File path or area: Tests and CI
- Evidence: Existing SDK tests use source paths and mocks; no CI-enforced test installs the built SDK wheel into a clean environment and calls a real gateway.
- Why it matters: Packaging, import, auth, discovery, and invocation contract can drift independently.
- Root cause or likely root cause: Local unit-focused validation grew faster than release-grade integration coverage.
- Impact on production readiness: High.
- Impact on developer experience: Consumers may discover integration breakage after install.
- Impact on security or reliability: Auth and error contract regressions can escape.
- Mentioned in prior review log: Local wheel and import checks were claimed.
- Previous fix claimed to address it: Partial local package checks.
- Previous fix sufficient: No.
- Recommended remediation: Add CI e2e: build wheel, install into clean venv, start gateway with seeded credential/tool, call discovery and invoke.
- Suggested validation or test: Installed SDK calls `/api/v1/gateway/tools` and `/api/v1/tools/{name}/invoke` against a running app.
- Should affect scoring: Yes.

### SDK-AUDIT-013: Optional Dependency Audit Is Not A Release Gate And Skips The Local Package

- Category: Security / release
- Severity: Medium
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/scripts/validate_release.py`
- Evidence: `--require-dependency-audit` passed but printed that `ophanix-tool-gateway-sdk` could not be audited because it was not found on PyPI.
- Why it matters: The audit does not validate the unpublished package itself and is not wired into visible CI/publish workflows.
- Root cause or likely root cause: Optional local audit rather than enforced release workflow.
- Impact on production readiness: Medium.
- Impact on developer experience: Security posture appears stronger than it is.
- Impact on security or reliability: Vulnerable dependencies can escape if audit is not mandatory.
- Mentioned in prior review log: Yes, dependency audit was claimed.
- Previous fix claimed to address it: Yes.
- Previous fix sufficient: No.
- Recommended remediation: Gate dependency audit in CI and archive audit output; audit dependency set separately from unpublished package identity.
- Suggested validation or test: CI fails on known-vulnerable dependency and stores SBOM/audit artifact.
- Should affect scoring: Yes.

### SDK-AUDIT-014: Source-Tree SDK Version Reports 0.0.0

- Category: Developer experience / diagnostics
- Severity: Low
- Confidence: High
- File path or area: `packages/product-platform/src/ophanix_tool_gateway/sdk.py`
- Evidence: `_sdk_version()` falls back to `"0.0.0"` when package metadata is unavailable; source import printed `0.0.0`.
- Why it matters: User-Agent and diagnostics are misleading during source-based development and tests.
- Root cause or likely root cause: Version is derived only from installed distribution metadata.
- Impact on production readiness: Low.
- Impact on developer experience: Harder to debug which SDK revision generated logs.
- Impact on security or reliability: Weakens incident correlation.
- Mentioned in prior review log: Version export was claimed.
- Previous fix claimed to address it: Yes.
- Previous fix sufficient: Partial only.
- Recommended remediation: Generate or maintain a source-readable version fallback.
- Suggested validation or test: Source import reports expected package version or explicit dev version.
- Should affect scoring: Minor yes.

### SDK-AUDIT-015: Injected HTTP Client Type Is Not Validated

- Category: Public API / runtime behavior
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/src/ophanix_tool_gateway/sdk.py`
- Evidence: Sync client accepts `http_client` and stores it directly; passing `httpx.AsyncClient` produced an unawaited coroutine warning and `AttributeError`.
- Why it matters: A common integration mistake fails unclearly and can leak resources.
- Root cause or likely root cause: Type hints were used without runtime protocol validation.
- Impact on production readiness: Medium.
- Impact on developer experience: Error is confusing and not actionable.
- Impact on security or reliability: Resource leaks and unexpected failures under load.
- Mentioned in prior review log: No.
- Previous fix claimed to address it: No.
- Previous fix sufficient: Not applicable.
- Recommended remediation: Validate sync/async HTTP client protocols at construction.
- Suggested validation or test: Negative tests for passing async client to sync SDK and sync client to async SDK.
- Should affect scoring: Yes.

### SDK-AUDIT-016: StaticTokenProvider Does Not Validate Token Type

- Category: Public API / developer experience
- Severity: Low
- Confidence: High
- File path or area: `packages/product-platform/src/ophanix_tool_gateway/sdk.py`
- Evidence: `StaticTokenProvider(123).get_token()` raises `AttributeError: 'int' object has no attribute 'strip'`.
- Why it matters: Public API should fail deterministically with a clear `ValueError`.
- Root cause or likely root cause: Dataclass field type was trusted at runtime.
- Impact on production readiness: Low.
- Impact on developer experience: Poor error message.
- Impact on security or reliability: Minimal direct impact.
- Mentioned in prior review log: Constructor validation was discussed generally.
- Previous fix claimed to address it: Partial validation claims.
- Previous fix sufficient: No.
- Recommended remediation: Reuse `_require_text` for static token validation.
- Suggested validation or test: `StaticTokenProvider(123).get_token()` raises a clear `ValueError`.
- Should affect scoring: Minor yes.

### SDK-AUDIT-017: Secret Redaction Partially Leaks Colon-Bearing Bearer Tokens

- Category: Security
- Severity: High
- Confidence: High
- File path or area: `packages/product-platform/src/ophanix_tool_gateway/sdk.py`
- Evidence: Sanitizing `Authorization: Bearer abc:def` produced `Authorization: [redacted]:def`; regex excludes `:`.
- Why it matters: Diagnostic bodies can expose token suffixes.
- Root cause or likely root cause: Bearer-token regex character class is too narrow.
- Impact on production readiness: High.
- Impact on developer experience: Users may trust redaction that is incomplete.
- Impact on security or reliability: Potential credential exposure in logs/errors.
- Mentioned in prior review log: Redaction was heavily discussed.
- Previous fix claimed to address it: Yes.
- Previous fix sufficient: No.
- Recommended remediation: Broaden bearer and assignment redaction to consume full non-delimiter token values safely.
- Suggested validation or test: Corpus tests for bearer tokens with colon, JWT-like strings, opaque tokens, quoted values, and delimiters.
- Should affect scoring: Yes.

### SDK-AUDIT-018: Malformed Discovery Description Is Silently Coerced To Empty

- Category: Runtime contract / SDK validation
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/src/ophanix_tool_gateway/sdk.py`
- Evidence: `_tool_definition()` uses `_response_string(body.get("description")) or ""`; a list description becomes `""` instead of an invalid response error.
- Why it matters: Server contract drift is hidden from clients and tests.
- Root cause or likely root cause: Optional field coercion was made too permissive.
- Impact on production readiness: Medium.
- Impact on developer experience: Consumers see missing descriptions rather than a clear gateway contract problem.
- Impact on security or reliability: Low direct impact, but weakens contract reliability.
- Mentioned in prior review log: Strict response validation was claimed.
- Previous fix claimed to address it: Yes, broadly.
- Previous fix sufficient: No.
- Recommended remediation: Accept only string or null for description.
- Suggested validation or test: Discovery response with non-string description raises `ToolGatewayError(code="invalid_response")`.
- Should affect scoring: Yes.

### SDK-AUDIT-019: reason_code Response Field Is Not Type-Validated

- Category: Runtime contract / SDK validation
- Severity: Low
- Confidence: High
- File path or area: `packages/product-platform/src/ophanix_tool_gateway/sdk.py`
- Evidence: `_tool_call_result()` assigns `reason_code=body.get("reason_code")` directly.
- Why it matters: Public dataclass field can contain unexpected non-string data.
- Root cause or likely root cause: Optional field validation omitted.
- Impact on production readiness: Low.
- Impact on developer experience: Type annotations can be violated at runtime.
- Impact on security or reliability: Low direct impact.
- Mentioned in prior review log: No.
- Previous fix claimed to address it: No.
- Previous fix sufficient: Not applicable.
- Recommended remediation: Validate optional response string fields consistently.
- Suggested validation or test: Successful response with numeric `reason_code` is rejected.
- Should affect scoring: Minor yes.

### SDK-AUDIT-020: Frozen SDK Result Objects Contain Mutable Raw Dictionaries

- Category: API design / maintainability
- Severity: Low
- Confidence: High
- File path or area: `ToolCallResult.raw`, `ToolDefinition.raw`
- Evidence: Frozen dataclasses expose `raw: dict[str, Any]` from the original response body.
- Why it matters: Callers can mutate state on objects that appear immutable.
- Root cause or likely root cause: Convenience escape hatch added without immutability policy.
- Impact on production readiness: Low.
- Impact on developer experience: Can cause surprising behavior in shared/cached results.
- Impact on security or reliability: Low direct impact.
- Mentioned in prior review log: No.
- Previous fix claimed to address it: No.
- Previous fix sufficient: Not applicable.
- Recommended remediation: Expose read-only mappings or document mutability explicitly.
- Suggested validation or test: Mutating `raw` cannot mutate cached SDK objects, or docs state it can.
- Should affect scoring: Minor yes.

### SDK-AUDIT-021: Error-Body Sanitizer Has No Recursion Depth Cap

- Category: Reliability / security
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/src/ophanix_tool_gateway/sdk.py`
- Evidence: `_sanitize_error_value()` recursively handles dicts/lists with item caps but no depth cap.
- Why it matters: Deep malicious or accidental responses can trigger recursion errors or expensive processing.
- Root cause or likely root cause: Item-count cap was added without depth/global complexity cap.
- Impact on production readiness: Medium.
- Impact on developer experience: Error handling can fail while reporting an error.
- Impact on security or reliability: Possible denial-of-service in client process.
- Mentioned in prior review log: Redaction was discussed.
- Previous fix claimed to address it: Partial.
- Previous fix sufficient: No.
- Recommended remediation: Add max depth and global node/byte budget.
- Suggested validation or test: Deep nested diagnostic body sanitizes safely without recursion failure.
- Should affect scoring: Yes.

### SDK-AUDIT-022: Non-JSON Response Handling Reads Full Response Text Before Truncation

- Category: Reliability / security
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/src/ophanix_tool_gateway/sdk.py`
- Evidence: `_response_data()` uses `response.text` before `_sanitize_text()` truncates.
- Why it matters: Huge upstream/gateway error pages can be loaded into memory just to produce a short diagnostic.
- Root cause or likely root cause: Simple diagnostic extraction without byte cap.
- Impact on production readiness: Medium.
- Impact on developer experience: Error handling can be slow or memory-heavy.
- Impact on security or reliability: Potential client memory pressure.
- Mentioned in prior review log: No.
- Previous fix claimed to address it: No.
- Previous fix sufficient: Not applicable.
- Recommended remediation: Cap diagnostic bytes before decoding or use streamed/limited content.
- Suggested validation or test: Large non-JSON response produces bounded memory and bounded diagnostic body.
- Should affect scoring: Yes.

### SDK-AUDIT-023: SDK Has No Client-Side Payload Size Cap

- Category: Reliability
- Severity: Medium
- Confidence: High
- File path or area: SDK payload validation
- Evidence: Payload validation checks JSON object shape, key types, serializability, and finite numbers, but no payload byte size cap was found.
- Why it matters: Accidental large payloads can harm SDK callers, gateway, network, and audit storage.
- Root cause or likely root cause: Shape validation was prioritized over resource limits.
- Impact on production readiness: Medium.
- Impact on developer experience: Users get late gateway/server failures rather than clear SDK errors.
- Impact on security or reliability: Memory and request-size risk.
- Mentioned in prior review log: No.
- Previous fix claimed to address it: No.
- Previous fix sufficient: Not applicable.
- Recommended remediation: Add configurable `max_payload_bytes`.
- Suggested validation or test: Oversized payload fails locally with clear error.
- Should affect scoring: Yes.

### SDK-AUDIT-024: Tool Invocation Has No Idempotency Contract Or Safe Retry Support

- Category: Reliability / API contract
- Severity: Medium
- Confidence: High
- File path or area: SDK README and invocation API
- Evidence: README states tool invocation requests are not retried because mutating tools need an idempotency contract first.
- Why it matters: Production callers cannot safely recover from transient gateway or network failures for mutating tools.
- Root cause or likely root cause: Server contract lacks idempotency keys.
- Impact on production readiness: Medium.
- Impact on developer experience: Callers must design their own retry/idempotency behavior.
- Impact on security or reliability: Higher incident risk during transient failures.
- Mentioned in prior review log: It was documented.
- Previous fix claimed to address it: Documentation only.
- Previous fix sufficient: No, documentation is not the feature.
- Recommended remediation: Add idempotency key contract, server dedupe semantics, and opt-in safe retries.
- Suggested validation or test: Retried invocation with same idempotency key executes once and returns consistent result.
- Should affect scoring: Yes.

### SDK-AUDIT-025: Discovery Cache Has No TTL Or Built-In Synchronization

- Category: Reliability / developer experience
- Severity: Medium
- Confidence: High
- File path or area: SDK cache behavior
- Evidence: README documents process-local cache with no TTL and no thread-safety guarantee.
- Why it matters: Long-running agents can use stale tool/permission data.
- Root cause or likely root cause: Minimal opt-in cache added without lifecycle policy.
- Impact on production readiness: Medium.
- Impact on developer experience: Users must understand and manage cache invalidation manually.
- Impact on security or reliability: Stale permissions or contracts may be observed client-side.
- Mentioned in prior review log: Cache partitioning and docs were mentioned.
- Previous fix claimed to address it: Partial, by documenting.
- Previous fix sufficient: Partial only.
- Recommended remediation: Add TTL, max entries, and synchronization or explicitly keep cache experimental.
- Suggested validation or test: Permission changes expire from cache after TTL.
- Should affect scoring: Yes.

### SDK-AUDIT-026: list_tools(status=...) Exposes A Mostly Useless Parameter

- Category: Public API / developer experience
- Severity: Low
- Confidence: High
- File path or area: SDK `list_tools`
- Evidence: Public method accepts `status: Literal["active"] | None`; non-active statuses are rejected.
- Why it matters: The API suggests filtering flexibility that does not exist.
- Root cause or likely root cause: Operator API shape influenced SDK discovery API.
- Impact on production readiness: Low.
- Impact on developer experience: Confusing method signature.
- Impact on security or reliability: No direct impact.
- Mentioned in prior review log: No.
- Previous fix claimed to address it: No.
- Previous fix sufficient: Not applicable.
- Recommended remediation: Remove `status` from SDK method or support documented statuses if safe.
- Suggested validation or test: Public API docs and signature match actual supported behavior.
- Should affect scoring: Minor yes.

### SDK-AUDIT-027: Auth Failures Are Not Exposed As A Clear Typed SDK Error

- Category: API / developer experience
- Severity: Medium
- Confidence: Medium
- File path or area: Gateway auth dependency and SDK error mapping
- Evidence: Gateway auth failure raises HTTP 401 with a detail string; SDK maps generic gateway errors based on response body shape.
- Why it matters: Credential setup and rotation problems need precise, stable diagnostics.
- Root cause or likely root cause: Auth error contract is not a dedicated SDK-facing envelope.
- Impact on production readiness: Medium.
- Impact on developer experience: Harder to debug missing, expired, revoked, or malformed credentials.
- Impact on security or reliability: Operators may over-log raw diagnostics while debugging.
- Mentioned in prior review log: Error handling was discussed broadly.
- Previous fix claimed to address it: Partial.
- Previous fix sufficient: No.
- Recommended remediation: Add stable auth error envelope and `ToolAuthenticationError`.
- Suggested validation or test: Missing/expired/revoked token maps to typed SDK auth error with reason code and no token material.
- Should affect scoring: Yes.

### SDK-AUDIT-028: SDK Lacks Structured Telemetry Hooks

- Category: Operability
- Severity: Low
- Confidence: High
- File path or area: SDK constructors and runtime methods
- Evidence: No logging/tracing/event callback options were found.
- Why it matters: Production agents need request IDs, retries, latency, and error events without wrapping private internals.
- Root cause or likely root cause: Minimal client API.
- Impact on production readiness: Low to medium depending on adopter observability requirements.
- Impact on developer experience: Integrators must build wrappers.
- Impact on security or reliability: Incident diagnosis is harder.
- Mentioned in prior review log: No.
- Previous fix claimed to address it: No.
- Previous fix sufficient: Not applicable.
- Recommended remediation: Add optional hooks or structured event callbacks with redaction guarantees.
- Suggested validation or test: Hook receives retry/error/latency events with no token material.
- Should affect scoring: Minor yes.

### SDK-AUDIT-029: Gateway Auth Bypass Pattern Is Too Broad

- Category: Security / API routing
- Severity: High
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/api/app.py`
- Evidence: Auth middleware bypasses all paths starting with `/api/v1/gateway/` and `/api/v1/tools/*/invoke`.
- Why it matters: Any future route under the bypassed prefix without explicit gateway dependency becomes unauthenticated.
- Root cause or likely root cause: Prefix-level bypass instead of explicit allowlist or mandatory gateway auth middleware.
- Impact on production readiness: High.
- Impact on developer experience: Maintainers can accidentally create public routes.
- Impact on security or reliability: Potential authentication bypass for future endpoints.
- Mentioned in prior review log: No.
- Previous fix claimed to address it: No.
- Previous fix sufficient: Not applicable.
- Recommended remediation: Replace prefix bypass with route allowlist or gateway-auth middleware for the prefix.
- Suggested validation or test: Test-only route under `/api/v1/gateway/` without dependency must not be reachable unauthenticated.
- Should affect scoring: Yes.

### SDK-AUDIT-030: Invocation Validates Payload Schema Before Authorization

- Category: Security
- Severity: High
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/api/app.py`
- Evidence: Invocation route loads tool and validates input schema before `ToolPolicyDecisionService.evaluate_tool_call()`.
- Why it matters: An authenticated but unauthorized agent can infer schema requirements and validation behavior.
- Root cause or likely root cause: Validation was placed before policy evaluation for convenience.
- Impact on production readiness: High.
- Impact on developer experience: Error ordering is inconsistent with least-privilege expectations.
- Impact on security or reliability: Schema oracle for unauthorized callers.
- Mentioned in prior review log: No.
- Previous fix claimed to address it: No.
- Previous fix sufficient: Not applicable.
- Recommended remediation: Evaluate authorization/resource binding before schema validation.
- Suggested validation or test: Unauthorized credential receives denial without schema-specific error for invalid payload.
- Should affect scoring: Yes.

### SDK-AUDIT-031: Invocation Reveals Active Tool Existence Before Authorization

- Category: Security
- Severity: High
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/api/app.py`
- Evidence: Route returns `404 Tool not found` before policy decision; active existing tool proceeds to schema/policy path.
- Why it matters: Authenticated but unauthorized agents can enumerate active tool names through response differences.
- Root cause or likely root cause: Direct repository lookup before policy decision.
- Impact on production readiness: High.
- Impact on developer experience: Error behavior leaks internal registry details.
- Impact on security or reliability: Tool enumeration risk.
- Mentioned in prior review log: No.
- Previous fix claimed to address it: No.
- Previous fix sufficient: Not applicable.
- Recommended remediation: Normalize unauthorized/missing responses or evaluate through a policy path that does not expose registry existence to unauthorized principals.
- Suggested validation or test: Unauthorized calls to existing and missing tools produce indistinguishable responses where appropriate.
- Should affect scoring: Yes.

### SDK-AUDIT-032: Default Executor Creates Unclosed httpx.Client Instances

- Category: Reliability / resource cleanup
- Severity: High
- Confidence: High
- File path or area: `app.py`, `tool_gateway/invocation.py`
- Evidence: Invocation route creates `HttpToolInvocationExecutor` when app state has none; executor creates `httpx.Client()` with no close method or app shutdown lifecycle.
- Why it matters: Production traffic can leak connections and file descriptors.
- Root cause or likely root cause: Per-request fallback executor without managed client lifecycle.
- Impact on production readiness: High.
- Impact on developer experience: Incidents may appear as intermittent connection failures.
- Impact on security or reliability: Resource exhaustion under load.
- Mentioned in prior review log: No.
- Previous fix claimed to address it: No.
- Previous fix sufficient: Not applicable.
- Recommended remediation: Create one managed HTTP client/executor at app startup and close it on shutdown.
- Suggested validation or test: Repeated invocations do not create unclosed clients; resource warnings fail tests.
- Should affect scoring: Yes.

### SDK-AUDIT-033: Manual Health Checker Creates Unclosed httpx.Client Instances

- Category: Reliability / resource cleanup
- Severity: Medium
- Confidence: High
- File path or area: `app.py`, `tool_gateway/health.py`
- Evidence: Manual health route creates `ToolUpstreamHealthChecker`; checker creates `httpx.Client()` if none is injected and has no close lifecycle.
- Why it matters: Repeated health checks can leak resources.
- Root cause or likely root cause: Same unmanaged fallback pattern as executor.
- Impact on production readiness: Medium.
- Impact on developer experience: Hard-to-diagnose resource warnings or FD exhaustion.
- Impact on security or reliability: Reliability degradation.
- Mentioned in prior review log: No.
- Previous fix claimed to address it: No.
- Previous fix sufficient: Not applicable.
- Recommended remediation: Use shared app-lifecycle HTTP client.
- Suggested validation or test: Health-check loop under warnings-as-errors produces no unclosed resource warnings.
- Should affect scoring: Yes.

### SDK-AUDIT-034: Upstream auth_mode Is Accepted But Unused

- Category: Runtime correctness / security
- Severity: High
- Confidence: High
- File path or area: `tool_gateway/models.py`, `tool_gateway/invocation.py`
- Evidence: Supported modes include `none`, `api_key`, `bearer`, `mtls`, and `custom`, but executor forwards only Ophanix metadata headers and never applies upstream authentication.
- Why it matters: Operators can configure authenticated upstream modes and still send unauthenticated requests.
- Root cause or likely root cause: Data model was designed before credential injection implementation.
- Impact on production readiness: High.
- Impact on developer experience: Misleading configuration field.
- Impact on security or reliability: Tool calls may fail or be routed around intended upstream auth expectations.
- Mentioned in prior review log: No.
- Previous fix claimed to address it: No.
- Previous fix sufficient: Not applicable.
- Recommended remediation: Implement credential references for each supported mode or restrict supported modes to `none` until implemented.
- Suggested validation or test: `auth_mode="bearer"` adds expected upstream Authorization header from secret store; unsupported modes are rejected.
- Should affect scoring: Yes.

### SDK-AUDIT-035: Upstream Target URL Validation Allows Arbitrary HTTP(S)

- Category: Security / SSRF
- Severity: High
- Confidence: High
- File path or area: `tool_gateway/models.py`, `tool_gateway/invocation.py`, `tool_gateway/health.py`
- Evidence: `validate_http_url()` accepts any absolute `http` or `https` URL; executor and health checker call configured URLs.
- Why it matters: Upstream and health targets can reach internal networks, metadata services, or unintended hosts.
- Root cause or likely root cause: Basic URL validation without trust-boundary controls.
- Impact on production readiness: High.
- Impact on developer experience: Operators can accidentally configure unsafe targets.
- Impact on security or reliability: SSRF and internal service exposure.
- Mentioned in prior review log: No.
- Previous fix claimed to address it: No.
- Previous fix sufficient: Not applicable.
- Recommended remediation: Enforce HTTPS for production, allowlist hosts, deny private/loopback/link-local/metadata IPs unless explicitly allowed, and handle DNS rebinding.
- Suggested validation or test: Attempts to configure `169.254.169.254`, localhost, private IPs, and rebinding-style hosts are blocked by policy.
- Should affect scoring: Yes.

### SDK-AUDIT-036: Upstream Calls Send JSON Bodies For GET And DELETE

- Category: Runtime correctness
- Severity: Medium
- Confidence: High
- File path or area: `tool_gateway/invocation.py`
- Evidence: Executor always calls `http_client.request(..., json=payload, ...)` for every configured method.
- Why it matters: Many upstreams and intermediaries reject or mishandle GET/DELETE bodies.
- Root cause or likely root cause: Single forwarding path for all methods.
- Impact on production readiness: Medium.
- Impact on developer experience: Integrations with common REST APIs can fail unexpectedly.
- Impact on security or reliability: Incorrect upstream behavior and hard-to-debug failures.
- Mentioned in prior review log: No.
- Previous fix claimed to address it: No.
- Previous fix sufficient: Not applicable.
- Recommended remediation: Define method-specific mapping for body, query parameters, and path templates.
- Suggested validation or test: GET maps payload fields to path/query and does not send JSON body unless explicitly configured.
- Should affect scoring: Yes.

### SDK-AUDIT-037: Failed Upstream Responses Bypass Response Policy

- Category: Security / reliability
- Severity: Critical
- Confidence: High
- File path or area: `tool_gateway/response.py`, `api/app.py`
- Evidence: `process_tool_execution_response()` immediately returns failed executions unchanged; API returns failed execution result in the response body.
- Why it matters: Failed upstream bodies can leak secrets, ignore `expose_to_agent=false`, and bypass response size limits.
- Root cause or likely root cause: Response policy was implemented only for successful upstream responses.
- Impact on production readiness: Critical.
- Impact on developer experience: Policy behavior differs by status in a surprising and unsafe way.
- Impact on security or reliability: Direct data leakage and oversized response risk.
- Mentioned in prior review log: No.
- Previous fix claimed to address it: No.
- Previous fix sufficient: Not applicable.
- Recommended remediation: Apply redaction, exposure, and size policy to all upstream responses before returning or storing summaries.
- Suggested validation or test: Failed upstream response containing `token` is redacted and hidden when `expose_to_agent=false`.
- Should affect scoring: Yes.

### SDK-AUDIT-038: store_full_response Policy Is Persisted But Not Honored

- Category: Runtime correctness / privacy
- Severity: High
- Confidence: High
- File path or area: `tool_gateway/models.py`, `repository.py`, migration `0054`, runtime response/audit paths
- Evidence: `store_full_response` exists in schema/model/repository, but runtime response handling and audit storage do not branch on it.
- Why it matters: Operators see a privacy/storage policy that does not actually control storage behavior.
- Root cause or likely root cause: Policy model was created before full runtime enforcement.
- Impact on production readiness: High.
- Impact on developer experience: Misleading control plane behavior.
- Impact on security or reliability: Privacy expectations can be violated.
- Mentioned in prior review log: No.
- Previous fix claimed to address it: No.
- Previous fix sufficient: Not applicable.
- Recommended remediation: Define and implement exact storage semantics for `store_full_response`.
- Suggested validation or test: With `store_full_response=false`, raw response body is not persisted; with true, only allowed/redacted form is stored according to policy.
- Should affect scoring: Yes.

### SDK-AUDIT-039: Redaction Regex Patterns Are Unvalidated And Compiled Per Response

- Category: Security / reliability
- Severity: High
- Confidence: High
- File path or area: `tool_gateway/models.py`, `tool_gateway/response.py`
- Evidence: Redaction rules validator checks only nonblank strings; response handling compiles every configured regex on every response.
- Why it matters: Invalid regex can fail at runtime; catastrophic regex can cause response-processing DoS.
- Root cause or likely root cause: Regex validation and safe-regex policy omitted.
- Impact on production readiness: High.
- Impact on developer experience: Policy misconfiguration appears as runtime invocation failures.
- Impact on security or reliability: ReDoS risk.
- Mentioned in prior review log: No.
- Previous fix claimed to address it: No.
- Previous fix sufficient: Not applicable.
- Recommended remediation: Compile/validate regex on policy write, constrain pattern complexity, cache compiled patterns, or use safer matching primitives.
- Suggested validation or test: Invalid and catastrophic patterns are rejected before activation.
- Should affect scoring: Yes.

### SDK-AUDIT-040: Response Redaction Key Matching Over-Redacts By Substring

- Category: Correctness / developer experience
- Severity: Low
- Confidence: High
- File path or area: `tool_gateway/response.py`
- Evidence: Redaction checks `any(token in lowered for token in redact_keys)`, so `key` can match unrelated field names like `monkey`.
- Why it matters: Response data can be unnecessarily removed, reducing usefulness of diagnostics and tool output.
- Root cause or likely root cause: Simple substring matching.
- Impact on production readiness: Low.
- Impact on developer experience: Unexpected redaction behavior.
- Impact on security or reliability: Low security risk; primarily correctness/noise.
- Mentioned in prior review log: No.
- Previous fix claimed to address it: No.
- Previous fix sufficient: Not applicable.
- Recommended remediation: Normalize exact names and well-defined suffix/pattern rules consistently with SDK sanitizer.
- Suggested validation or test: `monkey` is not redacted when only `key` is configured, while `api_key` is redacted.
- Should affect scoring: Minor yes.

### SDK-AUDIT-041: Runtime Payload And Response Summaries Lack Global Size/Depth Caps

- Category: Reliability / data handling
- Severity: Medium
- Confidence: High
- File path or area: `tool_gateway/decision.py`, `tool_gateway/runtime_audit.py`
- Evidence: `summarize_tool_payload()` recursively summarizes dicts with list cap but no dict count, depth, or total byte cap.
- Why it matters: Large payloads can bloat database rows and audit records.
- Root cause or likely root cause: Summary redaction was added without global complexity limits.
- Impact on production readiness: Medium.
- Impact on developer experience: Slow or huge audit records are hard to inspect.
- Impact on security or reliability: Storage and performance risk.
- Mentioned in prior review log: No.
- Previous fix claimed to address it: No.
- Previous fix sufficient: Not applicable.
- Recommended remediation: Add depth, item, and byte caps to all audit summaries.
- Suggested validation or test: Huge nested payload produces bounded summary size.
- Should affect scoring: Yes.

### SDK-AUDIT-042: No Tool Gateway Rate Limiting

- Category: Reliability / security
- Severity: High
- Confidence: High
- File path or area: Tool Gateway API routes and middleware
- Evidence: Search found MCP rate-limit support but no Tool Gateway token or invocation rate limiter.
- Why it matters: Token verification and tool invocation can be brute-forced or overloaded.
- Root cause or likely root cause: Gateway-specific abuse controls not implemented.
- Impact on production readiness: High.
- Impact on developer experience: Downstream teams must rely on external infrastructure without clear contract.
- Impact on security or reliability: Brute-force and denial-of-service exposure.
- Mentioned in prior review log: No.
- Previous fix claimed to address it: No.
- Previous fix sufficient: Not applicable.
- Recommended remediation: Add per-token, per-agent, per-IP, and per-tool rate limits, or document required edge controls.
- Suggested validation or test: Excess requests receive stable 429 with no upstream invocation.
- Should affect scoring: Yes.

### SDK-AUDIT-043: No API Request Body Size Limit For Gateway Invocation

- Category: Reliability / security
- Severity: High
- Confidence: High
- File path or area: Tool Gateway API and SDK validation
- Evidence: No Tool Gateway request body size limit or `Content-Length` enforcement was found.
- Why it matters: Large requests can exhaust memory, slow validation, and bloat audit storage.
- Root cause or likely root cause: Payload schema validation added without transport/resource limits.
- Impact on production readiness: High.
- Impact on developer experience: Failures occur late and unpredictably.
- Impact on security or reliability: DoS risk.
- Mentioned in prior review log: No.
- Previous fix claimed to address it: No.
- Previous fix sufficient: Not applicable.
- Recommended remediation: Enforce gateway body limits at ASGI/server layer and SDK client-side cap.
- Suggested validation or test: Oversized request is rejected before schema validation and audit storage.
- Should affect scoring: Yes.

### SDK-AUDIT-044: CORS Is Broad With Credentials Enabled

- Category: Security / configuration
- Severity: Medium
- Confidence: Medium
- File path or area: `packages/product-platform/src/product_platform/api/app.py`
- Evidence: CORS middleware enables credentials with all methods and all headers, relying on configured origins.
- Why it matters: Safety depends entirely on production origin configuration.
- Root cause or likely root cause: Broad application-level CORS defaults.
- Impact on production readiness: Medium.
- Impact on developer experience: Misconfiguration can be hard to detect locally.
- Impact on security or reliability: Cross-origin request exposure if origins are too permissive.
- Mentioned in prior review log: No.
- Previous fix claimed to address it: No.
- Previous fix sufficient: Not applicable.
- Recommended remediation: Narrow methods/headers for production and add config validation that rejects wildcard origins with credentials.
- Suggested validation or test: Production settings cannot enable credentials with wildcard or unexpected origins.
- Should affect scoring: Yes.

### SDK-AUDIT-045: Token Hashing Uses Unsalted SHA-256 Without Documented Entropy Requirement

- Category: Security
- Severity: Medium
- Confidence: High
- File path or area: `product_platform/agents/credentials.py`, `tool_gateway/auth.py`
- Evidence: Credential tokens are hashed with plain SHA-256.
- Why it matters: Plain SHA-256 is acceptable only if raw tokens are high-entropy random secrets; docs do not specify or prove entropy requirements.
- Root cause or likely root cause: Stable hash lookup design without explicit entropy enforcement in reviewed docs.
- Impact on production readiness: Medium.
- Impact on developer experience: Operators may create weak deterministic tokens.
- Impact on security or reliability: Offline guessing risk if DB leaks and tokens are low entropy.
- Mentioned in prior review log: No.
- Previous fix claimed to address it: No.
- Previous fix sufficient: Not applicable.
- Recommended remediation: Enforce high-entropy token issuance, document requirements, or use keyed hash/pepper.
- Suggested validation or test: Credential creation rejects weak/manual low-entropy gateway tokens.
- Should affect scoring: Yes.

### SDK-AUDIT-046: Schema Validation Error Messages Can Expose Instance Values

- Category: Security / data exposure
- Severity: Medium
- Confidence: Medium
- File path or area: `tool_gateway/schemas.py`, `api/app.py`
- Evidence: Runtime schema validation forwards `ValidationError.message`; response-blocked paths can return exception messages to agents.
- Why it matters: JSON Schema validation messages may include parts of invalid upstream output or payload values.
- Root cause or likely root cause: Developer-friendly validation messages reused in agent-facing paths.
- Impact on production readiness: Medium.
- Impact on developer experience: Useful but potentially over-detailed errors.
- Impact on security or reliability: Potential sensitive data exposure in validation errors.
- Mentioned in prior review log: No.
- Previous fix claimed to address it: No.
- Previous fix sufficient: Not applicable.
- Recommended remediation: Use generic agent-facing schema errors and put sanitized details only in protected audit logs.
- Suggested validation or test: Invalid output containing secret value does not echo that value to SDK caller.
- Should affect scoring: Yes.

### SDK-AUDIT-047: JSON Schema Validators Are Instantiated On Every Runtime Validation

- Category: Performance / reliability
- Severity: Low
- Confidence: High
- File path or area: `tool_gateway/schemas.py`
- Evidence: `Draft202012Validator(schema).validate(instance)` is called per validation.
- Why it matters: Repeated validator creation adds avoidable overhead on hot paths.
- Root cause or likely root cause: Simple helper implementation.
- Impact on production readiness: Low.
- Impact on developer experience: Mostly invisible until high traffic.
- Impact on security or reliability: Performance degradation under load.
- Mentioned in prior review log: No.
- Previous fix claimed to address it: No.
- Previous fix sufficient: Not applicable.
- Recommended remediation: Cache compiled validators by schema hash/version.
- Suggested validation or test: Repeated calls reuse validators and preserve correctness.
- Should affect scoring: Minor yes.

### SDK-AUDIT-048: Direct HTTP Example Is Less Safe Than SDK

- Category: Documentation / examples
- Severity: Low
- Confidence: High
- File path or area: `packages/product-platform/examples/tool-gateway-direct-http/direct_http_requests_example.py`
- Evidence: Example performs minimal base URL handling, blindly parses JSON, and raises raw HTTP errors for non-403 errors.
- Why it matters: Users may copy the example instead of the hardened SDK behavior.
- Root cause or likely root cause: Example optimized for minimal direct HTTP demonstration.
- Impact on production readiness: Low.
- Impact on developer experience: Copied code can fail unclearly.
- Impact on security or reliability: Example lacks SDK safeguards.
- Mentioned in prior review log: Direct HTTP examples were discussed, but this gap was not.
- Previous fix claimed to address it: No.
- Previous fix sufficient: Not applicable.
- Recommended remediation: Add explicit warning that production Python agents should prefer the SDK, or harden the example.
- Suggested validation or test: Example rejects unsafe base URLs and non-JSON responses with clear diagnostics.
- Should affect scoring: Minor yes.

### SDK-AUDIT-049: Token Issuance And Setup Flow Is Underdocumented

- Category: Documentation / developer experience
- Severity: Medium
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/README.md`, `packages/product-platform/README.md`
- Evidence: README says tokens are issued by Ophanix but does not show the operator/API/CLI flow to create one.
- Why it matters: External teams cannot self-serve initial setup.
- Root cause or likely root cause: SDK usage docs were written without credential administration guide.
- Impact on production readiness: Medium.
- Impact on developer experience: Onboarding friction and support load.
- Impact on security or reliability: Users may mishandle tokens while trying to bootstrap.
- Mentioned in prior review log: Documentation expansion was claimed.
- Previous fix claimed to address it: Partial docs.
- Previous fix sufficient: No.
- Recommended remediation: Add credential issuance quickstart, scope/resource binding explanation, rotation and revocation flow.
- Suggested validation or test: New-user walkthrough creates token, lists tools, invokes tool, rotates token.
- Should affect scoring: Yes.

### SDK-AUDIT-050: Install Docs Assume Public Package Availability

- Category: Documentation / release
- Severity: Medium
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/README.md`
- Evidence: README instructs `pip install ophanix-tool-gateway-sdk`; dependency audit reports package not found on PyPI.
- Why it matters: External users may fail at the first step.
- Root cause or likely root cause: Docs were written for intended package name before publication path existed.
- Impact on production readiness: Medium.
- Impact on developer experience: Broken install path.
- Impact on security or reliability: Users may install from an unofficial or stale source if package is unavailable.
- Mentioned in prior review log: Install docs were claimed.
- Previous fix claimed to address it: Yes.
- Previous fix sufficient: No.
- Recommended remediation: Document current package index/source, publication status, or private registry configuration.
- Suggested validation or test: Fresh environment can install exactly as documented.
- Should affect scoring: Yes.

### SDK-AUDIT-051: No SDK Changelog, Migration, Deprecation, Or Security Policy In Package

- Category: Documentation / release governance
- Severity: Medium
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/`
- Evidence: No package-local `CHANGELOG.md`, `SECURITY.md`, migration notes, or compatibility/deprecation policy were found.
- Why it matters: Production consumers need upgrade guidance and vulnerability reporting path.
- Root cause or likely root cause: Package is still scaffold-level.
- Impact on production readiness: Medium.
- Impact on developer experience: Harder to adopt safely and plan upgrades.
- Impact on security or reliability: Vulnerability disclosure path unclear.
- Mentioned in prior review log: Compatibility exports were mentioned; governance docs were not.
- Previous fix claimed to address it: No.
- Previous fix sufficient: Not applicable.
- Recommended remediation: Add changelog, security policy, semantic versioning policy, and compatibility import deprecation plan.
- Suggested validation or test: Release checklist requires changelog entry and security policy link.
- Should affect scoring: Yes.

### SDK-AUDIT-052: Package Source Files Lack Repository-Standard License Headers

- Category: Compliance / maintainability
- Severity: Low
- Confidence: Medium
- File path or area: New SDK Python files
- Evidence: New files start with docstrings and do not include repo-standard copyright/license headers referenced by repository instructions.
- Why it matters: Inconsistent compliance hygiene can block enterprise review.
- Root cause or likely root cause: New files were created without header lint.
- Impact on production readiness: Low.
- Impact on developer experience: Minor review churn.
- Impact on security or reliability: No runtime impact.
- Mentioned in prior review log: No.
- Previous fix claimed to address it: No.
- Previous fix sufficient: Not applicable.
- Recommended remediation: Add standard headers or documented exemption.
- Suggested validation or test: Header lint includes SDK package files.
- Should affect scoring: Minor yes.

### SDK-AUDIT-053: Product-Platform Package Has No Explicit Sdist Include/Exclude Policy

- Category: Packaging
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/pyproject.toml`
- Evidence: Wheel packages are configured, but sdist behavior is broad enough to include DB files.
- Why it matters: Source artifacts can include unintended local state and large files.
- Root cause or likely root cause: Hatch sdist config omitted.
- Impact on production readiness: Medium.
- Impact on developer experience: Artifact contents are unpredictable.
- Impact on security or reliability: Data leakage and packaging bloat.
- Mentioned in prior review log: No.
- Previous fix claimed to address it: No.
- Previous fix sufficient: Not applicable.
- Recommended remediation: Add explicit sdist include/exclude policy and package artifact tests.
- Suggested validation or test: Product-platform sdist contains only intended source/docs/config files.
- Should affect scoring: Yes.

### SDK-AUDIT-054: Broad Dependency Ranges Are Not Locked For Release

- Category: Supply chain / reliability
- Severity: Medium
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/pyproject.toml`, `packages/product-platform/pyproject.toml`
- Evidence: Runtime dependencies use broad ranges such as `httpx>=0.27.0,<1.0` and broader product dependencies.
- Why it matters: Future dependency releases can break behavior unless release validation uses a locked/controlled set.
- Root cause or likely root cause: Library-style ranges without separate release constraints.
- Impact on production readiness: Medium.
- Impact on developer experience: Reproducibility gaps.
- Impact on security or reliability: Dependency drift can cause runtime incidents.
- Mentioned in prior review log: No.
- Previous fix claimed to address it: No.
- Previous fix sufficient: Not applicable.
- Recommended remediation: Use constraints/lock files for CI and release validation while retaining reasonable library ranges if desired.
- Suggested validation or test: CI tests minimum supported and latest allowed dependency sets.
- Should affect scoring: Yes.

### SDK-AUDIT-055: Test Suite Misses Several Proven Negative Cases

- Category: Testing
- Severity: High
- Confidence: High
- File path or area: SDK and gateway tests
- Evidence: Local probes found redaction leak, malformed description acceptance, wrong HTTP client failure, and source `0.0.0` version while all focused SDK tests still passed.
- Why it matters: Test count overstates behavioral coverage.
- Root cause or likely root cause: Tests target prior remediations but not adversarial edge cases.
- Impact on production readiness: High.
- Impact on developer experience: Regressions and edge cases reach users.
- Impact on security or reliability: Security and runtime defects remain undetected.
- Mentioned in prior review log: Prior emphasized test counts.
- Previous fix claimed to address it: Many tests were added.
- Previous fix sufficient: No.
- Recommended remediation: Add regression tests for every issue in this register.
- Suggested validation or test: New tests fail on current code for proven gaps, then pass after fixes.
- Should affect scoring: Yes.

### SDK-AUDIT-056: Server Tests Do Not Cover Failed-Response Policy Bypass

- Category: Testing / security
- Severity: High
- Confidence: High
- File path or area: `packages/product-platform/tests/test_tool_gateway_response_*.py`
- Evidence: Response policy tests pass, but `process_tool_execution_response()` bypasses all failed executions unchanged.
- Why it matters: Critical leak path is not tested.
- Root cause or likely root cause: Tests focus on successful response handling and explicit policy-block path.
- Impact on production readiness: High.
- Impact on developer experience: Operators may trust policies that fail on error responses.
- Impact on security or reliability: Failed upstream secrets can leak.
- Mentioned in prior review log: No.
- Previous fix claimed to address it: No.
- Previous fix sufficient: Not applicable.
- Recommended remediation: Add failed upstream redaction, size, and visibility policy tests.
- Suggested validation or test: Upstream 500 containing secret does not expose or persist secret.
- Should affect scoring: Yes.

### SDK-AUDIT-057: No Production Adoption Checklist

- Category: Documentation / adoption
- Severity: Medium
- Confidence: High
- File path or area: SDK README and product-platform docs
- Evidence: Docs include usage snippets but no checklist for token rotation, rate limits, timeout selection, idempotency, TLS, observability, incident handling, and upgrade policy.
- Why it matters: External teams need operational guidance before production use.
- Root cause or likely root cause: README optimized for quickstart rather than production adoption.
- Impact on production readiness: Medium.
- Impact on developer experience: Adoption requires support conversations and guesswork.
- Impact on security or reliability: Missing operational safeguards can cause incidents.
- Mentioned in prior review log: Documentation was improved generally.
- Previous fix claimed to address it: Partial.
- Previous fix sufficient: No.
- Recommended remediation: Add production adoption guide and checklist.
- Suggested validation or test: Independent team can follow docs to deploy with secure token storage, monitoring, retries, and rotation.
- Should affect scoring: Yes.

### SDK-AUDIT-058: Local Validation Is Not Equivalent To Release Validation

- Category: Process / release readiness
- Severity: High
- Confidence: High
- File path or area: Repository CI/release process
- Evidence: Local SDK tests and release validator pass, but CI/publish omit the SDK and product-platform sdist leaks DB files.
- Why it matters: Production readiness depends on reproducible enforced gates, not one-off local commands.
- Root cause or likely root cause: Remediation proceeded locally without updating repository automation.
- Impact on production readiness: High.
- Impact on developer experience: Contributors and adopters get false confidence.
- Impact on security or reliability: Critical regressions and leaks can bypass release checks.
- Mentioned in prior review log: Prior relied heavily on local validation.
- Previous fix claimed to address it: Local validation and release validator.
- Previous fix sufficient: No.
- Recommended remediation: Move all critical checks into required CI and publish workflows.
- Suggested validation or test: Protected branch cannot merge or publish SDK without tests, package checks, dependency audit, artifact denylist, and installed-wheel e2e passing.
- Should affect scoring: Yes.

## Issues Grouped By Category

CI, release, and packaging:

- SDK-AUDIT-001
- SDK-AUDIT-003
- SDK-AUDIT-004
- SDK-AUDIT-005
- SDK-AUDIT-006
- SDK-AUDIT-007
- SDK-AUDIT-008
- SDK-AUDIT-009
- SDK-AUDIT-010
- SDK-AUDIT-013
- SDK-AUDIT-050
- SDK-AUDIT-053
- SDK-AUDIT-054
- SDK-AUDIT-058

Public API and developer experience:

- SDK-AUDIT-014
- SDK-AUDIT-015
- SDK-AUDIT-016
- SDK-AUDIT-020
- SDK-AUDIT-026
- SDK-AUDIT-027
- SDK-AUDIT-028
- SDK-AUDIT-049
- SDK-AUDIT-051
- SDK-AUDIT-057

Runtime correctness:

- SDK-AUDIT-018
- SDK-AUDIT-019
- SDK-AUDIT-024
- SDK-AUDIT-025
- SDK-AUDIT-034
- SDK-AUDIT-036
- SDK-AUDIT-038
- SDK-AUDIT-047

Security:

- SDK-AUDIT-017
- SDK-AUDIT-029
- SDK-AUDIT-030
- SDK-AUDIT-031
- SDK-AUDIT-035
- SDK-AUDIT-037
- SDK-AUDIT-039
- SDK-AUDIT-044
- SDK-AUDIT-045
- SDK-AUDIT-046

Reliability and resource handling:

- SDK-AUDIT-021
- SDK-AUDIT-022
- SDK-AUDIT-023
- SDK-AUDIT-032
- SDK-AUDIT-033
- SDK-AUDIT-041
- SDK-AUDIT-042
- SDK-AUDIT-043

Testing:

- SDK-AUDIT-011
- SDK-AUDIT-012
- SDK-AUDIT-055
- SDK-AUDIT-056

Documentation, compliance, and process:

- SDK-AUDIT-002
- SDK-AUDIT-048
- SDK-AUDIT-052

## Critical And High-Severity Blockers

Critical:

- SDK-AUDIT-001: Untracked SDK package and namespace.
- SDK-AUDIT-003: CI path filters exclude product-platform and SDK.
- SDK-AUDIT-004: Publish workflow cannot publish the SDK.
- SDK-AUDIT-005: Product-platform sdist includes local SQLite database files.
- SDK-AUDIT-037: Failed upstream responses bypass response policy.

High:

- SDK-AUDIT-006
- SDK-AUDIT-012
- SDK-AUDIT-017
- SDK-AUDIT-029
- SDK-AUDIT-030
- SDK-AUDIT-031
- SDK-AUDIT-032
- SDK-AUDIT-034
- SDK-AUDIT-035
- SDK-AUDIT-038
- SDK-AUDIT-039
- SDK-AUDIT-042
- SDK-AUDIT-043
- SDK-AUDIT-055
- SDK-AUDIT-056
- SDK-AUDIT-058

## Medium-Severity Production Risks

- SDK-AUDIT-002
- SDK-AUDIT-007
- SDK-AUDIT-008
- SDK-AUDIT-009
- SDK-AUDIT-011
- SDK-AUDIT-013
- SDK-AUDIT-015
- SDK-AUDIT-018
- SDK-AUDIT-021
- SDK-AUDIT-022
- SDK-AUDIT-023
- SDK-AUDIT-024
- SDK-AUDIT-025
- SDK-AUDIT-027
- SDK-AUDIT-033
- SDK-AUDIT-036
- SDK-AUDIT-041
- SDK-AUDIT-044
- SDK-AUDIT-045
- SDK-AUDIT-046
- SDK-AUDIT-049
- SDK-AUDIT-050
- SDK-AUDIT-051
- SDK-AUDIT-053
- SDK-AUDIT-054
- SDK-AUDIT-057

## Low-Severity And Nit-Level Issues

- SDK-AUDIT-010
- SDK-AUDIT-014
- SDK-AUDIT-016
- SDK-AUDIT-019
- SDK-AUDIT-020
- SDK-AUDIT-026
- SDK-AUDIT-028
- SDK-AUDIT-040
- SDK-AUDIT-047
- SDK-AUDIT-048
- SDK-AUDIT-052

## Prior Findings Status Table

| Prior finding | Current status |
| --- | --- |
| Wrong discovery route | Appears fixed in SDK/server, but CI does not gate it. |
| Unsafe discovery response model | Mostly fixed; malformed `description` still silently accepted. |
| Weak SDK validation | Improved, but gaps remain for token type, HTTP client type, response field types, and payload size. |
| `get_tool` first-page only | Appears fixed by tests. |
| Token repr/error redaction | Improved, but colon-bearing bearer tokens partially leak. |
| Env token provider | Implemented. |
| Async SDK | Implemented, tests pass. |
| `py.typed` | Present, but no type-checker gate. |
| Cache partitioning | Implemented, but no TTL or thread safety. |
| Standalone package | Locally builds, but package/source are untracked, symlinked, and omitted from CI/publish. |
| Release validator | Exists and passes, but too shallow and not CI-enforced. |
| Scores 8.1 / 8.3 / 8.3 | Lowered due current repo evidence. |

## Scoring Matrix

### Implementation Quality

- Current score: 6.0 / 10
- Prior score: 8.1 / 10
- Direction: Lower
- Exact reasons:
  - SDK implementation is materially improved and local focused tests pass.
  - Current repository state does not prove the standalone package is committed.
  - CI and publish workflows do not cover the package.
  - Product-platform sdist leaks database artifacts.
  - Server runtime has unresolved correctness and resource lifecycle gaps.
- Score cap caused by unresolved issues: 6
- Must fix to reach next score:
  - Commit/package intended SDK files.
  - Add CI and publish coverage.
  - Remove DB artifacts.
  - Fix high runtime correctness issues.
- Must fix to reach 8:
  - Installed-wheel gateway e2e.
  - Response policy fixes.
  - Upstream auth implementation.
  - Managed resource lifecycle.
- Must fix to reach 9:
  - Mature release automation.
  - Type/SAST/SBOM gates.
  - Strong backwards compatibility policy and regression suite.

### Ease Of Use

- Current score: 6.0 / 10
- Prior score: 8.3 / 10
- Direction: Lower
- Exact reasons:
  - Sync and async clients are useful and documented.
  - Install path may not be real/publicly available.
  - Token issuance flow is underdocumented.
  - Auth errors are too coarse.
  - Direct HTTP examples are less safe than SDK.
  - Production adoption guidance is missing.
- Score cap caused by unresolved issues: 6
- Must fix to reach next score:
  - Document token issuance and package index/source.
  - Improve auth diagnostics.
  - Align examples with safe SDK behavior.
- Must fix to reach 8:
  - Complete production adoption guide.
  - Generated or comprehensive API reference.
  - Clear setup, rotation, and troubleshooting path.
- Must fix to reach 9:
  - Changelog, migration, security, and deprecation policy.
  - Stable semantic versioning and support model.

### Security And Reliability

- Current score: 5.0 / 10
- Prior score: 8.3 / 10
- Direction: Lower
- Exact reasons:
  - Failed upstream responses bypass response policies.
  - Product artifacts can leak DB files.
  - SSRF controls are missing for upstream targets.
  - Authorization ordering leaks schema/tool existence.
  - Rate/body limits are missing.
  - HTTP clients can leak resources.
  - Redaction has a proven bearer-token leak case.
  - Upstream auth modes are accepted but not implemented.
- Score cap caused by unresolved issues: 5
- Must fix to reach next score:
  - Fix critical leak paths, resource leaks, and artifact leaks.
- Must fix to reach 8:
  - SSRF controls.
  - Rate/body/idempotency safeguards.
  - Failed-response policy enforcement.
  - Production observability.
- Must fix to reach 9:
  - Formal threat model.
  - Security regression suite.
  - Dependency/SBOM/provenance gates.
  - Operational runbooks.

## Score Cap Explanation

Implementation quality is capped at 6 because the repository does not prove a
committed, CI-protected, publishable SDK package. Passing local tests cannot
override that release gap.

Ease of use is capped at 6 because install/setup and credential issuance are not
complete enough for an external team to adopt the SDK without extra help.

Security and reliability is capped at 5 because critical server-side paths can
leak data or bypass configured policy, and the release artifacts can include
local database files.

## Required Fixes To Reach Production Readiness

1. Commit or intentionally remove all SDK/package/test/doc artifacts and release
   only from a clean worktree.
2. Add `product-platform` and `ophanix-tool-gateway-sdk` to CI
   test/build/lint/security matrices.
3. Add the SDK to the publish workflow with provenance/signing and artifact
   retention.
4. Remove DB files from version control and package artifacts; add artifact
   denylist tests.
5. Apply response policy to failed upstream responses.
6. Implement or remove upstream `auth_mode`.
7. Add SSRF controls for upstream and health URLs.
8. Move authorization/resource checks before schema validation/tool-specific
   feedback.
9. Use app-lifecycle managed HTTP clients and close them.
10. Add gateway rate limits and request body limits.

## Required Fixes To Reach 8 Out Of 10

- All production-readiness fixes above.
- Installed-wheel plus running-gateway e2e in CI.
- Type checker against public SDK API.
- SDK/server contract tests for malformed response fields and error envelopes.
- Token issuance quickstart and production adoption checklist.
- Release validator with license, denylist, installed import, metadata, and
  dependency audit gates.

## Required Fixes To Reach 9 Out Of 10

- SBOM/provenance/signing for SDK release artifacts.
- Security policy, changelog, migration, and deprecation policy.
- Idempotency key contract for tool invocations.
- Observability hooks and documented operational metrics.
- Formal threat model for gateway trust boundaries.
- Cross-platform package validation and compatibility matrix.
- Strong dependency management and vulnerability remediation workflow.

## Recommended Remediation Order

1. Stop release risk: commit intended files, fix CI/publish, remove DB artifacts.
2. Fix security leaks: failed response policy, redaction regex, schema/auth
   ordering, SSRF controls.
3. Fix reliability: shared/closed clients, body limits, rate limits, payload
   summary caps.
4. Fix runtime correctness: upstream auth modes, method-specific request mapping,
   `store_full_response`.
5. Fix SDK API hardening: HTTP client validation, token type validation, stricter
   response fields.
6. Fix docs/adoption: token issuance, install source, production checklist,
   changelog/security policy.
7. Add missing tests and make all validation mandatory.

## Validation Plan

Required CI/release validations:

- `python -m unittest discover -s tests -p 'test_tool_gateway_*.py' -v`
- SDK-only tests from source and from installed wheel.
- `python -m build` for product-platform and SDK.
- SDK `scripts/validate_release.py --require-dependency-audit`.
- Artifact denylist check for `*.db*`, secrets, pycache, local backups, and
  unexpected generated files.
- Installed-wheel e2e against a real FastAPI gateway with seeded token/tool.
- SSRF tests for localhost, private IPs, metadata IPs, and rebinding-style
  targets.
- Failed-upstream response policy tests for redaction, size limit, and
  `expose_to_agent=false`.
- Type checker and import smoke across Python 3.11, 3.12, and 3.13.

## Final Strict Assessment

The SDK is usable for controlled internal testing, but the current repository
state is not ready for broad external production adoption.

The implementation has a solid foundation, but production readiness is capped by
release-process gaps, packaging hygiene failures, untracked artifacts, server
runtime security issues, resource lifecycle risks, and missing production-grade
validation.
