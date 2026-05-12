# Strict MVP Readiness Audit: Tool Gateway SDK And Product Gateway

Date: 2026-05-12

Scope: fresh strict MVP-readiness audit of the Ophanix Tool Gateway SDK package, the product-platform gateway runtime, tests, docs, packaging, CI, and release evidence.

Source context reviewed first: `docs/product-platform-worktree/execution-logs/06-tool-gateway-logs/13-sdk-review-remediation.md`.

Important reviewer constraints:

- No product code fixes were implemented during the initial audit pass. Follow-up
  remediation passes were implemented after the strict finding register; see
  section 18.
- Prior remediation claims were treated as untrusted until checked against current code, tests, docs, and package metadata.
- Load balancing was not treated as a flaw. This SDK/gateway path is not expected to need load balancing for MVP traffic.
- Publication to PyPI was not treated as missing. The package is understood to be published; this audit only flags repository evidence gaps that remain relevant after publication.

## 1. Executive Summary

Strict result: the current repository is a credible controlled MVP for internal teams and closely supported design partners, but it is not a clean 8/10 production pilot and should not be described as production-ready.

The current code is materially stronger than several older audit notes. The SDK is a standalone PyPI-oriented package, has sync and async clients, secure URL defaults, strict token and payload validation, bounded response handling, idempotency-key support, retries only for idempotent invocations, compatibility probing, release validation, package smoke tests, installed-wheel network gateway tests, product gateway runtime tests, and strong local validation results.

The remaining weaknesses are mostly medium and low severity, not proven critical failures. The biggest MVP risks are lifecycle bypass for creating already-active tools, idempotency recovery edge cases, manual retention cleanup, upstream redaction assumptions, DNS/egress trust assumptions, SDK result-shape ergonomics, ambiguous compatibility/deprecated knobs, source-copy maintenance risk, and documentation examples that make unsafe or confusing patterns too easy to copy.

Scores assigned in this audit:

| Category | Current score | Prior score from `13-sdk-review-remediation.md` | Direction | MVP interpretation |
| --- | ---: | ---: | --- | --- |
| Implementation quality | 7.0/10 | 8.1/10 | Lowered | Credible MVP, but capped by lifecycle/idempotency gaps, large mirrored implementation, and source-copy maintenance risk. |
| Ease of use | 7.0/10 | 8.3/10 | Lowered | A competent engineer can adopt it in a few hours with support, but result shape, credential issuance, examples, and compatibility knobs still cause avoidable confusion. |
| Security and reliability | 6.8/10 | 8.3/10 | Lowered | Good controlled-MVP baseline, but not enough to call broad external usage low-risk without fixing retention, upstream redaction, DNS/egress, and proxy/default behavior concerns. |

No critical or high-severity issue was directly proven in the current code. Multiple medium issues still cap the security/reliability score below 7.

## 2. Prior Review Summary And Challenge

### Previously Reported Issues, Ignoring Deferred Items

The remediation log previously reported these non-deferred issues:

- SDK discovery used `/api/v1/tools`, which required product-user auth instead of gateway bearer auth.
- Gateway discovery exposed broad operator-facing fields.
- SDK input validation, response validation, and non-local HTTP defaults were weak.
- `get_tool()` searched only the first discovery page.
- `StaticTokenProvider` representation could expose tokens.
- SDK exceptions could retain raw response bodies.
- No environment token provider, no `list_all_tools()`, and weak discovery ergonomics.
- Payload validation allowed non-strict JSON shapes and unsafe URL construction.
- Numeric configuration accepted unsafe values.
- Discovery retries ignored `Retry-After`.
- SDK was embedded only in product-platform.
- Credential resource binding was flattened to scope strings.
- Discovery cache crossed credential contexts.
- No async SDK.
- Standalone package buildability and docs were thin.
- Optional response contract validation was incomplete.
- Error redaction missed common secret patterns.
- Release validation was ad hoc.
- Sync and async config validation was duplicated.
- Later remediation work claimed CI/release, package, auth-route, schema-order, upstream SSRF, response-policy, rate-limit, body-limit, docs, and provenance improvements.

### Fixes Claimed

The prior log claimed fixes including:

- Gateway discovery route and capabilities route.
- Agent-safe discovery response type.
- Standalone `ophanix-tool-gateway-sdk` package with compatibility exports.
- Strict client-side URL, token, payload, response parsing, retry, cache, and telemetry controls.
- Sync and async clients plus `ToolGatewayClientConfig`.
- Environment/static token providers.
- Idempotency-key support and idempotent invocation retries.
- Credential-partitioned discovery cache.
- Runtime idempotency persistence.
- Gateway request body cap, rate limiting, circuit breaker, upstream URL validation, and response policy controls.
- Release validation scripts, CI/publish workflow entries, README/API/MIGRATION/CHANGELOG/SECURITY docs.

### Validation Evidence Claimed

The prior log claimed unittest and pytest runs, compile checks, package builds, release validator runs, dependency audit attempts, and static workflow review. This audit independently re-ran the current focused checks listed in section 16 instead of trusting those older counts.

### Scores Assigned

The latest explicit scores in the prior remediation log were:

- Implementation quality: 8.1/10.
- Ease of use: 8.3/10.
- Security/reliability: 8.3/10.

### Suspicious, Under-Evidenced, Too Lenient, Or Too Strict Prior Conclusions

- Too lenient: the prior 8+ scores overweighted implemented controls and underweighted lifecycle/idempotency edge cases, retention cleanup, operator error paths, and source-copy maintenance risk.
- Too lenient: release confidence still depends on an external PyPI handoff. Publication is not disputed, but the repo does not itself close the "validated artifact equals published artifact" loop.
- Too lenient: docs and examples are extensive, but several first-copy examples omit idempotency or use idempotency/correlation IDs that are too broad or PII-like.
- Under-evidenced: the previous review treated optional compatibility probing as stronger than it is. Current clients do not automatically gate calls on compatibility.
- Too strict or stale: older concerns about no async SDK, no standalone package, no installed-wheel network gateway test, no min-SDK check, duplicate product wheel ownership of `ophanix_tool_gateway`, and agent-facing full decision exposure are no longer current in their original form.

### Areas Not Deeply Reviewed Before

- Direct creation of active tool definitions, not just activation lifecycle.
- Idempotency behavior when completion persistence fails after upstream success.
- Operational scheduling of idempotency cleanup.
- SDK default proxy behavior.
- Exact async cache-clear API semantics.
- Result envelope ergonomics for SDK consumers.
- Source-tree compatibility copy risks after product wheel exclusion was fixed.
- DNS rebinding and staging/non-production external deployment assumptions.

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
- `packages/ophanix-tool-gateway-sdk/examples/langgraph_node_example.py`

Relevant product-platform gateway and compatibility surface:

- `packages/product-platform/pyproject.toml`
- `packages/product-platform/src/ophanix_tool_gateway/__init__.py`
- `packages/product-platform/src/ophanix_tool_gateway/sdk.py`
- `packages/product-platform/src/product_platform/tool_gateway/__init__.py`
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
- `packages/product-platform/src/product_platform/integrations/secrets.py`
- `packages/product-platform/src/product_platform/cli.py`
- `packages/product-platform/src/product_platform/db/migrations/0050_*` through `0060_*`
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

Relevant CI, release, and governance:

- `.github/workflows/ci.yml`
- `.github/workflows/publish.yml`
- `.github/dependabot.yml`
- `.github/workflows/security-scan.yml`
- `.github/workflows/weekly-security-audit.yml`
- `.github/workflows/ai-breaking-change-detector.yml`
- `docs/product-platform-worktree/execution-logs/06-tool-gateway-logs/13-sdk-review-remediation.md`

## 4. Exhaustive Issue Register

### SDK-AUDIT-001

- Title: Direct tool creation can set `status="active"` and bypass activation safeguards.
- Category: Runtime correctness / lifecycle / security control boundary
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/tool_gateway/models.py:29-69`, `packages/product-platform/src/product_platform/tool_gateway/repository.py:79-128`, `packages/product-platform/src/product_platform/tool_gateway/repository.py:498-517`, `packages/product-platform/src/product_platform/api/app.py:5844-5869`
- Evidence: `ToolDefinitionCreateRequest.status` accepts all supported statuses, including `active`. `create_tool()` persists `body.status` directly. The activation path separately requires an input schema before activation, but that guard is only in `activate_tool()`.
- Why it matters: Operators can create an active tool without exercising the activation lifecycle check or activation audit event. If `input_schema_json` is omitted, invocation skips payload schema validation because the runtime only validates when a schema exists.
- Root cause or likely root cause: Create and activate lifecycle responsibilities are split, but create accepts active status without delegating to activation validation.
- Impact on MVP readiness: Concerning for MVP. It does not let unauthenticated users create tools, but it weakens the main control-plane invariant around "active means contract-approved."
- Impact on developer experience: Operators can accidentally create a callable tool that later behaves differently from one activated through the documented path.
- Impact on security or reliability: Missing input schema means broader payloads can reach upstream targets, increasing misuse and operator error risk.
- Mentioned in prior review log: No.
- Previous fix claimed to address it: No.
- Whether previous fix is sufficient: Not applicable.
- Recommended remediation: Reject `status="active"` on create, or route active creates through the same validation/audit logic used by `activate_tool()`.
- Suggested validation or test: Add repository and API tests that `POST /api/v1/tools` with `status="active"` and no input schema returns 422, and that active creation with schema either fails or emits activation-equivalent audit.
- Should affect scoring: Yes. Caps implementation quality below 8.

### SDK-AUDIT-002

- Title: Current tests can mask the active-create lifecycle bypass.
- Category: Testing
- Severity: Low
- Confidence: High
- File path or area: `packages/product-platform/tests/test_tool_gateway_forwarding_phase*.py`, `packages/product-platform/tests/test_tool_gateway_installed_sdk_contract.py`, `packages/product-platform/tests/test_tool_gateway_runtime_audit_phase*.py`
- Evidence: Several setup paths create fixtures with `ToolDefinitionCreateRequest(status="active")` and then call `activate_tool()` anyway. Registry tests verify activation fails when schema is missing, but do not prove create rejects an already-active missing-schema tool.
- Why it matters: A test suite can look comprehensive while missing the bypass route that production callers can use.
- Root cause or likely root cause: Fixture convenience leaked into test setup and did not become a negative-path test.
- Impact on MVP readiness: Low by itself, but it leaves SDK-AUDIT-001 unguarded.
- Impact on developer experience: Future maintainers may believe activation invariants are fully covered.
- Impact on security or reliability: Indirect, through missed lifecycle validation.
- Mentioned in prior review log: No.
- Previous fix claimed to address it: No.
- Whether previous fix is sufficient: Not applicable.
- Recommended remediation: Normalize fixtures to create draft tools, then activate. Add explicit create-status tests.
- Suggested validation or test: Search for `status="active"` in tool-definition create fixtures and remove or justify each occurrence.
- Should affect scoring: Yes, as a test gap.

### SDK-AUDIT-003

- Title: Idempotency starts after policy and schema checks, so denials and validation failures are not replayed.
- Category: Reliability / API semantics
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/api/app.py:3461-3564`, `packages/product-platform/src/product_platform/api/app.py:3564-3656`
- Evidence: The runtime evaluates policy and input schema before calling `ToolInvocationIdempotencyRepository.begin_invocation()`. Denied calls and schema-validation failures return before an idempotency record exists.
- Why it matters: A caller providing an idempotency key may expect the whole invocation attempt to be idempotent. In reality, only post-policy, post-schema execution is replayable.
- Root cause or likely root cause: Idempotency was scoped to upstream execution rather than the full public invocation contract.
- Impact on MVP readiness: Acceptable if documented as "execution idempotency," but concerning because the SDK and docs present it as invocation idempotency.
- Impact on developer experience: Repeated invalid or denied calls can produce new request IDs and audit records instead of replayed responses, surprising callers.
- Impact on security or reliability: Can create noisy audit duplication and inconsistent reconciliation behavior.
- Mentioned in prior review log: Partially, under idempotency contract concerns.
- Previous fix claimed to address it: Yes, by adding runtime idempotency.
- Whether previous fix is sufficient: Partial.
- Recommended remediation: Either document the exact scope clearly or move idempotency begin earlier and store deterministic denied/validation responses too.
- Suggested validation or test: Add tests for repeated denied calls and repeated schema-invalid calls with the same idempotency key.
- Should affect scoring: Yes.

### SDK-AUDIT-004

- Title: Successful upstream outcomes can become unreplayable if idempotency completion persistence fails.
- Category: Reliability / failure recovery
- Severity: Medium
- Confidence: Medium
- File path or area: `packages/product-platform/src/product_platform/api/app.py:3703-3721`, `packages/product-platform/src/product_platform/api/app.py:3924-3958`, `packages/product-platform/src/product_platform/tool_gateway/runtime_audit.py:491-528`
- Evidence: The idempotency record is created before upstream execution, but completion is stored in a later transaction after execution and response processing. If the process crashes or DB update fails after upstream success but before `complete_invocation()`, later retries see a stale/unknown outcome instead of replaying the successful response.
- Why it matters: This is the hardest idempotency failure mode for callers: the upstream side effect may have happened, but the gateway cannot prove it.
- Root cause or likely root cause: Upstream execution and replay-record completion cannot be committed atomically.
- Impact on MVP readiness: Controlled MVP can tolerate this if docs emphasize reconciliation, but broad external usage needs a stronger story.
- Impact on developer experience: Callers must do source-level debugging or business reconciliation when `idempotency_stale` happens after an apparently successful upstream side effect.
- Impact on security or reliability: Creates duplicate-side-effect risk if callers retry with a new key without reconciling.
- Mentioned in prior review log: Partially, under idempotency durability/recovery.
- Previous fix claimed to address it: Yes, runtime idempotency and stale handling were added.
- Whether previous fix is sufficient: Partial. It detects unknown outcomes but does not recover them.
- Recommended remediation: Document this explicitly, expose lookup/reconciliation by request/correlation ID, and consider storing an execution-start marker plus upstream idempotency token where upstream supports it.
- Suggested validation or test: Inject a failure into `complete_invocation()` after a fake upstream success and assert the retry behavior and operator audit path.
- Should affect scoring: Yes. Caps reliability below 8.

### SDK-AUDIT-005

- Title: Idempotency cleanup is manual CLI work, not operationally scheduled.
- Category: Reliability / operations / data retention
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/cli.py:37-46`, `packages/product-platform/src/product_platform/cli.py:90-105`, `packages/product-platform/README.md:130-131`
- Evidence: `db cleanup-idempotency` exists and calls `purge_tool_invocation_idempotency_records()`, but there is no scheduler, worker job, startup task, or deployment manifest proving it runs periodically.
- Why it matters: Retention controls that depend on humans remembering a CLI command are fragile.
- Root cause or likely root cause: MVP added a cleanup primitive but not an operations loop.
- Impact on MVP readiness: Acceptable for internal MVP if runbook-owned, but not enough for broader external design partners without explicit scheduling guidance.
- Impact on developer experience: Operators must infer how often to run cleanup and where to run it.
- Impact on security or reliability: Old replay response bodies remain in the database until cleanup runs.
- Mentioned in prior review log: Partially.
- Previous fix claimed to address it: Yes, retention settings and cleanup were added.
- Whether previous fix is sufficient: Partial.
- Recommended remediation: Add a scheduled worker/cron example, deployment guidance, and observability metric for deleted/retained idempotency records.
- Suggested validation or test: Add an operations test or documented runbook proving cleanup is part of the deployment path.
- Should affect scoring: Yes.

### SDK-AUDIT-006

- Title: Old `in_progress` idempotency records are not purged unless a later retry marks them terminal.
- Category: Reliability / data retention
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/tool_gateway/runtime_audit.py:590-619`, `packages/product-platform/src/product_platform/tool_gateway/runtime_audit.py:622-641`
- Evidence: Stale `in_progress` records become `failed_unknown` only when `begin_invocation()` sees them again. The purge query deletes only `completed`, `failed_unknown`, and `expired` records, not stale untouched `in_progress` records.
- Why it matters: A crashed or abandoned idempotent call that is never retried can persist indefinitely.
- Root cause or likely root cause: Stale detection happens on lookup, not in cleanup.
- Impact on MVP readiness: Important MVP risk for any long-running internal pilot.
- Impact on developer experience: Operators may see records that do not age out despite retention settings.
- Impact on security or reliability: Indefinite metadata retention and table growth risk.
- Mentioned in prior review log: Partially.
- Previous fix claimed to address it: Yes, stale handling and cleanup were added.
- Whether previous fix is sufficient: Partial.
- Recommended remediation: Have cleanup mark or delete `in_progress` records older than the in-progress TTL plus retention policy, with conservative audit logging.
- Suggested validation or test: Extend runtime-audit cleanup tests to include stale untouched `in_progress` rows.
- Should affect scoring: Yes.

### SDK-AUDIT-007

- Title: Replay records store full public response bodies and rely on cleanup for data minimization.
- Category: Security / privacy / reliability
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/tool_gateway/runtime_audit.py:491-518`, `packages/product-platform/src/product_platform/api/settings.py:151-155`
- Evidence: `complete_invocation()` stores `response_body_json`. Retention defaults to seven days, but actual deletion depends on the manual cleanup path from SDK-AUDIT-005.
- Why it matters: Public gateway responses can include business data even after redaction. Storage should be intentional and bounded.
- Root cause or likely root cause: Replay correctness stores the full public response envelope, but retention enforcement is operational rather than automatic.
- Impact on MVP readiness: Acceptable for controlled pilots with runbooks; risky for broader partner data.
- Impact on developer experience: Operators need clear guidance on whether replay bodies contain sensitive data.
- Impact on security or reliability: Increased data exposure and retention blast radius.
- Mentioned in prior review log: Partially.
- Previous fix claimed to address it: Yes.
- Whether previous fix is sufficient: Partial.
- Recommended remediation: Add automatic cleanup, document data classification, and consider storing only replay-minimum fields or encrypted response bodies.
- Suggested validation or test: Verify cleanup removes old completed replay bodies and add docs for retention.
- Should affect scoring: Yes.

### SDK-AUDIT-008

- Title: SDK `ToolCallResult.result` exposes the gateway execution envelope instead of an ergonomic tool body.
- Category: Public API / developer experience
- Severity: Medium
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py:248-259`, `packages/product-platform/src/product_platform/tool_gateway/invocation.py:132-144`, `packages/product-platform/src/product_platform/api/app.py:3948-3958`, `packages/ophanix-tool-gateway-sdk/examples/langgraph_node_example.py:37-42`
- Evidence: The product runtime returns `ToolExecutionResult.model_dump()` as `result`, so consumers often need `result.result["body"]`. The LangGraph example includes helper logic to unwrap `body`.
- Why it matters: SDK users expect `call_tool()` to return the tool output, not a gateway executor record with `status`, `body`, `headers_summary`, `latency_ms`, and policy fields.
- Root cause or likely root cause: SDK exposes the HTTP contract directly without a higher-level body helper.
- Impact on MVP readiness: Does not block adoption, but slows onboarding and increases source-level debugging.
- Impact on developer experience: High friction in common code paths.
- Impact on security or reliability: Slightly increases accidental logging of metadata included in the envelope.
- Mentioned in prior review log: No.
- Previous fix claimed to address it: No.
- Whether previous fix is sufficient: Not applicable.
- Recommended remediation: Add `ToolCallResult.body` and `ToolCallResult.execution` properties, or document the exact shape prominently.
- Suggested validation or test: Add SDK tests and docs showing the preferred way to access upstream body.
- Should affect scoring: Yes, for ease of use.

### SDK-AUDIT-009

- Title: Main README sync quickstart calls a tool without an idempotency key.
- Category: Documentation / reliability
- Severity: Low
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/README.md:47-69`
- Evidence: The first sync example calls `client.call_tool("claims.lookup", {"claim_id": "claim_123"})` without `idempotency_key`, even though later sections recommend keys for retried/reconciled work.
- Why it matters: The first copied example sets user habits.
- Root cause or likely root cause: Quickstart simplicity was favored over reliability defaults.
- Impact on MVP readiness: Low but avoidable.
- Impact on developer experience: Users may later wonder why retries do not happen.
- Impact on security or reliability: Increases duplicate/unknown-outcome risk for copied worker code.
- Mentioned in prior review log: Prior docs were discussed generally.
- Previous fix claimed to address it: Documentation improvements were claimed.
- Whether previous fix is sufficient: Partial.
- Recommended remediation: Add an idempotency key to the quickstart or explicitly say why the example omits it.
- Suggested validation or test: Documentation review check for first `call_tool` examples.
- Should affect scoring: Slightly.

### SDK-AUDIT-010

- Title: Async worker example omits idempotency for a retriable worker-shaped call.
- Category: Documentation / examples / reliability
- Severity: Low
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/examples/async_worker_example.py:39-44`
- Evidence: The worker example sets `correlation_id` but not `idempotency_key`.
- Why it matters: Worker jobs are exactly where retries, cancellation, and reconciliation usually happen.
- Root cause or likely root cause: Example focuses on async setup rather than retry semantics.
- Impact on MVP readiness: Low.
- Impact on developer experience: Developers may copy a fragile worker pattern.
- Impact on security or reliability: Duplicate side-effect and unknown-outcome risk if users add their own outer retry loop.
- Mentioned in prior review log: Prior docs/examples were discussed generally.
- Previous fix claimed to address it: Documentation improvements were claimed.
- Whether previous fix is sufficient: Partial.
- Recommended remediation: Add a unique job/run idempotency key to the example.
- Suggested validation or test: Static docs/example check for worker examples.
- Should affect scoring: Slightly.

### SDK-AUDIT-011

- Title: LangGraph example uses an idempotency key that may be too coarse.
- Category: Documentation / reliability
- Severity: Low
- Confidence: Medium
- File path or area: `packages/ophanix-tool-gateway-sdk/examples/langgraph_node_example.py:22-27`
- Evidence: The example uses `idempotency_key=f"claims.lookup:{claim_id}"`.
- Why it matters: Reusing a claim-level key across distinct logical refreshes can replay stale data for the retention window.
- Root cause or likely root cause: Example uses a stable business identifier rather than a logical invocation identifier.
- Impact on MVP readiness: Low, but this is a copy-paste hazard.
- Impact on developer experience: Users may not understand why later calls replay old responses.
- Impact on security or reliability: Stale data risk.
- Mentioned in prior review log: No.
- Previous fix claimed to address it: No.
- Whether previous fix is sufficient: Not applicable.
- Recommended remediation: Include a workflow/run/step id in the key and explain stable-vs-unique tradeoffs.
- Suggested validation or test: Documentation review.
- Should affect scoring: Slightly.

### SDK-AUDIT-012

- Title: Telemetry and examples treat correlation IDs as token-free but not PII-free.
- Category: Security / privacy / developer experience
- Severity: Low
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py:558-565`, `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py:652-660`, `packages/ophanix-tool-gateway-sdk/examples/async_worker_example.py:43`, `packages/ophanix-tool-gateway-sdk/examples/langgraph_node_example.py:25`
- Evidence: Event hooks include correlation IDs. Examples build correlation IDs from `claim_id`.
- Why it matters: Claim IDs may be sensitive or customer-identifying in real deployments.
- Root cause or likely root cause: Docs emphasize "token-free" telemetry but do not warn against PII-bearing correlation IDs.
- Impact on MVP readiness: Low for internal pilots, but should be fixed before wider partner guidance.
- Impact on developer experience: Users may copy identifiers into logs/metrics.
- Impact on security or reliability: PII leakage through telemetry/log pipelines.
- Mentioned in prior review log: No.
- Previous fix claimed to address it: Documentation redaction improvements were claimed but not this nuance.
- Whether previous fix is sufficient: Partial.
- Recommended remediation: Document correlation IDs as non-secret and non-PII, and update examples to use opaque job/request IDs.
- Suggested validation or test: Documentation review.
- Should affect scoring: Slightly.

### SDK-AUDIT-013

- Title: SDK default HTTPX clients honor environment proxies.
- Category: Security / configuration
- Severity: Medium
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py:526`, `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py:1235`
- Evidence: The SDK creates `httpx.Client(timeout=...)` and `httpx.AsyncClient(timeout=...)` without `trust_env=False`. The product gateway runtime explicitly sets `trust_env=False` for its managed upstream client.
- Why it matters: In environments with `HTTP_PROXY` or `HTTPS_PROXY`, gateway requests with bearer tokens may be routed through a proxy unexpectedly.
- Root cause or likely root cause: SDK follows HTTPX defaults while server runtime hardened its client separately.
- Impact on MVP readiness: Acceptable if documented and intentional, but risky as a silent default for external SDK users.
- Impact on developer experience: Hard-to-debug network behavior in corporate or CI environments.
- Impact on security or reliability: Potential token exposure to configured proxies and availability issues through unintended proxy routing.
- Mentioned in prior review log: No.
- Previous fix claimed to address it: No.
- Whether previous fix is sufficient: Not applicable.
- Recommended remediation: Consider `trust_env=False` by default, or add a documented config option and explicit README warning.
- Suggested validation or test: Add tests showing proxy env vars are ignored or intentionally honored.
- Should affect scoring: Yes, especially security/reliability.

### SDK-AUDIT-014

- Title: Compatibility probing is opt-in and not enforced by SDK calls.
- Category: Public API / reliability
- Severity: Low
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py:535-662`, `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py:760-783`, `packages/ophanix-tool-gateway-sdk/README.md:51-57`
- Evidence: `check_compatibility()` exists and checks contract/min-SDK, but `call_tool()`, discovery, and `get_tool()` do not automatically require a successful compatibility check.
- Why it matters: Users can skip the check and hit confusing runtime failures after a gateway upgrade.
- Root cause or likely root cause: SDK preserves simple client construction without startup handshake state.
- Impact on MVP readiness: Acceptable MVP shortcut, but below an 8/10 SDK posture.
- Impact on developer experience: Integrations can fail later and less clearly.
- Impact on security or reliability: Contract drift can cause runtime reliability issues.
- Mentioned in prior review log: Compatibility was mentioned.
- Previous fix claimed to address it: Yes, by adding `check_compatibility()`.
- Whether previous fix is sufficient: Partial.
- Recommended remediation: Add an optional `require_compatible=True` startup helper or client method that caches a successful check.
- Suggested validation or test: Add integration test using a mismatched capabilities response and a helper that fails closed before calls.
- Should affect scoring: Slightly.

### SDK-AUDIT-015

- Title: SDK version comparison is not PEP 440 compliant.
- Category: Runtime compatibility
- Severity: Low
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py:2143-2160`
- Evidence: `_version_parts()` extracts leading numeric dotted parts with regex. Pre-release, local, post-release, and epoch semantics are not handled.
- Why it matters: `0.1.0rc1` or other PEP 440 versions may compare incorrectly.
- Root cause or likely root cause: Lightweight parser instead of `packaging.version.Version`.
- Impact on MVP readiness: Low for current `0.1.0`, but a future release-process hazard.
- Impact on developer experience: Compatibility errors may be wrong for pre-release pilots.
- Impact on security or reliability: Contract gating can be too lenient or too strict.
- Mentioned in prior review log: Min-SDK checking was mentioned.
- Previous fix claimed to address it: Yes, min-SDK checking was added.
- Whether previous fix is sufficient: Partial.
- Recommended remediation: Use `packaging.version.Version` or keep versions simple and document only numeric versions are supported.
- Suggested validation or test: Add tests for `0.1.0rc1`, `0.1.0.post1`, and invalid gateway version strings.
- Should affect scoring: Slightly.

### SDK-AUDIT-016

- Title: `allow_buffered_custom_http_client` is a compatibility no-op that still appears in the public API.
- Category: Public API / developer experience
- Severity: Low
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py:311`, `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py:1969-2006`, `packages/ophanix-tool-gateway-sdk/README.md:131-133`
- Evidence: The config field is accepted but ignored in validators, and custom clients without `stream()` are rejected regardless of its value.
- Why it matters: A public flag named "allow" that does not allow the behavior is confusing even if documented.
- Root cause or likely root cause: Backward-compatibility field retained after a security hardening decision.
- Impact on MVP readiness: Acceptable shortcut, but contributes to API instability.
- Impact on developer experience: Users may waste time trying the flag.
- Impact on security or reliability: Positive security posture, but confusing surface.
- Mentioned in prior review log: Yes.
- Previous fix claimed to address it: Yes, as compatibility field.
- Whether previous fix is sufficient: Mostly, but ergonomically poor.
- Recommended remediation: Deprecate the parameter loudly or rename to a private compatibility sentinel in 0.x.
- Suggested validation or test: Add a deprecation warning test when `allow_buffered_custom_http_client=True`.
- Should affect scoring: Slightly.

### SDK-AUDIT-017

- Title: Async cache clearing has both sync and async methods, but only the async method locks.
- Category: Runtime reliability / API clarity
- Severity: Low
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py:1460-1475`, `packages/ophanix-tool-gateway-sdk/API_REFERENCE.md:55-59`
- Evidence: `AsyncOphanixToolGatewayClient.clear_tool_cache()` mutates caches without `asyncio.Lock`; `aclear_tool_cache()` locks but is not documented in the API reference.
- Why it matters: Concurrent async discovery and cache clearing can race, and users may choose the wrong method because docs say async method names mirror sync methods.
- Root cause or likely root cause: Sync API compatibility was mirrored onto async client, then an async-safe method was added without full docs alignment.
- Impact on MVP readiness: Low unless users enable caching and clear under concurrency.
- Impact on developer experience: Confusing method contract.
- Impact on security or reliability: Possible stale cache or transient race under concurrent cache use.
- Mentioned in prior review log: Cache/thread-safety was discussed generally.
- Previous fix claimed to address it: Partially.
- Whether previous fix is sufficient: Partial.
- Recommended remediation: Document `aclear_tool_cache()`, make sync method call an async-safe path where possible, or deprecate sync cache clearing on async client.
- Suggested validation or test: Add async concurrency test around list/discovery and cache clear.
- Should affect scoring: Slightly.

### SDK-AUDIT-018

- Title: SDK payloads must be JSON objects even though JSON Schema can describe arrays/scalars.
- Category: Public API / extensibility
- Severity: Low
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py:535-548`, `packages/product-platform/src/product_platform/tool_gateway/invocation.py:51-85`
- Evidence: `call_tool()` accepts `payload: dict[str, Any]`, and server `ToolInvocationRequest.payload` is also a dict.
- Why it matters: Tools whose natural input is an array or scalar cannot be represented directly.
- Root cause or likely root cause: Gateway contract intentionally treats tool input as an object.
- Impact on MVP readiness: Acceptable MVP constraint if documented as object-only.
- Impact on developer experience: Integrators may need wrapper objects like `{"items": [...]}`.
- Impact on security or reliability: Minimal.
- Mentioned in prior review log: Payload validation was discussed.
- Previous fix claimed to address it: Not as a bug.
- Whether previous fix is sufficient: Acceptable if documented.
- Recommended remediation: Keep object-only but document as a contract decision, or broaden to any JSON value in a future version.
- Suggested validation or test: Docs test or API reference update.
- Should affect scoring: Minimal.

### SDK-AUDIT-019

- Title: SDK error taxonomy is still coarse for rate-limit, timeout, and retryable failures.
- Category: Public API / developer experience
- Severity: Low
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py:315-367`, `packages/ophanix-tool-gateway-sdk/API_REFERENCE.md:121-133`
- Evidence: Errors collapse many cases into `ToolGatewayError` with `code`, `status_code`, and `retry_after_seconds`.
- Why it matters: Consumers must branch on strings/status codes instead of type-specific exceptions.
- Root cause or likely root cause: MVP kept a small exception hierarchy.
- Impact on MVP readiness: Acceptable MVP shortcut.
- Impact on developer experience: More boilerplate and less discoverable handling.
- Impact on security or reliability: Reliability handlers can be missed by callers.
- Mentioned in prior review log: Yes, as a reason scores were not higher.
- Previous fix claimed to address it: No full fix claimed.
- Whether previous fix is sufficient: Acceptable for MVP, not for 8/10.
- Recommended remediation: Add typed subclasses for timeout, rate limit, response-too-large, and compatibility errors.
- Suggested validation or test: Add exception mapping tests.
- Should affect scoring: Slightly.

### SDK-AUDIT-020

- Title: SDK tests still normalize an internal-looking decision object that docs say should not exist.
- Category: Cross-file consistency / testing
- Severity: Low
- Confidence: High
- File path or area: `packages/product-platform/tests/test_tool_gateway_sdk_phase2.py:62-80`, `packages/ophanix-tool-gateway-sdk/README.md:160-164`, `packages/ophanix-tool-gateway-sdk/API_REFERENCE.md:117-119`, `packages/product-platform/src/product_platform/api/app.py:695-699`
- Evidence: Tests assert `result.decision == {"id": "decision_1", "decision": "allow"}` for SDK behavior with a fake gateway, while current product gateway returns only `decision` and `reason_code`.
- Why it matters: The SDK intentionally preserves arbitrary gateway fields, but the test fixture contradicts the documented product contract and may confuse maintainers.
- Root cause or likely root cause: Old fixture shape remained after gateway decision summary was narrowed.
- Impact on MVP readiness: Low; actual product route is fixed.
- Impact on developer experience: Maintainers may reintroduce internal IDs by treating the fixture as canonical.
- Impact on security or reliability: Low data-exposure regression risk if copied.
- Mentioned in prior review log: Decision exposure was a prior/stale concern in later audits, not in the original remediation summary as current.
- Previous fix claimed to address it: Current route fixed it.
- Whether previous fix is sufficient: Runtime fix is sufficient; test fixture should be cleaned.
- Recommended remediation: Update SDK tests to use the current decision summary shape and add a product contract assertion that no `decision.id` is returned.
- Suggested validation or test: Existing product route test plus fixture cleanup.
- Should affect scoring: Slightly.

### SDK-AUDIT-021

- Title: Default response redaction has no built-in plaintext secret patterns.
- Category: Security / data handling
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/tool_gateway/repository.py:625-660`, `packages/product-platform/src/product_platform/tool_gateway/response.py:54-161`, `packages/product-platform/src/product_platform/tool_gateway/invocation.py:673-688`
- Evidence: Default policy includes `redact_keys` but `redact_patterns` is empty. Non-JSON/text successful upstream bodies can be returned as text and only pattern rules can redact inside strings.
- Why it matters: A successful upstream text response containing a token, email, or other sensitive string is exposed unless operators author regex rules or an output schema blocks it.
- Root cause or likely root cause: Default redaction was optimized for structured JSON keys.
- Impact on MVP readiness: Acceptable for controlled pilots with vetted upstreams, but high-friction for broader partner use.
- Impact on developer experience: Operators must understand and configure response policies correctly.
- Impact on security or reliability: Potential sensitive data exposure in agent-visible responses.
- Mentioned in prior review log: Redaction was discussed.
- Previous fix claimed to address it: Yes, broader redaction was added.
- Whether previous fix is sufficient: Partial.
- Recommended remediation: Add conservative built-in string redaction patterns or default output schema examples, and document text response risk.
- Suggested validation or test: Add response-policy tests for text bodies containing `token=...` and email-like values.
- Should affect scoring: Yes.

### SDK-AUDIT-022

- Title: Agent-facing upstream error sanitizer does not redact PII-like text.
- Category: Security / data handling
- Severity: Low
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/tool_gateway/invocation.py:31-39`, `packages/product-platform/src/product_platform/tool_gateway/invocation.py:165-173`
- Evidence: `safe_agent_error_message()` redacts bearer tokens and sensitive assignments, but unlike SDK diagnostic sanitizer it does not cover email, phone, address, or SSN-like text unless in an assignment pattern.
- Why it matters: Custom executors or upstream wrappers could raise controlled `ToolExecutionError` messages containing customer identifiers.
- Root cause or likely root cause: Error sanitizer focused on secrets rather than broader PII.
- Impact on MVP readiness: Low for default executor, because default messages are generic.
- Impact on developer experience: Custom executor authors need undocumented caution.
- Impact on security or reliability: PII exposure risk if custom executor messages are not disciplined.
- Mentioned in prior review log: Redaction was discussed generally.
- Previous fix claimed to address it: Partial.
- Whether previous fix is sufficient: Partial.
- Recommended remediation: Align server error text sanitizer with SDK diagnostic redaction or document custom executor message rules.
- Suggested validation or test: Add tests for email/phone/SSN-like strings in `ToolExecutionError.message`.
- Should affect scoring: Slightly.

### SDK-AUDIT-023

- Title: Upstream SSRF guard has a DNS validate-then-connect gap.
- Category: Security / upstream networking
- Severity: Medium
- Confidence: Medium
- File path or area: `packages/product-platform/src/product_platform/tool_gateway/models.py:530-554`, `packages/product-platform/src/product_platform/tool_gateway/models.py:722-748`, `packages/product-platform/src/product_platform/tool_gateway/invocation.py:516-558`
- Evidence: Hostnames are resolved during validation and runtime URL construction, but HTTPX performs its own connection resolution later. The README acknowledges application DNS checks cannot pin every downstream route.
- Why it matters: DNS rebinding or infrastructure routing changes can bypass application-level checks unless egress controls exist.
- Root cause or likely root cause: Application-level DNS validation cannot enforce network egress pinning.
- Impact on MVP readiness: Acceptable only with controlled upstream allowlists and infrastructure egress boundaries.
- Impact on developer experience: Operators may overestimate the app-level SSRF protection.
- Impact on security or reliability: Potential SSRF path if untrusted operators can configure upstream hosts and infrastructure egress is permissive.
- Mentioned in prior review log: Upstream SSRF hardening was mentioned.
- Previous fix claimed to address it: Yes.
- Whether previous fix is sufficient: Partial; defense in depth remains required.
- Recommended remediation: Document required egress firewall/proxy policy more prominently and consider resolved-IP pinning or network-layer deny lists.
- Suggested validation or test: Add security tests for hostnames resolving to private ranges and document non-testable DNS rebinding assumptions.
- Should affect scoring: Yes.

### SDK-AUDIT-024

- Title: Upstream URL validation performs blocking DNS lookups in request validation paths.
- Category: Reliability / performance
- Severity: Low
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/tool_gateway/models.py:530-554`, `packages/product-platform/src/product_platform/tool_gateway/models.py:733-748`
- Evidence: `validate_http_url()` calls `_hostname_resolves_to_forbidden_address()`, which uses `socket.getaddrinfo()`.
- Why it matters: Operator requests that create/update upstream targets can block on DNS latency or failure.
- Root cause or likely root cause: Synchronous validation in Pydantic model helpers.
- Impact on MVP readiness: Acceptable for low traffic, but can make control-plane operations feel unreliable.
- Impact on developer experience: Slow or surprising upstream target writes.
- Impact on security or reliability: DNS failures can become API failures; repeated bad hosts can consume request workers.
- Mentioned in prior review log: No.
- Previous fix claimed to address it: No.
- Whether previous fix is sufficient: Not applicable.
- Recommended remediation: Add timeout/caching around DNS checks or move validation to an async/background health path.
- Suggested validation or test: Add tests using monkeypatched slow/failing resolver and assert bounded behavior.
- Should affect scoring: Slightly.

### SDK-AUDIT-025

- Title: Upstream host allowlist is required only for `environment="production"`.
- Category: Security configuration
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/api/app.py:743-772`, `packages/product-platform/src/product_platform/api/settings.py:157-159`
- Evidence: `_validate_production_settings()` requires `tool_gateway_upstream_host_allowlist` only inside the `is_production` branch. Staging, pilot, or other non-local external environments can start with an empty allowlist.
- Why it matters: External pilots often run in staging-like environments that still handle real partner data.
- Root cause or likely root cause: Strictest startup checks are tied to the literal production environment.
- Impact on MVP readiness: Controlled internal MVP can accept this, but design-partner pilots should not.
- Impact on developer experience: Operators may assume any non-local environment enforces production-like upstream controls.
- Impact on security or reliability: Wider SSRF/misconfiguration risk outside literal production.
- Mentioned in prior review log: Upstream allowlist hardening was discussed.
- Previous fix claimed to address it: Yes for production.
- Whether previous fix is sufficient: Partial.
- Recommended remediation: Require allowlists for all non-local environments unless an explicit `ALLOW_UNRESTRICTED_UPSTREAMS` development flag is set.
- Suggested validation or test: Startup tests for `environment="staging"` with no allowlist.
- Should affect scoring: Yes.

### SDK-AUDIT-026

- Title: Non-local deployments can boot without a secret-manager ref and fail lazily on first upstream-auth use.
- Category: Reliability / configuration / developer experience
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/api/app.py:743-772`, `packages/product-platform/src/product_platform/integrations/secrets.py:95-122`, `packages/product-platform/src/product_platform/api/app.py:1265-1273`
- Evidence: Startup validation requires `secret_manager_ref` only for literal production. `build_secret_provider()` rejects missing secret manager outside local/test, but `_secret_provider()` is called lazily.
- Why it matters: A staging or partner pilot can start successfully and then fail at runtime when invoking an authenticated upstream.
- Root cause or likely root cause: Startup validation and lazy provider construction do not share the same non-local requirement.
- Impact on MVP readiness: Important for external pilots.
- Impact on developer experience: Runtime failures look like upstream auth problems instead of a startup misconfiguration.
- Impact on security or reliability: Reliability failure for authenticated tools.
- Mentioned in prior review log: Secret manager production hardening was mentioned.
- Previous fix claimed to address it: Partial.
- Whether previous fix is sufficient: Partial.
- Recommended remediation: Validate secret-manager config at startup for all non-local environments, or eagerly construct `_secret_provider()`.
- Suggested validation or test: Startup test for `environment="staging"` with bearer upstream and missing secret manager.
- Should affect scoring: Yes.

### SDK-AUDIT-027

- Title: Standalone sync upstream executor defaults to environment-proxy behavior.
- Category: Security / reliability
- Severity: Low
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/tool_gateway/invocation.py:243-260`, `packages/product-platform/src/product_platform/api/app.py:1035`
- Evidence: `HttpToolInvocationExecutor` creates `httpx.Client()` without `trust_env=False`. The app-managed async client uses `httpx.AsyncClient(follow_redirects=False, trust_env=False)`, so the default product route is safer.
- Why it matters: Unit or custom deployments using the sync executor directly can send upstream auth headers through configured proxies.
- Root cause or likely root cause: Sync executor is older/general-purpose and not aligned with app-managed client hardening.
- Impact on MVP readiness: Low for the default app path, because it uses async managed client.
- Impact on developer experience: Custom executor users have a subtle config hazard.
- Impact on security or reliability: Possible upstream secret exposure to proxies.
- Mentioned in prior review log: No.
- Previous fix claimed to address it: No.
- Whether previous fix is sufficient: Not applicable.
- Recommended remediation: Set `trust_env=False` on owned sync/async executor clients or document custom deployment requirements.
- Suggested validation or test: Executor construction test or proxy-env behavior test.
- Should affect scoring: Slightly.

### SDK-AUDIT-028

- Title: Gateway body-limit middleware matches only exact runtime paths.
- Category: Reliability / security
- Severity: Low
- Confidence: Medium
- File path or area: `packages/product-platform/src/product_platform/api/app.py:805-810`, `packages/product-platform/src/product_platform/api/app.py:877-957`
- Evidence: `_is_tool_gateway_runtime_path()` caps `/api/v1/gateway/tools`, `/api/v1/gateway/capabilities`, and exact `/api/v1/tools/{name}/invoke` shape. Trailing slashes, path normalization variants, or future runtime routes would not be covered until added.
- Why it matters: Body caps are easy to accidentally bypass when routes evolve.
- Root cause or likely root cause: Explicit allowlist uses string/path-shape matching.
- Impact on MVP readiness: Low today, because current canonical routes are covered.
- Impact on developer experience: Future route additions need manual middleware updates.
- Impact on security or reliability: Potential request-body DoS on near-runtime paths or future routes.
- Mentioned in prior review log: Body-size limit was discussed.
- Previous fix claimed to address it: Yes.
- Whether previous fix is sufficient: Mostly for current routes; fragile for evolution.
- Recommended remediation: Normalize trailing slashes and cover route groups declaratively, or add a broader gateway prefix cap.
- Suggested validation or test: Add tests for trailing slash and future route registration behavior.
- Should affect scoring: Slightly.

### SDK-AUDIT-029

- Title: Product-platform keeps a source-tree SDK compatibility copy beside a standalone SDK dependency.
- Category: Packaging / maintainability
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/src/ophanix_tool_gateway/sdk.py`, `packages/product-platform/pyproject.toml:15-25`, `packages/product-platform/pyproject.toml:63-87`, `packages/ophanix-tool-gateway-sdk/scripts/validate_release.py:253-260`
- Evidence: Product-platform declares dependency on `ophanix-tool-gateway-sdk` and excludes `/src/ophanix_tool_gateway` from wheel/sdist, but the source tree still contains a copy for compatibility. SDK release validation enforces byte parity.
- Why it matters: Editable installs and local source imports can still shadow the standalone package. Parity is checked during SDK release validation, not automatically on every product-platform edit unless CI path hits it.
- Root cause or likely root cause: Backward-compatible internal import path was retained while extracting standalone package.
- Impact on MVP readiness: Manageable but maintainability-heavy.
- Impact on developer experience: Confusing import behavior in local development.
- Impact on security or reliability: Drift could create mismatched SDK behavior across install modes.
- Mentioned in prior review log: Yes, older duplicate package concerns existed.
- Previous fix claimed to address it: Yes, product wheel exclusion and parity validator.
- Whether previous fix is sufficient: Partial.
- Recommended remediation: Remove the source copy when possible, or make product-platform import from installed standalone SDK with a compatibility shim only.
- Suggested validation or test: CI parity check independent of release validation; editable-install import test.
- Should affect scoring: Yes, for maintainability.

### SDK-AUDIT-030

- Title: Product Tool Gateway mypy settings weaken type validation.
- Category: Testing / maintainability
- Severity: Low
- Confidence: High
- File path or area: `packages/product-platform/pyproject.toml:99-104`
- Evidence: Product mypy uses `ignore_missing_imports = true` and `follow_imports = "skip"`.
- Why it matters: Passing mypy does not prove much about external dependency contracts or deeper product-platform call paths.
- Root cause or likely root cause: Monorepo dependency typing constraints.
- Impact on MVP readiness: Low because runtime tests are strong, but it limits confidence.
- Impact on developer experience: Type regressions may reach runtime tests.
- Impact on security or reliability: Indirect reliability risk.
- Mentioned in prior review log: Type gates were discussed.
- Previous fix claimed to address it: Type checks were added.
- Whether previous fix is sufficient: Partial.
- Recommended remediation: Tighten mypy incrementally for `product_platform.tool_gateway` and local dependencies.
- Suggested validation or test: Enable stricter mypy for one module at a time.
- Should affect scoring: Slightly.

### SDK-AUDIT-031

- Title: Repository does not close the final PyPI provenance loop.
- Category: Packaging / release / supply chain
- Severity: Medium
- Confidence: High
- File path or area: `.github/workflows/publish.yml:31-37`, `.github/workflows/publish.yml:115-133`, `packages/ophanix-tool-gateway-sdk/README.md:458-462`
- Evidence: The publish workflow builds, validates, signs, attests, and uploads artifacts, but comments say actual PyPI publishing is intentionally outside the GitHub job.
- Why it matters: The package being published is accepted, but the repo alone cannot prove the artifact uploaded to PyPI is exactly the signed/validated artifact.
- Root cause or likely root cause: External organizational release process.
- Impact on MVP readiness: Acceptable for internal MVP if release owners preserve evidence; not ideal for external trust.
- Impact on developer experience: Consumers cannot verify provenance from repo automation alone.
- Impact on security or reliability: Supply-chain assurance gap.
- Mentioned in prior review log: Yes.
- Previous fix claimed to address it: Partial, with attestations and docs.
- Whether previous fix is sufficient: Partial.
- Recommended remediation: Add trusted publishing or an auditable release manifest linking PyPI file hashes to workflow artifact hashes.
- Suggested validation or test: Release checklist test or documented artifact-hash verification.
- Should affect scoring: Yes, but publication itself is not a missing item.

### SDK-AUDIT-032

- Title: Release validators can intentionally skip `twine check`.
- Category: Packaging / release
- Severity: Low
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/scripts/validate_release.py:41-83`, `packages/product-platform/scripts/validate_release.py`
- Evidence: `--skip-twine-check` exists and records a warning. CI/publish paths run validators without skip, but local validation can bypass metadata checking.
- Why it matters: Local release evidence can look green while metadata checks were skipped.
- Root cause or likely root cause: Convenience for environments without release extras.
- Impact on MVP readiness: Low, because CI/publish enforce full validation.
- Impact on developer experience: Reviewers must inspect manifest flags.
- Impact on security or reliability: Low supply-chain/process risk.
- Mentioned in prior review log: Release validation was discussed.
- Previous fix claimed to address it: Yes.
- Whether previous fix is sufficient: Mostly.
- Recommended remediation: Keep skip, but make final release docs forbid skip and require manifest review.
- Suggested validation or test: CI assertion that publish workflow never passes `--skip-twine-check`.
- Should affect scoring: Minimal.

### SDK-AUDIT-033

- Title: Credential issuance docs still warn endpoint names may differ.
- Category: Documentation / developer experience
- Severity: Medium
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/README.md:325-358`
- Evidence: README provides a local credential issuance flow, then says exact endpoint names may differ in private operator builds.
- Why it matters: SDK consumers need a stable path to get a token. If the issuance API is not stable, onboarding depends on operator support.
- Root cause or likely root cause: Product API and private deployments may not yet have a stable external credential issuance contract.
- Impact on MVP readiness: Important DX risk for external design partners.
- Impact on developer experience: Slows onboarding and automation.
- Impact on security or reliability: Workarounds can lead to fixture tokens or manual token handling.
- Mentioned in prior review log: Token issuance/setup documentation was discussed.
- Previous fix claimed to address it: Yes, docs improved.
- Whether previous fix is sufficient: Partial.
- Recommended remediation: Publish a stable credential issuance contract or explicit operator-runbook API for MVP pilots.
- Suggested validation or test: End-to-end quickstart test from dev login to issued gateway token to SDK invocation.
- Should affect scoring: Yes, ease of use.

### SDK-AUDIT-034

- Title: API reference does not document async cache-clear semantics accurately.
- Category: Documentation / public API
- Severity: Low
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/API_REFERENCE.md:55-59`, `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py:1460-1475`
- Evidence: API reference says async client methods mirror sync and lists awaitable methods, but it omits `aclear_tool_cache()` and does not state that `clear_tool_cache()` is synchronous on the async client.
- Why it matters: Users may call the wrong cache-clear method in async code.
- Root cause or likely root cause: Docs lagged behind async cache API details.
- Impact on MVP readiness: Low.
- Impact on developer experience: Minor confusion.
- Impact on security or reliability: Stale discovery cache risk if users avoid clearing due to uncertainty.
- Mentioned in prior review log: Docs were discussed.
- Previous fix claimed to address it: Documentation improvements were claimed.
- Whether previous fix is sufficient: Partial.
- Recommended remediation: Update API reference and README method lists.
- Suggested validation or test: Documentation/API surface sync check.
- Should affect scoring: Minimal.

### SDK-AUDIT-035

- Title: Public API docs are manually maintained and can drift from source.
- Category: Documentation / maintainability
- Severity: Low
- Confidence: Medium
- File path or area: `packages/ophanix-tool-gateway-sdk/API_REFERENCE.md`, `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/__init__.py`
- Evidence: API docs are hand-written Markdown. Current drift exists around async cache clearing.
- Why it matters: Manual docs are easy to miss as the 0.x API evolves.
- Root cause or likely root cause: No generated API docs or public-surface contract checker.
- Impact on MVP readiness: Low, but relevant for early adopters.
- Impact on developer experience: Confusing or stale docs.
- Impact on security or reliability: Indirect.
- Mentioned in prior review log: No generated API reference was mentioned as a cap.
- Previous fix claimed to address it: No full fix.
- Whether previous fix is sufficient: Partial.
- Recommended remediation: Generate API reference from types/docstrings or add an export/signature snapshot test.
- Suggested validation or test: Snapshot `__all__` and constructor signatures against docs.
- Should affect scoring: Slightly.

### SDK-AUDIT-036

- Title: Missing negative test for API create with active status and missing schema.
- Category: Testing
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/tests/test_tool_gateway_registry_phase3.py:169-179`
- Evidence: Existing API test covers activation failure when schema is missing, but not create failure when request body sets `status="active"` and `input_schema_json=null`.
- Why it matters: This is the exact gap behind SDK-AUDIT-001.
- Root cause or likely root cause: Tests target documented lifecycle path only.
- Impact on MVP readiness: Test gap for a control-plane invariant.
- Impact on developer experience: Maintainers may miss the bypass.
- Impact on security or reliability: Indirect but meaningful.
- Mentioned in prior review log: No.
- Previous fix claimed to address it: No.
- Whether previous fix is sufficient: Not applicable.
- Recommended remediation: Add the negative test and then fix the behavior.
- Suggested validation or test: `POST /api/v1/tools` with active status and no schema returns 422.
- Should affect scoring: Yes.

### SDK-AUDIT-037

- Title: Missing test for idempotency completion failure after upstream success.
- Category: Testing / reliability
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/tests/test_tool_gateway_invocation_phase3.py:190-291`, `packages/product-platform/tests/test_tool_gateway_runtime_audit_phase3.py:133-244`
- Evidence: Tests cover replay, conflict, stale retry, mismatched header/body, and cleanup of terminal rows. They do not inject failure into `complete_invocation()` after upstream success.
- Why it matters: The hardest idempotency failure mode remains unproven.
- Root cause or likely root cause: Tests cover steady-state repository behavior, not crash/failure injection between transactions.
- Impact on MVP readiness: Important reliability gap.
- Impact on developer experience: Unknown-outcome behavior can surprise adopters.
- Impact on security or reliability: Duplicate side effects if callers do not reconcile.
- Mentioned in prior review log: Idempotency validation was discussed.
- Previous fix claimed to address it: Runtime idempotency tests were added.
- Whether previous fix is sufficient: Partial.
- Recommended remediation: Add a failure-injection test around `_store_idempotency_response()`.
- Suggested validation or test: Monkeypatch repository completion to raise after fake executor success; assert stale/unknown docs and audit.
- Should affect scoring: Yes.

### SDK-AUDIT-038

- Title: Missing tests for proxy environment behavior.
- Category: Testing / security configuration
- Severity: Low
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/tests/test_sdk_behavior.py`, `packages/product-platform/tests/test_tool_gateway_forwarding_phase*.py`
- Evidence: Search found no tests around `trust_env`, `HTTP_PROXY`, `HTTPS_PROXY`, or proxy routing for SDK clients.
- Why it matters: SDK-AUDIT-013 and SDK-AUDIT-027 are silent default behavior risks.
- Root cause or likely root cause: Network proxy behavior was not part of the MVP test matrix.
- Impact on MVP readiness: Low unless users run in proxy-heavy environments.
- Impact on developer experience: Hidden network behavior can be hard to debug.
- Impact on security or reliability: Token/upstream-secret proxy exposure risk if defaults are undesirable.
- Mentioned in prior review log: No.
- Previous fix claimed to address it: No.
- Whether previous fix is sufficient: Not applicable.
- Recommended remediation: Add tests that owned clients set intended `trust_env` behavior or docs warning.
- Suggested validation or test: Unit tests around constructed clients or integration test with local proxy env vars.
- Should affect scoring: Slightly.

### SDK-AUDIT-039

- Title: Missing tests for DNS rebinding or runtime DNS changes.
- Category: Testing / security
- Severity: Low
- Confidence: Medium
- File path or area: `packages/product-platform/tests/test_tool_gateway_upstream_phase*.py`
- Evidence: Tests cover private/loopback/url validation and allowlist behavior, but not a hostname that resolves safely during validation and differently during connect.
- Why it matters: The README acknowledges DNS checks are not a complete boundary.
- Root cause or likely root cause: Rebinding is hard to test in normal unit tests.
- Impact on MVP readiness: Low if infrastructure egress controls are documented and enforced.
- Impact on developer experience: Security assumptions may be unclear.
- Impact on security or reliability: SSRF defense-in-depth gap remains unverified.
- Mentioned in prior review log: SSRF hardening was mentioned.
- Previous fix claimed to address it: Yes, partial.
- Whether previous fix is sufficient: Partial.
- Recommended remediation: Add threat-model documentation and, if practical, resolver-injection tests.
- Suggested validation or test: Mock resolver/connect split and assert documented behavior.
- Should affect scoring: Slightly.

### SDK-AUDIT-040

- Title: Response schemas remain optional for active tools.
- Category: Runtime correctness / API contract
- Severity: Low
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/tool_gateway/models.py:37-38`, `packages/product-platform/src/product_platform/tool_gateway/repository.py:510-517`, `packages/product-platform/src/product_platform/tool_gateway/response.py:39-52`
- Evidence: Activation requires input schema but not output schema. Response validation only runs if `output_schema_json` exists.
- Why it matters: Without output schema, upstream responses are less predictable and consumers must inspect source/docs for shape.
- Root cause or likely root cause: MVP allows incremental tool onboarding.
- Impact on MVP readiness: Acceptable MVP shortcut, but not ideal for broader rollout.
- Impact on developer experience: SDK consumers may get inconsistent response body shapes across tools.
- Impact on security or reliability: Reduced guardrail against unexpected upstream data.
- Mentioned in prior review log: Response contract validation was discussed.
- Previous fix claimed to address it: Optional response validation was improved.
- Whether previous fix is sufficient: Acceptable for MVP, incomplete for 8/10.
- Recommended remediation: Require output schemas for externally exposed tools or add a readiness check that flags missing schemas.
- Suggested validation or test: Tool activation test with policy requiring output schema for external exposure.
- Should affect scoring: Slightly.

### SDK-AUDIT-041

- Title: SDK API stability policy is still mostly "0.x beta" rather than integration-grade.
- Category: API stability / documentation
- Severity: Low
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/API_REFERENCE.md:1-4`, `packages/ophanix-tool-gateway-sdk/CHANGELOG.md:3-31`, `packages/ophanix-tool-gateway-sdk/pyproject.toml:18-28`
- Evidence: Package is classified Beta and docs refer to the supported `0.x` line, but there is no detailed breaking-change policy beyond migration notes and compatibility shim guidance.
- Why it matters: Early external adopters need to know how stable names, result shapes, retry semantics, and deprecated fields are.
- Root cause or likely root cause: Package is newly extracted and pre-1.0.
- Impact on MVP readiness: Acceptable for controlled MVP, not for broad self-service adoption.
- Impact on developer experience: Consumers may pin tightly or avoid adoption without clearer compatibility guarantees.
- Impact on security or reliability: Indirect.
- Mentioned in prior review log: Stability/deprecation was discussed generally.
- Previous fix claimed to address it: Partial.
- Whether previous fix is sufficient: Partial.
- Recommended remediation: Add a 0.x compatibility policy with explicit guarantees and known unstable surfaces.
- Suggested validation or test: Docs review.
- Should affect scoring: Slightly.

### SDK-AUDIT-042

- Title: No end-to-end quickstart validation proves README token issuance commands still work.
- Category: Testing / documentation
- Severity: Medium
- Confidence: Medium
- File path or area: `packages/ophanix-tool-gateway-sdk/README.md:325-358`, `packages/product-platform/tests/test_tool_gateway_installed_sdk_contract.py`
- Evidence: Installed-wheel network gateway tests prove SDK-to-running-gateway behavior, but there is no test that executes the README dev-login plus credential issuance flow as written.
- Why it matters: The token path is often the hardest first-hour onboarding step.
- Root cause or likely root cause: Test suite validates pieces but not the docs workflow.
- Impact on MVP readiness: Meaningful DX gap for external design partners.
- Impact on developer experience: Users may need operator help before their first successful call.
- Impact on security or reliability: Workarounds can lead to unsafe manual token handling.
- Mentioned in prior review log: Token issuance docs were discussed.
- Previous fix claimed to address it: Documentation improved.
- Whether previous fix is sufficient: Partial.
- Recommended remediation: Add a docs smoke test or scripted local quickstart that issues a credential and calls a tool.
- Suggested validation or test: Run README command sequence against a local server in CI.
- Should affect scoring: Yes, ease of use.

## 5. Issues Grouped By Category

Public API and developer experience:

- SDK-AUDIT-008, SDK-AUDIT-014, SDK-AUDIT-016, SDK-AUDIT-017, SDK-AUDIT-018, SDK-AUDIT-019, SDK-AUDIT-033, SDK-AUDIT-034, SDK-AUDIT-035, SDK-AUDIT-041, SDK-AUDIT-042

Runtime correctness and lifecycle:

- SDK-AUDIT-001, SDK-AUDIT-003, SDK-AUDIT-004, SDK-AUDIT-040

Security and data handling:

- SDK-AUDIT-007, SDK-AUDIT-012, SDK-AUDIT-013, SDK-AUDIT-021, SDK-AUDIT-022, SDK-AUDIT-023, SDK-AUDIT-025, SDK-AUDIT-026, SDK-AUDIT-027, SDK-AUDIT-028, SDK-AUDIT-031

Reliability and operations:

- SDK-AUDIT-004, SDK-AUDIT-005, SDK-AUDIT-006, SDK-AUDIT-024, SDK-AUDIT-026

Testing:

- SDK-AUDIT-002, SDK-AUDIT-036, SDK-AUDIT-037, SDK-AUDIT-038, SDK-AUDIT-039, SDK-AUDIT-042

Packaging and release:

- SDK-AUDIT-029, SDK-AUDIT-030, SDK-AUDIT-031, SDK-AUDIT-032

Documentation and examples:

- SDK-AUDIT-009, SDK-AUDIT-010, SDK-AUDIT-011, SDK-AUDIT-012, SDK-AUDIT-033, SDK-AUDIT-034, SDK-AUDIT-035, SDK-AUDIT-041, SDK-AUDIT-042

Cross-file consistency:

- SDK-AUDIT-020, SDK-AUDIT-029, SDK-AUDIT-034

## 6. Critical And High-Severity Blockers

No critical or high-severity blocker was directly proven in the current repository.

The strongest medium-severity blockers for broader MVP adoption are:

- SDK-AUDIT-001: active tool creation bypasses activation safeguards.
- SDK-AUDIT-004: idempotency completion failure can leave successful upstream outcomes unreplayable.
- SDK-AUDIT-005/006/007: cleanup and retention are manual and incomplete for untouched stale `in_progress` rows.
- SDK-AUDIT-021/023/025/026: upstream data and network boundaries still depend on operator configuration and infrastructure.
- SDK-AUDIT-033/042: credential issuance/onboarding path is not yet self-service-stable enough.

## 7. Medium-Severity MVP Risks

- SDK-AUDIT-001
- SDK-AUDIT-003
- SDK-AUDIT-004
- SDK-AUDIT-005
- SDK-AUDIT-006
- SDK-AUDIT-007
- SDK-AUDIT-008
- SDK-AUDIT-013
- SDK-AUDIT-021
- SDK-AUDIT-023
- SDK-AUDIT-025
- SDK-AUDIT-026
- SDK-AUDIT-029
- SDK-AUDIT-031
- SDK-AUDIT-033
- SDK-AUDIT-036
- SDK-AUDIT-037
- SDK-AUDIT-042

## 8. Low-Severity And Nit-Level Issues

- SDK-AUDIT-002
- SDK-AUDIT-009
- SDK-AUDIT-010
- SDK-AUDIT-011
- SDK-AUDIT-012
- SDK-AUDIT-014
- SDK-AUDIT-015
- SDK-AUDIT-016
- SDK-AUDIT-017
- SDK-AUDIT-018
- SDK-AUDIT-019
- SDK-AUDIT-020
- SDK-AUDIT-022
- SDK-AUDIT-024
- SDK-AUDIT-027
- SDK-AUDIT-028
- SDK-AUDIT-030
- SDK-AUDIT-032
- SDK-AUDIT-034
- SDK-AUDIT-035
- SDK-AUDIT-038
- SDK-AUDIT-039
- SDK-AUDIT-040
- SDK-AUDIT-041

## 9. Prior Findings Status Table

| Prior finding area | Current status | Challenge |
| --- | --- | --- |
| Wrong SDK discovery endpoint | Resolved | SDK uses `/api/v1/gateway/tools`. |
| Operator-facing discovery shape | Resolved | Product gateway returns gateway-safe discovery shape. |
| Weak SDK URL/token/payload validation | Mostly resolved | Strict validation exists; object-only payload is an intentional MVP constraint. |
| `get_tool()` first-page only | Resolved | `get_tool()` uses paginated discovery. |
| `StaticTokenProvider` repr leak | Resolved | Token field uses `repr=False`. |
| Raw exception bodies | Mostly resolved | SDK sanitizes diagnostic bodies; server upstream text sanitization is narrower. |
| Missing environment provider/list_all/retries/cache clear | Resolved | Current SDK has these. |
| Retry-After ignored | Resolved | SDK uses `Retry-After` for retries. |
| SDK embedded only in product-platform | Resolved for distribution | Standalone package exists and is published; source compatibility copy remains a maintainability risk. |
| Credential resource binding flattened | Resolved | Discovery and auth check resource-scoped credential scopes. |
| Discovery cache crossing credentials | Resolved | Cache keys include token fingerprint. |
| No async SDK | Resolved | Async client exists. |
| Standalone package buildability thin | Resolved enough for MVP | Release validators and packaging tests pass. |
| Response contract validation incomplete | Mostly resolved | Output schema remains optional. |
| Error redaction missing common patterns | Improved | Text response and server error redaction still have gaps. |
| Release validation ad hoc | Resolved for build validation | Final PyPI provenance handoff remains external. |
| Sync/async config duplication | Improved | Main SDK remains a large mirrored single-file implementation. |
| Idempotency missing | Resolved at happy-path level | Edge cases remain around failed completion, manual cleanup, and partial replay scope. |
| Min SDK version ignored | Resolved | Current compatibility check compares min SDK version, though parser is simplistic. |
| No installed-wheel running-gateway test | Resolved | Product tests include installed wheel against a running network gateway. |
| Full internal decision object exposed | Resolved in current product route | Some SDK fake-gateway tests still use old internal-looking shape. |
| Duplicate top-level SDK package in product wheel | Resolved in wheel/sdist | Source-tree compatibility copy remains. |

## 10. Scoring Matrix

| Category | Current score | Prior score | Upheld, raised, or lowered | Exact reasons | Score cap caused by unresolved issues |
| --- | ---: | ---: | --- | --- | --- |
| Implementation quality | 7.0/10 | 8.1/10 | Lowered | Current implementation is functional and well-tested, but active-create lifecycle bypass, idempotency edge cases, optional output contracts, large mirrored SDK file, and source-copy maintenance risk prevent 8. | Capped at 7 by SDK-AUDIT-001, 004, 029, 036, 037. |
| Ease of use | 7.0/10 | 8.3/10 | Lowered | Docs are substantial and examples exist, but first-copy examples omit or misuse idempotency, result shape requires envelope unwrapping, credential issuance is not fully stable/self-service, and async cache docs drift. | Capped at 7 by SDK-AUDIT-008, 009, 010, 011, 033, 034, 042. |
| Security and reliability | 6.8/10 | 8.3/10 | Lowered | Strong MVP controls exist, but retention cleanup, stale idempotency, text redaction, proxy defaults, DNS/egress assumptions, staging config gaps, and manual operations keep risk above a 7. | Capped below 7 by SDK-AUDIT-005, 006, 007, 013, 021, 023, 025, 026. |

## 11. Score Cap Explanation

Implementation quality cannot exceed 7 until the control-plane lifecycle invariant is fixed and idempotency edge cases are validated.

Ease of use cannot exceed 7 until the first-hour onboarding path is stable: issued token, compatibility check, discovery, invocation with idempotency, and ergonomic result access.

Security/reliability cannot exceed 7 until replay retention is operationally enforced, stale `in_progress` records are handled without needing a retry, upstream response text redaction is safer by default, and external pilot environments enforce production-like upstream/secret-manager settings.

No score should reach 8 until repository evidence proves the current package, gateway runtime, docs, release path, and tests all support a serious production pilot without source-level debugging.

## 12. Required Fixes To Reach MVP Readiness

The repository is already a credible controlled MVP, but these should be fixed before wider MVP rollout:

1. Block or validate direct `status="active"` creates.
2. Add missing tests for active-create missing schema and idempotency completion failure.
3. Operationalize idempotency cleanup and handle stale untouched `in_progress` records.
4. Clarify and improve idempotency docs/examples.
5. Add result-body ergonomics or stronger docs.
6. Close staging/non-production secret-manager and upstream allowlist config gaps for external pilots.
7. Document or change SDK proxy defaults.
8. Stabilize credential issuance quickstart.

## 13. Required Fixes To Reach 7 Out Of 10

Implementation quality is already at 7. Ease of use is already at 7. Security/reliability is slightly below a clean 7 and needs:

1. Scheduled or deployment-integrated idempotency cleanup.
2. Cleanup handling for old untouched `in_progress` rows.
3. Clear docs for unknown idempotency outcomes and reconciliation.
4. Explicit SDK proxy-default decision and tests.
5. Production-like upstream allowlist and secret-manager validation for non-local pilot environments.

## 14. Required Fixes To Reach 8 Out Of 10

1. Lifecycle invariant fully enforced and covered by tests.
2. Idempotency semantics precisely scoped, tested under failure injection, and operationally cleaned.
3. SDK result ergonomics improved without breaking existing consumers.
4. Output schemas or response-readiness checks required for externally exposed tools.
5. Text response and server error redaction made safer by default.
6. Source-copy compatibility risk removed or continuously enforced outside release scripts.
7. PyPI provenance loop closed with trusted publishing or hash linkage.
8. API reference generated or snapshot-checked against exported source.
9. End-to-end README quickstart test issues a token and performs a real SDK call.
10. Staging/external-pilot config validation aligned with production safety requirements.

## 15. Recommended Remediation Order

1. Fix SDK-AUDIT-001 and SDK-AUDIT-036 together.
2. Fix SDK-AUDIT-004, SDK-AUDIT-005, SDK-AUDIT-006, SDK-AUDIT-007, and SDK-AUDIT-037 as one idempotency reliability package.
3. Fix SDK-AUDIT-021, SDK-AUDIT-022, SDK-AUDIT-023, SDK-AUDIT-025, SDK-AUDIT-026, SDK-AUDIT-027, and SDK-AUDIT-038/039 as one security hardening package.
4. Fix SDK-AUDIT-008, SDK-AUDIT-009, SDK-AUDIT-010, SDK-AUDIT-011, SDK-AUDIT-012, SDK-AUDIT-033, SDK-AUDIT-034, and SDK-AUDIT-042 as one onboarding package.
5. Fix SDK-AUDIT-029, SDK-AUDIT-030, SDK-AUDIT-031, SDK-AUDIT-032, SDK-AUDIT-035, and SDK-AUDIT-041 as one packaging/governance package.
6. Clean up low-risk API nits SDK-AUDIT-014 through SDK-AUDIT-020.

## 16. Validation Plan

Validation already run during this audit:

| Command | Result |
| --- | --- |
| `python3 -m pytest tests -q --tb=short` in `packages/ophanix-tool-gateway-sdk` | Passed: 33 tests. |
| `python3 -m mypy src/ophanix_tool_gateway` in `packages/ophanix-tool-gateway-sdk` | Passed. |
| `python3 scripts/validate_release.py --out-dir /tmp/ophanix-sdk-audit-current --skip-twine-check` | Passed; built wheel/sdist and validated artifacts, with twine intentionally skipped for local audit. |
| `python3 -m pytest tests/test_tool_gateway_*.py -q --tb=short` in `packages/product-platform` | Passed: 312 tests, 2 warnings. |
| `python3 -m mypy src/product_platform/tool_gateway src/ophanix_tool_gateway` in `packages/product-platform` | Passed. |
| `python3 scripts/validate_release.py --out-dir /tmp/ophanix-product-audit-current --skip-twine-check` | Passed; built wheel/sdist and validated artifacts, with twine intentionally skipped for local audit. |

Additional validation required after remediations:

1. API negative test for active create without schema.
2. Failure-injection test around idempotency completion.
3. Cleanup test for stale untouched `in_progress` records.
4. Proxy environment test for SDK and sync executor defaults.
5. Text-response redaction tests.
6. Staging startup config tests for secret manager and upstream allowlist.
7. Docs quickstart smoke test from token issuance to SDK invocation.
8. API-doc signature/export snapshot test.
9. Package provenance check linking PyPI file hashes to signed workflow artifacts.

## 17. Final Strict MVP Assessment

This is a credible MVP for controlled evaluation. A competent internal team or supported design partner can install the published package, obtain a gateway token, discover tools, call tools, handle denied/auth errors, use idempotency on retryable calls, and validate behavior with the current test suite.

It is not yet a broad self-service MVP and not a production-ready SDK/gateway pair. The main reason is not missing happy-path functionality; the happy path is real and tested. The risk is in the edges early adopters hit quickly: lifecycle shortcuts, idempotency unknown outcomes, cleanup operations, response data handling, upstream network assumptions, confusing result shape, and onboarding/token issuance uncertainty.

Initial strict assessment before remediation: functional controlled MVP, score profile `7.0 / 7.0 / 6.8`. Broader adoption should wait for the remediation order above.

## 18. Remediation Passes After Initial Audit

### Pass 1: Tool Lifecycle Invariant

Issues addressed:

- SDK-AUDIT-001
- SDK-AUDIT-002
- SDK-AUDIT-036

Root cause confirmed:

- `ToolDefinitionCreateRequest` accepted every supported lifecycle state.
- `ToolRegistryRepository.create_tool()` persisted that caller-provided status directly.
- The activation guard requiring an input schema lived only in `activate_tool()`, so direct active creation was a bypass of the lifecycle invariant.

Implemented fix:

- `packages/product-platform/src/product_platform/tool_gateway/models.py` now rejects creation requests unless `status == "draft"`.
- Operators must create draft tools and then use lifecycle endpoints to activate, disable, or retire tools.
- `packages/product-platform/tests/test_tool_gateway_registry_phase3.py` now has an API negative test proving non-draft creation is rejected.

Validation:

- `python3 -m pytest tests/test_tool_gateway_registry_phase3.py -q --tb=short`: passed, 7 tests.
- Later full Tool Gateway validation passed, proving existing fixtures use draft-then-activate flows or otherwise do not depend on the bypass.

Residual concern:

- Existing database rows created before this fix could still be active without a schema. That is an operational data-quality concern, not a code-path bypass in the current repository.

Status:

- SDK-AUDIT-001: resolved for new create requests.
- SDK-AUDIT-002: resolved enough for the identified gap.
- SDK-AUDIT-036: resolved.

### Pass 2: Idempotency Recovery And Unknown Outcomes

Issues addressed:

- SDK-AUDIT-004
- SDK-AUDIT-005
- SDK-AUDIT-006
- SDK-AUDIT-007
- SDK-AUDIT-037

Root cause confirmed:

- Completed replay rows were retained until manual cleanup.
- Untouched stale `in_progress` rows were only marked unknown if a caller retried the same idempotency key.
- A failure in `complete_invocation()` after successful upstream execution produced an internal gateway failure and left the caller without a precise unknown-outcome signal.
- SDK invocation retries treated every `503` as retryable when an idempotency key was present, which would have retried a newly explicit unknown-outcome response and degraded it into a confusing `409`.

Implemented fix:

- `packages/product-platform/src/product_platform/tool_gateway/runtime_audit.py` now returns `IdempotencyCleanupResult` from cleanup and marks stale `in_progress` rows as `failed_unknown` before deleting terminal rows beyond retention.
- `packages/product-platform/src/product_platform/cli.py` now reports both stale rows marked unknown and terminal rows deleted.
- `packages/product-platform/src/product_platform/api/app.py` now catches idempotency replay persistence failures after attempted execution, logs the exception, and returns a structured `503` with `error.code == "idempotency_persistence_failed"` and `Idempotency-Persistence: failed`.
- `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py` and the product compatibility copy now treat `idempotency_persistence_failed` as non-retryable and preserve the specific error message for that code only.

Validation:

- `python3 -m pytest tests/test_tool_gateway_runtime_audit_phase3.py -q --tb=short`: passed, 6 tests.
- `python3 -m pytest tests/test_tool_gateway_invocation_phase3.py -q --tb=short`: passed, 12 tests.
- `python3 -m pytest tests/test_sdk_behavior.py -q --tb=short`: passed, 34 tests.
- Full Tool Gateway and SDK validation later passed.

Residual concern:

- Exact-once semantics cannot be guaranteed if the upstream side effect succeeds and the gateway cannot persist the replay record. The current behavior is now explicit, safer, and tested, but still requires reconciliation before issuing a new idempotency key.
- Cleanup is still exposed as a CLI operation; the repository does not yet prove scheduled execution in deployment.

Status:

- SDK-AUDIT-004: substantially mitigated; not mathematically eliminated because distributed side effects still require reconciliation.
- SDK-AUDIT-005: partially resolved; cleanup is stronger, but scheduling remains unproven.
- SDK-AUDIT-006: resolved for cleanup and retry paths.
- SDK-AUDIT-007: partially resolved; retention deletion is still operationally dependent.
- SDK-AUDIT-037: resolved for the identified missing failure-injection coverage.

### Pass 3: SDK Proxy Defaults, Result Ergonomics, Redaction Defaults, And Examples

Issues addressed:

- SDK-AUDIT-008
- SDK-AUDIT-009
- SDK-AUDIT-010
- SDK-AUDIT-011
- SDK-AUDIT-013
- SDK-AUDIT-021
- SDK-AUDIT-027
- SDK-AUDIT-038

Root cause confirmed:

- SDK-owned HTTPX clients inherited proxy environment variables by default.
- The upstream executor also used HTTPX defaults for owned clients.
- SDK consumers had to know that standard gateway execution results placed the upstream payload under `result["body"]`.
- Default response policy redacted sensitive keys but did not include text-pattern redaction for common token-like strings.
- First-copy README and example flows did not consistently show unique operation-level idempotency keys or `ToolCallResult.body`.

Implemented fix:

- SDK-owned sync and async clients now use `trust_env=False`.
- Product upstream executor-owned sync and async clients now use `trust_env=False`.
- `ToolCallResult.body` now unwraps the standard gateway execution envelope and leaves `result` available for compatibility and diagnostics.
- Default response policy now includes built-in redaction patterns for bearer tokens, common secret assignments, and SSN-like assignments.
- README, API reference, security docs, async worker example, and LangGraph-style example now document or use operation-level idempotency keys, `ToolCallResult.body`, explicit proxy behavior, and non-retry of `idempotency_persistence_failed`.

Validation:

- `python3 -m pytest tests/test_sdk_behavior.py -q --tb=short`: passed, 34 tests.
- `python3 -m pytest tests/test_tool_gateway_forwarding_phase1.py -q --tb=short`: passed, 5 tests.
- `python3 -m pytest tests/test_tool_gateway_response_phase1.py tests/test_tool_gateway_response_phase3.py -q --tb=short`: passed, 18 tests.
- SDK source copy parity was checked with `cmp`; standalone and product compatibility copies matched.

Residual concern:

- Redaction remains best-effort. Operators should still avoid sending sensitive free text to agent-facing tools and should review custom redaction patterns.
- `ToolCallResult.body` improves ergonomics, but consumers that already use `.result` still need to understand the full gateway envelope.

Status:

- SDK-AUDIT-008: resolved enough for MVP ergonomics.
- SDK-AUDIT-009: resolved for first-copy README invocation.
- SDK-AUDIT-010: resolved for async example idempotency usage.
- SDK-AUDIT-011: resolved for workflow-step scoped example keying.
- SDK-AUDIT-013: resolved for SDK-owned clients.
- SDK-AUDIT-021: improved; not a complete data-loss-prevention guarantee.
- SDK-AUDIT-027: resolved for owned upstream executor clients.
- SDK-AUDIT-038: resolved for proxy default tests.

### Pass 4: Credential Quickstart End-To-End Test

Issues addressed:

- SDK-AUDIT-033
- SDK-AUDIT-042

Root cause confirmed:

- Existing tests proved individual pieces of credential storage, gateway auth, installed-wheel SDK calls, and network invocation.
- They did not prove the first-adopter flow from operator credential issuance to SDK discovery and invocation.
- Fixture-seeded raw tokens would not have validated the documented handoff between an operator/admin and an SDK consumer.

Implemented fix:

- `packages/product-platform/tests/test_tool_gateway_installed_sdk_contract.py` now includes `test_readme_quickstart_issues_credential_and_invokes_tool_over_http`.
- The test starts a real local uvicorn gateway, logs in through `/api/v1/auth/dev-login`, creates and activates a tool through the public operator API, registers/identifies/submits/approves/activates an agent through the public API, grants the active agent tool permission through the public API, issues a bearer gateway credential through `/api/v1/agents/{agent_id}/credentials`, and then uses the built standalone SDK wheel with `EnvironmentTokenProvider`.
- The SDK side verifies compatibility, discovers only the visible tool, invokes with `idempotency_key`, reads `ToolCallResult.body`, repeats the same call, and proves the replay did not execute the upstream tool twice.

Validation:

- `python3 -m pytest tests/test_tool_gateway_installed_sdk_contract.py -q --tb=short`: passed, 3 tests, 2 existing websocket deprecation warnings.
- `python3 -m pytest tests/test_tool_gateway_*.py -q --tb=short`: passed, 318 tests, 2 existing websocket deprecation warnings.

Residual concern:

- This closes the in-repository quickstart proof for the local/dev-login path. It still does not prove hosted identity-provider login, external operator onboarding, or published PyPI artifact provenance.

Status:

- SDK-AUDIT-033: substantially improved; credential issuance-to-SDK invocation is now validated end to end for the local operator flow.
- SDK-AUDIT-042: improved; the README-style SDK path is now covered by a network e2e test using the built wheel and `EnvironmentTokenProvider`.

### Post-Remediation Validation

| Command | Result |
| --- | --- |
| `python3 -m pytest tests/test_tool_gateway_*.py -q --tb=short` in `packages/product-platform` | Passed: 318 tests, 2 existing websocket deprecation warnings. |
| `python3 -m mypy src/product_platform/api/app.py src/product_platform/tool_gateway src/ophanix_tool_gateway` in `packages/product-platform` | Passed. |
| `python3 scripts/validate_release.py --out-dir /tmp/ophanix-product-remediation-final2 --skip-twine-check` in `packages/product-platform` | Passed; built and validated wheel/sdist, with twine intentionally skipped for local audit. |
| `python3 -m pytest tests -q --tb=short` in `packages/ophanix-tool-gateway-sdk` | Passed after remediation: 36 tests. |
| `python3 -m mypy src/ophanix_tool_gateway` in `packages/ophanix-tool-gateway-sdk` | Passed. |
| `python3 scripts/validate_release.py --out-dir /tmp/ophanix-sdk-remediation-final --skip-twine-check` in `packages/ophanix-tool-gateway-sdk` | Passed; built and validated wheel/sdist, with twine intentionally skipped for local audit. |
| `cmp -s packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py packages/product-platform/src/ophanix_tool_gateway/sdk.py` | Passed; compatibility copies match. |

### Post-Remediation Score Reassessment

| Category | Initial strict score | Post-remediation score | Direction | Evidence for change | Remaining cap |
| --- | ---: | ---: | --- | --- | --- |
| Implementation quality | 7.0/10 | 7.5/10 | Raised | Active-create bypass is blocked, idempotency persistence failure is explicit and tested, stale cleanup marks unknown rows, and full Tool Gateway tests pass. | Capped below 8 by optional output contracts, source-copy maintenance risk, and lack of scheduled cleanup evidence. |
| Ease of use | 7.0/10 | 7.6/10 | Raised | `ToolCallResult.body`, safer examples, stronger README/API guidance, explicit proxy/idempotency behavior, and a credential issuance-to-SDK invocation e2e test reduce first-integration confusion. | Capped below 8 by hosted/external onboarding gaps and remaining need for source-level understanding in some gateway/operator flows. |
| Security and reliability | 6.8/10 | 7.2/10 | Raised | SDK and executor owned clients ignore ambient proxies, default redaction patterns are stronger, stale idempotency rows are recoverable by cleanup, and unknown outcomes are explicit/non-retryable. | Capped near 7 by manual cleanup scheduling, DNS/egress assumptions, staging config gaps, and best-effort redaction limits. |

### Remaining Material Issues After Remediation

- Scheduled idempotency cleanup is still not proven by deployment configuration.
- External pilot environments still need production-like enforcement for upstream allowlists and secret manager configuration.
- DNS rebinding and broader egress-control guarantees remain infrastructure responsibilities not proven by this repository.
- Output schema enforcement is still optional, so response contract quality depends on tool authors and response policy settings.
- Credential issuance through local operator APIs to SDK invocation is now tested; hosted/external onboarding and identity-provider login are still not proven.
- The standalone SDK and product compatibility copy still create a source-copy governance risk, although release validation and parity checks reduce it.
- PyPI publication is accepted as real, but the repository still does not link published artifact hashes to a trusted release workflow artifact.

### Updated Strict Assessment

After remediation, this is a stronger controlled MVP and crosses a cleaner 7/10 threshold for security/reliability. It is still not production-ready or an 8/10 serious production pilot. The remaining blockers are operationalization and governance more than happy-path SDK capability: scheduled cleanup, environment safety enforcement, provenance, self-service onboarding, and contract strictness.

Current strict post-remediation score profile: `7.5 / 7.6 / 7.2`.
