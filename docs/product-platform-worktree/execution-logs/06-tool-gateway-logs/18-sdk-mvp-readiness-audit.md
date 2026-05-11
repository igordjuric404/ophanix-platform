# Tool Gateway SDK Strict MVP Readiness Audit

Date: 2026-05-11

Scope: strict MVP-readiness audit of the current `ophanix-platform` Tool Gateway
SDK and its relevant server contract. Reviewed the standalone Python SDK,
product-platform compatibility exports, gateway discovery and invocation
runtime, auth and permission checks, response handling, tests, packaging, CI,
release validation, direct HTTP examples, and docs.

This is not a production-readiness certification. The standard is whether the
SDK and gateway surface are credible enough for controlled MVP evaluation by an
internal team or early design partner.

Validation run during this audit:

- `python3 -m pytest tests -q --tb=short` from `packages/ophanix-tool-gateway-sdk`: 16 passed.
- `python3 scripts/validate_release.py --out-dir /tmp/ophanix-sdk-mvp-audit --skip-twine-check` from `packages/ophanix-tool-gateway-sdk`: passed.
- `python3 scripts/validate_release.py --out-dir /tmp/ophanix-product-mvp-audit --skip-twine-check` from `packages/product-platform`: passed.
- `python3 -m pytest tests/test_tool_gateway_*.py -q --tb=short` from `packages/product-platform`: 283 passed.
- `git status --short` from repo root: clean.

Initial failed validation attempts:

- `python -m pytest ...` and `python scripts/validate_release.py ...` failed because `python` is not on PATH in this environment. Re-run with `python3` succeeded.

## Executive Summary

Current strict MVP scores:

| Category | Current score | Prior score from log 13 | Direction |
| --- | ---: | --- | --- |
| Implementation quality | 6.5 / 10 | None assigned | New score |
| Ease of use | 6.5 / 10 | None assigned | New score |
| Security and reliability | 6.0 / 10 | None assigned | New score |

The current repository is a credible controlled MVP, but it is not a clean or
low-friction external SDK release yet.

The strongest positive evidence:

- The standalone `ophanix-tool-gateway-sdk` package is present, tracked, and
  builds into wheel and sdist artifacts.
- Product-platform and standalone SDK release validators reject local/generated
  artifact leakage such as SQLite databases, `__pycache__`, and `node_modules`.
- CI now includes `packages/product-platform/**` and
  `packages/ophanix-tool-gateway-sdk/**` in Python lint, test, build, security,
  and publish-artifact paths.
- The SDK validates base URLs, payloads, response sizes, tokens, retry config,
  booleans, strict JSON values, and malformed response bodies.
- Gateway discovery uses `/api/v1/gateway/tools` and filters by authenticated
  credential, permission, scope, resource binding, and tool activity.
- Server-side upstream URL validation now rejects non-HTTPS, private, loopback,
  link-local, reserved, metadata, credential-bearing, query-bearing, and
  fragment-bearing targets, with production allowlist requirements.
- Product gateway tests are broad for an MVP: 283 tool-gateway tests passed.

The main blockers to a higher MVP score:

- Compatibility exports from `product_platform.tool_gateway` are incomplete:
  `ToolGatewayValidationError` exists in the standalone SDK but cannot be
  imported through the compatibility path.
- There is no true end-to-end SDK-to-running-gateway test that installs the
  built wheel and calls a live FastAPI/TestClient gateway through the SDK.
- The SDK package and product-platform package both ship the same
  `ophanix_tool_gateway` top-level package, creating a namespace ownership and
  install-order risk.
- Invocation has no idempotency-key contract and intentionally avoids automatic
  retries. That is acceptable for MVP safety, but it makes adoption fragile for
  unreliable networks and read-only tools that could be safely retried.
- The built-in gateway rate limiter is in-process only and explicitly lets new
  keys through once `tool_gateway_rate_limit_max_keys` is exhausted, creating a
  DoS exposure that must be handled at ingress for any broader pilot.
- Denied invocation responses disclose precise reason codes such as
  `tool_missing`, `permission_missing`, and `scope_insufficient` to any valid
  gateway credential.
- The direct HTTP example is intentionally thinner than the SDK and can teach
  weaker integration behavior if copied into production.
- Documentation tells operators the credential issuance steps conceptually, but
  does not provide a concrete API command sequence or copy-pasteable token
  issuance quickstart.

MVP conclusion: credible for controlled internal/design-partner evaluation if
operators use the SDK, a tightly scoped gateway environment, ingress rate
limits, pre-issued short-lived tokens, and source-level support. It is not yet
smooth enough to hand to arbitrary external adopters without close support.

## Prior Review Summary And Challenge

Prior file reviewed:

- `docs/product-platform-worktree/execution-logs/06-tool-gateway-logs/13-sdk-review-remediation.md`

Previously reported issues, ignoring deferred notes:

- SDK discovery called `/api/v1/tools` using gateway bearer auth even though the
  endpoint expected product-user auth.
- Gateway discovery returned operator-facing fields such as tenant IDs and
  creator metadata.
- SDK validation was weak for invalid tool names, non-JSON payloads, malformed
  successful responses, and non-local plain HTTP.
- `get_tool()` searched only the first discovery page.
- `StaticTokenProvider` repr exposed raw token material.
- SDK exceptions retained too much raw gateway/upstream response body material.
- No environment token provider existed.
- Developers had to paginate discovery manually.
- Discovery had no transient retry handling.
- Discovery cache invalidation and typed downstream integration support were
  missing.
- Payload validation accepted loose Python JSON-ish shapes, including non-string
  keys and non-finite numbers.
- Base URLs could include userinfo, query strings, or fragments.
- Header values were not consistently checked for control characters.
- Numeric configuration accepted non-finite values.
- Security-sensitive booleans accepted truthy non-booleans.
- Exception messages could include server-supplied sensitive text.
- Discovery retries ignored `Retry-After`.
- The SDK had no lightweight standalone distribution path.
- Credential scope enforcement flattened resource grants into scope strings,
  creating object-level authorization risk.
- Cache keys were not partitioned by credential context.
- Retry backoff lacked jitter.
- There was no async SDK client.
- Standalone package buildability and external docs were incomplete.

Fixes claimed:

- Added gateway-authenticated `/api/v1/gateway/tools`.
- Added a gateway-safe discovery response model.
- Added stricter SDK validation for inputs, payload JSON, responses, URLs,
  config numbers, booleans, headers, and tokens.
- Added HTTPS-by-default with localhost and explicit insecure opt-in.
- Added environment/static token providers, sanitized diagnostics, generic
  exception messages, SDK user agent, and bounded non-JSON excerpts.
- Added pagination helpers, `list_all_tools()`, cache invalidation, typed
  marker files, discovery retries, `Retry-After`, backoff caps, and jitter.
- Added credential-fingerprint cache partitioning.
- Added resource-bound credential scope enforcement.
- Added standalone `ophanix_tool_gateway` package and compatibility re-exports.
- Added async SDK client.
- Added package smoke tests, wheel validation, docs, migration notes, security
  policy, and release validation scripts.

Validation evidence claimed:

- SDK phase/remediation/package tests passed.
- Tool Gateway tests passed.
- Full product-platform tests passed in that remediation context.
- Compile checks passed.
- Wheel and import sanity checks passed.
- Release validation passed in later iterations.

Scores assigned in log 13:

- None. The file is a remediation narrative, not a scored audit.

Suspicious, under-evidenced, too lenient, or too strict prior conclusions:

- Earlier concerns that the SDK package was untracked are no longer true in the
  current repository state. `git status --short` is clean.
- Earlier concerns that product-platform sdist leaked local SQLite databases are
  no longer true in the current package validator run. The product sdist and
  wheel built during this audit contained no `.db`, `.sqlite`, or `__pycache__`
  entries.
- Prior remediation over-credits compatibility exports. The standalone SDK
  exports `ToolGatewayValidationError`, but both product compatibility paths
  omit it.
- Prior validation is still not enough for a higher score because it does not
  prove installed-wheel SDK calls against a live gateway contract.
- Prior API confidence is slightly too optimistic because two distributions
  ship the same `ophanix_tool_gateway` top-level package.
- Prior security confidence is slightly too optimistic because rate limiting is
  local/in-memory, reason-code exposure remains, and ingress/egress controls are
  still assumed for real pilots.

Areas not deeply reviewed before or still under-reviewed:

- Installed wheel invoking a real gateway endpoint.
- External package install-order behavior when both product-platform and SDK
  wheels are installed.
- Multi-worker gateway behavior and distributed rate limiting.
- Token issuance API workflow from an SDK consumer's perspective.
- Real secret-provider integrations beyond environment-based demo/provider
  paths.
- Long-running async client lifecycle and cancellation behavior under load.
- Real network TLS/proxy/corporate CA behavior.
- Contract compatibility with older/newer gateway deployments.

## Repository Surface Reviewed

Relevant SDK files:

- `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/__init__.py`
- `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py`
- `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/py.typed`
- `packages/ophanix-tool-gateway-sdk/pyproject.toml`
- `packages/ophanix-tool-gateway-sdk/scripts/validate_release.py`
- `packages/ophanix-tool-gateway-sdk/tests/test_package_smoke.py`
- `packages/ophanix-tool-gateway-sdk/tests/test_sdk_behavior.py`
- `packages/ophanix-tool-gateway-sdk/README.md`
- `packages/ophanix-tool-gateway-sdk/API_REFERENCE.md`
- `packages/ophanix-tool-gateway-sdk/MIGRATION.md`
- `packages/ophanix-tool-gateway-sdk/SECURITY.md`
- `packages/ophanix-tool-gateway-sdk/CHANGELOG.md`

Relevant product/gateway files:

- `packages/product-platform/src/ophanix_tool_gateway/`
- `packages/product-platform/src/product_platform/tool_gateway/__init__.py`
- `packages/product-platform/src/product_platform/tool_gateway/sdk.py`
- `packages/product-platform/src/product_platform/tool_gateway/auth.py`
- `packages/product-platform/src/product_platform/tool_gateway/decision.py`
- `packages/product-platform/src/product_platform/tool_gateway/health.py`
- `packages/product-platform/src/product_platform/tool_gateway/invocation.py`
- `packages/product-platform/src/product_platform/tool_gateway/models.py`
- `packages/product-platform/src/product_platform/tool_gateway/repository.py`
- `packages/product-platform/src/product_platform/tool_gateway/response.py`
- `packages/product-platform/src/product_platform/tool_gateway/runtime_audit.py`
- `packages/product-platform/src/product_platform/tool_gateway/schemas.py`
- `packages/product-platform/src/product_platform/api/app.py`
- `packages/product-platform/src/product_platform/api/settings.py`
- `packages/product-platform/pyproject.toml`
- `packages/product-platform/scripts/validate_release.py`
- `packages/product-platform/tests/test_tool_gateway_*.py`
- `packages/product-platform/examples/tool-gateway-direct-http/`
- `packages/product-platform/README.md`

Relevant CI/release/docs:

- `.github/workflows/ci.yml`
- `.github/workflows/publish.yml`
- `.github/workflows/product-platform-images.yml`
- `.github/dependabot.yml`
- `.github/CODEOWNERS`
- `.github/labeler.yml`
- `docs/product-platform-worktree/tool-gateway-threat-model.md`
- `docs/product-platform-worktree/tool-gateway-production-runbook.md`
- `docs/product-platform-worktree/execution-logs/06-tool-gateway-logs/13-sdk-review-remediation.md`
- `docs/product-platform-worktree/execution-logs/06-tool-gateway-logs/14-sdk-production-readiness-audit.md`
- `docs/product-platform-worktree/execution-logs/06-tool-gateway-logs/15-sdk-production-readiness-audit-v2.md`
- `docs/product-platform-worktree/execution-logs/06-tool-gateway-logs/16-sdk-production-readiness-audit-v3.md`
- `docs/product-platform-worktree/execution-logs/06-tool-gateway-logs/17-sdk-production-readiness-audit-v4.md`

Concise repository map:

- `packages/ophanix-tool-gateway-sdk/`: standalone SDK package, tests, docs,
  release validator.
- `packages/product-platform/src/ophanix_tool_gateway/`: product-platform copy
  of standalone SDK namespace.
- `packages/product-platform/src/product_platform/tool_gateway/`: gateway auth,
  registry, policy, invocation, response, health, runtime audit, compatibility
  SDK exports.
- `packages/product-platform/src/product_platform/api/app.py`: FastAPI gateway
  routes, middleware, body caps, rate limiting, app-state HTTP client lifecycle.
- `packages/product-platform/tests/test_tool_gateway_*.py`: broad unit/API
  tests for gateway and vendored SDK behavior.
- `.github/workflows/ci.yml` and `.github/workflows/publish.yml`: current CI,
  build, validation, SBOM, signing, and artifact handoff.

## Exhaustive Issue Register

### SDK-AUDIT-001: Compatibility Exports Omit `ToolGatewayValidationError`

- Category: Public API / compatibility
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/tool_gateway/sdk.py`, `packages/product-platform/src/product_platform/tool_gateway/__init__.py`
- Evidence: The standalone SDK exports `ToolGatewayValidationError` at `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/__init__.py:19` and `:37`. The product compatibility export files omit it at `packages/product-platform/src/product_platform/tool_gateway/sdk.py:5-18` and `:22-35`, and `packages/product-platform/src/product_platform/tool_gateway/__init__.py:5-18` and `:20-33`. Runtime verification: `from product_platform.tool_gateway import ToolGatewayValidationError` and `from product_platform.tool_gateway.sdk import ToolGatewayValidationError` both raise `ImportError`.
- Why it matters: Existing internal callers following the compatibility shim cannot catch the SDK's local validation exception by name, even though the standalone package supports it.
- Root cause or likely root cause: Compatibility re-export list was not kept in parity with standalone public exports.
- Impact on MVP readiness: Does not block standalone SDK adoption, but breaks the migration promise for internal product-platform imports.
- Impact on developer experience, if applicable: Developers using older import paths get surprising import errors and may catch broad `ValueError` or `Exception` instead.
- Impact on security or reliability, if applicable: Weakens typed handling for invalid local configuration.
- Whether it was mentioned in the prior review log: No.
- Whether a previous fix claimed to address it: Indirectly. Prior log claimed compatibility exports remained stable.
- Whether that previous fix is sufficient: No.
- Recommended remediation: Re-export `ToolGatewayValidationError` from both compatibility modules and add parity tests over `__all__`.
- Suggested validation or test: Add tests that import every standalone public symbol from `product_platform.tool_gateway` and `product_platform.tool_gateway.sdk`.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-002: No Installed-Wheel SDK Test Calls A Live Gateway Contract

- Category: Testing / contract validation
- Severity: High
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/tests/`, `packages/product-platform/tests/test_tool_gateway_sdk_remediation.py`, release validators
- Evidence: Standalone package tests use `httpx.MockTransport` and package smoke imports. Product remediation tests use `fastapi.testclient.TestClient` directly against API routes, but not the SDK client. Release validation installs/imports the wheel but does not invoke a gateway endpoint through the installed SDK.
- Why it matters: The highest-risk integration boundary is the SDK wire contract against the actual gateway. Current tests verify both sides separately, not the installed artifact using the real route shape.
- Root cause or likely root cause: Tests grew from unit and remediation phases rather than a single black-box consumer journey.
- Impact on MVP readiness: Controlled MVP is still possible, but a design partner could hit a contract mismatch that local unit tests miss.
- Impact on developer experience, if applicable: First external adopter may become the integration test.
- Impact on security or reliability, if applicable: Response/error compatibility regressions can ship despite broad unit coverage.
- Whether it was mentioned in the prior review log: No.
- Whether a previous fix claimed to address it: Package and gateway validations were claimed, but not a true installed-wheel gateway call.
- Whether that previous fix is sufficient: No.
- Recommended remediation: Add an e2e test that installs the built wheel into a temporary target, starts or mounts a test gateway, and calls discovery plus allowed/denied invocation through `OphanixToolGatewayClient`.
- Suggested validation or test: CI job: build SDK wheel, install it into a clean venv/target, run SDK against a seeded FastAPI app with real gateway tokens.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-003: Two Distributions Ship The Same `ophanix_tool_gateway` Top-Level Package

- Category: Packaging / dependency integration
- Severity: Medium
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/`, `packages/product-platform/src/ophanix_tool_gateway/`, `packages/product-platform/pyproject.toml`
- Evidence: Standalone package wheel includes `ophanix_tool_gateway`; product-platform wheel also includes `src/ophanix_tool_gateway` via `packages = ["src/product_platform", "src/ophanix_tool_gateway"]`.
- Why it matters: If consumers install both packages, Python import ownership depends on installation order and file contents. Current release validation checks parity, but this remains a brittle packaging pattern.
- Root cause or likely root cause: Product-platform needs a compatibility copy while standalone extraction is new.
- Impact on MVP readiness: Acceptable for an internal MVP if parity is enforced, but risky for broad distribution and dependency resolution.
- Impact on developer experience, if applicable: `ophanix_tool_gateway.__version__` and source location may be confusing when both packages are installed.
- Impact on security or reliability, if applicable: A stale copy in one distribution could shadow a patched copy from the other.
- Whether it was mentioned in the prior review log: Partially. Standalone extraction and compatibility were discussed.
- Whether a previous fix claimed to address it: Yes, parity validation was added.
- Whether that previous fix is sufficient: Partially. It reduces drift, but does not remove namespace ownership ambiguity.
- Recommended remediation: Prefer making product-platform depend on the standalone package, or move compatibility imports to `product_platform.tool_gateway` without shipping a second top-level `ophanix_tool_gateway` copy.
- Suggested validation or test: Install product-platform and SDK wheels in both orders in a temp environment and assert import source, version, and class identity.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-004: Invocation Has No Idempotency-Key Contract

- Category: Reliability / API contract
- Severity: Medium
- Confidence: High
- File path or area: SDK `call_tool()`, server `/api/v1/tools/{tool_name}/invoke`
- Evidence: SDK docs explicitly state tool invocations are not retried because the server contract lacks idempotency keys. `call_tool()` posts without an idempotency header or request key.
- Why it matters: Real agents operate on unreliable networks. A timeout after upstream execution leaves the caller unable to safely retry mutating tools or know if a side effect occurred.
- Root cause or likely root cause: Gateway invocation contract was designed before idempotent mutation semantics.
- Impact on MVP readiness: Acceptable for controlled MVP if tools are low-risk or manually recoverable, but it caps reliability and external readiness.
- Impact on developer experience, if applicable: SDK users must build bespoke retry rules per tool.
- Impact on security or reliability, if applicable: Duplicate side effects or lost confirmation are possible if callers retry blindly.
- Whether it was mentioned in the prior review log: Yes, deferred.
- Whether a previous fix claimed to address it: No.
- Whether that previous fix is sufficient: Not applicable.
- Recommended remediation: Add optional idempotency key support to SDK and server, persist dedupe records per credential/tool, and document retry-safe tools.
- Suggested validation or test: Simulate timeout after execution, retry with same idempotency key, and assert no duplicate upstream call.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-005: SDK Does Not Retry Safe Tool Invocations Even When Tool Contract Could Permit It

- Category: Reliability / API ergonomics
- Severity: Low
- Confidence: High
- File path or area: SDK `call_tool()`, docs
- Evidence: Discovery retries transient failures, but invocation catches `httpx.HTTPError` and immediately raises `ToolGatewayError("transport_error")`. No opt-in retry policy exists for read-only or explicitly idempotent tools.
- Why it matters: Some tools will be read-only lookups. The SDK forces every adopter to implement their own retry and backoff if they want basic transient resilience.
- Root cause or likely root cause: The SDK takes a safe default because idempotency metadata is absent.
- Impact on MVP readiness: Acceptable shortcut, but slows realistic adoption.
- Impact on developer experience, if applicable: More boilerplate and inconsistent retry behavior across agents.
- Impact on security or reliability, if applicable: Fragile under moderate real-world network blips.
- Whether it was mentioned in the prior review log: Yes, as a deferred idempotency concern.
- Whether a previous fix claimed to address it: No.
- Whether that previous fix is sufficient: Not applicable.
- Recommended remediation: After idempotency/read-only metadata exists, add opt-in invocation retry configuration gated by tool contract.
- Suggested validation or test: Mock transient 503 for a read-only tool and assert retry obeys `Retry-After`, cap, jitter, and idempotency key.
- Whether it should affect scoring: Yes, lightly.

### SDK-AUDIT-006: Built-In Gateway Rate Limiter Is Process-Local Only

- Category: Reliability / abuse resistance
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/api/app.py:767-804`, `packages/product-platform/README.md:88`
- Evidence: Rate-limit state is stored in `app.state.tool_gateway_rate_limits = {}` and guarded by an in-process `threading.Lock`. README acknowledges global edge rate limits are still required.
- Why it matters: Multi-worker, multi-pod, or restarted deployments do not share counters. A real pilot behind multiple workers can exceed intended limits.
- Root cause or likely root cause: MVP-local implementation avoids Redis or edge dependencies.
- Impact on MVP readiness: Acceptable for a single-process internal demo, but a controlled external pilot must add ingress/distributed limits.
- Impact on developer experience, if applicable: Operators may overestimate built-in protection.
- Impact on security or reliability, if applicable: DoS and brute-force token attempts can scale with worker count.
- Whether it was mentioned in the prior review log: Not in log 13.
- Whether a previous fix claimed to address it: Partial docs mention process-local behavior.
- Whether that previous fix is sufficient: No for broader MVP rollout; yes for local demo.
- Recommended remediation: Use Redis/shared rate-limit store or require deployment-level edge rate limiting in runnable configs.
- Suggested validation or test: Multi-worker test or deployment smoke that proves shared counters across two app instances.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-007: Rate-Limit Key Exhaustion Allows New Authorization Keys Through

- Category: Security / reliability
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/api/app.py:788-801`
- Evidence: When the max key budget is full, new unseen keys are explicitly allowed through without being stored: `return False, 0`.
- Why it matters: Attackers can spray many syntactically valid bearer tokens after filling the key budget, forcing authentication/database work without being rate-limited per new token.
- Root cause or likely root cause: Design prioritizes avoiding legitimate-user denial when the key table is exhausted.
- Impact on MVP readiness: Controlled MVP can tolerate this with ingress limits, but it is unsafe as the only gateway abuse control.
- Impact on developer experience, if applicable: Operators need to understand the built-in limiter is not a complete perimeter control.
- Impact on security or reliability, if applicable: Token brute force and DB load attacks remain possible.
- Whether it was mentioned in the prior review log: No.
- Whether a previous fix claimed to address it: Tests appear to validate bounded key behavior, but not the DoS implication.
- Whether that previous fix is sufficient: Partially.
- Recommended remediation: Add a separate overflow bucket per client/IP, or fail closed for new keys after budget with a carefully documented protected-key strategy.
- Suggested validation or test: Fill `tool_gateway_rate_limit_max_keys`, then send many unique valid-looking tokens and assert bounded authentication load or overflow rate limiting.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-008: Denied Invocation Responses Reveal Fine-Grained Authorization State

- Category: Security / information disclosure
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/api/app.py:3362-3402`, `packages/product-platform/src/product_platform/tool_gateway/decision.py`
- Evidence: Denied responses include exact reason codes and messages from decisions, including `tool_missing`, `permission_missing`, and `scope_insufficient`. Tests assert these reason codes in invocation responses.
- Why it matters: Any valid gateway credential can probe tool names and infer whether a tool exists, whether a permission exists with a wrong scope, or whether a resource binding is missing.
- Root cause or likely root cause: Runtime diagnostics and policy transparency are returned directly to agents.
- Impact on MVP readiness: Acceptable for trusted internal agents, concerning for external or less-trusted design partners.
- Impact on developer experience, if applicable: Useful diagnostics, but potentially too revealing.
- Impact on security or reliability, if applicable: Tool inventory enumeration risk.
- Whether it was mentioned in the prior review log: No.
- Whether a previous fix claimed to address it: No.
- Whether that previous fix is sufficient: Not applicable.
- Recommended remediation: Return a coarse agent-facing denial code such as `tool_call_denied`, while preserving detailed reason codes in audit logs/operator UI.
- Suggested validation or test: Unauthorized valid credential probes missing/existing tools and receives indistinguishable denial payloads.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-009: `get_tool()` Raises A Locally Synthesized 404 Instead Of Preserving Gateway Context

- Category: Public API / diagnostics
- Severity: Low
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py:520-542`
- Evidence: `get_tool()` paginates discovery and, if no matching tool is found, raises `ToolGatewayError("Tool not found: ...", status_code=404, code="tool_not_found")` without a gateway request ID or server response body.
- Why it matters: A missing tool may mean lack of permission, stale cache, wrong tenant, wrong credential, or actual absence. Local 404 can imply a server decision that never happened.
- Root cause or likely root cause: Convenience method is implemented entirely over list discovery.
- Impact on MVP readiness: Acceptable, but may cause source-level debugging during onboarding.
- Impact on developer experience, if applicable: Developers lose request correlation for "not found" troubleshooting.
- Impact on security or reliability, if applicable: Low direct risk.
- Whether it was mentioned in the prior review log: No.
- Whether a previous fix claimed to address it: `get_tool()` pagination was claimed.
- Whether that previous fix is sufficient: Functionally yes, diagnostically incomplete.
- Recommended remediation: Add a distinct code like `tool_not_visible` and include last discovery request metadata if available.
- Suggested validation or test: Assert `get_tool()` not-found includes safe guidance and last request correlation when gateway supplies it.
- Whether it should affect scoring: Yes, lightly.

### SDK-AUDIT-010: Standalone SDK Test Suite Is Much Thinner Than Product-Platform Vendored SDK Tests

- Category: Testing / package confidence
- Severity: Medium
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/tests/`, `packages/product-platform/tests/test_tool_gateway_sdk_phase*.py`
- Evidence: Standalone SDK package has 16 tests; product-platform has many more SDK phase tests covering async, retry, cache partitioning, validation, and redaction. The standalone release package itself does not directly own most of its behavioral tests.
- Why it matters: A contributor working only inside the standalone package could run its local tests and miss behavior covered only by product-platform tests.
- Root cause or likely root cause: SDK was extracted after product-platform tests were already written.
- Impact on MVP readiness: CI currently runs both packages, so this is not blocking, but local package confidence is weaker than it looks.
- Impact on developer experience, if applicable: Maintainers may run the smaller package tests and miss regressions.
- Impact on security or reliability, if applicable: Security-sensitive validation regressions could be missed in standalone-only local workflows.
- Whether it was mentioned in the prior review log: No.
- Whether a previous fix claimed to address it: Package smoke tests were claimed.
- Whether that previous fix is sufficient: Partially.
- Recommended remediation: Move or duplicate the full SDK behavior suite into the standalone package, leaving product-platform tests for compatibility and server contract only.
- Suggested validation or test: Standalone package `pytest tests` should cover async, retry, cache partitioning, redaction, strict JSON, response caps, custom clients, and error classes.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-011: Product README Says Compatibility Imports Continue To Work, But They Do Not Fully Work

- Category: Documentation / API consistency
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/README.md:52-60`, product compatibility exports
- Evidence: Product README says internal imports from `product_platform.tool_gateway` continue to work as compatibility exports. The example imports only a subset, but `ToolGatewayValidationError` does not work through that path.
- Why it matters: Documentation overstates compatibility and can mislead internal adopters.
- Root cause or likely root cause: Docs and exports were updated independently.
- Impact on MVP readiness: Friction for internal adopters using old import paths.
- Impact on developer experience, if applicable: Import-time failure after following migration messaging.
- Impact on security or reliability, if applicable: None direct.
- Whether it was mentioned in the prior review log: Indirectly, compatibility was claimed.
- Whether a previous fix claimed to address it: Yes.
- Whether that previous fix is sufficient: No.
- Recommended remediation: Fix exports and update docs to specify exactly which compatibility imports are supported.
- Suggested validation or test: Docs snippet test or import matrix for all documented compatibility symbols.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-012: Credential Issuance Documentation Is Conceptual, Not A Runnable Quickstart

- Category: Documentation / onboarding
- Severity: Medium
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/README.md:188-200`, `packages/product-platform/README.md:80`
- Evidence: Docs list conceptual steps for registering/selecting an agent, approving scope, binding scope, issuing bearer credentials, and storing token. They do not provide concrete API calls, CLI commands, expected request/response shapes, or a minimal setup script for a new SDK consumer.
- Why it matters: The SDK cannot be used without a gateway token. A competent engineer may still need source-level digging or operator help to get one.
- Root cause or likely root cause: Credential issuance belongs to product-platform, while SDK docs focus on consumption.
- Impact on MVP readiness: Significant onboarding drag for design partners.
- Impact on developer experience, if applicable: First-run path is incomplete.
- Impact on security or reliability, if applicable: Developers may reuse fixture tokens or hard-code tokens while figuring out issuance.
- Whether it was mentioned in the prior review log: Partially, docs were expanded.
- Whether a previous fix claimed to address it: Yes, credential issuance guidance was claimed.
- Whether that previous fix is sufficient: No.
- Recommended remediation: Add an end-to-end "create tool, grant permission, issue credential, call via SDK" quickstart with curl/CLI examples and safe fixture boundaries.
- Suggested validation or test: A docs smoke test or scripted quickstart that provisions a local credential and invokes `client.list_all_tools()`.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-013: Direct HTTP Example Lacks SDK-Equivalent Safety Controls

- Category: Developer experience / security guidance
- Severity: Low
- Confidence: High
- File path or area: `packages/product-platform/examples/tool-gateway-direct-http/direct_http_requests_example.py`
- Evidence: Direct HTTP helper posts payloads through `requests` without SDK strict JSON validation, response-size streaming cap, retry handling for discovery, typed exceptions beyond denial, or HTTPS enforcement.
- Why it matters: The README warns production agents should use the SDK, but examples are often copied into production.
- Root cause or likely root cause: Example intentionally demonstrates raw HTTP contract.
- Impact on MVP readiness: Acceptable if clearly positioned as local-only, but still a foot-gun.
- Impact on developer experience, if applicable: Users who cannot install SDK may copy weaker code.
- Impact on security or reliability, if applicable: Larger accidental response bodies, weaker validation, and plain HTTP local defaults.
- Whether it was mentioned in the prior review log: Direct HTTP examples were discussed but this residual risk was not emphasized.
- Whether a previous fix claimed to address it: Partial documentation warnings.
- Whether that previous fix is sufficient: Partially.
- Recommended remediation: Add a "do not copy for production" banner and a hardened direct HTTP variant or point exclusively to SDK for production.
- Suggested validation or test: Example lint/test asserts timeout exists, token not logged, and README warnings remain.
- Whether it should affect scoring: Yes, lightly.

### SDK-AUDIT-014: No Contract Version Negotiation Or Compatibility Probe

- Category: Public API / release compatibility
- Severity: Medium
- Confidence: High
- File path or area: SDK constants, README compatibility matrix
- Evidence: SDK hardcodes `/api/v1/gateway/tools` and `/api/v1/tools/{name}/invoke`; compatibility matrix documents expected gateway contract, but SDK does not expose a handshake, min gateway version, or compatibility check.
- Why it matters: During MVP iteration, gateway and SDK versions will drift. A client can fail at runtime with generic HTTP errors rather than a clear version mismatch.
- Root cause or likely root cause: Early SDK assumes aligned deployment.
- Impact on MVP readiness: Acceptable for same-repo internal pilots, risky for external package release.
- Impact on developer experience, if applicable: Slower debugging when SDK and gateway versions do not match.
- Impact on security or reliability, if applicable: Low direct risk, but operational reliability suffers.
- Whether it was mentioned in the prior review log: No.
- Whether a previous fix claimed to address it: No.
- Whether that previous fix is sufficient: Not applicable.
- Recommended remediation: Add a lightweight `/api/v1/gateway/capabilities` or version endpoint and SDK `check_compatibility()`.
- Suggested validation or test: SDK against incompatible mocked gateway returns a typed compatibility error with remediation guidance.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-015: SDK Public API Exposes Many Constructor Options Without A Config Object

- Category: Public API ergonomics
- Severity: Low
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py:282-303`
- Evidence: `OphanixToolGatewayClient.__init__` has 17 keyword parameters; async client mirrors the same shape.
- Why it matters: The API is discoverable enough for MVP but easy to misconfigure as reliability/security knobs grow.
- Root cause or likely root cause: Options were added incrementally during hardening.
- Impact on MVP readiness: Acceptable, but API stability risk before 1.0.
- Impact on developer experience, if applicable: Constructor is intimidating and harder to document exhaustively.
- Impact on security or reliability, if applicable: Misconfiguration risk for `allow_insecure_http`, `allow_buffered_custom_http_client`, cache, and retry knobs.
- Whether it was mentioned in the prior review log: No.
- Whether a previous fix claimed to address it: No.
- Whether that previous fix is sufficient: Not applicable.
- Recommended remediation: Add optional `ToolGatewayClientConfig` dataclass while keeping keyword args for backward compatibility.
- Suggested validation or test: Type-check config object construction and equivalence with keyword constructor.
- Whether it should affect scoring: Yes, lightly.

### SDK-AUDIT-016: `allow_buffered_custom_http_client=True` Relies Entirely On Caller Discipline

- Category: Reliability / unsafe opt-in
- Severity: Medium
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py:1298-1327`, README
- Evidence: Custom clients without `stream()` are rejected by default, but can be accepted with `allow_buffered_custom_http_client=True`. The SDK cannot prove the custom client enforces equivalent response-size limits before materializing bodies.
- Why it matters: A consumer can accidentally defeat the SDK's strongest response-size protection by using a buffered custom client.
- Root cause or likely root cause: Flexibility for custom transports/proxies.
- Impact on MVP readiness: Acceptable as explicit opt-in, but should remain a scoring concern.
- Impact on developer experience, if applicable: Users may not understand the memory-safety implication.
- Impact on security or reliability, if applicable: Large response memory pressure before SDK can inspect content.
- Whether it was mentioned in the prior review log: Custom client safety was claimed as addressed.
- Whether a previous fix claimed to address it: Yes.
- Whether that previous fix is sufficient: Mostly, but residual risk remains.
- Recommended remediation: Add a custom transport adapter interface that preserves streaming, or make buffered opt-in require a named wrapper documenting max bytes.
- Suggested validation or test: Buffered custom client returning huge body demonstrates memory behavior and documents failure mode.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-017: SDK Allows Arbitrarily Long Bearer Tokens Up To Header Library Limits

- Category: Input validation / reliability
- Severity: Low
- Confidence: Medium
- File path or area: SDK `_require_gateway_token()`, server `MAX_GATEWAY_TOKEN_LENGTH`
- Evidence: Server `parse_bearer_authorization()` enforces `MAX_GATEWAY_TOKEN_LENGTH = 4096`; SDK `_require_gateway_token()` checks content but not length.
- Why it matters: Very large token strings can create large headers and fail in HTTPX, proxies, or gateway with less clear errors.
- Root cause or likely root cause: SDK validation mirrored allowed characters but not server length.
- Impact on MVP readiness: Minor, because server rejects large tokens.
- Impact on developer experience, if applicable: Less deterministic local error.
- Impact on security or reliability, if applicable: Header bloat and transport errors.
- Whether it was mentioned in the prior review log: No.
- Whether a previous fix claimed to address it: Token validation was claimed.
- Whether that previous fix is sufficient: Partial.
- Recommended remediation: Mirror server token length limit in SDK.
- Suggested validation or test: `StaticTokenProvider("x" * 4097)` raises `ToolGatewayValidationError` before network call.
- Whether it should affect scoring: Yes, lightly.

### SDK-AUDIT-018: SDK Token Character Policy May Reject Real-World Token Formats

- Category: API compatibility / token handling
- Severity: Low
- Confidence: Medium
- File path or area: SDK `_require_gateway_token()`, server `BEARER_TOKEN_PATTERN`
- Evidence: SDK and server token regex allow `[A-Za-z0-9._~+/=-]+`; tokens containing colon, URL-safe unusual characters, or opaque provider-specific delimiters are rejected locally.
- Why it matters: If future credential issuers use opaque tokens outside this character set, clients break before a server can authenticate them.
- Root cause or likely root cause: Tight header-safety validation.
- Impact on MVP readiness: Acceptable if Ophanix controls token issuance, but an extensibility risk.
- Impact on developer experience, if applicable: Custom token providers may be surprised.
- Impact on security or reliability, if applicable: Low, strictness is safer than permissiveness.
- Whether it was mentioned in the prior review log: Token validation was claimed.
- Whether a previous fix claimed to address it: Yes.
- Whether that previous fix is sufficient: Sufficient for current issuer, not future-proof.
- Recommended remediation: Document exact token grammar in credential issuance docs or loosen to RFC-safe opaque tokens while retaining whitespace/control rejection.
- Suggested validation or test: Contract test between credential issuer output and SDK token regex.
- Whether it should affect scoring: Yes, lightly.

### SDK-AUDIT-019: Discovery Cache Can Serve Stale Authorization Data For Up To Five Minutes

- Category: Reliability / authorization freshness
- Severity: Medium
- Confidence: High
- File path or area: SDK cache defaults and README
- Evidence: `cache_tools=False` by default, but when enabled the default TTL is `300.0` seconds. Docs say callers should clear cache after urgent permission changes.
- Why it matters: If a consumer enables caching, revoked permissions or tool changes can remain visible locally until TTL expires.
- Root cause or likely root cause: Process-local cache has no server invalidation signal.
- Impact on MVP readiness: Acceptable because caching is opt-in, but hazardous if recommended for performance.
- Impact on developer experience, if applicable: Stale `get_tool()` results can confuse operators after permission changes.
- Impact on security or reliability, if applicable: SDK discovery visibility can lag revocation, though invocation should still be server-authorized.
- Whether it was mentioned in the prior review log: Cache partitioning was mentioned.
- Whether a previous fix claimed to address it: Yes, partitioning and clear method.
- Whether that previous fix is sufficient: Partial.
- Recommended remediation: Add shorter suggested TTL for sensitive deployments, server ETags/revision IDs, or revocation-aware cache invalidation.
- Suggested validation or test: Permission revoked after discovery cache; `get_tool()` stale but `call_tool()` denied; docs explain behavior.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-020: `list_all_tools()` Uses Offset Pagination Without A Stable Cursor

- Category: Runtime correctness / pagination
- Severity: Low
- Confidence: Medium
- File path or area: SDK `list_all_tools()`, repository `ORDER BY updated_at DESC, id DESC`
- Evidence: SDK increments offset by page size. Server list ordering is based on mutable `updated_at` and id. The SDK deduplicates overlapping IDs, but offset pagination can still skip or duplicate entries if tools change during traversal.
- Why it matters: Moderate real-world usage with concurrent tool changes can produce inconsistent discovery snapshots.
- Root cause or likely root cause: Simple page API lacks cursor/snapshot semantics.
- Impact on MVP readiness: Acceptable for controlled MVP with small/stable tool sets.
- Impact on developer experience, if applicable: Rare "missing tool" confusion during active admin changes.
- Impact on security or reliability, if applicable: Low direct security impact.
- Whether it was mentioned in the prior review log: `get_tool()` pagination was discussed.
- Whether a previous fix claimed to address it: Partial pagination hardening.
- Whether that previous fix is sufficient: Partial.
- Recommended remediation: Add cursor-based discovery or stable sort by immutable id with snapshot timestamp.
- Suggested validation or test: Mutate tool ordering between pages and assert cursor pagination is stable.
- Whether it should affect scoring: Yes, lightly.

### SDK-AUDIT-021: Owner-Team Discovery Filter Is Exact And Case-Sensitive

- Category: API ergonomics / discoverability
- Severity: Low
- Confidence: Medium
- File path or area: `ToolRegistryRepository.list_tools_for_gateway_principal()`, `list_tools(owner_team=...)`
- Evidence: Operator list code uses `owner_team = ?`; gateway discovery owner-team filter uses repository SQL filter. Docs do not clarify case sensitivity or canonical owner-team values.
- Why it matters: Developers may fail to discover tools due to casing or display-name mismatch.
- Root cause or likely root cause: Direct database filter.
- Impact on MVP readiness: Minor DX issue.
- Impact on developer experience, if applicable: Confusing empty lists.
- Impact on security or reliability, if applicable: None direct.
- Whether it was mentioned in the prior review log: No.
- Whether a previous fix claimed to address it: No.
- Whether that previous fix is sufficient: Not applicable.
- Recommended remediation: Document exact matching or normalize owner-team values consistently.
- Suggested validation or test: Discovery with `Claims` vs `claims` expected behavior is asserted and documented.
- Whether it should affect scoring: Yes, lightly.

### SDK-AUDIT-022: Response Redaction Defaults Depend On Per-Tool Policy Configuration

- Category: Security / data handling
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/tool_gateway/response.py`
- Evidence: `process_tool_execution_response()` applies redaction rules from `policy["redaction_rules_json"]`. If rules are empty, successful upstream response bodies are exposed unless `expose_to_agent` is false or output schema/size blocks them.
- Why it matters: Tool authors can accidentally expose sensitive upstream fields if response policies are not configured carefully.
- Root cause or likely root cause: Redaction policy is configurable rather than default deny for common secret fields.
- Impact on MVP readiness: Acceptable for internal curated tools, risky for arbitrary partner upstreams.
- Impact on developer experience, if applicable: Tool operators must know to configure redaction rules.
- Impact on security or reliability, if applicable: Potential PII/secret exposure to agents.
- Whether it was mentioned in the prior review log: Redaction was discussed.
- Whether a previous fix claimed to address it: Yes, response handling/redaction.
- Whether that previous fix is sufficient: Partial; engine exists, safe defaults remain policy-dependent.
- Recommended remediation: Seed default redaction keys/patterns for common sensitive fields in every response policy.
- Suggested validation or test: New tool default policy redacts `token`, `secret`, `password`, `api_key` fields without operator customization.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-023: Failed Upstream Calls Still Return A Result Envelope

- Category: API clarity / runtime behavior
- Severity: Low
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/api/app.py:3615-3650`
- Evidence: When `ToolExecutionResult.status == "failed"`, the gateway returns HTTP 502 with both `result=result` and `error=execution.error`. Body is nulled and `exposed_to_agent=False`, but result metadata still appears.
- Why it matters: SDK consumers may incorrectly inspect `result` on exceptions or direct HTTP callers may treat a populated `result` as partial success.
- Root cause or likely root cause: Response envelope preserves execution diagnostics for failed calls.
- Impact on MVP readiness: Acceptable, but response contract is a bit ambiguous.
- Impact on developer experience, if applicable: Direct HTTP clients need careful error handling.
- Impact on security or reliability, if applicable: Low, body is hidden.
- Whether it was mentioned in the prior review log: Prior production audit raised failed response policy concerns; current code mitigates body exposure.
- Whether a previous fix claimed to address it: Yes.
- Whether that previous fix is sufficient: Mostly, but contract clarity remains.
- Recommended remediation: For failed upstream responses, omit `result` or move metadata into a clearly non-success `diagnostics` field.
- Suggested validation or test: Direct HTTP failed-upstream example asserts no success-like result is returned.
- Whether it should affect scoring: Yes, lightly.

### SDK-AUDIT-024: SDK Treats Generic 403 Differently From Policy Denial

- Category: Error model / ergonomics
- Severity: Low
- Confidence: High
- File path or area: SDK `_raise_denied()`, tests
- Evidence: A 403 with `decision` and `reason_code` raises `ToolDeniedError`; a generic 403 raises `ToolGatewayError`.
- Why it matters: This is correct technically, but can surprise callers expecting every 403 to be a denial.
- Root cause or likely root cause: Gateway policy denials have a structured envelope; proxy/server 403s do not.
- Impact on MVP readiness: Acceptable with docs.
- Impact on developer experience, if applicable: Callers must catch both `ToolDeniedError` and `ToolGatewayError` for 403 paths.
- Impact on security or reliability, if applicable: Low.
- Whether it was mentioned in the prior review log: No.
- Whether a previous fix claimed to address it: No.
- Whether that previous fix is sufficient: Not applicable.
- Recommended remediation: Document this distinction in API reference and expose helper predicates or `is_policy_denial`.
- Suggested validation or test: Docs example catches generic `ToolGatewayError` and branches on `status_code == 403`.
- Whether it should affect scoring: Yes, lightly.

### SDK-AUDIT-025: `ToolDefinition.raw` Can Preserve Extra Gateway Fields Indefinitely

- Category: API surface / data exposure
- Severity: Low
- Confidence: Medium
- File path or area: SDK `ToolDefinition.raw`
- Evidence: SDK stores the entire gateway discovery item in `raw`. Current gateway discovery model is narrow, but future added fields will be exposed through `raw` even if not first-class SDK fields.
- Why it matters: A future server-side field addition could silently become accessible to agents.
- Root cause or likely root cause: SDK preserves raw responses for diagnostics/extensibility.
- Impact on MVP readiness: Acceptable, but should be treated as part of the public data exposure surface.
- Impact on developer experience, if applicable: Useful escape hatch.
- Impact on security or reliability, if applicable: Future least-privilege risk.
- Whether it was mentioned in the prior review log: Gateway-safe discovery shape was mentioned.
- Whether a previous fix claimed to address it: Yes, narrowed model.
- Whether that previous fix is sufficient: Current state yes, future risk remains.
- Recommended remediation: Document `raw` as safe-discovery-only and add server tests preventing sensitive fields in gateway discovery payloads.
- Suggested validation or test: Discovery response never includes organization, environment, creator, internal policy IDs, or secret refs, including in raw SDK mapping.
- Whether it should affect scoring: Yes, lightly.

### SDK-AUDIT-026: Async SDK Uses Threading Lock Inside Async Methods

- Category: Async runtime / maintainability
- Severity: Low
- Confidence: Medium
- File path or area: `AsyncOphanixToolGatewayClient` cache handling
- Evidence: Async client uses `threading.RLock()` for cache protection, same as sync client.
- Why it matters: The lock is held around small in-memory operations, so it is unlikely to block meaningfully, but it is not idiomatic async and could become problematic if code inside the lock grows.
- Root cause or likely root cause: Sync and async clients share cache implementation.
- Impact on MVP readiness: Acceptable.
- Impact on developer experience, if applicable: Minimal.
- Impact on security or reliability, if applicable: Low risk of event-loop blocking under high concurrency.
- Whether it was mentioned in the prior review log: No.
- Whether a previous fix claimed to address it: Async SDK was claimed.
- Whether that previous fix is sufficient: Functionally yes, stylistically imperfect.
- Recommended remediation: Keep locked sections minimal or switch async client to `asyncio.Lock` with separated sync/async cache helpers.
- Suggested validation or test: Concurrent async discovery stress test with cache enabled.
- Whether it should affect scoring: Yes, lightly.

### SDK-AUDIT-027: Async SDK Does Not Document Cancellation Semantics

- Category: Documentation / async reliability
- Severity: Low
- Confidence: Medium
- File path or area: `packages/ophanix-tool-gateway-sdk/README.md`, `AsyncOphanixToolGatewayClient`
- Evidence: Async usage is documented, but cancellation behavior during request streaming, retry sleep, and context manager cleanup is not described.
- Why it matters: Async agent frameworks commonly cancel tasks. Users need to know whether calls can be safely cancelled and whether clients remain usable.
- Root cause or likely root cause: Async API was added after sync docs.
- Impact on MVP readiness: Minor for controlled usage.
- Impact on developer experience, if applicable: Source-level debugging if cancellation leaves uncertain state.
- Impact on security or reliability, if applicable: Low to medium under load.
- Whether it was mentioned in the prior review log: No.
- Whether a previous fix claimed to address it: Async SDK docs were claimed.
- Whether that previous fix is sufficient: Partial.
- Recommended remediation: Document cancellation expectations and add tests for cancellation during retry sleep and streaming response.
- Suggested validation or test: Cancel `list_tools()` during retry sleep and assert client can be closed/reused predictably.
- Whether it should affect scoring: Yes, lightly.

### SDK-AUDIT-028: Publish Workflow Builds And Signs Artifacts But Explicitly Does Not Publish Python Packages

- Category: Release / operational readiness
- Severity: Medium
- Confidence: High
- File path or area: `.github/workflows/publish.yml`
- Evidence: Workflow comments state actual PyPI publishing is intentionally outside the build job and reference an internal handoff. It builds, validates, signs, attests, and uploads artifacts.
- Why it matters: For an external design partner, "pip install" depends on an out-of-band release process not proven by the repository alone.
- Root cause or likely root cause: Organizational publishing requirements.
- Impact on MVP readiness: Acceptable for internal artifact handoff, weak for public/external install flow.
- Impact on developer experience, if applicable: Package may be buildable but unavailable on the expected index.
- Impact on security or reliability, if applicable: Manual handoff can introduce process drift unless tightly controlled.
- Whether it was mentioned in the prior review log: Standalone packaging was discussed.
- Whether a previous fix claimed to address it: Release validation claimed, not actual publishing.
- Whether that previous fix is sufficient: Partial.
- Recommended remediation: Document the exact package index and publication process for MVP consumers; add a dry-run publish/provenance checklist.
- Suggested validation or test: Release rehearsal that produces an installable artifact in the actual internal package index.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-029: Package Version Is Static `0.1.0` With No Visible Automated Version Bump Policy

- Category: Release / versioning
- Severity: Low
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/pyproject.toml`, `CHANGELOG.md`
- Evidence: SDK version is `0.1.0`; changelog has initial release notes. No automated versioning policy or release note gate is evident for SDK changes.
- Why it matters: MVP iteration can produce incompatible builds with the same version if release discipline is manual.
- Root cause or likely root cause: Early package lifecycle.
- Impact on MVP readiness: Minor for internal pilots, risky for external artifacts.
- Impact on developer experience, if applicable: Harder to debug which SDK behavior a partner has installed.
- Impact on security or reliability, if applicable: Patch tracking ambiguity.
- Whether it was mentioned in the prior review log: No.
- Whether a previous fix claimed to address it: No.
- Whether that previous fix is sufficient: Not applicable.
- Recommended remediation: Add release checklist requiring version bump, changelog entry, tag, and strict-git validation.
- Suggested validation or test: CI/release check fails if SDK source changes without changelog/version decision.
- Whether it should affect scoring: Yes, lightly.

### SDK-AUDIT-030: Product README Admits SQLite Runtime Remains The Worktree Baseline

- Category: Runtime persistence / adoption
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/README.md:100`
- Evidence: README states product runtime remains SQLite-backed in this worktree and broad production adoption needs managed database, backup/restore, and multi-worker/load validation.
- Why it matters: Tool Gateway server-side behavior is part of the SDK MVP. SQLite is acceptable for local demos but constrains concurrent pilot reliability.
- Root cause or likely root cause: Product platform remains a local/demo-first control plane.
- Impact on MVP readiness: Controlled single-node MVP is credible; broader internal/external rollout is constrained.
- Impact on developer experience, if applicable: Operators must know the deployment envelope.
- Impact on security or reliability, if applicable: Durability, concurrency, backup/restore, and multi-worker risks.
- Whether it was mentioned in the prior review log: Not as a scored issue.
- Whether a previous fix claimed to address it: No.
- Whether that previous fix is sufficient: Not applicable.
- Recommended remediation: Provide a Postgres-backed deployment recipe and run gateway test suite against it.
- Suggested validation or test: Tool Gateway API tests against Postgres or managed DB test container.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-031: Gateway Runtime Has No Circuit Breaker For Repeated Upstream Failures

- Category: Reliability
- Severity: Medium
- Confidence: Medium
- File path or area: `AsyncHttpToolInvocationExecutor`, upstream health/status handling
- Evidence: Executor checks configured target status and fails closed when `status == "unhealthy"`, but repeated live invocation failures do not appear to update target status or trip an automatic circuit breaker.
- Why it matters: A degraded upstream can be hammered by agents until health checks or manual status updates intervene.
- Root cause or likely root cause: Health checking and invocation failure handling are separate.
- Impact on MVP readiness: Acceptable for low-volume controlled pilots, fragile under moderate usage.
- Impact on developer experience, if applicable: Operators must manually correlate failures and disable targets.
- Impact on security or reliability, if applicable: Upstream overload and noisy failures.
- Whether it was mentioned in the prior review log: No.
- Whether a previous fix claimed to address it: Upstream health was implemented, not circuit breaking.
- Whether that previous fix is sufficient: Partial.
- Recommended remediation: Track rolling upstream failures and automatically degrade/disable or pause forwarding according to policy.
- Suggested validation or test: Consecutive upstream timeouts trigger a degraded/unhealthy state and block later calls until recovery.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-032: Health Checks Do Not Enforce Response Body Size Caps

- Category: Reliability / resource safety
- Severity: Low
- Confidence: Medium
- File path or area: `packages/product-platform/src/product_platform/tool_gateway/health.py`
- Evidence: Health checker calls `http_client.get(health["health_url"], timeout=timeout_seconds)` and only inspects `response.status_code`; no streaming response cap is applied.
- Why it matters: A malicious or broken health endpoint could return a very large body. HTTPX may buffer it before status inspection.
- Root cause or likely root cause: Health probes were treated as lightweight status checks.
- Impact on MVP readiness: Low risk if health URLs are operator-controlled and allowlisted.
- Impact on developer experience, if applicable: Unexpected memory use during health checks.
- Impact on security or reliability, if applicable: Resource exhaustion risk from misbehaving health endpoint.
- Whether it was mentioned in the prior review log: No.
- Whether a previous fix claimed to address it: No.
- Whether that previous fix is sufficient: Not applicable.
- Recommended remediation: Use streaming HEAD/GET with body discard and byte cap for health checks.
- Suggested validation or test: Health endpoint with huge body does not materialize beyond configured cap.
- Whether it should affect scoring: Yes, lightly.

### SDK-AUDIT-033: Upstream Host Validation Depends On DNS Resolution At Write/Runtime Time

- Category: Security / SSRF residual risk
- Severity: Medium
- Confidence: Medium
- File path or area: `packages/product-platform/src/product_platform/tool_gateway/models.py`
- Evidence: `validate_http_url()` rejects hostnames that resolve to forbidden addresses during validation, and runtime revalidates persisted URLs. DNS can change between validation and connection.
- Why it matters: DNS rebinding or split-horizon changes can bypass validation unless egress firewall/network policy also blocks private destinations.
- Root cause or likely root cause: Application-layer SSRF validation cannot fully replace network egress controls.
- Impact on MVP readiness: Acceptable with controlled allowlists and egress firewall; not enough alone for broader external usage.
- Impact on developer experience, if applicable: Operators must configure network controls beyond app settings.
- Impact on security or reliability, if applicable: SSRF/private network access residual risk.
- Whether it was mentioned in the prior review log: SSRF concerns were part of later audits, not log 13.
- Whether a previous fix claimed to address it: URL validation and allowlists were implemented.
- Whether that previous fix is sufficient: Partial.
- Recommended remediation: Enforce egress network policies, resolve/connect pinning where practical, and document DNS rebinding limitations.
- Suggested validation or test: Security test with hostname changing from public to private address is blocked by egress policy or runtime resolver strategy.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-034: Local/Test Environments Allow Unresolved Upstream Hostnames By Default

- Category: Security / environment drift
- Severity: Low
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/tool_gateway/models.py`
- Evidence: `_allow_unresolved_upstream_hosts()` returns true for development/dev/local/test by default.
- Why it matters: Local/test behavior can accept targets that production rejects, hiding deployment-time failures until late.
- Root cause or likely root cause: Local development convenience.
- Impact on MVP readiness: Acceptable for local MVP, but can surprise early deployments.
- Impact on developer experience, if applicable: "Works locally, fails in staging/prod" risk.
- Impact on security or reliability, if applicable: Lower security parity in non-prod.
- Whether it was mentioned in the prior review log: No.
- Whether a previous fix claimed to address it: Production startup rejects unresolved-host bypass.
- Whether that previous fix is sufficient: Mostly for production, not for parity.
- Recommended remediation: Add a stricter staging mode and document local-only unresolved behavior in target creation errors.
- Suggested validation or test: Same unresolved target accepted in local but rejected in production/staging, with clear docs.
- Whether it should affect scoring: Yes, lightly.

### SDK-AUDIT-035: Runtime Action Payload Summary Stores Request Payload Before Schema Validation

- Category: Data handling / audit
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/api/app.py:3415-3427`, `ToolRuntimeActionCreate(payload_summary=body.payload)`
- Evidence: On schema validation failure, the runtime action stores `payload_summary=body.payload`. Runtime repository may redact/summarize, but this route passes the raw payload object into audit creation.
- Why it matters: Invalid payloads often contain accidental sensitive data. The safety depends on repository-side summarization/redaction, not the call-site.
- Root cause or likely root cause: Runtime action constructor accepts payload summary and relies on downstream sanitization.
- Impact on MVP readiness: Needs verification before broader pilots; tests show some redaction paths, but this call-site is easy to misuse.
- Impact on developer experience, if applicable: Operators may see unexpected audit payload shape.
- Impact on security or reliability, if applicable: Potential sensitive data in audit records if repository redaction is incomplete.
- Whether it was mentioned in the prior review log: Redaction was discussed generally.
- Whether a previous fix claimed to address it: Partial runtime audit redaction.
- Whether that previous fix is sufficient: Needs targeted validation.
- Recommended remediation: Rename field to `payload` or force explicit `summarize_tool_payload()` call at every call-site before persistence.
- Suggested validation or test: Invalid schema payload containing `api_key`, `token`, nested secret-like values never appears raw in runtime action rows.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-036: Error-Body Sanitization Is Bounded But Still Keeps Arbitrary Non-Sensitive Upstream Text

- Category: Security / logging
- Severity: Low
- Confidence: Medium
- File path or area: SDK `_sanitize_error_body()`, `ToolGatewayError.response_body`
- Evidence: SDK redacts known sensitive keys and patterns, truncates strings and depth, and uses generic exception messages. Non-sensitive arbitrary strings remain in `response_body`.
- Why it matters: PII that does not match sensitive key/pattern heuristics can still appear in application logs if callers log `response_body`.
- Root cause or likely root cause: Diagnostic usefulness balanced against redaction.
- Impact on MVP readiness: Acceptable if users follow docs, but still a logging risk.
- Impact on developer experience, if applicable: Helpful debugging.
- Impact on security or reliability, if applicable: PII leakage via application logs.
- Whether it was mentioned in the prior review log: Yes, exception body redaction.
- Whether a previous fix claimed to address it: Yes.
- Whether that previous fix is sufficient: Partial.
- Recommended remediation: Add optional `include_response_body=False` or configurable diagnostic redaction policy for strict environments.
- Suggested validation or test: Error body containing generic PII-like fields such as `email` and `ssn` is redacted by default or documented.
- Whether it should affect scoring: Yes, lightly.

### SDK-AUDIT-037: `EnvironmentTokenProvider` Reads Environment On Every Request

- Category: Runtime behavior / token lifecycle
- Severity: Low
- Confidence: High
- File path or area: `EnvironmentTokenProvider.get_token()`
- Evidence: Provider calls `os.environ.get(env_var)` every time `get_token()` is invoked.
- Why it matters: This supports rotation, but process environment mutation at runtime is not a robust secret-rotation mechanism and can cause per-request token changes within a running process.
- Root cause or likely root cause: Simple MVP provider.
- Impact on MVP readiness: Acceptable.
- Impact on developer experience, if applicable: Developers may assume it is a full secret-manager integration.
- Impact on security or reliability, if applicable: Token rotation semantics are weak; use custom providers for real stores.
- Whether it was mentioned in the prior review log: Environment provider was claimed.
- Whether a previous fix claimed to address it: Yes.
- Whether that previous fix is sufficient: Sufficient for MVP, not robust rotation.
- Recommended remediation: Add a documented secret-manager provider pattern with caching/refresh semantics.
- Suggested validation or test: Example custom provider refreshes token before expiry.
- Whether it should affect scoring: Yes, lightly.

### SDK-AUDIT-038: Event Hook Telemetry Is Too Minimal For Performance Diagnosis

- Category: Observability / DX
- Severity: Low
- Confidence: High
- File path or area: SDK `_emit_event()` payloads
- Evidence: SDK emits start/success/denied/error events with tool name, request/correlation IDs, reason/status/code, but no elapsed duration or retry attempt count.
- Why it matters: Early adopters debugging latency, retries, or gateway slowness need timing without wrapping every SDK call.
- Root cause or likely root cause: Hook designed to avoid payload/token exposure and stay simple.
- Impact on MVP readiness: Not blocking.
- Impact on developer experience, if applicable: More custom instrumentation required.
- Impact on security or reliability, if applicable: Lower operational visibility.
- Whether it was mentioned in the prior review log: Event hook was later added, not in log 13.
- Whether a previous fix claimed to address it: Partial.
- Whether that previous fix is sufficient: Functional but minimal.
- Recommended remediation: Add safe elapsed milliseconds, retry count for discovery, and final status to events.
- Suggested validation or test: Event hook receives no payload/token but includes latency and retry metadata.
- Whether it should affect scoring: Yes, lightly.

### SDK-AUDIT-039: No Framework-Specific Integration Examples For Common Agent Runtimes

- Category: Developer experience / adoption
- Severity: Low
- Confidence: High
- File path or area: SDK docs/examples
- Evidence: SDK README has generic sync and async examples only. No LangGraph, OpenAI Agents, CrewAI, or FastAPI worker examples show practical token provider and error handling integration.
- Why it matters: SDK consumers are likely agent developers. Generic examples are enough for competent engineers, but framework examples would reduce onboarding time.
- Root cause or likely root cause: SDK is new.
- Impact on MVP readiness: Acceptable.
- Impact on developer experience, if applicable: Slower adoption by early teams.
- Impact on security or reliability, if applicable: Users may implement ad hoc lifecycle/token handling.
- Whether it was mentioned in the prior review log: No.
- Whether a previous fix claimed to address it: Docs were expanded generally.
- Whether that previous fix is sufficient: Partial.
- Recommended remediation: Add one async agent framework example and one worker/service lifecycle example.
- Suggested validation or test: Example files are executed or type-checked in CI.
- Whether it should affect scoring: Yes, lightly.

### SDK-AUDIT-040: Migration Notes Do Not State A Removal Timeline For Compatibility Shims

- Category: Documentation / API stability
- Severity: Nit
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/MIGRATION.md`, README stability section
- Evidence: Docs say `product_platform.tool_gateway` is a compatibility shim and should not be used for new integrations, but no removal version or support horizon is stated.
- Why it matters: Internal consumers cannot plan migration urgency.
- Root cause or likely root cause: Pre-1.0 package lifecycle.
- Impact on MVP readiness: Minor.
- Impact on developer experience, if applicable: Unclear deprecation planning.
- Impact on security or reliability, if applicable: None direct.
- Whether it was mentioned in the prior review log: Compatibility shims were mentioned.
- Whether a previous fix claimed to address it: Partial.
- Whether that previous fix is sufficient: Mostly for MVP.
- Recommended remediation: Add "supported through 0.x" or a specific removal target.
- Suggested validation or test: Docs lint/check for migration support statement.
- Whether it should affect scoring: No, except slight DX.

### SDK-AUDIT-041: Labeler And CODEOWNERS Do Not Name Product Platform Or SDK Explicitly

- Category: Governance / maintenance
- Severity: Low
- Confidence: High
- File path or area: `.github/labeler.yml`, `.github/CODEOWNERS`
- Evidence: CI and Dependabot include product-platform and SDK, but labeler lacks package labels for them, and CODEOWNERS package-specific list omits `/packages/product-platform/` and `/packages/ophanix-tool-gateway-sdk/`.
- Why it matters: Review routing and triage labels may be weaker than CI enforcement.
- Root cause or likely root cause: New packages were added to workflows but not all repo governance files.
- Impact on MVP readiness: Not blocking, but weakens maintenance readiness.
- Impact on developer experience, if applicable: PRs may be mislabeled or miss package-specific reviewers.
- Impact on security or reliability, if applicable: Security-sensitive gateway changes still fall under broad owners, but not explicit package ownership.
- Whether it was mentioned in the prior review log: No.
- Whether a previous fix claimed to address it: No.
- Whether that previous fix is sufficient: Not applicable.
- Recommended remediation: Add labeler entries and CODEOWNERS package paths for both product-platform and SDK.
- Suggested validation or test: Labeler dry run on SDK/product paths.
- Whether it should affect scoring: Yes, lightly.

### SDK-AUDIT-042: Release Validation Skips `twine check` In The Audit Command Unless Tooling Is Installed

- Category: Release validation
- Severity: Low
- Confidence: High
- File path or area: Release validation scripts and local audit run
- Evidence: This audit used `--skip-twine-check` to avoid depending on local release extras. CI/publish runs install release extras and call validators without skipping, but local validation can pass shape checks without metadata validation.
- Why it matters: Local maintainers may think artifacts are fully release-validated when metadata checks were skipped.
- Root cause or likely root cause: Validator supports partial local validation.
- Impact on MVP readiness: Low, because CI covers it.
- Impact on developer experience, if applicable: Ambiguous local confidence.
- Impact on security or reliability, if applicable: Low.
- Whether it was mentioned in the prior review log: Release validation was claimed.
- Whether a previous fix claimed to address it: Yes.
- Whether that previous fix is sufficient: Mostly.
- Recommended remediation: Make validator output a clear warning and manifest flag when twine check is skipped.
- Suggested validation or test: `--skip-twine-check` manifest records incomplete metadata validation.
- Whether it should affect scoring: No or minor.

### SDK-AUDIT-043: Product Gateway Tests Are Strong But Mostly Mocked/Local

- Category: Testing / realism
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/tests/test_tool_gateway_*.py`
- Evidence: Tests use in-process test databases, FastAPI TestClient, fake HTTP clients, and mock transports. No real network gateway, real TLS, real reverse proxy, or multi-process deployment is validated in this audit.
- Why it matters: MVP adopters will run through proxies, TLS termination, real DNS, and possibly multiple workers.
- Root cause or likely root cause: Unit/API tests optimize speed and determinism.
- Impact on MVP readiness: Controlled MVP is fine, but operational risk remains.
- Impact on developer experience, if applicable: Deployment bugs may appear only during pilot setup.
- Impact on security or reliability, if applicable: Proxy header, TLS, body size, timeout, and rate-limit behavior may differ.
- Whether it was mentioned in the prior review log: Validation was local.
- Whether a previous fix claimed to address it: Local tests claimed.
- Whether that previous fix is sufficient: Partial.
- Recommended remediation: Add a docker-compose or ephemeral integration smoke with real ASGI server, TLS/ingress-like proxy, SDK wheel, and seeded gateway.
- Suggested validation or test: End-to-end smoke in CI or nightly using `uvicorn` and SDK wheel.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-044: API Reference Does Not Fully Document Event Hook Event Schemas

- Category: Documentation / observability
- Severity: Low
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/API_REFERENCE.md`, README
- Evidence: Constructor mentions `event_hook`, but there is no table of event names and fields.
- Why it matters: Consumers cannot reliably type or process telemetry events.
- Root cause or likely root cause: Event hook added as lightweight supportability feature.
- Impact on MVP readiness: Minor.
- Impact on developer experience, if applicable: Trial-and-error instrumentation.
- Impact on security or reliability, if applicable: Lower observability consistency.
- Whether it was mentioned in the prior review log: No.
- Whether a previous fix claimed to address it: Event hook added later.
- Whether that previous fix is sufficient: Partial.
- Recommended remediation: Document event names, field meanings, stability, and no-payload/no-token guarantee.
- Suggested validation or test: Snapshot event schema tests and docs table.
- Whether it should affect scoring: Yes, lightly.

### SDK-AUDIT-045: API Reference Does Not Document Response Body Redaction Limits

- Category: Documentation / security
- Severity: Low
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/API_REFERENCE.md`, SDK constants
- Evidence: API reference says `response_body` is sanitized, but does not document max string length, item cap, depth cap, or redaction heuristics.
- Why it matters: Security reviewers and SDK consumers cannot easily assess what "sanitized" means without source code.
- Root cause or likely root cause: Docs focus on usage rather than security internals.
- Impact on MVP readiness: Minor but relevant for design partners reviewing logging posture.
- Impact on developer experience, if applicable: Source-level inspection required.
- Impact on security or reliability, if applicable: Misuse of diagnostics in logs.
- Whether it was mentioned in the prior review log: Redaction was claimed.
- Whether a previous fix claimed to address it: Yes.
- Whether that previous fix is sufficient: Code mostly yes, docs partial.
- Recommended remediation: Add a security diagnostics section describing redaction keys/patterns and bounded limits.
- Suggested validation or test: Docs include constants or policy names checked by a simple doc test.
- Whether it should affect scoring: Yes, lightly.

### SDK-AUDIT-046: `list_tools(status="active")` Remains In Public Signature Despite Being Deprecated

- Category: Public API stability
- Severity: Low
- Confidence: High
- File path or area: SDK `list_tools()` and API reference
- Evidence: `list_tools(status: Literal["active"] | None = None, ...)` remains documented and emits a deprecation warning when provided.
- Why it matters: Carrying a deprecated parameter in a 0.1 SDK entrenches compatibility debt early.
- Root cause or likely root cause: Migration support for old operator-style discovery API.
- Impact on MVP readiness: Acceptable.
- Impact on developer experience, if applicable: Users may copy the deprecated argument from type hints or old code.
- Impact on security or reliability, if applicable: None direct.
- Whether it was mentioned in the prior review log: Yes, active-only discovery and compatibility were discussed.
- Whether a previous fix claimed to address it: Yes.
- Whether that previous fix is sufficient: Sufficient for compatibility, not ideal for clean API.
- Recommended remediation: Add removal target and avoid showing `status` in quickstart examples.
- Suggested validation or test: Deprecation warning test exists; add migration timeline docs.
- Whether it should affect scoring: Yes, lightly.

### SDK-AUDIT-047: No Explicit Public API Stability Tests For Constructor Signature

- Category: Testing / API stability
- Severity: Low
- Confidence: Medium
- File path or area: SDK tests
- Evidence: Tests instantiate clients with many options, but there is no golden test for public constructor signatures, `__all__`, dataclass fields, or error attributes.
- Why it matters: Pre-1.0 SDKs can still break MVP adopters if supported surface shifts unexpectedly.
- Root cause or likely root cause: Behavior tests rather than API snapshot tests.
- Impact on MVP readiness: Minor.
- Impact on developer experience, if applicable: Integrations can break after small refactors.
- Impact on security or reliability, if applicable: Low.
- Whether it was mentioned in the prior review log: No.
- Whether a previous fix claimed to address it: No.
- Whether that previous fix is sufficient: Not applicable.
- Recommended remediation: Add public API snapshot tests for exports, signatures, dataclass fields, and exception attributes.
- Suggested validation or test: `inspect.signature()` snapshots reviewed intentionally on changes.
- Whether it should affect scoring: Yes, lightly.

### SDK-AUDIT-048: Security Policy References GitHub Advisory But Not An Internal Escalation Owner

- Category: Security process
- Severity: Low
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/SECURITY.md`
- Evidence: Security policy points to GitHub private vulnerability reporting and says use private organizational intake if available, but names no owner/team/email for MVP partners.
- Why it matters: Early design partners may not know who to contact if they do not have GitHub advisory access.
- Root cause or likely root cause: Generic security policy.
- Impact on MVP readiness: Minor for internal teams, worse for external pilots.
- Impact on developer experience, if applicable: Slower vulnerability reporting.
- Impact on security or reliability, if applicable: Delayed security triage.
- Whether it was mentioned in the prior review log: No.
- Whether a previous fix claimed to address it: Security policy added.
- Whether that previous fix is sufficient: Partial.
- Recommended remediation: Add an MVP/private support channel or named security intake alias.
- Suggested validation or test: Docs review confirms security contact is actionable for non-repo members.
- Whether it should affect scoring: Yes, lightly.

### SDK-AUDIT-049: No SBOM Or Provenance Validation In Local SDK Release Validator

- Category: Supply chain / release
- Severity: Low
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/scripts/validate_release.py`, `.github/workflows/publish.yml`
- Evidence: Publish workflow generates SBOM and attestations. Local validator writes a manifest with artifact hashes but does not generate/verify SBOM or provenance.
- Why it matters: Local release validation is not equivalent to publish workflow validation.
- Root cause or likely root cause: SBOM/provenance handled in GitHub Actions.
- Impact on MVP readiness: Acceptable if artifacts come from CI; risky if local artifacts are handed to partners.
- Impact on developer experience, if applicable: Local artifact handoff may lack supply-chain evidence.
- Impact on security or reliability, if applicable: Lower release traceability.
- Whether it was mentioned in the prior review log: No.
- Whether a previous fix claimed to address it: Release validation claimed.
- Whether that previous fix is sufficient: Partial.
- Recommended remediation: Document that only CI artifacts are approved, or add optional local SBOM generation.
- Suggested validation or test: Release manifest records SBOM/provenance presence or absence.
- Whether it should affect scoring: Yes, lightly.

### SDK-AUDIT-050: README Mentions "Production Tokens" In An MVP/Beta Package Without Clear Environment Boundary

- Category: Documentation / maturity signaling
- Severity: Low
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/README.md`, `packages/product-platform/README.md`
- Evidence: Docs use production-oriented wording and a production adoption checklist while the package is `0.1.0` beta and this audit finds MVP constraints.
- Why it matters: Docs can make the package sound more mature than its validation envelope.
- Root cause or likely root cause: Security guidance was written in production terms.
- Impact on MVP readiness: Does not block MVP, but can mis-set expectations.
- Impact on developer experience, if applicable: Users may expect enterprise-grade release/support path.
- Impact on security or reliability, if applicable: Overconfidence risk.
- Whether it was mentioned in the prior review log: Production readiness was the prior framing.
- Whether a previous fix claimed to address it: Docs were expanded.
- Whether that previous fix is sufficient: Partial.
- Recommended remediation: Add a clear "MVP/beta support envelope" section with approved deployment assumptions and non-goals.
- Suggested validation or test: Docs review confirms MVP, pilot, and production language are distinct.
- Whether it should affect scoring: Yes, lightly.

## Issues Grouped By Category

Public API and compatibility:

- SDK-AUDIT-001: Compatibility exports omit `ToolGatewayValidationError`.
- SDK-AUDIT-003: Two distributions ship the same top-level package.
- SDK-AUDIT-009: `get_tool()` synthesizes local 404 without gateway context.
- SDK-AUDIT-014: No contract version negotiation.
- SDK-AUDIT-015: Constructor has many options without config object.
- SDK-AUDIT-024: Generic 403 and policy denial error split can surprise callers.
- SDK-AUDIT-025: `ToolDefinition.raw` is a future data exposure surface.
- SDK-AUDIT-046: Deprecated `status` parameter remains public.
- SDK-AUDIT-047: No public API snapshot tests.

Runtime behavior and reliability:

- SDK-AUDIT-004: No idempotency-key contract.
- SDK-AUDIT-005: No opt-in retries for safe invocations.
- SDK-AUDIT-006: Process-local rate limiter.
- SDK-AUDIT-007: Rate-limit key exhaustion allows new keys through.
- SDK-AUDIT-019: Discovery cache can be stale.
- SDK-AUDIT-020: Offset pagination lacks stable cursor.
- SDK-AUDIT-021: Owner-team filter exactness is unclear.
- SDK-AUDIT-023: Failed upstream calls still return result metadata.
- SDK-AUDIT-026: Async SDK uses threading lock.
- SDK-AUDIT-027: Async cancellation semantics undocumented.
- SDK-AUDIT-030: SQLite remains worktree runtime baseline.
- SDK-AUDIT-031: No upstream circuit breaker.
- SDK-AUDIT-032: Health checks lack response body cap.
- SDK-AUDIT-037: Environment token provider is simple env read.
- SDK-AUDIT-038: Event hook telemetry is minimal.

Security and data handling:

- SDK-AUDIT-008: Denied invocation responses reveal authorization state.
- SDK-AUDIT-016: Buffered custom clients rely on caller discipline.
- SDK-AUDIT-017: SDK does not mirror server max token length.
- SDK-AUDIT-018: Strict token grammar may reject future opaque formats.
- SDK-AUDIT-022: Response redaction defaults depend on per-tool policy.
- SDK-AUDIT-033: DNS-based SSRF validation has residual rebinding risk.
- SDK-AUDIT-034: Local/test unresolved host behavior differs from production.
- SDK-AUDIT-035: Raw payload is passed into runtime audit creation on schema failure.
- SDK-AUDIT-036: Sanitized diagnostics can still contain arbitrary PII-like text.
- SDK-AUDIT-048: Security policy lacks concrete MVP escalation owner.

Testing:

- SDK-AUDIT-002: No installed-wheel SDK-to-live-gateway test.
- SDK-AUDIT-010: Standalone SDK tests are thinner than vendored SDK tests.
- SDK-AUDIT-043: Tests are strong but mostly mocked/local.
- SDK-AUDIT-047: No public API stability snapshots.

Packaging and release:

- SDK-AUDIT-003: Duplicate top-level package ownership.
- SDK-AUDIT-028: Publish workflow builds artifacts but does not publish Python packages.
- SDK-AUDIT-029: Static `0.1.0` with no visible version bump policy.
- SDK-AUDIT-042: Local validator can skip `twine check`.
- SDK-AUDIT-049: Local validator lacks SBOM/provenance validation.

Documentation and DX:

- SDK-AUDIT-011: README overstates compatibility.
- SDK-AUDIT-012: Credential issuance docs are not runnable.
- SDK-AUDIT-013: Direct HTTP example has weaker safety controls.
- SDK-AUDIT-027: Async cancellation docs missing.
- SDK-AUDIT-039: No framework-specific examples.
- SDK-AUDIT-040: No removal timeline for compatibility shims.
- SDK-AUDIT-044: Event hook schemas not documented.
- SDK-AUDIT-045: Redaction limits not documented.
- SDK-AUDIT-050: Production language can overstate beta maturity.

Governance and maintainability:

- SDK-AUDIT-041: Labeler/CODEOWNERS omit explicit package entries.

## Critical And High-Severity Blockers

Critical:

- None found in the current repository state.

High:

- SDK-AUDIT-002: No installed-wheel SDK test calls a live gateway contract.

The absence of critical issues is a major improvement over earlier production
audits. It does not imply production readiness; it means the current state is
credible enough for controlled MVP evaluation.

## Medium-Severity MVP Risks

- SDK-AUDIT-001
- SDK-AUDIT-003
- SDK-AUDIT-004
- SDK-AUDIT-006
- SDK-AUDIT-007
- SDK-AUDIT-008
- SDK-AUDIT-010
- SDK-AUDIT-011
- SDK-AUDIT-012
- SDK-AUDIT-014
- SDK-AUDIT-016
- SDK-AUDIT-019
- SDK-AUDIT-022
- SDK-AUDIT-028
- SDK-AUDIT-030
- SDK-AUDIT-031
- SDK-AUDIT-033
- SDK-AUDIT-035
- SDK-AUDIT-043

## Low-Severity And Nit-Level Issues

- SDK-AUDIT-005
- SDK-AUDIT-009
- SDK-AUDIT-013
- SDK-AUDIT-015
- SDK-AUDIT-017
- SDK-AUDIT-018
- SDK-AUDIT-020
- SDK-AUDIT-021
- SDK-AUDIT-023
- SDK-AUDIT-024
- SDK-AUDIT-025
- SDK-AUDIT-026
- SDK-AUDIT-027
- SDK-AUDIT-029
- SDK-AUDIT-032
- SDK-AUDIT-034
- SDK-AUDIT-036
- SDK-AUDIT-037
- SDK-AUDIT-038
- SDK-AUDIT-039
- SDK-AUDIT-040
- SDK-AUDIT-041
- SDK-AUDIT-042
- SDK-AUDIT-044
- SDK-AUDIT-045
- SDK-AUDIT-046
- SDK-AUDIT-047
- SDK-AUDIT-048
- SDK-AUDIT-049
- SDK-AUDIT-050

## Prior Findings Status Table

| Prior finding from log 13 | Current status | Current issue |
| --- | --- | --- |
| Discovery used operator `/api/v1/tools` with gateway token | Resolved. SDK uses `/api/v1/gateway/tools`; gateway route exists and tests pass. | None |
| Gateway discovery exposed operator fields | Resolved. Gateway-safe response model and tests omit org/env/creator fields. | SDK-AUDIT-025 for future raw-field drift |
| Weak SDK input/payload/response validation | Mostly resolved. Strict validation exists and tests pass. | SDK-AUDIT-017, SDK-AUDIT-018 |
| Non-local plain HTTP allowed by default | Resolved. SDK rejects non-local HTTP unless explicitly opted in. | None |
| `get_tool()` only searched first page | Resolved. Pagination exists. | SDK-AUDIT-009, SDK-AUDIT-020 residual |
| Static token repr exposed token | Resolved. `repr=False`. | None |
| Exception bodies could expose secrets | Improved. Generic messages and sanitized bodies exist. | SDK-AUDIT-036, SDK-AUDIT-045 |
| No env token provider | Resolved. | SDK-AUDIT-037 residual simplicity |
| Manual discovery pagination | Resolved with `list_all_tools()`. | SDK-AUDIT-020 residual offset stability |
| No discovery retries | Resolved for discovery. | SDK-AUDIT-004, SDK-AUDIT-005 for invocation |
| No cache invalidation / partitioning | Improved with `clear_tool_cache()` and token fingerprint partitioning. | SDK-AUDIT-019 |
| No typed marker | Resolved with `py.typed`. | None |
| Loose JSON and URL boundary | Mostly resolved. | SDK-AUDIT-017, SDK-AUDIT-018 |
| Non-finite numeric config accepted | Resolved. | None |
| Booleans accepted truthy values | Resolved. | None |
| Server text in exception messages | Resolved for messages. | SDK-AUDIT-036 residual body diagnostics |
| Retry-After ignored | Resolved for discovery and error exposure. | None |
| SDK embedded only in product-platform | Improved with standalone package. | SDK-AUDIT-003, SDK-AUDIT-028 |
| Resource-bound credential scopes ignored | Resolved by structured grants and tests. | SDK-AUDIT-008 residual reason-code exposure |
| Cache keyed only by query params | Resolved. | SDK-AUDIT-019 |
| Retry backoff lacked jitter | Resolved for discovery. | None |
| No async SDK | Resolved. | SDK-AUDIT-026, SDK-AUDIT-027 |
| Standalone package buildability incomplete | Resolved in current state. Release validators pass. | SDK-AUDIT-002, SDK-AUDIT-028, SDK-AUDIT-049 residual |
| Docs incomplete | Improved substantially. | SDK-AUDIT-011, SDK-AUDIT-012, SDK-AUDIT-044, SDK-AUDIT-045, SDK-AUDIT-050 |

## Scoring Matrix

### Implementation Quality

1. Current score: 6.5 / 10
2. Prior score from review log: None assigned in log 13.
3. Direction: New score; if compared to later production audits, current state should be raised from their older pessimistic blocker state because the worktree is clean, CI includes the packages, product sdist no longer leaks DB files, and tests/validators pass.
4. Exact reasons:
   - Strong SDK implementation for input validation, strict JSON, response caps, retries for discovery, async/sync clients, typed errors, and release validation.
   - Strong gateway tests: 283 tool-gateway tests passed.
   - Remaining gaps include no installed-wheel live gateway SDK e2e, duplicate package ownership, missing compatibility export, offset pagination, no idempotency, and process-local runtime assumptions.
5. Score cap caused by unresolved issues: Capped below 7 by SDK-AUDIT-002 and the cluster of medium runtime/package issues.
6. What must be fixed to reach next score:
   - Add installed-wheel SDK-to-gateway e2e test.
   - Fix compatibility export parity.
   - Add install-order test for product-platform plus standalone SDK.
7. What must be fixed to reach 7:
   - Same as next score, plus runnable credential issuance quickstart and public API snapshot tests.
8. What must be fixed to reach 8:
   - Add idempotency contract, cursor/compatibility contract, stronger standalone tests, and real deployment smoke with running ASGI server.

### Ease Of Use

1. Current score: 6.5 / 10
2. Prior score from review log: None assigned in log 13.
3. Direction: New score.
4. Exact reasons:
   - Sync and async examples exist.
   - Error classes and troubleshooting are documented.
   - Docs explain security and reliability posture.
   - Main first-run gap remains token issuance. A user cannot go from zero to SDK call using only SDK README commands unless a token is already provisioned.
   - Compatibility docs overstate old import-path behavior.
5. Score cap caused by unresolved issues: Capped below 7 by SDK-AUDIT-011 and SDK-AUDIT-012.
6. What must be fixed to reach next score:
   - Fix compatibility export docs/code.
   - Add concrete token issuance quickstart.
7. What must be fixed to reach 7:
   - Add copy-pasteable local setup that creates/grants/issues a token and calls SDK.
   - Document event hook schema and redaction limits.
8. What must be fixed to reach 8:
   - Add framework-specific examples, compatibility checker, and polished migration/support lifecycle docs.

### Security And Reliability

1. Current score: 6.0 / 10
2. Prior score from review log: None assigned in log 13.
3. Direction: New score.
4. Exact reasons:
   - Strong improvements: HTTPS default, strict payloads, token validation, redacted diagnostics, upstream URL restrictions, resource-bound scopes, response caps, production startup guardrails.
   - Still fragile: process-local rate limiting, rate-limit overflow behavior, reason-code disclosure, no idempotency, no circuit breaker, SQLite baseline, DNS/egress residual SSRF risk, policy-dependent response redaction defaults.
5. Score cap caused by unresolved issues: Capped at 6 by the combined medium security/reliability issues; no critical issue caps it lower.
6. What must be fixed to reach next score:
   - Add ingress/distributed rate-limit story or implement shared limiter.
   - Coarsen agent-facing denial reasons.
   - Add default response redaction policy.
7. What must be fixed to reach 7:
   - Add idempotency support or explicit safe retry contract for relevant tools.
   - Add real gateway deployment smoke and operational runbook for ingress/egress.
8. What must be fixed to reach 8:
   - Add circuit breaker, Postgres/multi-worker validation, DNS rebinding/egress controls, and stronger secret-provider integration tests.

## Score Cap Explanation

No single critical issue caps the repository at 4 or lower. The repository is
functional and validated enough for a controlled MVP.

The high issue SDK-AUDIT-002 caps implementation quality below 7 because the
most important consumer journey is not directly tested from an installed SDK
artifact against the live gateway contract.

Multiple medium issues cap security/reliability at 6:

- SDK-AUDIT-006 and SDK-AUDIT-007 mean gateway abuse protection is not robust
  without deployment-layer controls.
- SDK-AUDIT-008 exposes precise authorization state to valid credentials.
- SDK-AUDIT-004 leaves callers without safe retry semantics for ambiguous
  mutating calls.
- SDK-AUDIT-022 makes response secrecy dependent on operator policy setup.
- SDK-AUDIT-030 and SDK-AUDIT-043 show the server side is still local/test
  heavy rather than deployment-proven.

Multiple medium DX issues cap ease of use below 7:

- SDK-AUDIT-011 breaks a compatibility promise.
- SDK-AUDIT-012 leaves credential issuance non-runnable.
- SDK-AUDIT-014 leaves version mismatch diagnosis to runtime failures.

## Required Fixes To Reach MVP Readiness

The repository is already credible for controlled MVP readiness, with caveats.
The minimum fixes before handing it to a design partner without source-level
support are:

1. Fix `ToolGatewayValidationError` compatibility exports.
2. Add a live contract test using the built SDK wheel against a seeded gateway.
3. Add a runnable credential issuance quickstart.
4. Document the MVP support envelope: single-process/local demo vs controlled
   pilot with ingress rate limits and egress controls.
5. Add explicit edge/ingress rate-limit requirement to deployment runbooks.
6. Add default response redaction for common sensitive fields or require it in
   tool creation.

## Required Fixes To Reach 7 Out Of 10

1. All MVP readiness fixes above.
2. Install-order/package ownership test for product-platform plus SDK.
3. Public API snapshot tests for exports, signatures, dataclass fields, and
   exception attributes.
4. Event hook schema docs and tests.
5. Redaction limit/heuristic docs.
6. Gateway compatibility/version probe.
7. Standalone SDK test suite expanded to cover the full SDK behavior matrix.

## Required Fixes To Reach 8 Out Of 10

1. Idempotency-key contract for invocation and safe opt-in retries.
2. Cursor or snapshot-based discovery pagination.
3. Distributed/shared rate limiter or proven ingress rate-limit deployment.
4. Circuit breaker/degradation loop for repeated upstream failures.
5. Postgres or managed DB validation for Tool Gateway runtime.
6. Real ASGI/TLS/proxy deployment smoke using the built SDK wheel.
7. Stronger DNS rebinding/egress controls and tests.
8. Published/internal package-index release rehearsal with SBOM and provenance
   tied to the consumed artifact.

## Recommended Remediation Order

1. Fix compatibility export parity for `ToolGatewayValidationError`.
2. Add installed-wheel SDK-to-gateway e2e test.
3. Add runnable local credential issuance quickstart.
4. Add standalone SDK full behavior tests or move product SDK tests into the
   standalone package.
5. Add default response redaction policy for common sensitive keys.
6. Add agent-facing coarse denial reason while preserving detailed operator
   audit reasons.
7. Add package install-order validation and decide long-term top-level package
   ownership.
8. Add distributed/ingress rate-limit story and document deployment requirement.
9. Add idempotency-key contract and opt-in invocation retries.
10. Add deployment smoke with real ASGI server and managed DB path.

## Validation Plan

Short-term validation:

- Run standalone SDK tests.
- Run product gateway tests.
- Run both release validators without `--skip-twine-check` in CI.
- Add import parity tests for all standalone SDK exports through compatibility
  modules.
- Add installed-wheel e2e contract test.

MVP pilot validation:

- Seed local gateway.
- Create tool, upstream target, response policy, agent, credential scopes, and
  agent-tool permission through documented APIs or CLI.
- Install built SDK wheel in a clean environment.
- Call discovery, `get_tool()`, allowed invocation, denied invocation,
  malformed payload, expired token, revoked permission, too-large response, and
  upstream failure.
- Verify runtime action audit entries are redacted and correlated.
- Verify ingress body/rate limits outside the app process.

Broader rollout validation:

- Run tests against a non-SQLite database.
- Run two gateway workers and verify shared rate limit or ingress enforcement.
- Exercise DNS/egress SSRF controls.
- Exercise secret-provider integration with bearer and API-key upstream targets.
- Run package install-order matrix for SDK and product-platform.
- Verify package artifact from actual internal/public package index installs and
  matches CI provenance.

## Final Strict MVP Assessment

This is a credible controlled MVP, not a polished external SDK release.

It is credible because the current code is coherent, tracked, packageable,
tested, and substantially hardened. The SDK has real sync/async clients,
typed results/errors, strict validation, bounded responses, discovery retries,
credential-aware caching, and reasonable docs. The server contract now enforces
gateway authentication, resource-bound credential scopes, upstream URL safety,
response policies, body caps, and audit records.

It is still fragile because the most important black-box consumer journey is
not directly tested, the compatibility path has a real missing export, token
issuance is not runnable from docs, rate limiting is local and incomplete as a
security boundary, invocation lacks idempotency, and deployment realism is still
thin.

Strict answer: usable for an internal team or closely supported design partner
who can run the product-platform gateway in a controlled environment and get
operator-issued tokens. Not ready for broad external self-serve adoption.
