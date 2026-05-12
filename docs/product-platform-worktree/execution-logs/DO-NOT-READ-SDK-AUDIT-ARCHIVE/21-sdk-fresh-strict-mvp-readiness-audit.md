# Tool Gateway SDK Fresh Strict MVP Readiness Audit

Date: 2026-05-12

Scope: Fresh strict MVP-readiness audit of the Ophanix Tool Gateway SDK package, the product-platform gateway runtime contract it depends on, package/release tooling, tests, CI, examples, and documentation. The prior remediation log at `13-sdk-review-remediation.md` was read only as context and was treated as untrusted until checked against current files.

Important scope notes:

- No issue is logged for lack of load balancing. Expected MVP traffic does not justify treating that as a flaw.
- The package is understood to be published to PyPI per reviewer context. This audit does not score "package is unpublished" as a flaw. It does flag a separate evidence/discoverability problem because a public-index lookup from this environment did not resolve `ophanix-tool-gateway-sdk`, while the README tells users to install from PyPI.
- This is an MVP-readiness audit, not an enterprise production certification.

## 1. Executive Summary

The repository is materially credible as a controlled internal MVP. The SDK has a real standalone package, sync and async clients, strict payload/token validation, safe non-local HTTPS defaults, response-size caps for built-in clients, gateway-authenticated discovery, resource-scoped credential enforcement, idempotency-key support, typed exports, package tests, product gateway contract tests, release validation tooling, and meaningful documentation.

It is not ready to be scored as an 8+ serious production pilot from repository evidence alone. The prior remediation score increase to `8.1/8.3/8.3` is too lenient for the current full system. The biggest unresolved MVP risks are:

- SDK invocation retry semantics are misleading once the gateway's idempotency replay behavior is included. Upstream `5xx` failures that are persisted as completed idempotency responses are replayed, not re-executed, so the SDK's documented "retry transient 5xx with idempotency key" promise is only partly true.
- PyPI install evidence is inconsistent from this environment: README says `pip install ophanix-tool-gateway-sdk`, but `python3 -m pip index versions ophanix-tool-gateway-sdk` returned no matching distribution. This may be an environment/index issue or a recent/private-publication lag, but it is a serious onboarding risk unless documented with an exact package URL/version.
- Publishing and provenance are not closed in-repo. The workflow builds, validates, signs, attests, and uploads artifacts, but intentionally does not upload to PyPI. The handoff runbook exists, but there is no enforced link proving the published files match the validated files.
- Idempotency is execution-scoped, not full-invocation scoped. Policy denials and schema validation failures happen before the idempotency record is opened.
- Idempotency cleanup is manual; no scheduler, deployment manifest, or operational check proves stale/replay records are cleaned.
- Security and reliability depend on operational assumptions: DNS/egress controls for upstream SSRF, host allowlists outside production, secret-manager configuration, log hygiene, and manual release handoff discipline.

Strict current scores:

| Category                 | Current score | Prior score from `13-sdk-review-remediation.md` | Direction | MVP interpretation                                                                                                                                                                                            |
| ------------------------ | ------------: | ----------------------------------------------: | --------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Implementation quality   |        6.8/10 |                                          8.1/10 | Lowered   | Functional but fragile MVP. Core behavior exists and tests pass, but idempotency/retry semantics, duplicated SDK source, and coverage gaps cap confidence.                                                    |
| Ease of use              |        6.7/10 |                                          8.3/10 | Lowered   | A competent engineer can adopt it in a few hours in a controlled environment, but install evidence, credential issuance ambiguity, and API/documentation rough edges can force source-level debugging.        |
| Security and reliability |        6.4/10 |                                          8.3/10 | Lowered   | Safe defaults are much better than earlier versions, but replay/retry semantics, manual cleanup, egress assumptions, retention, and operational-state hashing keep this below a broad external MVP threshold. |

Final assessment: credible for supervised internal pilot or a closely supported design partner; not yet a clean self-serve external MVP. To reach a credible `7`, fix or clearly document idempotent retry semantics, close package install/provenance evidence, add cleanup scheduling guidance, and strengthen tests around real gateway replay behavior. To reach `8`, add end-to-end release provenance, broader async/integration coverage, stronger operational runbooks, and remove the source-copy drift risk.

## 2. Prior Review Summary And Challenge

### Previously Reported Issues, Ignoring Deferred Items

The prior remediation log reported these non-deferred issues:

- SDK discovery called the operator `/api/v1/tools` endpoint with gateway bearer tokens.
- Gateway discovery returned an operator-facing response shape with tenant/creator metadata.
- SDK input validation was weak for type errors, non-JSON payloads, malformed successful responses, and non-local plain HTTP.
- `get_tool()` searched only the first page.
- `StaticTokenProvider` repr exposed token material.
- SDK exceptions retained raw response bodies.
- External users lacked an environment-token provider, `list_all_tools()`, cache invalidation, and ergonomic discovery retries.
- Payload validation allowed loose JSON shapes and unsafe URL shapes.
- Numeric config accepted non-finite values and boolean options accepted truthy non-booleans.
- Discovery ignored `Retry-After`.
- The SDK was embedded in `ophanix-product-platform` instead of being a lightweight distribution.
- Credential authorization flattened resource-scoped credential grants to scope strings.
- Discovery cache keys could cross credential rotations.
- Async SDK support was missing.
- Standalone package build/docs were weak.
- `get_tool()` and paginated helpers had residual credential-cache consistency gaps.
- Optional response object fields were under-validated.
- Sync client could receive async token providers with unclear failure behavior.
- Redaction coverage missed common secret text shapes.
- Production developer documentation was incomplete.
- Release validation was not repeatable.
- Sync and async constructor validation was duplicated.

### Fixes Claimed

The remediation log claimed fixes including:

- New gateway-authenticated `/api/v1/gateway/tools` route.
- Agent-safe `GatewayToolDefinitionResponse`.
- SDK strict validation of payloads, tokens, headers, URLs, successful responses, and optional mapping fields.
- HTTPS-by-default base URL handling.
- Pagination fixes for `get_tool()` and `list_all_tools()`.
- Token repr redaction and sanitized exception diagnostics.
- `EnvironmentTokenProvider`, discovery retries, retry jitter, `Retry-After`, `clear_tool_cache()`, `py.typed`, SDK version export, and compatibility probe.
- Resource-bound credential scopes enforced in discovery and invocation.
- Cache partitioning by process-local HMAC token fingerprint.
- Async client and async token provider support.
- Standalone package metadata, docs, smoke tests, wheel/sdist checks, and release validator.
- Runtime idempotency support.
- Expanded secret redaction.
- Shared `_client_config()` validation.

### Validation Evidence Claimed

The log claimed many validation runs across phases, including:

- SDK unittest suites with counts from 30 to 76 tests.
- Product Tool Gateway tests with counts up to 199 tests.
- Full product-platform tests with counts up to 695 tests.
- Compile checks.
- Wheel and sdist builds.
- `pip wheel` checks.
- `twine check`.
- Optional `pip-audit`.
- `git diff --check`.

### Scores Assigned

The latest explicit scores in the remediation log were:

- Implementation quality: `8.1/10`.
- Ease of use: `8.3/10`.
- Security/reliability: `8.3/10`.

Earlier in the same log, after Pass 16, scores were:

- Implementation quality: `7.8/10`.
- Ease of use: `8.0/10`.
- Security/reliability: `8.1/10`.

### Suspicious, Under-Evidenced, Too Lenient, Or Too Strict Conclusions

- Too lenient: The prior scoring treats SDK-local improvements as if they fully prove the gateway runtime contract. The most serious current retry/idempotency problem only appears when SDK retry behavior is evaluated against server-side idempotency replay.
- Too lenient: The prior log says release validation improved supply-chain readiness, but current publishing still relies on a manual handoff outside GitHub Actions. The runbook exists, but provenance is not closed.
- Too lenient: Documentation is good, but the README's PyPI install claim was not verified from this environment.
- Too lenient: Runtime idempotency is treated as a resolved risk, but denials/schema failures happen before idempotency begins and successful upstream outcomes can still become unreplayable when completion persistence fails.
- Too lenient: Async support exists, but standalone tests have very limited async behavior coverage compared with sync behavior.
- Correctly strict in earlier parts: The prior concerns about single-file SDK and sync/async duplication remain legitimate maintainability issues.
- Too strict or stale in later separate audit notes, not in the remediation log itself: direct active tool creation is now blocked by model validation, and built-in SDK clients now set `trust_env=False`; these should not remain unresolved findings.

### Areas Not Deeply Reviewed Before

- Gateway idempotency replay behavior combined with SDK retry promises.
- Public PyPI package discoverability from a clean consumer command.
- Final published-artifact provenance from CI artifact to package index file hash.
- Manual cleanup/scheduling of idempotency replay records.
- Rate-limit operational-state keying and high-cardinality invalid token behavior.
- Policy hook return-contract validation.
- Query-parameter allowlist ergonomics and false positives.
- Product wheel versus source-tree import divergence caused by the vendored SDK copy.
- Release tag/version consistency when `--expected-tag` is supplied.
- Example copy-paste risks around idempotency and correlation identifiers.

## 3. Repository Surface Reviewed

### SDK Package

- `packages/ophanix-tool-gateway-sdk/pyproject.toml`
- `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/__init__.py`
- `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py`
- `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/py.typed`
- `packages/ophanix-tool-gateway-sdk/README.md`
- `packages/ophanix-tool-gateway-sdk/API_REFERENCE.md`
- `packages/ophanix-tool-gateway-sdk/CHANGELOG.md`
- `packages/ophanix-tool-gateway-sdk/MIGRATION.md`
- `packages/ophanix-tool-gateway-sdk/SECURITY.md`
- `packages/ophanix-tool-gateway-sdk/examples/async_worker_example.py`
- `packages/ophanix-tool-gateway-sdk/examples/langgraph_node_example.py`
- `packages/ophanix-tool-gateway-sdk/tests/test_sdk_behavior.py`
- `packages/ophanix-tool-gateway-sdk/tests/test_package_smoke.py`
- `packages/ophanix-tool-gateway-sdk/scripts/validate_release.py`

### Product Gateway Runtime

- `packages/product-platform/src/ophanix_tool_gateway/__init__.py`
- `packages/product-platform/src/ophanix_tool_gateway/sdk.py`
- `packages/product-platform/src/ophanix_tool_gateway/py.typed`
- `packages/product-platform/src/product_platform/api/app.py`
- `packages/product-platform/src/product_platform/api/settings.py`
- `packages/product-platform/src/product_platform/agents/credentials.py`
- `packages/product-platform/src/product_platform/integrations/secrets.py`
- `packages/product-platform/src/product_platform/tool_gateway/auth.py`
- `packages/product-platform/src/product_platform/tool_gateway/decision.py`
- `packages/product-platform/src/product_platform/tool_gateway/health.py`
- `packages/product-platform/src/product_platform/tool_gateway/invocation.py`
- `packages/product-platform/src/product_platform/tool_gateway/models.py`
- `packages/product-platform/src/product_platform/tool_gateway/operational_state.py`
- `packages/product-platform/src/product_platform/tool_gateway/pagination.py`
- `packages/product-platform/src/product_platform/tool_gateway/repository.py`
- `packages/product-platform/src/product_platform/tool_gateway/response.py`
- `packages/product-platform/src/product_platform/tool_gateway/runtime_audit.py`
- `packages/product-platform/src/product_platform/tool_gateway/schemas.py`
- `packages/product-platform/src/product_platform/tool_gateway/sdk.py`
- `packages/product-platform/src/product_platform/cli.py`

### Product Tests And Examples

- `packages/product-platform/tests/test_tool_gateway_*`
- `packages/product-platform/tests/test_tool_gateway_installed_sdk_contract.py`
- `packages/product-platform/examples/tool-gateway-direct-http/*`
- `packages/product-platform/README.md`

### Packaging, CI, And Release

- `.github/workflows/ci.yml`
- `.github/workflows/publish.yml`
- `docs/internal/pypi-publishing.md`
- `docs/product-platform-worktree/tool-gateway-production-runbook.md`
- `docs/product-platform-worktree/tool-gateway-threat-model.md`

### Validation Performed During This Audit

- `python3 -m pytest tests -q` in `packages/ophanix-tool-gateway-sdk`: 36 passed.
- `python3 -m pytest tests/test_tool_gateway_installed_sdk_contract.py tests/test_tool_gateway_invocation_phase3.py tests/test_tool_gateway_runtime_audit_phase3.py -q` in `packages/product-platform`: 21 passed, 2 deprecation warnings from `websockets`.
- `python3 scripts/validate_release.py --out-dir /tmp/ophanix-sdk-audit-release --skip-twine-check` in the SDK package: passed; twine metadata validation was intentionally skipped for this local run and recorded by the script.
- `python3 -m mypy src/ophanix_tool_gateway` in the SDK package: passed.
- `python3 -m py_compile examples/async_worker_example.py examples/langgraph_node_example.py` in the SDK package: passed.
- `git diff --check`: passed.
- `python3 -m pip index versions ophanix-tool-gateway-sdk`: returned `ERROR: No matching distribution found for ophanix-tool-gateway-sdk`.

## 4. Exhaustive Issue Register

### SDK-AUDIT-001

- Title: Public PyPI install evidence is inconsistent with the README.
- Category: Packaging / release / developer experience
- Severity: High
- Confidence: Medium
- File path or area: `packages/ophanix-tool-gateway-sdk/README.md`; consumer installation path.
- Evidence: README lines 7-10 state that the package is published on PyPI and show `pip install ophanix-tool-gateway-sdk`. In this audit environment, `python3 -m pip index versions ophanix-tool-gateway-sdk` returned `ERROR: No matching distribution found for ophanix-tool-gateway-sdk`. The reviewer context says the package is published, so this is logged as a verification/discoverability mismatch, not as proof that publication never happened.
- Why it matters: The first consumer command is the highest leverage onboarding path. If it fails for an early adopter, the SDK looks non-credible even if local wheel validation is strong.
- Root cause or likely root cause: Possible PyPI propagation/index configuration issue, package name mismatch, private index expectation, recent publication not visible to this environment, or README ahead of distribution reality.
- Impact on MVP readiness: Can block self-serve adoption if unresolved for the target audience.
- Impact on developer experience, if applicable: Forces users to source-install or ask maintainers for package coordinates.
- Impact on security or reliability, if applicable: Users may install from source or unverified artifacts, weakening supply-chain hygiene.
- Mentioned in prior review log: Partially. Packaging and release were discussed, but public package lookup was not independently verified there.
- Previous fix claimed to address it: Partially, via standalone package creation and release validation.
- Whether previous fix is sufficient: No. Buildability is not the same as consumer installability.
- Recommended remediation: Add the exact PyPI project URL, current version, expected install command, and a release note/hash that proves the published artifact. If a private index is expected, document the index URL/configuration explicitly.
- Suggested validation or test: In CI or release validation, run `python -m pip install --no-cache-dir ophanix-tool-gateway-sdk==<version>` from the intended public/private index in a clean environment.
- Whether it should affect scoring: Yes. It caps ease of use below 7 for unsupervised external adoption until verified.

### SDK-AUDIT-002

- Title: Repository does not close the final published-artifact provenance loop.
- Category: Packaging / release / supply chain
- Severity: Medium
- Confidence: High
- File path or area: `.github/workflows/publish.yml`; `docs/internal/pypi-publishing.md`; SDK release flow.
- Evidence: `publish.yml` comments state that actual PyPI publishing is intentionally outside the build job. The runbook requires release owners to preserve logs, checksums, provenance attestations, SBOM, and upload evidence, but the workflow itself stops at artifact upload/signing/attestation.
- Why it matters: The package can be published while still leaving reviewers unable to prove that the file on PyPI is exactly the validated, signed, attested artifact.
- Root cause or likely root cause: Manual or external release handoff is intentionally used instead of trusted publishing.
- Impact on MVP readiness: Acceptable for a supervised MVP, but weak for external design partners who expect package provenance.
- Impact on developer experience, if applicable: Consumers cannot verify provenance from repository docs alone.
- Impact on security or reliability, if applicable: Supply-chain integrity depends on manual process discipline.
- Mentioned in prior review log: Yes, release validation and provenance were discussed.
- Previous fix claimed to address it: Partially, via release validator, signing, attestation, and publishing runbook.
- Whether previous fix is sufficient: No. It improves local artifact quality but does not close package-index provenance.
- Recommended remediation: Use PyPI trusted publishing or publish a machine-readable release manifest linking PyPI file hashes to workflow artifact hashes and attestations.
- Suggested validation or test: Release job should fail if the published package hash does not match the validated artifact hash.
- Whether it should affect scoring: Yes, mainly security/reliability and packaging confidence.

### SDK-AUDIT-003

- Title: SDK retry semantics are misleading for persisted upstream `5xx` failures.
- Category: Runtime behavior / reliability / documentation
- Severity: High
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py`; `packages/product-platform/src/product_platform/api/app.py`; README reliability section.
- Evidence: SDK `call_tool()` retries `408`, `429`, and `5xx` only when an idempotency key is present. The gateway stores upstream failed executions as completed idempotency responses with status `502`, then replays completed responses on later uses of the same key with `Idempotency-Replayed: true`. Therefore a transient upstream `5xx` that was successfully persisted by the gateway is replayed as the same `502`; the SDK retry loop does not re-execute the upstream call.
- Why it matters: Developers will believe they are getting automatic resilience for transient upstream failures. In a real persisted gateway path, they may just receive the same replayed failure until retry budget is exhausted.
- Root cause or likely root cause: SDK retry design was evaluated against HTTP responses in isolation, not against the server's idempotency persistence semantics.
- Impact on MVP readiness: Serious for moderate real-world usage because idempotency and retries are central reliability claims.
- Impact on developer experience, if applicable: Causes confusion when retries appear to happen but no new upstream attempt occurs.
- Impact on security or reliability, if applicable: Reliability is over-promised. Failed calls may not recover automatically even when safe to retry.
- Mentioned in prior review log: Partially. Idempotency and retries were discussed, but this server/SDK interaction was not called out.
- Previous fix claimed to address it: Yes, by adding idempotency and invocation retries.
- Whether previous fix is sufficient: No. It fixes duplicate-suppression, not transient upstream retry semantics.
- Recommended remediation: Either change docs/API names to say retries only cover transport/gateway failures before a completed idempotency response exists, or change gateway semantics to not persist retryable upstream failures as terminal completed replays when safe. Consider separate response metadata such as `replayable_terminal=true` and SDK logic that stops retrying replayed failures immediately.
- Suggested validation or test: Add an installed SDK plus running gateway test where upstream returns `503` once, gateway stores the response, and SDK retry behavior is asserted explicitly.
- Whether it should affect scoring: Yes. This is the strongest reliability score cap.

### SDK-AUDIT-004

- Title: Idempotency starts after policy and schema validation, not at invocation receipt.
- Category: Runtime behavior / API semantics
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/api/app.py`
- Evidence: `invoke_tool_gateway_tool()` evaluates policy and validates input schema before calling `ToolInvocationIdempotencyRepository.begin_invocation()`. Denied calls and schema validation failures return before any idempotency record exists.
- Why it matters: A caller sending an idempotency key can reasonably assume the entire invocation attempt is idempotent. Current behavior only makes the post-policy, post-schema execution segment replayable.
- Root cause or likely root cause: Idempotency was inserted close to upstream execution to avoid storing denials and validation failures.
- Impact on MVP readiness: Acceptable if documented as execution idempotency, but currently ambiguous.
- Impact on developer experience, if applicable: Repeated denied or invalid requests do not get replay headers or conflict semantics, making the contract harder to reason about.
- Impact on security or reliability, if applicable: Mostly reliability/contract clarity; low direct security impact.
- Mentioned in prior review log: Partially. Idempotency contract concerns were discussed.
- Previous fix claimed to address it: Yes, runtime idempotency was added.
- Whether previous fix is sufficient: Partially. It prevents duplicate upstream execution for the allowed path, not for the whole invocation contract.
- Recommended remediation: Document the exact scope or move idempotency begin earlier and store deterministic denials and validation failures.
- Suggested validation or test: Add repeated denied-call and schema-invalid-call tests with the same idempotency key.
- Whether it should affect scoring: Yes, reliability and API clarity.

### SDK-AUDIT-005

- Title: Successful upstream outcomes can still become unreplayable if completion persistence fails.
- Category: Runtime behavior / reliability / idempotency
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/api/app.py`; `packages/product-platform/src/product_platform/tool_gateway/runtime_audit.py`
- Evidence: The idempotency row is opened before execution, but `complete_invocation()` runs in a later transaction after execution. If that completion write fails, the gateway returns `idempotency_persistence_failed`; a later retry can see `idempotency_in_progress` or stale/unknown state while the upstream side effect may already have happened.
- Why it matters: This is the exact failure mode idempotency is meant to make safe. Current behavior is explicit and safer than silence, but still leaves the user with a business reconciliation burden.
- Root cause or likely root cause: The gateway cannot atomically include the external upstream side effect and local DB persistence in one transaction.
- Impact on MVP readiness: Manageable for controlled MVP usage if documented and monitored; not clean for broad self-serve adoption.
- Impact on developer experience, if applicable: Callers must reconcile business state manually after a gateway-owned persistence failure.
- Impact on security or reliability, if applicable: Reliability risk around duplicate or unknown side effects.
- Mentioned in prior review log: Partially.
- Previous fix claimed to address it: Yes, by adding `idempotency_persistence_failed` handling.
- Whether previous fix is sufficient: Partially. It fails loudly, but does not provide a reconciliation mechanism.
- Recommended remediation: Provide a reconciliation/read API keyed by request ID, correlation ID, idempotency key, and runtime action ID. Document upstream idempotency propagation patterns.
- Suggested validation or test: Simulate DB failure after upstream success and assert operator-facing reconciliation data is sufficient.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-006

- Title: Idempotency replay cleanup is manual rather than operationally guaranteed.
- Category: Reliability / operations
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/cli.py`; `packages/product-platform/src/product_platform/tool_gateway/runtime_audit.py`
- Evidence: `db cleanup-idempotency` calls `purge_tool_invocation_idempotency_records()`, and the purge function marks stale in-progress rows and deletes terminal rows older than retention. No scheduler, background job, deployment manifest, or startup task proves this runs periodically.
- Why it matters: Replay records store response bodies and operational state. If cleanup is forgotten, retention and stale-state guarantees are aspirational.
- Root cause or likely root cause: MVP added a CLI maintenance command but not deployment automation.
- Impact on MVP readiness: Acceptable for internal MVP only if operators are explicitly assigned the task.
- Impact on developer experience, if applicable: Consumers cannot know how long idempotency replays are retained in practice.
- Impact on security or reliability, if applicable: Reliability and data-retention risk.
- Mentioned in prior review log: Partially.
- Previous fix claimed to address it: Partially, by adding purge behavior.
- Whether previous fix is sufficient: No. A function/CLI is not an operating schedule.
- Recommended remediation: Add cron/Kubernetes/Celery/worker guidance and an operational metric for rows purged, rows marked failed_unknown, and oldest retained row age.
- Suggested validation or test: Add deployment smoke or runbook validation that verifies cleanup has run within the expected interval.
- Whether it should affect scoring: Yes, security/reliability.

### SDK-AUDIT-007

- Title: Idempotency replay records store full public response bodies for the retention period.
- Category: Security / privacy / reliability
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/tool_gateway/runtime_audit.py`
- Evidence: `complete_invocation()` stores `response_body_json`. Default replay retention is seven days. Deletion depends on the manual cleanup path described in SDK-AUDIT-006.
- Why it matters: Successful tool responses can include business data. Even if agent-facing response policies redact some data, replay storage still increases the sensitive-data footprint.
- Root cause or likely root cause: Replay requires a stored terminal response body.
- Impact on MVP readiness: Acceptable for controlled MVP if retention is scheduled and documented; risky if cleanup is missed.
- Impact on developer experience, if applicable: Integrators need to know replay retention and data handling obligations.
- Impact on security or reliability, if applicable: Data minimization and retention risk.
- Mentioned in prior review log: Redaction and idempotency were discussed, but this retention consequence was underweighted.
- Previous fix claimed to address it: Partially.
- Whether previous fix is sufficient: No, because cleanup automation is not proven.
- Recommended remediation: Document data classes stored in replay, allow per-tool replay storage policy where feasible, encrypt at rest, and enforce cleanup schedule.
- Suggested validation or test: Add a retention test that runs cleanup and asserts replay bodies are removed after the configured window.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-008

- Title: Runtime audit can be left in partial states if the process dies between gateway phases.
- Category: Reliability / observability
- Severity: Medium
- Confidence: Medium
- File path or area: `packages/product-platform/src/product_platform/api/app.py`
- Evidence: The gateway creates an `allowed` runtime action, executes upstream work outside that transaction, then later updates the runtime action to forwarded/completed/failed in separate transactions. A process crash between those phases can leave the audit trail in an incomplete state.
- Why it matters: MVP adopters will rely on audit records to understand whether a tool call was executed. Partial state requires reconciliation logic.
- Root cause or likely root cause: Correctly avoiding a long DB transaction around network I/O creates a multi-phase workflow without a recovery worker.
- Impact on MVP readiness: Manageable for internal MVP, but should be documented.
- Impact on developer experience, if applicable: Debugging source-level runtime states may be required after crashes.
- Impact on security or reliability, if applicable: Audit completeness and operational reliability.
- Mentioned in prior review log: No.
- Previous fix claimed to address it: No.
- Whether previous fix is sufficient: Not applicable.
- Recommended remediation: Add a recovery job or explicit `unknown_after_timeout` state for runtime actions stuck in `allowed` or `forwarded`.
- Suggested validation or test: Simulate process interruption after the allowed event and verify recovery/alerting behavior.
- Whether it should affect scoring: Yes, modestly.

### SDK-AUDIT-009

- Title: Gateway rate-limit keys hash bearer tokens with unsalted SHA-256.
- Category: Security / operational state
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/api/app.py`
- Evidence: `_gateway_rate_limit_key()` parses the bearer token and returns `authorization:<sha256(token)>`. Credential storage uses peppered HMAC-style token hashes elsewhere, but the rate-limit key does not use that pepper.
- Why it matters: If operational-state rows or logs containing rate-limit keys leak, low-entropy fixture or misissued tokens are easier to enumerate than peppered hashes.
- Root cause or likely root cause: Rate-limiter keying was implemented separately from credential hashing.
- Impact on MVP readiness: Low risk for high-entropy production tokens, but inconsistent with the repo's stronger token-hash posture.
- Impact on developer experience, if applicable: None direct.
- Impact on security or reliability, if applicable: Token privacy hardening gap.
- Mentioned in prior review log: No.
- Previous fix claimed to address it: No.
- Whether previous fix is sufficient: Not applicable.
- Recommended remediation: Use HMAC with `OPHANIX_GATEWAY_TOKEN_HASH_PEPPER` or a separate rate-limit-key secret.
- Suggested validation or test: Unit test that the rate-limit key changes when the pepper changes and never equals raw SHA-256.
- Whether it should affect scoring: Yes, security/reliability.

### SDK-AUDIT-010

- Title: Random syntactically valid bearer tokens can create high-cardinality rate-limit buckets.
- Category: Reliability / abuse resistance
- Severity: Low
- Confidence: Medium
- File path or area: `packages/product-platform/src/product_platform/api/app.py`; operational-state rate limiting.
- Evidence: `_gateway_rate_limit_key()` buckets any parseable bearer token by its digest before authentication verifies whether it exists. An attacker can send many random valid-looking tokens to create many distinct keys until `tool_gateway_rate_limit_max_keys` overflow behavior is hit.
- Why it matters: Controlled MVPs may not see this, but it is an avoidable operational churn path.
- Root cause or likely root cause: Rate limiting runs before authentication and keys directly on presented token material.
- Impact on MVP readiness: Not a blocker for supervised MVP, but relevant before broader exposure.
- Impact on developer experience, if applicable: None direct.
- Impact on security or reliability, if applicable: Abuse and noisy storage risk.
- Mentioned in prior review log: No.
- Previous fix claimed to address it: No.
- Whether previous fix is sufficient: Not applicable.
- Recommended remediation: Consider IP plus invalid-token bucket for unknown tokens, or authenticate then key on credential ID where possible.
- Suggested validation or test: Abuse simulation with many unknown bearer tokens should not create unbounded unique state.
- Whether it should affect scoring: Slightly.

### SDK-AUDIT-011

- Title: Upstream SSRF safety still depends on DNS and egress assumptions outside the code.
- Category: Security / upstream networking
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/tool_gateway/models.py`; `packages/product-platform/src/product_platform/tool_gateway/invocation.py`
- Evidence: `validate_http_url()` rejects private/loopback/link-local/metadata hosts and resolves hostnames with `socket.getaddrinfo()`. Runtime URL construction revalidates against allowed hosts. This is good, but DNS rebinding and network routing changes still require egress controls not enforced by this repo.
- Why it matters: The gateway forwards server-side HTTP requests. SSRF controls need both application validation and network boundaries.
- Root cause or likely root cause: Application-level hostname validation cannot fully own egress policy.
- Impact on MVP readiness: Acceptable for internal MVP with known upstreams; high-risk for broad external deployment without egress policy.
- Impact on developer experience, if applicable: Operators must understand deployment responsibilities.
- Impact on security or reliability, if applicable: SSRF and metadata-service exposure risk if deployment is misconfigured.
- Mentioned in prior review log: Upstream safety was discussed generally.
- Previous fix claimed to address it: Partially, through URL validation and allowlist support.
- Whether previous fix is sufficient: Partially. It is strong app-layer defense, not a full network boundary.
- Recommended remediation: Add deployment examples with egress firewall/VPC policy and document DNS rebinding limits.
- Suggested validation or test: Integration test in a deployment-like environment proving metadata/private ranges are blocked by both app and network.
- Whether it should affect scoring: Yes, security/reliability.

### SDK-AUDIT-012

- Title: Upstream host allowlist is required only for `production`, not all shared MVP environments.
- Category: Security configuration
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/api/app.py`; settings validation.
- Evidence: `_validate_production_settings()` requires `tool_gateway_upstream_host_allowlist` only when `settings.environment == "production"`. Staging, pilot, demo, or design-partner environments can run without an allowlist if they are non-local but not literally named production.
- Why it matters: Early external pilots often run in staging-like environments. Those are exactly where controlled allowlists should be in place.
- Root cause or likely root cause: Environment-name gating is too narrow.
- Impact on MVP readiness: Acceptable for local demos; concerning for external design partners.
- Impact on developer experience, if applicable: Operators may miss a crucial configuration because the app starts without it.
- Impact on security or reliability, if applicable: SSRF risk increases if a shared environment lacks allowlist and network egress controls.
- Mentioned in prior review log: Partially.
- Previous fix claimed to address it: Partially.
- Whether previous fix is sufficient: No for external MVP environments.
- Recommended remediation: Require allowlist for all non-local environments, or add a separate explicit `OPHANIX_TOOL_GATEWAY_REQUIRE_UPSTREAM_ALLOWLIST=true` default for non-local.
- Suggested validation or test: Settings tests for `staging`, `pilot`, and `preview` environments.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-013

- Title: Inline upstream secrets can evade the `secret_ref` heuristic.
- Category: Security / secret handling
- Severity: Medium
- Confidence: Medium
- File path or area: `packages/product-platform/src/product_platform/tool_gateway/models.py`
- Evidence: `_looks_like_inline_secret_key()` only rejects `secret_ref` values starting with `bearer `, `sk-`, `pk_`, `eyj`, or longer than 256 characters. Many raw secrets are shorter and do not match these prefixes.
- Why it matters: The data model intends `secret_ref` to be an opaque reference, not a stored secret. Heuristic detection will miss common tokens.
- Root cause or likely root cause: The application cannot reliably distinguish opaque references from all possible secret values.
- Impact on MVP readiness: Manageable with operator discipline; risky if external operators configure upstream targets directly.
- Impact on developer experience, if applicable: Error behavior can seem arbitrary: some inline secrets rejected, others accepted.
- Impact on security or reliability, if applicable: Secret material may be stored in config rows.
- Mentioned in prior review log: Secret-manager production hardening was discussed generally.
- Previous fix claimed to address it: Partially.
- Whether previous fix is sufficient: No, because heuristic secret detection is incomplete by nature.
- Recommended remediation: Enforce a structured secret-ref scheme such as `env:NAME` or `sm://...`, and reject bare opaque strings unless they match an approved reference grammar.
- Suggested validation or test: Tests for common token prefixes such as `ghp_`, `xoxb-`, and random API keys shorter than 256 chars.
- Whether it should affect scoring: Yes, security.

### SDK-AUDIT-014

- Title: Retrieved upstream secret values are not validated for header control characters.
- Category: Security / runtime behavior
- Severity: Low
- Confidence: Medium
- File path or area: `packages/product-platform/src/product_platform/tool_gateway/invocation.py`
- Evidence: `_retrieve_upstream_secret()` checks that the value is a non-empty string, then `_upstream_auth_headers()` places it in `Authorization` or an API-key header. There is no explicit local rejection of CR/LF or other header control characters.
- Why it matters: HTTPX likely rejects invalid header values, but the gateway should fail deterministically and safely at its own boundary.
- Root cause or likely root cause: Secret provider outputs were trusted after retrieval.
- Impact on MVP readiness: Not a blocker if secret manager is trusted, but an avoidable hardening gap.
- Impact on developer experience, if applicable: Misconfigured secrets fail as generic upstream connection errors rather than clear configuration errors.
- Impact on security or reliability, if applicable: Header injection is likely mitigated downstream, but relying on transport-library validation is weaker than explicit validation.
- Mentioned in prior review log: No.
- Previous fix claimed to address it: No.
- Whether previous fix is sufficient: Not applicable.
- Recommended remediation: Reject header control characters in secret values and constructed header values before invoking HTTPX.
- Suggested validation or test: Secret provider returns `abc\r\nX-Test: injected`; gateway returns `upstream_auth_secret_invalid` before network I/O.
- Whether it should affect scoring: Slightly.

### SDK-AUDIT-015

- Title: GET/DELETE query safety check can false-positive on innocent keys containing `key`.
- Category: Developer experience / runtime behavior
- Severity: Low
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/tool_gateway/invocation.py`
- Evidence: `_request_payload_kwargs()` rejects query fields if any token in `SECRET_LIKE_QUERY_KEY_TOKENS` is a substring of the normalized key. That token set includes `key`, so keys such as `monkey` or `turnkey` can be rejected even when allowlisted.
- Why it matters: Strict query safety is good, but false positives will confuse tool authors and may force renaming harmless upstream parameters.
- Root cause or likely root cause: Broad substring matching was used for secret-like query detection.
- Impact on MVP readiness: Low, but it creates avoidable integration friction.
- Impact on developer experience, if applicable: Operators may need source-level debugging to understand why an allowlisted query field is still rejected.
- Impact on security or reliability, if applicable: False positive favors safety over availability.
- Mentioned in prior review log: No.
- Previous fix claimed to address it: No.
- Whether previous fix is sufficient: Not applicable.
- Recommended remediation: Use exact normalized names plus suffix/prefix word-boundary matching, not arbitrary substring matching for `key`.
- Suggested validation or test: Allowlisted `monkey` should pass; `api_key`, `access_token`, and `secret_key` should fail.
- Whether it should affect scoring: Slightly, DX.

### SDK-AUDIT-016

- Title: Policy hook return objects are not validated before attribute access.
- Category: Runtime behavior / extensibility
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/tool_gateway/decision.py`
- Evidence: `policy_hook.evaluate(context)` is inside a try/except, but later code accesses `hook_result.decision`, `hook_result.matched_policy_id`, and `hook_result.reason_message` after the try block. A hook returning the wrong object shape can raise outside the fail-closed `policy_error` path.
- Why it matters: Policy hooks are an extension point. Malformed hooks should deny safely, not crash the request path.
- Root cause or likely root cause: The exception boundary only wraps hook execution, not hook result normalization.
- Impact on MVP readiness: Not a blocker if no policy hook is configured, but risky for teams evaluating custom policy integration.
- Impact on developer experience, if applicable: Hook authors get runtime 500s rather than deterministic validation errors.
- Impact on security or reliability, if applicable: Potential fail-open is not evident, but availability/fail-closed reliability is weaker.
- Mentioned in prior review log: No.
- Previous fix claimed to address it: No.
- Whether previous fix is sufficient: Not applicable.
- Recommended remediation: Validate/normalize hook results with a Pydantic model inside the try block and fail closed on any exception.
- Suggested validation or test: Hook returns `{}` or `None`; gateway persists `policy_error` denial instead of raising 500.
- Whether it should affect scoring: Yes, modestly.

### SDK-AUDIT-017

- Title: Policy hook receives only redacted/truncated payload summary, not the full payload.
- Category: Public API / extensibility / authorization
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/tool_gateway/decision.py`
- Evidence: `ToolPolicyHookContext` is constructed with `payload_summary`, produced by `summarize_tool_payload()`, not the original payload. The summary redacts key names containing tokens such as `email`, `phone`, `address`, `key`, and truncates strings/items/depth.
- Why it matters: Some meaningful policy decisions require exact payload values. If hooks only see summaries, policy enforcement can be too coarse.
- Root cause or likely root cause: Privacy-preserving summary was reused as policy input.
- Impact on MVP readiness: Acceptable for simple allow/deny MVP policies; limiting for real policy pilots.
- Impact on developer experience, if applicable: Hook authors may be surprised that required fields are redacted or truncated.
- Impact on security or reliability, if applicable: Authorization decisions may be less precise than users expect.
- Mentioned in prior review log: No.
- Previous fix claimed to address it: No.
- Whether previous fix is sufficient: Not applicable.
- Recommended remediation: Document hook input as summary-only or add a separate opt-in full-payload hook with strict security controls.
- Suggested validation or test: Hook requiring an exact payload value should have a documented and tested path.
- Whether it should affect scoring: Yes, implementation/API.

### SDK-AUDIT-018

- Title: SDK does not enforce gateway compatibility before calls.
- Category: Public API / reliability
- Severity: Low
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py`; README examples.
- Evidence: `check_compatibility()` exists and examples call it, but `call_tool()`, `list_tools()`, and `list_all_tools()` do not automatically validate gateway contract compatibility.
- Why it matters: Consumers can skip compatibility checks and receive confusing errors from version-skewed gateways.
- Root cause or likely root cause: Compatibility probing is opt-in to avoid extra request overhead.
- Impact on MVP readiness: Acceptable MVP shortcut, but docs should be explicit that compatibility is caller-owned.
- Impact on developer experience, if applicable: Source-level debugging may be needed when old gateways return different shapes.
- Impact on security or reliability, if applicable: Reliability and supportability gap.
- Mentioned in prior review log: Compatibility was mentioned.
- Previous fix claimed to address it: Yes, compatibility endpoint and SDK method were added.
- Whether previous fix is sufficient: Partially.
- Recommended remediation: Add `require_compatible=True` optional constructor mode or a first-call compatibility cache.
- Suggested validation or test: With a mismatched gateway, `require_compatible=True` fails before invocation.
- Whether it should affect scoring: Slightly.

### SDK-AUDIT-019

- Title: SDK version comparison is not PEP 440 compliant.
- Category: Public API / compatibility
- Severity: Low
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py`
- Evidence: Compatibility uses a local numeric parser rather than `packaging.version`. Pre-release or local-version strings such as `0.1.0rc1` can compare incorrectly.
- Why it matters: Compatibility checks are meant to be trusted during upgrades. Incorrect handling of pre-releases can hide incompatibility.
- Root cause or likely root cause: Avoiding an extra runtime dependency.
- Impact on MVP readiness: Acceptable if only simple `x.y.z` versions are used; risky for beta/pre-release testing.
- Impact on developer experience, if applicable: Confusing compatibility results for pre-release builds.
- Impact on security or reliability, if applicable: Reliability/supportability only.
- Mentioned in prior review log: Min-SDK checks were discussed.
- Previous fix claimed to address it: Yes, compatibility checking was added.
- Whether previous fix is sufficient: Partially.
- Recommended remediation: Use `packaging.version.Version` or explicitly restrict SDK/gateway versions to simple semver and validate that shape.
- Suggested validation or test: Add compatibility tests for `0.1.0rc1`, `0.1.0.post1`, and `0.1.0+local`.
- Whether it should affect scoring: Slightly.

### SDK-AUDIT-020

- Title: Async cache-clearing API is inconsistent and under-documented.
- Category: Public API / async behavior / documentation
- Severity: Low
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py`; `packages/ophanix-tool-gateway-sdk/API_REFERENCE.md`
- Evidence: Async client has synchronous `clear_tool_cache()` that clears dictionaries without acquiring the async lock, and also has `aclear_tool_cache()` that uses the lock. API reference says async client has the same method names and lists awaitable methods but does not mention `aclear_tool_cache()`.
- Why it matters: Async developers may call the wrong method and bypass the intended lock.
- Root cause or likely root cause: Sync/async API mirroring plus a later async-safe method addition.
- Impact on MVP readiness: Low, because cache is opt-in and process-local.
- Impact on developer experience, if applicable: Confusing method naming and docs.
- Impact on security or reliability, if applicable: Minor cache consistency risk in async tasks.
- Mentioned in prior review log: Cache/thread-safety was discussed generally.
- Previous fix claimed to address it: Partially.
- Whether previous fix is sufficient: No for docs/API clarity.
- Recommended remediation: Document `await client.aclear_tool_cache()`, make async `clear_tool_cache()` acquire the lock or deprecate it, and test concurrent cache clearing.
- Suggested validation or test: Async cache clear during concurrent discovery does not mutate without the async lock.
- Whether it should affect scoring: Slightly.

### SDK-AUDIT-021

- Title: `allow_buffered_custom_http_client` is a public no-op compatibility flag.
- Category: Public API / maintainability / developer experience
- Severity: Low
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py`; API reference.
- Evidence: `ToolGatewayClientConfig` and constructors expose `allow_buffered_custom_http_client`, but validators assign it to `_` and still require `stream()`. Docs say buffered clients are rejected even if the flag is supplied.
- Why it matters: A public option that cannot change behavior is confusing and creates breaking-change baggage.
- Root cause or likely root cause: Backward compatibility after rejecting buffered custom clients for response-size safety.
- Impact on MVP readiness: Low.
- Impact on developer experience, if applicable: Users may waste time trying to use the flag.
- Impact on security or reliability, if applicable: The no-op preserves safety, but weakens API cleanliness.
- Mentioned in prior review log: No.
- Previous fix claimed to address it: No.
- Whether previous fix is sufficient: Not applicable.
- Recommended remediation: Deprecate the flag loudly, remove it in the next breaking pre-1.0 window, or rename it to a documented compatibility placeholder.
- Suggested validation or test: Constructor with the flag should emit a deprecation warning if a custom client lacks `stream()`.
- Whether it should affect scoring: Slightly, ease of use/API.

### SDK-AUDIT-022

- Title: SDK remains a very large single-file implementation with mirrored sync/async logic.
- Category: Maintainability / implementation quality
- Severity: Medium
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py`
- Evidence: The SDK is roughly 108 KB in one file and contains separate sync and async client classes with similar methods for invocation, discovery, retries, cache management, response parsing, and event emission.
- Why it matters: The current behavior is testable, but future changes are likely to drift between sync and async paths.
- Root cause or likely root cause: Rapid MVP evolution from an internal wrapper.
- Impact on MVP readiness: Not a blocker today, but it reduces confidence in fast iteration.
- Impact on developer experience, if applicable: Contributors must review a large file to understand a small API change.
- Impact on security or reliability, if applicable: Security-sensitive validation may drift if future edits touch only one path.
- Mentioned in prior review log: Yes.
- Previous fix claimed to address it: Partially, via shared `_client_config()`.
- Whether previous fix is sufficient: Partially. Configuration validation is centralized, but runtime logic remains mirrored.
- Recommended remediation: Split errors, models, validation, redaction, retry, sync transport, and async transport into modules with shared helpers.
- Suggested validation or test: Maintain parity tests that run the same behavior matrix against sync and async clients.
- Whether it should affect scoring: Yes, implementation quality.

### SDK-AUDIT-023

- Title: Vendored SDK parity validation checks only `sdk.py`, not the whole package surface.
- Category: Packaging / maintainability
- Severity: Low
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/scripts/validate_release.py`
- Evidence: `_validate_vendored_sdk_parity()` compares standalone `src/ophanix_tool_gateway/sdk.py` to product-platform `src/ophanix_tool_gateway/sdk.py` only. It does not compare `__init__.py`, `py.typed`, or packaging metadata.
- Why it matters: The current files match, but the guard can miss drift in public exports or typing markers.
- Root cause or likely root cause: Parity check focused on the main implementation file.
- Impact on MVP readiness: Low today; medium long-term maintenance risk.
- Impact on developer experience, if applicable: Product source users and standalone package users may see different exports.
- Impact on security or reliability, if applicable: Mostly maintainability; can affect compatibility.
- Mentioned in prior review log: Packaging/source-copy concerns were mentioned.
- Previous fix claimed to address it: Partially.
- Whether previous fix is sufficient: No.
- Recommended remediation: Compare the full `ophanix_tool_gateway` package directory or generate product compatibility exports from the standalone package.
- Suggested validation or test: Release validation fails if `__init__.py` differs between standalone and product vendored copies.
- Whether it should affect scoring: Slightly.

### SDK-AUDIT-024

- Title: Product-platform source imports can differ from installed product wheel behavior.
- Category: Packaging / integration risk
- Severity: Medium
- Confidence: High
- File path or area: `packages/product-platform/pyproject.toml`; `packages/product-platform/src/ophanix_tool_gateway`
- Evidence: Product-platform declares dependency `ophanix-tool-gateway-sdk>=0.1.0,<1.0`, while its wheel build excludes `/src/ophanix_tool_gateway`. The source tree still contains a vendored `src/ophanix_tool_gateway` used by local tests/type checks.
- Why it matters: Editable/source usage can import the vendored SDK, while installed wheel usage imports the dependency from the package index. If those ever drift, local tests can pass while real installs behave differently.
- Root cause or likely root cause: Transitional compatibility between monorepo source layout and standalone package dependency.
- Impact on MVP readiness: Manageable because parity currently matches and installed-wheel contract tests exist; still a packaging footgun.
- Impact on developer experience, if applicable: Developers may debug the source copy while users run the package dependency.
- Impact on security or reliability, if applicable: Version skew risk.
- Mentioned in prior review log: Standalone extraction and compatibility exports were discussed.
- Previous fix claimed to address it: Partially.
- Whether previous fix is sufficient: Mostly, but not fully because source/wheel paths differ by design.
- Recommended remediation: Remove the vendored package from product source or make it a generated/symlinked copy with full-package parity validation.
- Suggested validation or test: Product wheel test must install product from wheel plus index SDK and assert SDK `__version__` and file hash match expected release.
- Whether it should affect scoring: Yes, implementation/packaging.

### SDK-AUDIT-025

- Title: Standalone SDK async behavior coverage is thin.
- Category: Testing / async reliability
- Severity: Medium
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/tests/test_sdk_behavior.py`
- Evidence: The standalone SDK suite has limited async coverage compared with the sync behavior matrix. It checks async trust-env behavior and some public exports, but most retry/error/cache/redaction/pathological behavior tests are sync-oriented.
- Why it matters: Async client is a first-class public API. Mirrored code without mirrored tests raises drift risk.
- Root cause or likely root cause: Async support was added after the sync suite.
- Impact on MVP readiness: Acceptable for controlled MVP, but blocks higher confidence.
- Impact on developer experience, if applicable: Async users may hit bugs not covered by the main suite.
- Impact on security or reliability, if applicable: Reliability parity risk.
- Mentioned in prior review log: Async support was discussed, with claimed async tests.
- Previous fix claimed to address it: Partially.
- Whether previous fix is sufficient: No for full parity.
- Recommended remediation: Parametrize the behavior suite across sync and async clients or add async equivalents for retry, cache, malformed response, response-size, token-provider, and event-hook tests.
- Suggested validation or test: A sync/async parity matrix should run all SDK behavior scenarios in both modes.
- Whether it should affect scoring: Yes, implementation/reliability.

### SDK-AUDIT-026

- Title: Package smoke test compiles only one example.
- Category: Testing / documentation validation
- Severity: Low
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/tests/test_package_smoke.py`; SDK examples.
- Evidence: `test_examples_compile()` compiles `async_worker_example.py` only. This audit separately compiled `langgraph_node_example.py`, and it passed, but the repo test does not enforce that.
- Why it matters: Examples are part of the MVP developer experience and should stay syntactically valid.
- Root cause or likely root cause: New example was not added to the smoke test.
- Impact on MVP readiness: Low.
- Impact on developer experience, if applicable: Broken examples would confuse adopters.
- Impact on security or reliability, if applicable: None direct.
- Mentioned in prior review log: Docs/examples were discussed generally.
- Previous fix claimed to address it: Partially, via package smoke tests.
- Whether previous fix is sufficient: No.
- Recommended remediation: Compile all Python files under `examples/`.
- Suggested validation or test: Iterate through `examples/*.py` in smoke tests.
- Whether it should affect scoring: Slightly.

### SDK-AUDIT-027

- Title: SDK retry tests over-mock gateway behavior and miss server replay semantics.
- Category: Testing / reliability
- Severity: Medium
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/tests/test_sdk_behavior.py`; product installed SDK tests.
- Evidence: SDK retry tests use `httpx.MockTransport` returning a retryable error followed by success. That proves SDK loop mechanics, but not real gateway idempotency replay behavior where a persisted `502` can be replayed instead of re-executed.
- Why it matters: The highest-risk reliability behavior crosses package boundaries. Unit tests alone gave false confidence.
- Root cause or likely root cause: Package-local tests avoid product server coupling.
- Impact on MVP readiness: Significant because it allowed SDK-AUDIT-003 to remain untested.
- Impact on developer experience, if applicable: Developers trust docs/tests that do not match deployed behavior.
- Impact on security or reliability, if applicable: Reliability gap.
- Mentioned in prior review log: Validation was discussed, but this gap was not.
- Previous fix claimed to address it: Partially, via installed-wheel gateway tests.
- Whether previous fix is sufficient: No unless those tests cover replayed retryable failures.
- Recommended remediation: Add cross-package integration tests for retryable upstream failure with idempotency replay.
- Suggested validation or test: Running product gateway, upstream returns `503`, first SDK call gets persisted `502`, retry behavior asserted.
- Whether it should affect scoring: Yes.

### SDK-AUDIT-028

- Title: Release validation does not install the SDK from the target package index.
- Category: Packaging / release testing
- Severity: Medium
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/scripts/validate_release.py`; CI/release workflow.
- Evidence: The validator builds artifacts, installs the local wheel, checks contents, writes SBOM/manifest, and can run `pip-audit`. It does not verify that the package can be installed from the target index after publication.
- Why it matters: Local artifact correctness and index installability are different questions.
- Root cause or likely root cause: Validation script is pre-publish oriented.
- Impact on MVP readiness: Important for external onboarding.
- Impact on developer experience, if applicable: Same as SDK-AUDIT-001.
- Impact on security or reliability, if applicable: Index install validation also helps prove supply-chain path.
- Mentioned in prior review log: Release validation was discussed.
- Previous fix claimed to address it: Partially.
- Whether previous fix is sufficient: No.
- Recommended remediation: Add post-publish validation to install exact version from the intended index in a clean venv and run smoke tests.
- Suggested validation or test: `pip install --index-url <target> ophanix-tool-gateway-sdk==0.1.0` followed by import and basic MockTransport call.
- Whether it should affect scoring: Yes, packaging/ease.

### SDK-AUDIT-029

- Title: Quickstart idempotency key is static enough to invite copy-paste replay mistakes.
- Category: Documentation / developer experience / reliability
- Severity: Low
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/README.md`
- Evidence: The sync usage example uses `idempotency_key="claim-123-refresh-2026-05-11T09:00Z"`. It is illustrative, but static examples are often copied directly.
- Why it matters: Reusing idempotency keys can cause old responses to replay or conflicts to appear.
- Root cause or likely root cause: Example tries to be concrete.
- Impact on MVP readiness: Low, but easy to improve.
- Impact on developer experience, if applicable: Copy-paste users can accidentally create stale replay behavior.
- Impact on security or reliability, if applicable: Reliability risk due key reuse.
- Mentioned in prior review log: Docs/examples were discussed generally.
- Previous fix claimed to address it: Partially.
- Whether previous fix is sufficient: No.
- Recommended remediation: Show a generated operation ID and explicitly say never reuse an idempotency key across distinct business operations.
- Suggested validation or test: Documentation lint or example test checking for `uuid`/operation IDs in examples.
- Whether it should affect scoring: Slightly, ease.

### SDK-AUDIT-030

- Title: Examples put business identifiers in correlation IDs and idempotency keys.
- Category: Documentation / privacy / developer experience
- Severity: Low
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/examples/*.py`; README examples.
- Evidence: Examples use values such as `claim-job:{job_id}`, `claim:{workflow_step_id}`, `claims.lookup:{job_id}`, and fallback `manual:{claim_id}`. The README recommends capturing correlation IDs in diagnostics.
- Why it matters: Correlation IDs and idempotency keys often land in logs and operational state. Business IDs can be sensitive or linkable even if not strictly PII.
- Root cause or likely root cause: Examples use domain-natural identifiers for readability.
- Impact on MVP readiness: Low, but relevant for design partners in regulated domains.
- Impact on developer experience, if applicable: Users may copy identifiers directly into observability data.
- Impact on security or reliability, if applicable: Privacy/logging risk.
- Mentioned in prior review log: Redaction/logging was discussed generally.
- Previous fix claimed to address it: Partially.
- Whether previous fix is sufficient: No.
- Recommended remediation: Use opaque operation IDs in examples and add a note not to place PII/business identifiers in correlation IDs or idempotency keys.
- Suggested validation or test: Documentation review checklist for PII-bearing example identifiers.
- Whether it should affect scoring: Slightly, security/DX.

### SDK-AUDIT-031

- Title: Credential issuance docs still contain endpoint ambiguity.
- Category: Documentation / developer experience
- Severity: Medium
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/README.md`
- Evidence: README says exact endpoint names may differ in private operator builds and tells users to verify API shape before automation.
- Why it matters: Token acquisition is prerequisite number one. Ambiguity here slows onboarding even if the SDK API is polished.
- Root cause or likely root cause: Product/operator credential flows are still evolving or differ by deployment.
- Impact on MVP readiness: Significant DX issue for external early adopters.
- Impact on developer experience, if applicable: A competent engineer may need product-team help or source-level API inspection to obtain a token.
- Impact on security or reliability, if applicable: Workarounds may encourage local fixture tokens or manual secret handling.
- Mentioned in prior review log: Token issuance/setup documentation was discussed.
- Previous fix claimed to address it: Partially.
- Whether previous fix is sufficient: No for self-serve onboarding.
- Recommended remediation: Provide one supported credential issuance flow per deployment type, with exact endpoints, auth requirements, expected responses, and revocation/rotation steps.
- Suggested validation or test: Fresh-user docs test: create a token from scratch using only README/runbook instructions.
- Whether it should affect scoring: Yes, ease of use.

### SDK-AUDIT-032

- Title: Release tag/version consistency can be bypassed by supplying `--expected-tag`.
- Category: Packaging / release process
- Severity: Low
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/scripts/validate_release.py`; `.github/workflows/publish.yml`
- Evidence: `--strict-git` defaults to `v<project.version>`, but publish workflow supplies `--expected-tag "${{ github.event.release.tag_name }}"`. That proves checkout matches the release tag, but not that the tag name corresponds to `pyproject.toml` version.
- Why it matters: A release tagged `v0.1.1` could build package version `0.1.0` without this script detecting the semantic mismatch, if the expected tag is passed through.
- Root cause or likely root cause: The script supports arbitrary expected tags for monorepo flexibility.
- Impact on MVP readiness: Low for MVP, but release hygiene issue.
- Impact on developer experience, if applicable: Consumers can be confused by tag/package version mismatch.
- Impact on security or reliability, if applicable: Supply-chain/release traceability.
- Mentioned in prior review log: Release validation was discussed.
- Previous fix claimed to address it: Partially.
- Whether previous fix is sufficient: No.
- Recommended remediation: Require either exact `v<version>` or a documented package-specific pattern that embeds the version, even when `--expected-tag` is supplied.
- Suggested validation or test: Validator should fail if tag `v0.1.1` builds version `0.1.0`.
- Whether it should affect scoring: Slightly.

### SDK-AUDIT-033

- Title: Release validator deletes the requested output directory recursively.
- Category: Tooling / safety
- Severity: Low
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/scripts/validate_release.py`
- Evidence: `_artifact_directory.__enter__()` resolves the requested path and runs `shutil.rmtree(self.path)` if it exists.
- Why it matters: A mistyped `--out-dir` can delete unrelated local files.
- Root cause or likely root cause: Convenience cleanup for repeatable builds.
- Impact on MVP readiness: Not an SDK runtime issue, but a developer tooling hazard.
- Impact on developer experience, if applicable: Potential data loss for maintainers.
- Impact on security or reliability, if applicable: Local build reliability/safety.
- Mentioned in prior review log: No.
- Previous fix claimed to address it: No.
- Whether previous fix is sufficient: Not applicable.
- Recommended remediation: Require the output dir to be empty, require a known prefix, or delete only generated artifact names.
- Suggested validation or test: Passing an existing non-empty directory without a release marker should fail rather than delete it.
- Whether it should affect scoring: Slightly.

### SDK-AUDIT-034

- Title: Local SBOM from `validate_release.py` only covers direct runtime dependencies.
- Category: Packaging / supply chain
- Severity: Low
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/scripts/validate_release.py`; README release section.
- Evidence: `_write_minimal_sbom()` derives components from wheel `Requires-Dist`, which for the SDK is essentially direct dependencies such as `httpx`. CI additionally uses Anchore SBOM in `publish.yml`, but local validator output is minimal.
- Why it matters: A local release manifest may look stronger than it is if users assume transitive dependency inventory.
- Root cause or likely root cause: Lightweight local validator implementation.
- Impact on MVP readiness: Low; CI SBOM improves this.
- Impact on developer experience, if applicable: Release owners must understand which SBOM to use.
- Impact on security or reliability, if applicable: Supply-chain visibility gap.
- Mentioned in prior review log: Release validation was discussed.
- Previous fix claimed to address it: Partially.
- Whether previous fix is sufficient: Partially.
- Recommended remediation: Label the local SBOM clearly as direct-only or generate a transitive SBOM from the installed environment.
- Suggested validation or test: SBOM should include transitive `httpcore`, `certifi`, `anyio`, etc., if advertised as dependency inventory.
- Whether it should affect scoring: Slightly.

### SDK-AUDIT-035

- Title: `ToolCallResult.raw` can carry full successful response data into logs.
- Category: Public API / privacy / developer experience
- Severity: Low
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py`; API reference.
- Evidence: `ToolCallResult.raw` stores an immutable snapshot of the full successful gateway body. API reference calls raw fields diagnostic snapshots, but the README's logging guidance focuses on sanitized exception response bodies.
- Why it matters: Successful tool responses are not necessarily safe to log. Developers often log dataclasses during debugging.
- Root cause or likely root cause: Raw diagnostic snapshots were added for supportability.
- Impact on MVP readiness: Low, but relevant for regulated pilot data.
- Impact on developer experience, if applicable: Users need explicit logging guidance.
- Impact on security or reliability, if applicable: Privacy/logging risk.
- Mentioned in prior review log: Error-body redaction was discussed, not successful raw result logging.
- Previous fix claimed to address it: Partially.
- Whether previous fix is sufficient: No.
- Recommended remediation: Document `raw` as potentially sensitive, or provide a `safe_debug()` representation that excludes result body.
- Suggested validation or test: README/API reference includes "do not log raw successful responses" guidance.
- Whether it should affect scoring: Slightly.

### SDK-AUDIT-036

- Title: Generic API 500 responses expose exception class names.
- Category: Security / error exposure
- Severity: Low
- Confidence: High
- File path or area: `packages/product-platform/src/product_platform/api/app.py`
- Evidence: The unhandled exception handler returns `details={"error_type": exc.__class__.__name__}`.
- Why it matters: Exception class names can leak implementation details. This is low severity, but many security baselines prefer opaque 500 responses plus server-side logging.
- Root cause or likely root cause: Supportability/debugging convenience.
- Impact on MVP readiness: Acceptable for internal MVP; should be hidden for external deployments.
- Impact on developer experience, if applicable: Helps debugging, but at security cost.
- Impact on security or reliability, if applicable: Minor information disclosure.
- Mentioned in prior review log: Error exposure was discussed generally.
- Previous fix claimed to address it: Partially, for SDK exception text; not this API handler.
- Whether previous fix is sufficient: No.
- Recommended remediation: Only include `error_type` in local/development or behind an operator/debug flag.
- Suggested validation or test: Production settings should suppress internal exception class names.
- Whether it should affect scoring: Slightly, security.

### SDK-AUDIT-037

- Title: `list_all_tools()` default `max_total=10000` may hide large-catalog behavior.
- Category: Public API / scalability / developer experience
- Severity: Low
- Confidence: Medium
- File path or area: `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py`; README.
- Evidence: `list_all_tools()` defaults to `max_total=10_000`, page size up to 200, and raises `tool_discovery_too_large` only after it would exceed the cap.
- Why it matters: Fine for MVP, but large organizations may not realize discovery has a process-local cap until runtime.
- Root cause or likely root cause: Safety cap to prevent unbounded memory usage.
- Impact on MVP readiness: Acceptable MVP shortcut.
- Impact on developer experience, if applicable: Needs docs on handling catalogs above 10,000 tools.
- Impact on security or reliability, if applicable: Reliability/memory safety tradeoff.
- Mentioned in prior review log: Scalability and `list_all_tools()` were discussed.
- Previous fix claimed to address it: Partially.
- Whether previous fix is sufficient: Yes for MVP, but documentation can be clearer.
- Recommended remediation: Document paging APIs for large catalogs and expose a streaming iterator helper later.
- Suggested validation or test: Test exact behavior at `max_total` boundary.
- Whether it should affect scoring: Low impact only.

### SDK-AUDIT-038

- Title: `owner_team` discovery filter is exact and case-sensitive.
- Category: Developer experience / API ergonomics
- Severity: Low
- Confidence: High
- File path or area: SDK README; `ToolRegistryRepository.list_tools_for_gateway_principal()`
- Evidence: README explicitly says `owner_team` is exact and case-sensitive. Repository query uses `owner_team = ?`.
- Why it matters: This can surprise developers expecting case-insensitive filtering.
- Root cause or likely root cause: DB filter matches stored owner-team string exactly.
- Impact on MVP readiness: Acceptable MVP behavior because it is documented.
- Impact on developer experience, if applicable: Minor friction.
- Impact on security or reliability, if applicable: None.
- Mentioned in prior review log: No.
- Previous fix claimed to address it: No.
- Whether previous fix is sufficient: Not applicable.
- Recommended remediation: Leave as-is for MVP or provide a normalized team identifier field in future.
- Suggested validation or test: Current behavior should remain documented and tested.
- Whether it should affect scoring: Minimal.

### SDK-AUDIT-039

- Title: `status` parameter remains in `list_tools()` even though only active discovery is supported.
- Category: Public API / backwards compatibility
- Severity: Low
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py`; API reference.
- Evidence: `list_tools(status: Literal["active"] | None = None, ...)` emits a deprecation warning when provided and rejects non-active values.
- Why it matters: This is a compatibility wart that makes the public API look broader than the gateway contract.
- Root cause or likely root cause: Backward compatibility from operator-facing status filters.
- Impact on MVP readiness: Acceptable MVP shortcut.
- Impact on developer experience, if applicable: Minor confusion.
- Impact on security or reliability, if applicable: No security issue; active-only is safer.
- Mentioned in prior review log: Yes.
- Previous fix claimed to address it: Yes, deprecation warning and active-only validation.
- Whether previous fix is sufficient: Sufficient for MVP, but still a cleanup issue.
- Recommended remediation: Remove the parameter in the next breaking pre-1.0 release or keep the warning very visible in migration notes.
- Suggested validation or test: Deprecation warning remains until removal.
- Whether it should affect scoring: Slightly, API polish.

### SDK-AUDIT-040

- Title: Custom injected HTTP clients remain outside SDK proxy/TLS/default guarantees.
- Category: Security / reliability / configuration
- Severity: Low
- Confidence: High
- File path or area: `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py`; README.
- Evidence: Built-in sync/async clients set `trust_env=False`. Custom clients are only shape-validated for streaming and methods. README tells users to inject an explicitly configured client when an approved proxy is needed.
- Why it matters: The SDK's safe network defaults do not apply to a caller-supplied client.
- Root cause or likely root cause: SDK cannot inspect every custom client configuration.
- Impact on MVP readiness: Acceptable if documented; important for support.
- Impact on developer experience, if applicable: Users may assume SDK still controls proxy behavior.
- Impact on security or reliability, if applicable: Proxy/TLS behavior becomes caller-owned.
- Mentioned in prior review log: Proxy/security defaults were discussed.
- Previous fix claimed to address it: Yes, built-in clients use `trust_env=False`.
- Whether previous fix is sufficient: Mostly. Residual risk belongs to custom clients.
- Recommended remediation: Add a prominent warning in API reference and optional helper factory for approved proxy clients.
- Suggested validation or test: Docs and tests prove built-in clients ignore env proxies; custom client responsibility is documented.
- Whether it should affect scoring: Slightly.

## 5. Issues Grouped By Category

| Category                            | Issues                                                                                                                                                              |
| ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Runtime behavior and reliability    | SDK-AUDIT-003, SDK-AUDIT-004, SDK-AUDIT-005, SDK-AUDIT-006, SDK-AUDIT-008, SDK-AUDIT-016, SDK-AUDIT-017, SDK-AUDIT-027, SDK-AUDIT-037                               |
| Security and privacy                | SDK-AUDIT-007, SDK-AUDIT-009, SDK-AUDIT-010, SDK-AUDIT-011, SDK-AUDIT-012, SDK-AUDIT-013, SDK-AUDIT-014, SDK-AUDIT-030, SDK-AUDIT-035, SDK-AUDIT-036, SDK-AUDIT-040 |
| Public API and developer experience | SDK-AUDIT-018, SDK-AUDIT-019, SDK-AUDIT-020, SDK-AUDIT-021, SDK-AUDIT-029, SDK-AUDIT-031, SDK-AUDIT-038, SDK-AUDIT-039                                              |
| Testing                             | SDK-AUDIT-025, SDK-AUDIT-026, SDK-AUDIT-027, SDK-AUDIT-028                                                                                                          |
| Packaging and release               | SDK-AUDIT-001, SDK-AUDIT-002, SDK-AUDIT-023, SDK-AUDIT-024, SDK-AUDIT-028, SDK-AUDIT-032, SDK-AUDIT-033, SDK-AUDIT-034                                              |
| Maintainability                     | SDK-AUDIT-022, SDK-AUDIT-023, SDK-AUDIT-024                                                                                                                         |
| Documentation                       | SDK-AUDIT-001, SDK-AUDIT-003, SDK-AUDIT-029, SDK-AUDIT-030, SDK-AUDIT-031, SDK-AUDIT-035                                                                            |

## 6. Critical And High-Severity Blockers

No critical issue was directly proven.

High-severity issues:

- SDK-AUDIT-001: Public PyPI install evidence is inconsistent with the README. Severity is high because install failure blocks self-serve adoption; confidence is medium because the reviewer context says the package is published.
- SDK-AUDIT-003: SDK retry semantics are misleading for persisted upstream `5xx` failures. Severity is high and confidence is high because code paths directly prove the mismatch.

These high issues are enough to prevent an `8+` score. SDK-AUDIT-003 also prevents an unqualified `7+` reliability score until fixed or clearly documented.

## 7. Medium-Severity MVP Risks

- SDK-AUDIT-002: Final published-artifact provenance loop is not closed in repo.
- SDK-AUDIT-004: Idempotency starts after policy/schema validation.
- SDK-AUDIT-005: Upstream outcomes can become unreplayable if idempotency completion persistence fails.
- SDK-AUDIT-006: Idempotency cleanup is manual.
- SDK-AUDIT-007: Replay records store full public response bodies.
- SDK-AUDIT-008: Runtime audit can be left in partial states.
- SDK-AUDIT-009: Rate-limit keys use unsalted SHA-256 of bearer tokens.
- SDK-AUDIT-011: SSRF safety depends on deployment egress controls.
- SDK-AUDIT-012: Upstream allowlist is required only for literal production.
- SDK-AUDIT-013: Inline upstream secrets can evade `secret_ref` heuristic.
- SDK-AUDIT-016: Policy hook return objects are not validated.
- SDK-AUDIT-017: Policy hook only sees payload summaries.
- SDK-AUDIT-022: SDK is still a large single-file mirrored implementation.
- SDK-AUDIT-024: Product source imports can differ from installed product wheel behavior.
- SDK-AUDIT-025: Async SDK coverage is thin.
- SDK-AUDIT-027: SDK retry tests miss real gateway replay semantics.
- SDK-AUDIT-028: Release validation does not install from the target package index.
- SDK-AUDIT-031: Credential issuance docs remain ambiguous.

## 8. Low-Severity And Nit-Level Issues

- SDK-AUDIT-010: Random valid-looking tokens can create high-cardinality rate-limit buckets.
- SDK-AUDIT-014: Retrieved upstream secrets are not explicitly header-control validated.
- SDK-AUDIT-015: Query secret-like detection can false-positive on keys containing `key`.
- SDK-AUDIT-018: Compatibility probe is opt-in.
- SDK-AUDIT-019: Version comparison is not PEP 440 compliant.
- SDK-AUDIT-020: Async cache-clearing API is inconsistent.
- SDK-AUDIT-021: `allow_buffered_custom_http_client` is a no-op flag.
- SDK-AUDIT-023: Parity validation checks only `sdk.py`.
- SDK-AUDIT-026: Smoke tests compile only one example.
- SDK-AUDIT-029: Quickstart idempotency key is static enough for copy-paste mistakes.
- SDK-AUDIT-030: Examples use business identifiers in correlation/idempotency IDs.
- SDK-AUDIT-032: Release tag/version consistency can be bypassed.
- SDK-AUDIT-033: Release validator can delete an arbitrary requested output directory.
- SDK-AUDIT-034: Local SBOM is direct-dependency only.
- SDK-AUDIT-035: `ToolCallResult.raw` can carry full successful response data into logs.
- SDK-AUDIT-036: Generic 500 responses expose exception class names.
- SDK-AUDIT-037: `list_all_tools()` large-catalog behavior needs clearer docs.
- SDK-AUDIT-038: `owner_team` filter exact/case-sensitive behavior is minor friction.
- SDK-AUDIT-039: Deprecated `status` parameter remains in `list_tools()`.
- SDK-AUDIT-040: Custom HTTP clients remain outside built-in network defaults.

## 9. Prior Findings Status Table

| Prior finding from `13-sdk-review-remediation.md`      | Current status                    | Evidence / challenge                                                                                                            |
| ------------------------------------------------------ | --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| SDK discovery used operator endpoint                   | Fixed                             | SDK uses `/api/v1/gateway/tools`; product route exists and is gateway-authenticated.                                            |
| Gateway discovery exposed operator shape               | Fixed                             | `GatewayToolDefinitionResponse` excludes org/environment/creator metadata.                                                      |
| Weak SDK input validation and non-local HTTP default   | Mostly fixed                      | Strict JSON, token, URL, header, finite-number validation is present; non-local HTTP rejected by default.                       |
| `get_tool()` first-page only                           | Fixed                             | `get_tool()` and `list_all_tools()` paginate.                                                                                   |
| Static token repr exposed token                        | Fixed                             | `StaticTokenProvider.token` uses `repr=False`.                                                                                  |
| SDK exceptions retained raw bodies                     | Mostly fixed                      | Error bodies are sanitized; successful `raw` fields remain potentially sensitive. See SDK-AUDIT-035.                            |
| Missing env token provider/list_all/cache invalidation | Fixed with caveats                | `EnvironmentTokenProvider`, `list_all_tools()`, and cache clearing exist; async clear docs are inconsistent.                    |
| Loose payload and base URL boundaries                  | Fixed                             | Strict payload and base URL validation exist.                                                                                   |
| Non-finite config and unsafe exception messages        | Mostly fixed                      | Numeric validation and generic messages exist; `idempotency_persistence_failed` exposes sanitized server message intentionally. |
| Discovery ignored `Retry-After`                        | Fixed                             | Retry-After parsing and caps exist.                                                                                             |
| SDK embedded only in product-platform                  | Mostly fixed                      | Standalone package exists; product source still carries a vendored copy with drift risk.                                        |
| Resource-scoped credential grants flattened            | Fixed                             | Discovery and invocation check structured tool resource grants.                                                                 |
| Discovery cache crossed credential rotations           | Fixed                             | Cache partitioning by token fingerprint exists.                                                                                 |
| Missing async SDK                                      | Implemented with residual gaps    | Async client exists; coverage/docs have gaps.                                                                                   |
| Package buildability and external docs weak            | Improved                          | Local package tests and release validator pass; PyPI discoverability/provenance remain unresolved.                              |
| Optional response fields under-validated               | Fixed                             | Optional mapping fields are rejected if malformed.                                                                              |
| Sync client async token-provider misuse unclear        | Fixed                             | Sync token-provider guard exists.                                                                                               |
| Redaction missed common secret shapes                  | Improved                          | Expanded redaction exists, still best-effort.                                                                                   |
| Production developer docs incomplete                   | Improved but still not self-serve | Credential issuance and published-package evidence remain gaps.                                                                 |
| Release validation not repeatable                      | Improved                          | `validate_release.py` exists and passed locally. Target-index install validation is missing.                                    |
| Sync/async constructor validation duplicated           | Partially fixed                   | `_client_config()` centralizes config validation; runtime sync/async logic remains mirrored.                                    |

## 10. Scoring Matrix

### Implementation Quality

- Current score: 6.8/10.
- Prior score from review log: 8.1/10.
- Direction: Lowered.
- Exact reasons: Core implementation is real and validated locally, but SDK-AUDIT-003, SDK-AUDIT-022, SDK-AUDIT-024, SDK-AUDIT-025, and SDK-AUDIT-027 prevent a higher score. Runtime behavior across SDK and gateway is not coherent enough for an 8.
- Score cap caused by unresolved issues: Capped around 7 by misleading retry/idempotency semantics and insufficient cross-boundary tests.
- What must be fixed to reach next score: Fix/document SDK-AUDIT-003, add gateway replay integration tests, broaden async parity tests.
- What must be fixed to reach 7: Same as above plus clarify idempotency scope in docs/tests.
- What must be fixed to reach 8: Split/structure SDK internals, remove source-copy drift risk, add full sync/async behavior parity, and prove package-index install path.

### Ease Of Use

- Current score: 6.7/10.
- Prior score from review log: 8.3/10.
- Direction: Lowered.
- Exact reasons: Docs and examples are useful, but SDK-AUDIT-001 and SDK-AUDIT-031 are first-run blockers. API rough edges in SDK-AUDIT-020, SDK-AUDIT-021, SDK-AUDIT-029, SDK-AUDIT-030, SDK-AUDIT-038, and SDK-AUDIT-039 add friction.
- Score cap caused by unresolved issues: Capped below 7 for self-serve external adoption until the package install evidence and credential issuance path are unambiguous.
- What must be fixed to reach next score: Publish exact install/version evidence and make credential issuance instructions deterministic.
- What must be fixed to reach 7: Resolve SDK-AUDIT-001 for the target index, document one supported token issuance flow, and fix the async cache docs.
- What must be fixed to reach 8: Add richer quickstarts, troubleshooting, generated API docs or doc-tested examples, and eliminate/noisily deprecate confusing compatibility flags.

### Security And Reliability

- Current score: 6.4/10.
- Prior score from review log: 8.3/10.
- Direction: Lowered.
- Exact reasons: Strong secure defaults exist, but SDK-AUDIT-003, SDK-AUDIT-005, SDK-AUDIT-006, SDK-AUDIT-007, SDK-AUDIT-009, SDK-AUDIT-011, SDK-AUDIT-012, and SDK-AUDIT-013 cap the score. Reliability depends too much on manual cleanup, correct deployment egress, and exact interpretation of idempotency.
- Score cap caused by unresolved issues: Capped in the mid-6 range by one high-confidence high reliability issue plus multiple medium operational/security risks.
- What must be fixed to reach next score: Correct retry/replay semantics, automate cleanup, harden rate-limit keying, and document/enforce upstream allowlists for non-local environments.
- What must be fixed to reach 7: Resolve SDK-AUDIT-003 or document it plainly with SDK behavior changes that avoid misleading retries; add cleanup scheduling; add egress/allowlist deployment guidance.
- What must be fixed to reach 8: Close provenance, add stronger secret-ref grammar, add recovery jobs for partial runtime states, and add security tests around SSRF, retention, and policy hooks.

## 11. Score Cap Explanation

- A single critical issue would cap relevant scores at 4 or lower. No critical issue was proven.
- SDK-AUDIT-003 is a high-severity reliability issue with high confidence. It caps security/reliability below 7 unless fixed or documented with safer SDK behavior.
- SDK-AUDIT-001 is high severity but medium confidence because the package may be published in a way this environment could not resolve. It caps ease of use for self-serve users until the target install path is proven.
- Multiple medium issues around idempotency durability, manual cleanup, upstream SSRF assumptions, release provenance, async coverage, and source/wheel drift cap implementation and reliability below 8.
- Strong local validation prevents the score from falling into the 4-5 range. The SDK and gateway are not fake or non-functional; they are functional but still fragile.

## 12. Required Fixes To Reach MVP Readiness

For a supervised internal MVP, the repo is already usable if operators understand the caveats. For a broader credible MVP, fix these first:

1. Resolve SDK-AUDIT-003 by aligning SDK retry docs/tests with gateway replay behavior.
2. Resolve SDK-AUDIT-001 by proving the intended package-index install path.
3. Resolve SDK-AUDIT-031 by providing exact credential issuance instructions.
4. Resolve SDK-AUDIT-006 by adding cleanup scheduling guidance or automation.
5. Resolve SDK-AUDIT-011 and SDK-AUDIT-012 with explicit egress/allowlist deployment requirements for all shared environments.
6. Add integration tests that use the built package against a real gateway for success, denial, retryable upstream failure, idempotency replay, stale idempotency, and persistence failure.

## 13. Required Fixes To Reach 7 Out Of 10

- SDK-AUDIT-001: Verify and document exact package install path.
- SDK-AUDIT-003: Stop over-promising invocation retries or change server/SDK behavior.
- SDK-AUDIT-004: Document idempotency scope or store deterministic pre-execution responses.
- SDK-AUDIT-006: Add scheduled cleanup path and monitoring.
- SDK-AUDIT-025/027: Add async parity and gateway replay integration tests.
- SDK-AUDIT-031: Make credential issuance self-serve for a competent engineer.

## 14. Required Fixes To Reach 8 Out Of 10

- Close the PyPI provenance loop with trusted publishing or hash-linked manifests.
- Remove or fully automate the vendored SDK copy.
- Split the SDK into maintainable modules with shared sync/async behavior tests.
- Add production-like egress/SSRF validation and operational runbook checks.
- Add recovery handling for partial runtime audit/idempotency states.
- Add transitive SBOM/dependency-audit evidence and package-index install validation.
- Provide generated or doc-tested API reference and richer examples for common frameworks.

## 15. Recommended Remediation Order

1. Fix SDK-AUDIT-003, because it is the most consequential behavior mismatch.
2. Fix SDK-AUDIT-001 and SDK-AUDIT-028, because package installation is the first user journey.
3. Fix SDK-AUDIT-031, because token issuance is the second user journey.
4. Fix SDK-AUDIT-006 and SDK-AUDIT-007, because retention without scheduling is risky.
5. Fix SDK-AUDIT-011 and SDK-AUDIT-012 before any external deployment.
6. Add cross-package gateway replay integration tests and async parity tests.
7. Tighten release provenance and tag/version checks.
8. Clean up API/doc polish issues: async cache clear docs, no-op flag, example IDs, `raw` logging guidance.
9. Refactor SDK structure and vendored-source strategy.

## 16. Validation Plan

Minimum validation before raising scores:

- Clean public/private package-index install:
  - `python -m venv /tmp/ophanix-sdk-index-test`
  - install exact published version from the intended index
  - import `ophanix_tool_gateway`
  - run a MockTransport smoke call
- Running gateway contract tests from an installed SDK:
  - discovery success
  - invocation success
  - denial
  - schema validation failure with idempotency key
  - upstream `503` persisted as completed replay
  - idempotency persistence failure
  - stale in-progress record
- Async parity tests for:
  - retries
  - malformed responses
  - cache partitioning
  - response-size limits
  - event hooks
  - custom client validation
- Security tests for:
  - upstream metadata/private host rejection
  - allowed host requirements in `staging` or equivalent shared environment
  - `secret_ref` grammar
  - header-control character rejection for retrieved secrets
  - rate-limit key peppering
- Release tests:
  - build wheel/sdist
  - `twine check`
  - transitive SBOM
  - dependency audit
  - tag/version match
  - published file hash equals validated artifact hash
- Operations tests:
  - idempotency cleanup scheduled and observable
  - stale runtime action recovery/alert
  - replay retention enforced

## 17. Final Strict MVP Assessment

The current repository is a real, functional MVP candidate for controlled use. It is much stronger than the earliest SDK state and the most serious old security bugs have been addressed. A capable internal team can evaluate it with support.

It is not a clean, self-serve external MVP yet. The two issues that most clearly prevent that label are the package-install evidence mismatch and the SDK/gateway idempotent retry semantic mismatch. The rest of the register is mostly medium and low severity, but together they explain why the prior 8+ scores are not justified by current repository evidence.

Strict final call: functional but fragile MVP. Suitable for supervised internal pilot; borderline for a closely supported design partner; not yet suitable for broader early-adopter rollout without the remediation items above.

## 18. Iterative Remediation Passes

### Pass 21: SDK Retry And Gateway Replay Semantics

Issues addressed:

- SDK-AUDIT-003
- SDK-AUDIT-027
- SDK-AUDIT-025, partially

Root cause:

The SDK retry gate treated any retryable HTTP status as retryable when an idempotency key was present. That was correct for transport or gateway-level failures before the gateway has stored a terminal idempotency result, but incorrect for gateway execution failures such as `upstream_error`. The gateway stores those terminal responses for replay under the same idempotency key. Retrying the same key would replay the stored failure, not re-execute the upstream operation.

Implemented fix:

- Added `TERMINAL_TOOL_CALL_ERROR_CODES` to the standalone SDK and product-platform vendored SDK copy.
- Updated `_should_retry_tool_call_response()` to stop retrying:
  - responses with `Idempotency-Replayed: true`
  - `idempotency_persistence_failed`
  - terminal gateway execution errors such as `upstream_error`, `upstream_timeout`, `upstream_circuit_open`, target/auth/config errors, query/path validation errors, and response-size failures
- Kept retries for cases where retrying the same key can still help:
  - transport loss
  - transient gateway/throttling statuses without terminal execution codes
  - `409 idempotency_in_progress`
- Updated SDK README, SDK API reference, and product-platform README to describe the exact retry scope.
- Added standalone SDK tests proving sync and async clients do not retry terminal upstream execution failures or replayed retryable responses.
- Added an installed-wheel product gateway contract test proving the built SDK does not retry a persisted upstream failure and that explicit reuse of the same key replays without re-executing the gateway executor.

Impact and rationale:

This changes the SDK from "optimistic retry of any retryable status" to "conservative retry only while outcome may still become available." That is the safer production-grade behavior for a gateway that may front mutating tools. Retrying terminal upstream failures with the same idempotency key was misleading and wasted retry budget; retrying with a new key remains a business-level reconciliation decision.

Validation:

- `python3 -m pytest tests/test_sdk_behavior.py -q` in `packages/ophanix-tool-gateway-sdk`: passed.
- `python3 -m pytest tests/test_tool_gateway_installed_sdk_contract.py -q` in `packages/product-platform`: passed.
- Later full SDK and Tool Gateway suites also passed; see final validation below.

Remaining concerns:

- This does not provide automatic upstream retry for read-only tools. A future production feature could add explicit per-tool retry policy with method/idempotency guarantees, but the current safe default should not re-execute terminal gateway outcomes.

### Pass 22: Security-Sensitive Runtime Hardening

Issues addressed:

- SDK-AUDIT-009
- SDK-AUDIT-011, partially
- SDK-AUDIT-012
- SDK-AUDIT-013, partially
- SDK-AUDIT-014
- SDK-AUDIT-015
- SDK-AUDIT-016
- SDK-AUDIT-036

Root causes:

- Rate-limit bucket derivation hashed bearer tokens with raw SHA-256 before the operational-state hash, inconsistent with the stronger peppered credential-hash posture.
- Upstream allowlists were required only in literal `production`, leaving staging/pilot environments underprotected.
- Secret-reference validation relied on narrow heuristics.
- Retrieved upstream secrets were trusted when constructing HTTP headers.
- Query secret detection used broad substring matching that rejected harmless names such as `monkey`.
- Policy hook result validation only wrapped hook execution, not result normalization.
- Generic 500 responses always exposed exception class names.

Implemented fix:

- Changed Tool Gateway rate-limit authorization buckets to use HMAC-SHA256 with `gateway_token_hash_pepper` when configured, falling back to `session_secret` in local/test contexts.
- Required `OPHANIX_TOOL_GATEWAY_UPSTREAM_HOST_ALLOWLIST` in all non-local environments, not only literal `production`.
- Expanded inline-secret detection for `secret_ref` to reject common token prefixes and high-entropy/base64-like strings.
- Added explicit header-control-character rejection for retrieved upstream bearer/API-key secrets.
- Replaced broad query-key substring detection with exact/segment-aware secret-like query detection, preserving safety for `api_key`, `access_token`, `secret_key`, etc. while allowing innocuous names such as `monkey`.
- Normalized policy hook return values through `ToolPolicyHookResult.model_validate()` inside the fail-closed exception boundary.
- Suppressed `error_type` in generic 500 responses outside local/test environments.

Impact and rationale:

These changes tighten OWASP A01/A02/A04/A06/A09/A10-adjacent boundaries without changing normal happy-path SDK usage. They reduce secret exposure, make non-local upstream forwarding safer by default, make policy hooks fail closed on malformed returns, and improve operator ergonomics by avoiding false-positive query rejections.

Validation:

- `python3 -m pytest tests/test_tool_gateway_decision_phase3.py tests/test_tool_gateway_forwarding_phase2.py tests/test_tool_gateway_upstream_phase1.py tests/test_tool_gateway_auth_phase3.py -q`: 66 passed.
- `python3 -m pytest tests/test_mvp_cloud_deployment_phase2.py -q`: 7 passed.
- Later full Tool Gateway suite passed.

Remaining concerns:

- `secret_ref` validation is stronger but still heuristic. A future production step should enforce a structured reference grammar such as `env:NAME`, `sm://...`, or provider-specific URIs.
- Application-level SSRF controls are stronger because allowlists are required for all non-local environments, but network egress policy still needs deployment enforcement.

### Pass 23: Packaging, Release, And Developer-Experience Guardrails

Issues addressed:

- SDK-AUDIT-020, documentation portion
- SDK-AUDIT-023
- SDK-AUDIT-026
- SDK-AUDIT-028, partially
- SDK-AUDIT-029
- SDK-AUDIT-030, partially
- SDK-AUDIT-031
- SDK-AUDIT-032
- SDK-AUDIT-033
- SDK-AUDIT-035

Root causes:

- Release validation checked the main SDK file but not the full vendored package surface.
- The validator recursively deleted a requested output directory for convenience.
- Strict tag validation could be weakened by passing an arbitrary `--expected-tag`.
- Package smoke tests compiled only one example.
- Async cache-clearing docs omitted `aclear_tool_cache()`.
- Credential issuance docs still implied endpoint ambiguity.
- Examples used static or business-identifying idempotency/correlation patterns.
- Successful `ToolCallResult.raw` logging risk was not explicit.
- Release validation did not offer a post-publish index-install verification mode.

Implemented fix:

- Updated release validator to compare all expected package files between the standalone SDK and product-platform vendored SDK copy: `__init__.py`, `sdk.py`, and `py.typed`.
- Replaced recursive output-directory deletion with safe cleanup of only known release artifacts; non-release files now cause validation to fail.
- Enforced that any `--expected-tag` still includes the package version, supporting `v0.1.0` and package-specific forms such as `ophanix-tool-gateway-sdk-v0.1.0`.
- Added optional `--verify-index-install` and `--index-url` release-validator flags for post-publish clean install checks from the intended package index.
- Updated package smoke tests to compile every Python file under `examples/`.
- Updated API reference to document `await client.aclear_tool_cache()` for async runtimes.
- Updated API reference to warn that `ToolCallResult.raw` may contain successful response data and should not be logged blindly.
- Updated README quickstart to generate an opaque operation ID instead of showing a static idempotency key.
- Updated LangGraph example fallback to use an opaque manual operation ID instead of embedding `claim_id` in the idempotency/correlation path.
- Replaced the credential issuance caveat with a concrete statement that the documented Product Platform endpoints are the supported `0.1.x` issuance flow.

Impact and rationale:

The SDK is now harder to release incorrectly, harder to drift between standalone and product-platform source copies, and less likely to teach users unsafe copy-paste patterns. The optional package-index validation gives release owners a concrete way to prove a published artifact is installable, although it still must be run against the actual target index after publication.

Validation:

- `python3 -m pytest tests -q` in `packages/ophanix-tool-gateway-sdk`: 39 passed.
- `python3 scripts/validate_release.py --out-dir /tmp/ophanix-sdk-audit-release --skip-twine-check`: passed.
- `python3 -m py_compile scripts/validate_release.py examples/async_worker_example.py examples/langgraph_node_example.py`: passed.
- `python3 -m mypy src/ophanix_tool_gateway`: passed.

Remaining concerns:

- `--verify-index-install` was implemented but not run in this pass because the package-index availability issue remains environment/index dependent.
- The vendored source copy still exists. Full parity validation reduces drift risk, but generation or single-source packaging would be cleaner.

## 19. Post-Remediation Re-Review

Previously highest-risk findings changed as follows:

| Issue         | Status after passes               | Notes                                                                                                                                                                |
| ------------- | --------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| SDK-AUDIT-001 | Still open                        | Public package-index installability still needs target-index validation. The validator now has `--verify-index-install`, but this pass did not prove the index path. |
| SDK-AUDIT-002 | Partially open                    | Release validation is stronger, but final PyPI/provenance loop still requires trusted publishing or hash-linked post-publish evidence.                               |
| SDK-AUDIT-003 | Resolved for current SDK behavior | SDK no longer retries terminal/replayed gateway execution failures and docs now describe exact retry scope.                                                          |
| SDK-AUDIT-004 | Open                              | Idempotency still starts after policy/schema validation. This remains a contract semantics concern.                                                                  |
| SDK-AUDIT-005 | Open                              | Unknown outcome after idempotency completion persistence failure remains inherent without a reconciliation API.                                                      |
| SDK-AUDIT-006 | Open                              | Cleanup command exists, but no scheduler/deployment automation was added in this pass.                                                                               |
| SDK-AUDIT-007 | Open                              | Replay body retention still depends on cleanup execution.                                                                                                            |
| SDK-AUDIT-009 | Resolved                          | Rate-limit authorization buckets now use keyed HMAC before operational-state hashing.                                                                                |
| SDK-AUDIT-011 | Partially mitigated               | Non-local allowlists are now required; deployment egress policy remains external.                                                                                    |
| SDK-AUDIT-012 | Resolved                          | Upstream host allowlist required in all non-local environments.                                                                                                      |
| SDK-AUDIT-013 | Partially mitigated               | Inline-secret detection is stronger; structured secret-ref grammar remains future work.                                                                              |
| SDK-AUDIT-014 | Resolved                          | Retrieved secrets with header control characters now fail closed.                                                                                                    |
| SDK-AUDIT-015 | Resolved                          | Query secret detection is segment-aware and allows harmless keys containing `key`.                                                                                   |
| SDK-AUDIT-016 | Resolved                          | Malformed policy hook return values fail closed as `policy_error`.                                                                                                   |
| SDK-AUDIT-020 | Partially resolved                | Async cache-clear docs now identify `aclear_tool_cache()`. Code still keeps both methods for compatibility.                                                          |
| SDK-AUDIT-023 | Resolved                          | Release validator checks full expected package-file parity.                                                                                                          |
| SDK-AUDIT-025 | Partially mitigated               | Added async retry-semantic test. Full async parity matrix remains future work.                                                                                       |
| SDK-AUDIT-026 | Resolved                          | Smoke test compiles all example files.                                                                                                                               |
| SDK-AUDIT-027 | Resolved for retry/replay case    | Installed-wheel gateway contract now covers persisted upstream failure replay.                                                                                       |
| SDK-AUDIT-028 | Partially mitigated               | Optional post-publish index install validation added; actual package index still must be verified.                                                                   |
| SDK-AUDIT-029 | Resolved                          | README quickstart now generates opaque idempotency key.                                                                                                              |
| SDK-AUDIT-030 | Partially mitigated               | LangGraph fallback no longer embeds `claim_id`; examples still use human-readable job/workflow IDs where caller-provided.                                            |
| SDK-AUDIT-031 | Improved                          | README now documents supported `0.1.x` Product Platform issuance flow rather than warning endpoint names may differ.                                                 |
| SDK-AUDIT-032 | Resolved                          | Expected tags must include package version.                                                                                                                          |
| SDK-AUDIT-033 | Resolved                          | Release validator no longer recursively deletes arbitrary existing output directories.                                                                               |
| SDK-AUDIT-035 | Resolved in docs                  | API reference now warns against logging successful `raw` snapshots.                                                                                                  |
| SDK-AUDIT-036 | Resolved                          | Generic `error_type` detail is local/test only.                                                                                                                      |

Updated strict scores after remediation:

| Category                 | Previous current score | Updated score | Direction | Reason                                                                                                                                                                                                                                                                                                              |
| ------------------------ | ---------------------: | ------------: | --------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Implementation quality   |                 6.8/10 |        7.4/10 | Raised    | The main retry/idempotency mismatch is fixed, integration tests now cover it, and release/source-copy guards are stronger. Remaining caps: idempotency scope, persistence-failure reconciliation, source-copy design, and incomplete async parity.                                                                  |
| Ease of use              |                 6.7/10 |        7.3/10 | Raised    | Docs now describe exact retry scope, supported credential issuance, async cache clearing, safer examples, and raw logging risk. Remaining cap: public package-index installability still unverified from this environment.                                                                                          |
| Security and reliability |                 6.4/10 |        7.2/10 | Raised    | Keyed rate-limit buckets, non-local upstream allowlists, fail-closed policy hook validation, secret header validation, and safer retry semantics materially improve reliability/security. Remaining caps: cleanup scheduling, replay retention, egress enforcement, provenance, and unknown-outcome reconciliation. |

## 20. Final Validation After Iterative Remediation

Commands run and results:

- `python3 -m pytest tests/test_sdk_behavior.py -q` in `packages/ophanix-tool-gateway-sdk`: passed during Pass 21.
- `python3 -m pytest tests/test_tool_gateway_installed_sdk_contract.py -q` in `packages/product-platform`: 4 passed, 2 upstream dependency deprecation warnings.
- `python3 -m pytest tests/test_tool_gateway_decision_phase3.py tests/test_tool_gateway_forwarding_phase2.py tests/test_tool_gateway_upstream_phase1.py tests/test_tool_gateway_auth_phase3.py -q`: 66 passed.
- `python3 -m pytest tests/test_mvp_cloud_deployment_phase2.py -q`: 7 passed.
- `python3 -m pytest tests -q` in `packages/ophanix-tool-gateway-sdk`: 39 passed.
- `python3 scripts/validate_release.py --out-dir /tmp/ophanix-sdk-audit-release --skip-twine-check`: passed.
- `python3 -m py_compile scripts/validate_release.py examples/async_worker_example.py examples/langgraph_node_example.py`: passed.
- `python3 -m mypy src/ophanix_tool_gateway` in the SDK package: passed.
- `python3 -m mypy src/product_platform/tool_gateway src/ophanix_tool_gateway` in product-platform: passed.
- `python3 -m pytest tests/test_tool_gateway_*.py -q` in product-platform: 324 passed, 2 upstream dependency deprecation warnings.
- `git diff --check`: passed.

## 21. Remaining Production-Readiness Gaps

The SDK is now stronger than the original audit score suggested, and it clears the biggest correctness/reliability mismatch found in this review. It still should not be called fully production-ready until these are closed:

- Verify package-index installability and published artifact provenance for the exact released version.
- Add trusted publishing or a mandatory published-file hash check against the validated release manifest.
- Add scheduled idempotency cleanup and operational alerts for replay retention and stale in-progress rows.
- Add a reconciliation/read API for unknown idempotency outcomes after persistence failure.
- Enforce or document deployment-level egress policy for upstream forwarding.
- Replace heuristic `secret_ref` detection with a structured secret-reference grammar.
- Remove or generate the product-platform vendored SDK copy to eliminate dual-source maintenance.
- Expand async SDK parity tests beyond the retry/replay scenario.

Updated final call: credible MVP for supported internal and design-partner pilots, with several production-grade fixes now implemented and validated. Still not a fully production-ready self-serve external SDK until package-index provenance and operational idempotency/egress controls are proven.
