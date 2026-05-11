# Tool Gateway SDK Review Remediation

## Scope

Deep review and remediation pass for the Python Tool Gateway SDK and its matching server contract. The review focused on code quality, architecture, developer experience, security, reliability, and production readiness.

## Pass 1: SDK Discovery Contract

Issue: `OphanixToolGatewayClient.list_tools()` called `/api/v1/tools` with a gateway bearer token, but the server protects `/api/v1/tools` with product-user authorization. Real agent credentials could invoke tools but could not discover them.

Root cause: SDK discovery reused the operator registry endpoint instead of exposing an agent-safe gateway-authenticated discovery contract.

Fix:
- Added `GET /api/v1/gateway/tools` guarded by `GatewayPrincipal`.
- Added `ToolRegistryRepository.list_tools_for_gateway_principal()` to return only active tools with an active, unexpired agent-tool permission whose scope matches both the tool and credential scopes.
- Updated the SDK to call `/api/v1/gateway/tools`.

Impact and rationale: Discovery now uses the same trust boundary as gateway invocation and only exposes tools that the authenticated agent can actually call.

Validation:
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_sdk_remediation.py' -v`
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_sdk_phase*.py' -v`

## Pass 2: Gateway-Safe Discovery Shape

Issue: The new gateway discovery route initially returned the operator-facing `ToolDefinitionResponse`, which includes fields agents do not need, such as tenant IDs and creator metadata.

Root cause: The product API had only one tool-definition response model, optimized for the control-plane UI rather than external agent SDK discovery.

Fix:
- Added `GatewayToolDefinitionResponse`.
- Added `gateway_tool_definition_response()` serializer.
- Updated `/api/v1/gateway/tools` to use the narrower model.

Impact and rationale: Agent discovery now follows least-privilege data exposure while preserving all fields needed by the SDK.

Validation:
- Added assertions that discovery omits `organization_id`, `environment_id`, and `created_by`.
- Re-ran remediation and SDK test suites.

## Pass 3: SDK Hardening

Issues:
- `call_tool(123, {})` raised `AttributeError` instead of a clear validation error.
- Non-JSON-serializable payloads failed only inside HTTPX.
- Successful HTTP responses with malformed bodies were accepted as successful SDK results.
- Non-local plain HTTP was allowed by default.

Root cause: Early SDK code trusted caller inputs and gateway response shape too broadly to keep the wrapper thin.

Fix:
- Added runtime type validation for base URL, tool names, optional text values, tokens, and payload JSON serializability.
- Added strict success-response validation for tool calls and tool discovery.
- Required HTTPS by default for non-local hosts while preserving localhost development and explicit insecure opt-in.

Impact and rationale: Failures are now deterministic, typed, and easier to debug; token transport is safer by default.

Validation:
- Added SDK unit tests for malformed input, malformed successful responses, non-JSON success bodies, malformed discovery entries, and HTTP transport policy.
- Re-ran SDK tests after each change.

## Pass 4: Scalability and DX

Issue: `get_tool()` only searched the first `list_tools(limit=200)` page, so larger tenants could miss valid tools.

Root cause: The initial helper was implemented as a small convenience wrapper over the list endpoint.

Fix:
- Updated `get_tool()` to paginate until it finds a matching name/id or reaches the final page.
- Added a pagination regression test.

Impact and rationale: The helper remains simple for developers but now scales with tenant tool count.

Validation:
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_sdk_phase3.py' -v`

## Remaining Notes

- The SDK is still packaged inside `ophanix-product-platform`; a dedicated lightweight SDK package would improve install size and dependency clarity before external production adoption.
- Idempotency for mutating tool calls is not implemented in this pass because the server contract does not yet support it. Add an end-to-end idempotency key contract before introducing automatic retries for mutations.

## Final Validation

- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_sdk_phase*.py' -v`: 30 SDK tests passed after pagination hardening.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_sdk_remediation.py' -v`: 4 remediation tests passed.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_*.py' -v`: 157 Tool Gateway tests passed.
- `PYTHONPATH=src python3 -m unittest discover -s tests -v`: 653 product-platform tests passed.
- `git diff --check` over the touched files reported no whitespace errors.

## Iterative Review Passes

### Pass 5: Secret Representation and Error Diagnostics

Issue: `StaticTokenProvider` used the dataclass-generated representation, which included the raw bearer token. SDK exceptions also retained full gateway response bodies, which made accidental token, PII, or upstream payload logging too easy.

Root cause: The initial SDK optimized for a minimal wrapper and did not separate diagnostic usefulness from safe-by-default exception data.

Research and rationale:
- Python dataclasses support field-level `repr=False`, which is the correct language-native way to keep sensitive fields out of generated representations.
- OWASP logging guidance recommends removing, masking, or sanitizing access tokens, session identifiers, passwords, keys, and sensitive personal data before logging.

Fix:
- Marked `StaticTokenProvider.token` with `field(repr=False)`.
- Added bounded, recursive redaction for SDK `response_body` diagnostics.
- Converted non-JSON responses into a structured `non_json_response` error with a truncated excerpt instead of using arbitrary response text as the exception message.
- Added an SDK `User-Agent` for supportability without exposing caller secrets.

Impact: Accidental logging of token provider objects and exception bodies is now materially safer, while request IDs, reason codes, and bounded diagnostic context remain available.

Validation:
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_sdk_phase[12].py' -v`: 22 tests passed.

### Pass 6: Developer Experience and Discovery Reliability

Issue: External agents had to provide tokens manually, paginate discovery manually, and interpret a `ToolDefinition` type that still reflected older operator-facing fields.

Root cause: SDK ergonomics had grown from internal test fixtures rather than a first-run external developer journey.

Fix:
- Added `EnvironmentTokenProvider`, exported from `product_platform.tool_gateway`.
- Added `list_all_tools()` for common discovery flows.
- Added transient retries with exponential backoff for gateway discovery only. Tool invocations remain non-retried until the server supports idempotency keys.
- Added `clear_tool_cache()` for explicit cache invalidation.
- Aligned SDK `ToolDefinition` fields to the gateway-safe discovery contract and kept extra server fields only in `raw`.
- Added `py.typed` for typed downstream integrations.

Impact: Common setup now works from an environment variable, discovery is simpler for developers, and safe GET discovery is more resilient without risking duplicate tool mutations.

Validation:
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_sdk_phase*.py' -v`: 38 tests passed.

### Pass 7: Boundary Hardening

Issue: Payload validation relied on `json.dumps()`, which can silently accept Python shapes that are not strict JSON contracts, including non-string object keys and non-finite numbers. Base URLs with userinfo, query strings, or fragments could also create confusing or unsafe request construction.

Root cause: The SDK validated the happy path but did not fully enforce the SDK's public API boundary before handing values to HTTPX.

Fix:
- Enforced strict JSON object payloads with string keys and finite numbers.
- Rejected URL credentials, query strings, and fragments in `base_url`.
- Rejected header control characters in bearer tokens, correlation IDs, and custom user agents.
- Matched SDK-side `list_tools(limit=...)` validation to the gateway's `le=200` contract.
- Normalized integer argument validation for retry counts, discovery limits, offsets, and `list_all_tools()` page size.
- Returned a stable `invalid_response` code for malformed discovery bodies.

Impact: Invalid inputs now fail deterministically at the SDK boundary with clear errors instead of being normalized silently, rejected later by HTTPX/FastAPI, or serialized into surprising wire payloads.

Validation:
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_sdk_phase*.py' -v`: 50 tests passed.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_*.py' -v`: 177 Tool Gateway tests passed.
- `PYTHONPATH=src python3 -m unittest discover -s tests -v`: 670 product-platform tests passed.
- `git diff --check`: no whitespace errors.
- `PYTHONPATH=src python3 -m py_compile src/product_platform/tool_gateway/sdk.py src/product_platform/tool_gateway/__init__.py`: passed.
- Import sanity check confirmed `EnvironmentTokenProvider`, `OphanixToolGatewayClient`, and redacted `StaticTokenProvider()` representation.

### Pass 8: Numeric Configuration and Safe Exception Messages

Issues:
- `timeout_seconds`, `discovery_retry_backoff_seconds`, and related numeric configuration accepted non-finite values such as `NaN` and `Infinity`.
- `allow_insecure_http` and `cache_tools` accepted truthy non-boolean values, making security-sensitive configuration too easy to misread.
- SDK exception messages used server-supplied `error.message` values directly, which created a logging exposure path even though `response_body` diagnostics were being redacted.

Root cause: The previous hardening pass validated broad types and response bodies, but did not fully separate safe public exception text from untrusted server diagnostics.

Research and rationale:
- Production SDKs should validate public configuration before constructing network clients. Non-finite timeout/retry values are invalid transport configuration and can produce undefined or surprising behavior in downstream HTTP libraries.
- Security logging guidance treats exception messages as a common accidental log sink, so untrusted upstream messages should not become the primary exception message by default.

Fix:
- Added finite-number validation for timeout and discovery retry sleep configuration.
- Added strict boolean validation for `allow_insecure_http` and `cache_tools`.
- Added token-provider shape validation at client construction.
- Changed transport, denial, and gateway HTTP failures to use generic SDK-owned messages while preserving sanitized diagnostic data in `response_body`.
- Expanded text sanitization to redact bearer tokens and common `token=`, `secret=`, `password=`, and API key patterns inside diagnostic strings.

Impact: SDK configuration now fails fast with deterministic errors, and application logs that include exception messages no longer receive arbitrary gateway/upstream text by default.

Validation:
- Added regression tests for non-finite timeout/retry config, non-boolean security flags, missing token-provider methods, generic exception messages, and sanitized diagnostic text.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_sdk*.py' -v`: 62 SDK tests passed.

### Pass 9: Discovery Retry Behavior

Issue: Discovery retries used exponential backoff but ignored `Retry-After`, so clients could retry too aggressively during gateway throttling or controlled outages.

Root cause: The initial retry implementation focused on simple transient resilience and did not consume standard HTTP retry hints.

Research and rationale:
- `Retry-After` is the standard server hint for 429 and retryable 5xx/maintenance-style responses.
- SDKs should cap server-provided retry delays so a single response cannot stall an agent process for an unexpected duration.

Fix:
- Added `Retry-After` parsing for both delta-seconds and HTTP-date forms.
- Added `discovery_retry_max_sleep_seconds` with finite non-negative validation.
- Capped retry sleeps while continuing to avoid automatic retries for tool invocation until the gateway supports idempotency keys.

Impact: Safe GET discovery is more cooperative with gateway backpressure without creating unbounded sleeps or duplicate mutating calls.

Validation:
- Added a regression test proving `Retry-After` is honored and capped.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_sdk*.py' -v`: 62 SDK tests passed.

### Pass 10: Lightweight SDK Distribution Path

Issue: The SDK was embedded only under `product_platform.tool_gateway`, forcing external agents toward the full product-platform dependency graph.

Root cause: The SDK began as an internal integration helper inside the control-plane package and did not have a separate distribution boundary.

Research and rationale:
- External agent SDKs should keep dependency and install surfaces small. A dedicated namespace and package metadata reduce supply-chain exposure, import cost, and integration friction.
- Compatibility exports are useful during migration so existing internal callers do not have to change imports immediately.

Fix:
- Extracted the SDK implementation into the standalone `ophanix_tool_gateway` namespace.
- Kept `product_platform.tool_gateway.sdk` as a compatibility re-export.
- Added `packages/ophanix-tool-gateway-sdk` package metadata with only `httpx` as a runtime dependency.
- Included `ophanix_tool_gateway` in the product-platform wheel target so compatibility imports keep working in product builds.
- Added `py.typed` markers for typed downstream integrations.
- Updated README examples to use `ophanix_tool_gateway` as the preferred import path.

Impact: External agents now have a lightweight package path while existing product-platform imports remain stable.

Validation:
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_sdk*.py' -v`: 62 SDK tests passed.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_*.py' -v`: 185 Tool Gateway tests passed.
- Import sanity checks confirmed `ophanix_tool_gateway.OphanixToolGatewayClient` and `product_platform.tool_gateway.OphanixToolGatewayClient` resolve to the same class.
- Source-level standalone import check with `PYTHONPATH=packages/ophanix-tool-gateway-sdk/src` passed.
- Wheel build validation is still pending in this local environment because `python3 -m hatchling build -t wheel` failed with `No module named hatchling`.

### Pass 11: Resource-Bound Credential Scope Enforcement

Issue: Credential scopes carried `resource_type` and `resource_id`, but gateway authorization flattened them to a list of scope strings. A credential bound to one tool resource could satisfy another tool with the same required scope string if an agent permission existed.

Root cause: `GatewayPrincipal.scopes` represented only names such as `claims.lookup:read`; discovery and invocation compared `required_scope` against that list and did not preserve the credential's object-level binding.

Research and rationale:
- OWASP API guidance identifies broken object-level authorization as a core API risk. Authentication and scope strings are not sufficient when the credential grant is intended to be resource-specific.
- The durable fix is to centralize resource-aware authorization at the gateway principal/repository boundary rather than relying on SDK clients or callers to self-filter.

Fix:
- Added `GatewayCredentialScope` and `GatewayPrincipal.scope_grants`.
- Added `GatewayPrincipal.allows_tool_scope()` to check scope, `resource_type='tool'`, and `resource_id` matching the tool id or name, with `NULL` resource IDs treated as intentional wildcard grants.
- Updated gateway discovery SQL to require a matching structured credential scope for each returned tool.
- Updated invocation decisions to call `principal.allows_tool_scope()` before allowing policy hooks or upstream execution.
- Updated decision tests to construct realistic structured principals instead of legacy flattened-only principals.

Impact: Discovery and invocation now enforce the same object-level credential binding. A credential with the right scope string but the wrong tool resource no longer discovers or invokes the sibling tool.

Validation:
- Added a regression where `claims.lookup` and `claims.shared_scope` share `claims.lookup:read`; a credential bound to `claims.lookup` discovers only that tool and gets `scope_insufficient` for `claims.shared_scope`.
- Initial broader Tool Gateway run caught legacy test fixture regressions; fixtures were updated to the structured principal shape.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_sdk_remediation.py' -v`: 5 remediation tests passed.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_*.py' -v`: 192 Tool Gateway tests passed.

### Pass 12: Cache Partitioning and Retry Jitter

Issue: Opt-in discovery caching was keyed only by query parameters. If a token provider rotated to a different credential, cached tools from the previous credential could be reused. Discovery backoff also lacked jitter, increasing the chance of synchronized retries during outages.

Root cause: Cache keys did not include any credential identity, and retry delay calculation used deterministic exponential backoff only.

Research and rationale:
- SDK caches that represent authorization-filtered server data must be partitioned by credential context.
- Production retry loops should include bounded jitter for client-controlled backoff while still respecting server-provided `Retry-After`.

Fix:
- Added an internal auth context carrying request headers and a SHA-256 token fingerprint used only as a cache key component.
- Moved discovery auth evaluation before cache lookup so token providers are consulted for every discovery call, including cached calls.
- Added configurable `discovery_retry_jitter_ratio` with finite numeric validation and a safe default of `0.2`.
- Kept `Retry-After` authoritative and capped without jitter.

Impact: Cached discovery can no longer cross credential rotations, and discovery retry behavior is more production-friendly under load.

Validation:
- Added regression coverage proving cached discovery partitions by changing bearer token.
- Added validation coverage for invalid jitter ratios.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_sdk_phase*.py' -v`: 60 then 62 SDK phase tests passed during the pass.

### Pass 13: Async SDK API

Issue: The SDK exposed only a synchronous client, which forces async agent runtimes to block the event loop or write custom wrappers.

Root cause: The initial SDK optimized for the first synchronous direct-HTTP demo path and did not model async integration as a first-class public API.

Research and rationale:
- HTTPX provides both sync and async clients. Agent frameworks commonly run on async event loops, so a production SDK should expose an async API with the same semantics rather than asking users to bridge sync calls themselves.

Fix:
- Added `AsyncOphanixToolGatewayClient` with async context manager support.
- Added `AsyncTokenProvider` protocol. The async client accepts synchronous or awaitable `get_token()` implementations.
- Mirrored sync behavior for call invocation, discovery, pagination, cache partitioning, retries, redaction, and response validation.
- Exported async types from `ophanix_tool_gateway`, `product_platform.tool_gateway.sdk`, and `product_platform.tool_gateway`.

Impact: Async agents can now integrate directly with `async with AsyncOphanixToolGatewayClient(...)` and `await client.call_tool(...)` without changing gateway semantics.

Validation:
- Added async invocation and async pagination tests using `httpx.AsyncClient` and `httpx.MockTransport`.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_sdk_phase*.py' -v`: 62 SDK phase tests passed.

### Pass 14: Standalone Package Buildability and External DX

Issue: The standalone package metadata declared `src/ophanix_tool_gateway`, but the source path was not previously validated as a package root. The README also lacked production-ready install, async, error-handling, retry, and safety guidance.

Root cause: The package scaffold and the product-platform compatibility path were created separately from the external developer journey.

Research and rationale:
- Python's packaging guidance recommends a `src` layout for import correctness and reliable wheel/sdist boundaries.
- A production SDK should provide install-first examples, environment-variable token handling, async examples, and documented retry/security behavior.

Fix:
- Ensured `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway` resolves to the SDK source and includes `__init__.py`, `sdk.py`, and `py.typed`.
- Added package smoke tests that import the SDK from the standalone `src` layout.
- Built a wheel with `python3 -m pip wheel . --no-deps` and verified it contains `ophanix_tool_gateway/__init__.py`, `sdk.py`, and `py.typed`.
- Expanded standalone and product-platform README sections with install, sync, async, reliability, and safety notes.

Impact: The external SDK package path is now buildable and documented, while internal compatibility imports remain stable.

Validation:
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_sdk_package.py' -v`: 2 package tests passed.
- `python3 -m pip wheel . --no-deps` from `packages/ophanix-tool-gateway-sdk`: wheel built successfully and contained the expected SDK files.
- `python3 -m compileall -q packages/product-platform/src/ophanix_tool_gateway packages/product-platform/src/product_platform/tool_gateway packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway`: passed.

### Pass 15: Credential-Scoped Discovery Cache Consistency

Issue: Follow-up review found that `list_tools()` partitioned cached list pages by credential fingerprint, but `get_tool()` checked the per-tool cache by tool name/id before evaluating the current credential. A token provider that rotated from one credential to another could receive stale tool metadata discovered under the previous credential. The same review found that `list_all_tools()` and `get_tool()` could evaluate a rotating token provider once per page, mixing pages from different credentials in one logical discovery sequence.

Root cause: Cache partitioning had been added at the list-page level, but the object cache and paginated convenience helpers still treated credential identity as an implementation detail of each individual request instead of as part of the authorization-filtered discovery context.

Research and rationale:
- Authorization-filtered SDK caches must include the effective credential context in every cache key that can affect visible data.
- A paginated discovery helper should use a stable authorization context across all pages so the result set represents one principal's view, not an accidental merge of rotated credentials.

Fix:
- Changed `_tool_cache` keys to `(credential_fingerprint, tool_lookup)` for both sync and async clients.
- Added shared `_list_tools_with_auth()` helpers so `list_tools()`, `list_all_tools()`, and `get_tool()` all use the same cache and response-validation path.
- Updated `list_all_tools()` and `get_tool()` to create one auth context and reuse it across all paginated discovery requests.
- Added sync and async regressions proving `get_tool()` cache entries do not cross token rotations.
- Added a regression proving `list_all_tools()` uses one credential context across pages.

Impact: Opt-in SDK caching now preserves the gateway's authorization boundary for both list and object lookup helpers, and paginated convenience methods return a coherent principal-specific view.

Validation:
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_sdk_phase*.py' -v`: 67 SDK phase tests passed after the cache fix.

### Pass 16: Response Contract And Token Provider Boundary Hardening

Issue: A fresh response-contract review found that optional object fields such as `decision`, `input_schema_json`, and `output_schema_json` were silently coerced to `None` when the gateway returned a malformed non-object value. A usability review also found that passing an async token provider to the synchronous client produced an unclear type error and could leave an un-awaited coroutine warning. The public package also lacked a simple `__version__` export for diagnostics.

Root cause: Earlier validation focused on required fields and security-sensitive inputs. Optional response fields and sync/async token-provider boundary errors were treated as low-risk, but production SDKs should fail deterministically when the server violates the documented contract and should guide developers to the correct client type.

Research and rationale:
- SDKs should preserve server-contract integrity by rejecting malformed successful responses rather than hiding them as missing optional data.
- Sync and async public APIs should have explicit boundaries so integration mistakes fail with actionable messages.
- A package version export improves supportability and helps users include SDK version information in bug reports without reaching into packaging internals.

Fix:
- Added strict optional mapping validation for `decision`, `input_schema_json`, and `output_schema_json`.
- Added a sync-client guard that detects awaitable token values, closes coroutine objects when possible, and raises a clear message directing callers to `AsyncOphanixToolGatewayClient`.
- Added `SDK_VERSION` and public `__version__` exports from both the standalone and compatibility namespaces.
- Added regressions for malformed optional response objects, async-token-provider misuse in the sync client, and version export consistency.

Impact: Malformed gateway responses now surface as stable `invalid_response` errors, developers get clearer integration feedback, and support diagnostics can include the SDK version consistently.

Validation:
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_sdk_phase*.py' -v`: 68 SDK phase tests passed after the boundary hardening pass.

## Scoring Matrix For Future Reviewers

This section records the scoring rationale so a new reviewer can challenge it with a consistent rubric instead of relying on intuition. Scores below are for the SDK implementation after Pass 16, not for the broader product-platform gateway server.

### Rating Bands

- `9-10`: Production-ready for external customers with polished APIs, comprehensive docs, strong CI/release controls, robust security posture, and few meaningful caveats.
- `8-8.9`: Strong production candidate. Core risks are addressed, tests are broad, and defaults are safe, but some polish or release-hardening gaps remain.
- `7-7.9`: Good alpha/beta quality. Major design is sound, but one or more production-readiness areas still need clear work.
- `6-6.9`: Functional but not production-ready. Important maintainability, safety, packaging, documentation, or reliability gaps remain.
- `<6`: Significant design or safety concerns; requires major rework before external adoption.

### Implementation Quality Matrix

Recommended strict score: `7.8/10` (`8/10` if rounded to whole numbers).

| Criterion | Weight | Score | Evidence | Why Not Higher |
| --- | ---: | ---: | --- | --- |
| Public API structure and naming | 20% | 8.0 | Clear sync/async clients, typed dataclasses, token provider protocols, compatibility exports. | `list_tools(status="active")` is still a compatibility wart because only active discovery is supported. |
| Internal architecture and maintainability | 25% | 7.0 | Shared discovery/cache helpers now reduce drift; response parsing and validation are centralized. | The SDK is still a large single-file implementation with duplicated sync/async transport code. A reviewer who weights architecture heavily may score this lower. |
| Error model and response validation | 20% | 8.0 | Stable `ToolGatewayError` / `ToolDeniedError`, generic safe messages, strict required fields, strict optional object fields after Pass 16. | Error taxonomy is still small; no specialized timeout/rate-limit/config exceptions. |
| Packaging and distribution readiness | 15% | 7.5 | Wheel and sdist build and contain `__init__.py`, `sdk.py`, and `py.typed`; package has minimal `httpx` dependency. | Monorepo package path uses a symlink; release CI still needs to enforce wheel/sdist checks. |
| Test coverage and validation depth | 20% | 8.5 | 75 SDK/package/remediation tests, 198 Tool Gateway tests, 694 full product-platform tests, compile checks, artifact checks. | No type-checker run or SAST/dependency audit was available in this pass. |

Score calculation: `(8.0*0.20) + (7.0*0.25) + (8.0*0.20) + (7.5*0.15) + (8.5*0.20) = 7.775`.

Challenge guidance: If a reviewer considers "single-file SDK plus sync/async duplication" a major production architecture issue, `7.0-7.5` is defensible. If they focus on behavior, tests, and small dependency surface, `8.0` is defensible.

### Developer Experience Matrix

Recommended strict score: `8.0/10`.

| Criterion | Weight | Score | Evidence | Why Not Higher |
| --- | ---: | ---: | --- | --- |
| First-run setup | 20% | 8.0 | README has install, env-token setup, sync and async examples. | Token acquisition lifecycle is not documented; examples are still brief. |
| API ergonomics | 25% | 8.0 | `EnvironmentTokenProvider`, context managers, `list_all_tools()`, `get_tool()`, async client, injected `httpx` clients. | `status` parameter can confuse users; no higher-level "call by discovered tool" helper beyond direct name use. |
| Diagnostics and supportability | 20% | 8.0 | Public `__version__`, SDK `User-Agent`, request/correlation IDs on errors, safe diagnostic body. | No structured logging hooks or retry telemetry callbacks. |
| Documentation completeness | 20% | 7.0 | README covers reliability and safety basics. | No full API reference, no troubleshooting table, no advanced retry/timeout examples, no concurrency guidance. |
| Migration compatibility | 15% | 9.0 | Compatibility exports keep older `product_platform.tool_gateway` imports working. | Compatibility path should eventually have deprecation guidance if standalone becomes the canonical package. |

Score calculation: `(8.0*0.20) + (8.0*0.25) + (8.0*0.20) + (7.0*0.20) + (9.0*0.15) = 7.95`.

Challenge guidance: A reviewer focused on external developer docs may reasonably rate DX as `7.0-7.5`. A reviewer focused on API surface and examples may round to `8.0`.

### Security And Reliability Matrix

Recommended strict score: `8.1/10`.

| Criterion | Weight | Score | Evidence | Why Not Higher |
| --- | ---: | ---: | --- | --- |
| Secure transport defaults | 15% | 9.0 | HTTPS required for non-local hosts unless `allow_insecure_http=True`; localhost development preserved. | No certificate pinning or mTLS support, though those are not necessarily SDK responsibilities. |
| Secret handling and error exposure | 20% | 8.5 | Static token excluded from `repr`; header control chars rejected; error body redaction and truncation; generic exception messages. | Regex redaction is never complete; no formal secret scanner result beyond local pattern review. |
| Authorization-sensitive caching | 20% | 8.5 | Pass 15 partitions list and object caches by credential fingerprint; paginated helpers use one auth context. | Cache is mutable and not documented as thread-safe; no explicit TTL/invalidation beyond manual `clear_tool_cache()`. |
| Input and response validation | 15% | 8.0 | Strict JSON object payloads, string keys, finite numbers, required response fields, optional mapping field validation. | Output schemas are not semantically JSON-schema validated client-side; server contract trust remains. |
| Retry and resilience behavior | 15% | 8.0 | Discovery retries safe GETs only, bounded backoff, `Retry-After`, jitter, no mutation retries without idempotency. | No circuit breaker, no per-status retry customization beyond config knobs. |
| Supply-chain and release controls | 15% | 6.5 | Minimal dependency range and local wheel/sdist checks. | No lockfile/audit result, no provenance/signing, no CI release gate documented in code. |

Score calculation: `(9.0*0.15) + (8.5*0.20) + (8.5*0.20) + (8.0*0.15) + (8.0*0.15) + (6.5*0.15) = 8.125`.

Challenge guidance: A reviewer who treats missing dependency audit, release provenance, cache thread-safety docs, and idempotent mutation retries as production blockers may score security/reliability `7.0-7.5`. A reviewer focused on SDK-local controls and the fixed credential-cache bug may round to `8.0`.

### What Actually Improved After Pass 15 And Pass 16

The rating improvement should be modest, not dramatic:

| Dimension | Before Pass 15/16 | After Pass 15/16 | Defensible Improvement |
| --- | ---: | ---: | --- |
| Implementation quality | `7.0` | `7.8` | Fixed duplicated discovery/cache paths enough to reduce drift, added stricter response-contract handling, added version exports. |
| Developer experience | `8.0` | `8.0` | Better sync/async token-provider error and `__version__`, but docs/API ergonomics still cap the score. |
| Security/reliability | `7.0` | `8.1` | The high-impact credential-crossing `get_tool()` cache bug is fixed, paginated discovery now uses one auth context, and malformed optional response fields fail closed. |

The previous informal `8.5` security and DX ratings were optimistic. Under this strict matrix, the most defensible rounded scores are:

- Implementation quality: `8/10` when rounded, `7.8/10` exact.
- Ease of use: `8/10` exact.
- Security/reliability: `8/10` when rounded, `8.1/10` exact.

### Known Reasons Another Agent May Still Score 6-7

A new review agent should explicitly decide whether these are score reducers or production-blocking issues:

- The SDK implementation remains mostly single-file with mirrored sync/async classes. This is maintainable today but not ideal long-term architecture.
- The standalone package uses a symlink into product-platform source in the monorepo. Artifact builds pass, but CI must guard this continuously.
- The README is useful but not a full production developer guide. Missing: complete API reference, troubleshooting, credential issuance flow, concurrency/thread-safety guidance, and advanced retry/timeout examples.
- The SDK has no automatic `call_tool()` retry. This is intentional until an idempotency-key contract exists, but agents expecting SDK-managed resilience may view it as a reliability gap.
- There is no documented dependency audit, SAST, provenance/signing, or release checklist in this pass.
- Cache structures are mutable and not explicitly thread-safe. This is common for Python SDK clients, but it should be documented or guarded if clients are shared across threads.
- Error redaction is pattern-based. It is safer than raw bodies, but not a formal data-loss-prevention guarantee.

If those items are weighted heavily, a `7/10` overall rating is reasonable. If the review focuses on SDK-local behavior, secure defaults, test coverage, and the remediated credential-cache issue, an `8/10` rounded rating is reasonable.

### Remaining Production Notes

- Automatic retries for `call_tool()` remain intentionally absent until the server exposes an idempotency-key contract.
- The standalone package wheel and sdist now build locally and include the expected SDK files; release-pipeline validation should keep both artifact checks before publishing.
- The current monorepo uses a source link for the standalone SDK package path so product-platform compatibility imports and standalone packaging share one implementation. CI should keep the standalone package smoke, wheel, and sdist checks in place to guard that boundary.

## Final Iterative Validation

- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_sdk_phase*.py' -v`: 68 SDK phase tests passed.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_sdk*.py' -v`: 75 SDK/package/remediation tests passed.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_*.py' -v`: 198 Tool Gateway tests passed.
- `PYTHONPATH=src python3 -m unittest discover -s tests -v`: 694 product-platform tests passed.
- `python3 -m compileall -q packages/product-platform/src/ophanix_tool_gateway packages/product-platform/src/product_platform/tool_gateway packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway`: passed.
- `python3 -m pip wheel . --no-deps` from `packages/ophanix-tool-gateway-sdk`: wheel built and included `__init__.py`, `sdk.py`, and `py.typed`.
- `PYTHONPATH=<temporary build target> python3 -m build --sdist` from `packages/ophanix-tool-gateway-sdk`: sdist built and included `__init__.py`, `sdk.py`, and `py.typed`.
- `PYTHONPATH=packages/product-platform/src python3 -Werror` import sanity check confirmed `__version__`, SDK `User-Agent`, and redacted `StaticTokenProvider()` representation.
- `git diff --check`: no whitespace errors.
- `git diff --cached --check`: no whitespace errors.

## Further Iterative Review And Remediation

### Review Restart Summary

The restart review re-read this log and independently verified the current SDK source, package metadata, tests, standalone package path, compatibility exports, and gateway discovery/auth code. The earlier remediation passes were broadly accurate: the original SDK discovery contract, overbroad discovery shape, weak input and response validation, non-local HTTP default, token/error exposure, first-page `get_tool()` behavior, credential-cache crossing, missing async client, resource-bound authorization gap, and package buildability concerns had all been materially addressed.

Remaining concerns before this pass were still real:
- The SDK implementation remained largely single-file with mirrored sync/async setup.
- Error redaction was safer than raw bodies, but still pattern-based and missed common plain-text secret shapes.
- The README was useful but not a complete production integration guide.
- Release validation existed as evidence in the log, but not as a repeatable package-local command.
- Supply-chain validation was still not codified beyond a minimal dependency range and ad hoc artifact checks.

Score challenge: the prior strict scores (`7.8` implementation, `8.0` DX, `8.1` security/reliability) were defensible after Pass 16. A stricter reviewer could still score lower if they heavily weighted documentation depth, release controls, symlinked package layout, and sync/async duplication. The new passes below target those exact score reducers.

### Pass 17: Expanded Secret Redaction Coverage

Issue: The SDK sanitized structured error bodies and simple `token=` text, but common diagnostic strings could still retain partial secret material. Examples included hyphenated bearer tokens, `client_secret = '...'`, `x-api-key: "..."`, `access_token=...`, and `private_key: ...`. The previous sensitive-key matcher also used a broad substring check, so unrelated keys such as `monkey` could be over-redacted.

Root cause: Earlier redaction focused on a small set of simple key-value forms and bearer tokens. It did not normalize structured keys carefully or model quoted values, optional whitespace around separators, hyphenated token values, or common OAuth/API-key field names.

Security and reliability implications:
- This is an OWASP A09 logging concern. Exception diagnostic bodies are often logged by applications.
- The SDK already used generic exception messages, so the remaining risk was mostly sanitized `response_body` diagnostics.
- Redaction is still best-effort, not a full data-loss-prevention engine, but it should cover common production shapes deterministically.

Fix:
- Replaced broad substring key matching with normalized exact-name and suffix matching.
- Added compiled redaction patterns for common text assignment forms.
- Added support for quoted values, optional whitespace, `x-api-key`, OAuth token names, client secrets, private keys, and hyphenated bearer tokens.
- Preserved useful non-sensitive diagnostic keys such as `monkey`.
- Added a regression test for mixed text secret shapes and non-sensitive lookalike keys.

Impact: SDK diagnostics now reduce accidental secret logging for more realistic upstream error strings while preserving harmless diagnostics.

Validation:
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_sdk_phase2.py' -v`: 22 tests passed.

Score impact: Security/reliability should rise modestly. This reduces an identified logging weakness, but redaction remains pattern-based and should still be documented as best-effort.

### Pass 18: Production Developer Documentation

Issue: The standalone README had install, sync, async, reliability, and safety basics, but lacked enough guidance for a first production integration.

Root cause: Documentation had been expanded around smoke examples rather than around the complete external developer journey.

Developer-experience implications:
- Developers needed clearer expectations for token issuance/storage, constructor options, method semantics, error handling, retries, cache invalidation, thread-safety, and troubleshooting.
- The prior score matrix explicitly capped documentation completeness at `7.0`.

Fix:
- Added token lifecycle and secret-storage guidance.
- Added a concise API reference for constructors, token providers, retry options, cache options, and public methods.
- Added error-handling guidance for `ToolDeniedError` and `ToolGatewayError`.
- Added cache TTL/invalidation and thread-safety guidance.
- Added troubleshooting entries for HTTPS validation, missing tokens, gateway denial, invalid gateway responses, and transport failures.
- Added matching product-platform README notes that point internal users to the standalone SDK README.

Impact: The SDK is easier to adopt without reading tests or source code, and the remaining cache/thread-safety caveat is explicit rather than hidden.

Validation:
- Documentation changes were covered by broader SDK/package build and full product-platform validation below.

Score impact: Developer experience should rise. The README is still not a generated full API reference, but it now covers the production integration questions called out by the prior matrix.

### Pass 19: Repeatable Release Validation Tooling

Issue: Wheel and sdist checks were recorded in this log, but there was no package-local command to repeat those checks consistently in CI or before publishing.

Root cause: Release validation had been performed manually during remediation rather than encoded as a maintained workflow.

Supply-chain and release implications:
- The standalone package uses a symlinked source path in the monorepo, so artifact content checks are especially important.
- Without a repeatable release command, future source-layout or packaging changes could silently produce incomplete artifacts.
- Dependency audit and metadata checks should be explicit release gates rather than reviewer memory.

Fix:
- Added `packages/ophanix-tool-gateway-sdk/scripts/validate_release.py`.
- The script builds both wheel and sdist, verifies that each artifact contains `ophanix_tool_gateway/__init__.py`, `ophanix_tool_gateway/sdk.py`, and `ophanix_tool_gateway/py.typed`, and runs `twine check`.
- Added `release` optional dependencies for `build` and `twine`.
- Added `security` optional dependencies for `pip-audit`.
- Added an optional `--require-dependency-audit` mode.
- Documented release validation commands in the standalone README.

Impact: Packaging and release readiness are now operationalized. The symlinked package boundary remains a known design tradeoff, but artifact correctness can be enforced before publishing.

Validation:
- In a disposable virtual environment: `python -m pip install '.[release]'` then `python scripts/validate_release.py --out-dir /tmp/ophanix-sdk-release-artifacts`: wheel built, sdist built, artifact contents verified, and `twine check` passed.
- In the same disposable virtual environment after installing `.[security]`: `python scripts/validate_release.py --out-dir /tmp/ophanix-sdk-release-artifacts-audit --require-dependency-audit`: wheel built, sdist built, `twine check` passed, and `pip-audit` completed. `pip-audit` skipped the unpublished local `ophanix-tool-gateway-sdk` package because it is not on PyPI; no dependency vulnerability findings were printed.

Score impact: Packaging and supply-chain scores should rise, but not to a 9 until CI requires this script, release provenance/signing is defined, and dependency audit output is archived as a build artifact.

### Pass 20: Shared Client Configuration Validation

Issue: The sync and async clients duplicated constructor validation for base URLs, timeout values, retry configuration, boolean flags, and user-agent validation.

Root cause: The async client was intentionally mirrored from the sync client to preserve behavior, but the constructor validation remained copy-pasted.

Architecture and maintainability implications:
- Duplicate security-sensitive setup logic can drift over time.
- Future changes to retry, timeout, cache, or transport defaults should not require two parallel edits.
- The prior matrix scored internal architecture at `7.0` primarily because of single-file structure and sync/async duplication.

Fix:
- Added `_ClientConfig` and `_client_config()`.
- Both sync and async clients now use the same validation path for base URL policy, timeout, cache flag, insecure-HTTP flag, user-agent, retry count, retry backoff, max sleep, and jitter.
- Kept sync/async request execution separate because HTTPX exposes separate sync and async client APIs.

Impact: Configuration validation is now centralized, reducing drift risk while keeping the public API unchanged.

Validation:
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_sdk_phase1.py' -v`: 23 constructor/export tests passed.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_sdk*.py' -v`: 76 SDK/package/remediation tests passed.

Score impact: Implementation quality should rise modestly. The SDK is still mostly one file and still has mirrored request execution paths, so this is a maintainability improvement rather than a complete architecture cleanup.

## Updated Scoring After Pass 20

These scores are for the SDK and standalone package path, not the broader product-platform gateway server.

| Dimension | Prior strict score | Updated strict score | Direction | Rationale |
| --- | ---: | ---: | --- | --- |
| Implementation quality | `7.8` | `8.1` | Raised | Shared config validation reduces drift, release tooling is codified, tests increased to 76 SDK/package/remediation tests. Remaining cap: mostly single-file SDK and mirrored sync/async request execution. |
| Ease of use | `8.0` | `8.3` | Raised | README now covers token lifecycle, API reference, errors, cache behavior, thread-safety, troubleshooting, and release validation. Remaining cap: no generated API reference or richer examples. |
| Security/reliability | `8.1` | `8.3` | Raised | Broader secret redaction, explicit cache/thread-safety docs, repeatable artifact checks, optional dependency audit path. Remaining cap: pattern-based redaction, no mutation idempotency, no provenance/signing, CI enforcement not shown in this pass. |

The earlier `6-7` objections are less compelling after this pass, but still not entirely wrong if a reviewer weights CI/provenance, thread-safety guarantees, or architectural decomposition heavily. A rounded `8/10` remains the most defensible overall production-candidate rating.

### Remaining Accepted Risks

- Automatic retries for `call_tool()` remain intentionally absent until the server exposes an idempotency-key contract.
- The standalone package path still uses a symlink into product-platform source. Artifact validation now guards this, but CI must run it before every release.
- The SDK is still mostly single-file. Configuration drift risk is lower, but future growth should split models, errors, retry helpers, redaction, and transport layers.
- Error redaction is broader but remains best-effort.
- Cache structures are mutable and process-local. The README now documents that clients are not guaranteed thread-safe.
- Release provenance/signing and CI artifact retention are still outside this code change.

## Final Validation After Pass 20

- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_sdk_phase2.py' -v`: 22 tests passed after redaction hardening.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_sdk_phase1.py' -v`: 23 tests passed after shared config validation.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_sdk*.py' -v`: 76 SDK/package/remediation tests passed.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_*.py' -v`: 199 Tool Gateway tests passed.
- `PYTHONPATH=src python3 -m unittest discover -s tests -v`: 695 product-platform tests passed.
- `python3 -m compileall -q packages/product-platform/src/ophanix_tool_gateway packages/product-platform/src/product_platform/tool_gateway packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway packages/ophanix-tool-gateway-sdk/scripts`: passed.
- `python3 scripts/validate_release.py --out-dir /tmp/ophanix-sdk-release-artifacts` from a disposable venv with `.[release]`: wheel and sdist built, expected files verified, `twine check` passed.
- `python3 scripts/validate_release.py --out-dir /tmp/ophanix-sdk-release-artifacts-audit --require-dependency-audit` from a disposable venv with `.[release]` and `.[security]`: release validation passed and `pip-audit` completed, skipping only the unpublished local SDK package.
- `git diff --check`: no whitespace errors.
- `git diff --cached --check`: no whitespace errors.

## Pass 21: Exhaustive Production-Readiness Remediation

Date: 2026-05-11

Pass name: `SDK-AUDIT-001` through `SDK-AUDIT-058` remediation execution.

Starting repository state summary:

- The worktree started dirty with existing modified product-platform source,
  README, tests, package metadata, and local database files.
- No changes were staged at pass start.
- The prior review log, production-readiness audit log, standalone SDK package,
  preferred SDK namespace, SDK remediation tests, `py.typed`, and a database
  backup were untracked at pass start.
- This pass builds on the current worktree and does not revert prior user or
  generated work.

Initial remediation tracking table before code/config edits:

| Issue ID | Title | Severity | Category | Current status | Planned action | Files likely affected | Validation required | Score impact |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SDK-AUDIT-001 | Untracked SDK package and namespace | Critical | Repository / release | Pending | Stage/track intended SDK artifacts and document clean-release requirement | SDK package, SDK namespace, tests, logs | `git status`, package build | High |
| SDK-AUDIT-002 | Prior review log is untracked | Medium | Governance | Pending | Track remediation/audit logs | `docs/product-platform-worktree/...` | `git status` | Medium |
| SDK-AUDIT-003 | CI path filters exclude product-platform and SDK | Critical | CI / release | Pending | Add product-platform and SDK to CI filters/matrices and validation | `.github/workflows/ci.yml` | workflow static checks | High |
| SDK-AUDIT-004 | Publish workflow cannot publish SDK | Critical | Packaging / release | Pending | Add SDK/product-platform release options and build matrix entries | `.github/workflows/publish.yml` | workflow static checks | High |
| SDK-AUDIT-005 | Product-platform sdist includes DB files | Critical | Packaging / data | Pending | Remove DB files from package artifacts and VCS tracking; add denylist validation | `pyproject.toml`, `.gitignore`, DB files, tests | build artifacts, denylist test | High |
| SDK-AUDIT-006 | Standalone SDK source is symlinked | High | Packaging | Pending | Replace symlink with real package source or enforce robust artifact validation | SDK package source, release validator | package build | High |
| SDK-AUDIT-007 | Release validator is too shallow | Medium | Packaging / release | Pending | Add denylist, license, metadata, install smoke, and strict audit checks | `validate_release.py`, package metadata | release validation | Medium |
| SDK-AUDIT-008 | SDK artifacts omit license file | Medium | Packaging / legal | Pending | Include license in standalone package artifacts | SDK package metadata, license file | artifact listing | Medium |
| SDK-AUDIT-009 | SDK metadata incomplete and alpha | Medium | Packaging / DX | Pending | Complete metadata and maturity classifiers | SDK `pyproject.toml` | metadata/release validation | Medium |
| SDK-AUDIT-010 | Standalone pytest config points at missing tests | Low | Testing / packaging | Pending | Add package-local smoke tests or adjust test config | SDK package tests/config | package-local pytest | Low |
| SDK-AUDIT-011 | Typed SDK has no type-checker gate | Medium | Testing / typing | Pending | Add type-check config and CI entry where practical | `pyproject.toml`, CI, typing tests | typecheck | Medium |
| SDK-AUDIT-012 | No installed-wheel running-gateway contract test | High | Testing / integration | Pending | Add package/install smoke and document/defer true running-gateway CI if too large | tests, release validator, CI | package tests/build | High |
| SDK-AUDIT-013 | Dependency audit optional and skips local package | Medium | Security / release | Pending | Make audit stricter in release validation/CI and document local-package skip | release validator, CI | release validation | Medium |
| SDK-AUDIT-014 | Source-tree SDK version reports 0.0.0 | Low | DX / diagnostics | Pending | Add source/package metadata fallback | SDK source, tests | SDK tests | Low |
| SDK-AUDIT-015 | Injected HTTP client type is not validated | Medium | API / runtime | Pending | Add runtime protocol/type checks for sync/async clients | SDK source, tests | SDK tests | Medium |
| SDK-AUDIT-016 | StaticTokenProvider does not validate token type | Low | API / DX | Pending | Validate static token with shared text validation | SDK source, tests | SDK tests | Low |
| SDK-AUDIT-017 | Redaction leaks colon-bearing bearer token suffixes | High | Security | Pending | Harden text redaction patterns and regression tests | SDK source, tests | SDK tests | High |
| SDK-AUDIT-018 | Malformed discovery description silently coerced | Medium | Runtime contract | Pending | Reject non-string descriptions | SDK source, tests | SDK tests | Medium |
| SDK-AUDIT-019 | reason_code not type-validated | Low | Runtime contract | Pending | Validate optional response string fields | SDK source, tests | SDK tests | Low |
| SDK-AUDIT-020 | Frozen SDK result raw dicts are mutable | Low | API design | Pending | Return immutable raw mappings or document accepted risk | SDK source, tests/docs | SDK tests | Low |
| SDK-AUDIT-021 | Error sanitizer lacks recursion depth cap | Medium | Reliability / security | Pending | Add depth/node budget to sanitizer | SDK source, tests | SDK tests | Medium |
| SDK-AUDIT-022 | Non-JSON response reads full text | Medium | Reliability / security | Pending | Bound diagnostic response body excerpt | SDK source, tests | SDK tests | Medium |
| SDK-AUDIT-023 | SDK has no payload size cap | Medium | Reliability | Pending | Add configurable max payload bytes | SDK source, docs, tests | SDK tests | Medium |
| SDK-AUDIT-024 | Tool invocation lacks idempotency contract | Medium | Reliability / API | Pending | Defer full contract with rationale; document required future server design | docs/log | docs review | Medium |
| SDK-AUDIT-025 | Discovery cache lacks TTL/synchronization | Medium | Reliability / DX | Pending | Add TTL and lock or document accepted scope | SDK source, docs, tests | SDK tests | Medium |
| SDK-AUDIT-026 | `list_tools(status=...)` is misleading | Low | API / DX | Pending | Remove/deprecate parameter or document active-only behavior | SDK source/docs/tests | SDK tests | Low |
| SDK-AUDIT-027 | Auth failures lack typed SDK error | Medium | API / DX | Pending | Add typed auth error mapping for 401/reason codes | SDK/server source, tests | SDK/gateway tests | Medium |
| SDK-AUDIT-028 | SDK lacks telemetry hooks | Low | Operability | Pending | Add optional event hook or defer with rationale | SDK source/docs/tests | SDK tests | Low |
| SDK-AUDIT-029 | Gateway auth bypass pattern too broad | High | Security / routing | Pending | Replace broad bypass with explicit route allowlist and tests | `api/app.py`, tests | gateway tests | High |
| SDK-AUDIT-030 | Invocation validates schema before authz | High | Security | Pending | Evaluate authorization/resource binding before schema validation | `api/app.py`, tests | gateway tests | High |
| SDK-AUDIT-031 | Invocation reveals active tool existence before authz | High | Security | Pending | Normalize missing/unauthorized ordering and tests | `api/app.py`, tests | gateway tests | High |
| SDK-AUDIT-032 | Default executor creates unclosed clients | High | Reliability | Pending | Add managed client lifecycle or close owned clients | app/invocation source, tests | gateway tests | High |
| SDK-AUDIT-033 | Manual health checker creates unclosed clients | Medium | Reliability | Pending | Add managed client lifecycle or close owned clients | app/health source, tests | gateway tests | Medium |
| SDK-AUDIT-034 | Upstream `auth_mode` accepted but unused | High | Runtime / security | Pending | Restrict unsupported modes or implement secret-backed auth | models/invocation/tests/docs | gateway tests | High |
| SDK-AUDIT-035 | Upstream URL validation allows arbitrary HTTP(S) | High | Security / SSRF | Pending | Add SSRF/private-network controls and safe opt-in | models/tests/docs | gateway tests | High |
| SDK-AUDIT-036 | GET/DELETE upstream calls send JSON body | Medium | Runtime correctness | Pending | Add method-specific request construction | invocation/tests/docs | gateway tests | Medium |
| SDK-AUDIT-037 | Failed upstream responses bypass policy | Critical | Security / reliability | Pending | Apply response policy to all execution statuses | response/app/tests | gateway tests | High |
| SDK-AUDIT-038 | `store_full_response` not honored | High | Privacy / runtime | Pending | Implement storage semantics or remove field from API | response/runtime/docs/tests | gateway tests | High |
| SDK-AUDIT-039 | Redaction regex unvalidated and compiled per response | High | Security / reliability | Pending | Validate/compile patterns on policy write and cache/handle safely | models/response/tests | gateway tests | High |
| SDK-AUDIT-040 | Response key redaction over-redacts by substring | Low | Correctness / DX | Pending | Use normalized exact/suffix matching | response/tests | gateway tests | Low |
| SDK-AUDIT-041 | Runtime summaries lack global caps | Medium | Reliability / data | Pending | Add depth/item/byte caps to summaries | decision/runtime tests | gateway tests | Medium |
| SDK-AUDIT-042 | No Tool Gateway rate limiting | High | Reliability / security | Pending | Add lightweight in-process limiter or document edge dependency | app/tests/docs | gateway tests | High |
| SDK-AUDIT-043 | No gateway request body size limit | High | Reliability / security | Pending | Add content-length/body-size guard | app/tests/docs | gateway tests | High |
| SDK-AUDIT-044 | CORS broad with credentials | Medium | Security config | Pending | Add stricter production validation/docs | app/settings/tests/docs | tests/docs | Medium |
| SDK-AUDIT-045 | Token hashing lacks entropy documentation/enforcement | Medium | Security | Pending | Document/enforce entropy where token issuance is controlled | auth/credentials/docs/tests | tests/docs | Medium |
| SDK-AUDIT-046 | Schema validation messages can expose values | Medium | Security / data exposure | Pending | Sanitize agent-facing validation errors | schemas/app/tests | gateway tests | Medium |
| SDK-AUDIT-047 | JSON Schema validators instantiated per validation | Low | Performance | Pending | Cache validators by schema | schemas/tests | gateway tests | Low |
| SDK-AUDIT-048 | Direct HTTP example less safe than SDK | Low | Docs/examples | Pending | Harden example or add explicit SDK preference warnings | examples/tests/docs | example tests | Low |
| SDK-AUDIT-049 | Token issuance/setup underdocumented | Medium | Docs / DX | Pending | Add credential issuance/setup guide | README/docs | docs review | Medium |
| SDK-AUDIT-050 | Install docs assume public package availability | Medium | Docs / release | Pending | Document package index/publication status | SDK README | docs review | Medium |
| SDK-AUDIT-051 | No SDK changelog/migration/security policy | Medium | Docs / governance | Pending | Add package-local governance docs | SDK package docs | docs review | Medium |
| SDK-AUDIT-052 | Source files lack license headers | Low | Compliance | Pending | Add standard headers or document exemption | SDK source/scripts | compile/tests | Low |
| SDK-AUDIT-053 | Product-platform lacks sdist include/exclude policy | Medium | Packaging | Pending | Add explicit sdist include/exclude | product pyproject | product build | Medium |
| SDK-AUDIT-054 | Broad dependency ranges not locked for release | Medium | Supply chain | Pending | Add constraints guidance/CI min-latest strategy or defer lock policy | package metadata/docs/CI | docs/CI checks | Medium |
| SDK-AUDIT-055 | Tests miss proven negative cases | High | Testing | Pending | Add regression tests for proven gaps | tests | focused tests | High |
| SDK-AUDIT-056 | Server tests miss failed-response policy bypass | High | Testing / security | Pending | Add failed-response policy tests | response tests | gateway tests | High |
| SDK-AUDIT-057 | No production adoption checklist | Medium | Docs / adoption | Pending | Add production adoption checklist | SDK README/docs | docs review | Medium |
| SDK-AUDIT-058 | Local validation not equivalent to release validation | High | Process / release | Pending | Move critical checks into CI/release and document remaining local-only items | CI, release validator, log | workflow/static validation | High |

## Pass 21 Completion: Exhaustive SDK Remediation Execution

Date: 2026-05-11

Pass name: `SDK-AUDIT-001` through `SDK-AUDIT-058` production-readiness remediation completion.

### Starting Repository State Summary

At the start of this execution pass, `git status --short` showed staged removal
of `packages/product-platform/ophanix_product.db`, tracked modifications across
the gateway SDK/server/docs/test surface, and untracked SDK package, SDK
namespace, package smoke tests, and audit/remediation logs. The untracked SDK and
log artifacts were treated as release blockers because they could not be
reviewed, packaged, or protected by CI until explicitly added to the worktree
index.

### Final Repository State Summary

The standalone SDK package, duplicated import namespace, package-local tests, and
audit/remediation logs are now staged for tracking. The local SQLite database is
staged for removal from version control, and package artifact builds prove it is
excluded from both wheel and sdist outputs. No symlinks remain in either SDK
source package. The worktree still has unstaged tracked modifications from this
remediation pass and must be committed before merge or release.

### Full Issue Tracking And Remediation Table

| Issue | Original severity | Original category | Final status | Files changed or affected | Root cause | Fix implemented and production-grade rationale | Tests and validation | Remaining risk | Score impact |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SDK-AUDIT-001: Untracked SDK package and namespace | Critical | Repository / release | Fixed | `packages/ophanix-tool-gateway-sdk`, `packages/product-platform/src/ophanix_tool_gateway`, SDK tests, audit logs | Package-critical files existed outside version control visibility. | Staged SDK package, package namespace, SDK smoke tests, and audit logs so they are visible to review and release automation. Release validator and package builds now operate on the intended package. | `git status --short` shows staged additions instead of `??`; SDK release validator passed; product build artifact denylist passed. | Final commit still required before release. | Removes a critical release/publishing cap. |
| SDK-AUDIT-002: Prior review log is untracked | Medium | Governance | Fixed | `docs/product-platform-worktree/execution-logs/06-tool-gateway-logs/13-sdk-review-remediation.md`, `14-sdk-production-readiness-audit.md` | Review evidence was not tracked, making conclusions unverifiable in branch review. | Staged review and remediation logs and appended this completion section with issue-level disposition and validation evidence. | `git status --short` shows staged log additions; this file contains all 58 issue IDs. | Final commit still required. | Improves governance and auditability. |
| SDK-AUDIT-003: CI path filters exclude product-platform and SDK | Critical | CI / release | Fixed | `.github/workflows/ci.yml` | CI filters and matrices did not cover the package under review. | Added product-platform and standalone SDK paths/matrix coverage, SDK type checking, SDK release validation, and release-audit execution. Critical validation is no longer local-only. | Workflow static review; SDK release validator passed locally; product test suite passed locally. | Workflow must still run in GitHub after commit. | Removes a CI protection cap. |
| SDK-AUDIT-004: Publish workflow cannot publish SDK | Critical | Packaging / release | Fixed | `.github/workflows/publish.yml` | Publish workflow did not include SDK release artifacts. | Added SDK/product-platform publish coverage and SDK release validation with dependency audit before publish. | Workflow static review; SDK release validator passed locally. | Workflow must still run in GitHub after commit. | Removes a publishing blocker. |
| SDK-AUDIT-005: Product-platform sdist includes DB files | Critical | Packaging / data | Fixed | `.gitignore`, `packages/product-platform/pyproject.toml`, `packages/product-platform/ophanix_product.db` | Local SQLite database was tracked and packaging lacked explicit artifact exclusion. | Staged DB removal, added DB ignore patterns, added explicit product-platform wheel/sdist include/exclude policy, and verified artifacts contain no DB/sqlite/pycache files. | Product-platform build from `packages/product-platform` passed: wheel 248 files, sdist 445 files, forbidden `[]`. | Final commit required to remove DB from repository history/current branch. | Removes a critical data/package leakage cap. |
| SDK-AUDIT-006: Standalone SDK source is symlinked | High | Packaging | Fixed | `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway` | Standalone package pointed at source by symlink, risking broken artifacts and invisible drift. | Replaced symlink with real package files copied from the reviewed SDK namespace; release validator builds wheel/sdist from real files. | `find ... -type l` returned no SDK symlinks; SDK release validator passed. | Mirrored source still requires drift discipline until a shared generation/copy check is added. | Removes high packaging fragility. |
| SDK-AUDIT-007: Release validator is too shallow | Medium | Packaging / release | Fixed | `packages/ophanix-tool-gateway-sdk/scripts/validate_release.py`, SDK `pyproject.toml` | Validator only proved minimal build success and missed artifact contents/install/security gates. | Added forbidden artifact checks, SPDX/license checks, wheel and sdist inspection, metadata/license validation, installed-wheel smoke import, and optional required runtime dependency audit. | `validate_release.py --require-dependency-audit` passed. | Local package itself is skipped by pip-audit until public/package-index visibility. | Raises release confidence. |
| SDK-AUDIT-008: SDK artifacts omit license file | Medium | Packaging / legal | Fixed | `packages/ophanix-tool-gateway-sdk/LICENSE`, SDK `pyproject.toml` | Package metadata did not guarantee license inclusion. | Added package-local license and license-files metadata; validator checks artifacts. | SDK release validator passed twine and artifact checks. | None identified. | Removes legal/package completeness risk. |
| SDK-AUDIT-009: SDK metadata incomplete and alpha | Medium | Packaging / DX | Fixed | SDK `pyproject.toml`, `README.md`, `CHANGELOG.md`, `SECURITY.md` | Metadata lacked maturity, maintainers, project URLs, and governance docs. | Added authors/maintainers, Beta classifier, Python 3.13 classifier, URLs, changelog, and security policy. | SDK release validator/twine check passed. | Public support policy should evolve with first external release. | Improves install trust and DX. |
| SDK-AUDIT-010: Standalone pytest config points at missing tests | Low | Testing / packaging | Fixed | `packages/ophanix-tool-gateway-sdk/tests/test_package_smoke.py` | Standalone package had test config without package-local tests. | Added a package-local public export smoke test. | `PYTHONPATH=src python3 -m unittest discover -s tests -v` passed, 1 test. | Smoke is intentionally narrow; deeper behavior remains in product-platform tests. | Removes package-local test confusion. |
| SDK-AUDIT-011: Typed SDK has no type-checker gate | Medium | Testing / typing | Fixed | SDK `pyproject.toml`, `.github/workflows/ci.yml`, SDK source | Typed package exported `py.typed` but no strict checker gate protected it. | Added strict mypy config/dev extra and CI type-check step; fixed annotations/casts until strict mypy passed. | `/tmp/ophanix-sdk-remediation-venv/bin/python -m mypy src/ophanix_tool_gateway` passed. | CI must run after commit. | Raises implementation quality and consumer type trust. |
| SDK-AUDIT-012: No installed-wheel running-gateway contract test | High | Testing / integration | Deferred with rationale | SDK release validator, package tests, CI docs | A true installed-wheel-to-running-gateway test needs a durable CI harness that starts product-platform with seeded credentials and installs the built SDK wheel. | Added installed-wheel smoke validation and extensive source-level SDK/gateway contract tests, but deferred the live installed-wheel gateway e2e to a dedicated CI harness to avoid a brittle partial test. | SDK release validator passed installed-wheel import smoke; product-platform full suite passed 726 tests. | Still no proof that a built wheel can call a live gateway process in CI. | Caps implementation quality below 8. |
| SDK-AUDIT-013: Dependency audit optional and skips local package | Medium | Security / release | Accepted remaining risk | SDK release validator, `.github/workflows/ci.yml`, `.github/workflows/publish.yml` | Runtime dependency audit was optional and pip-audit cannot audit an unpublished local project as a PyPI advisory subject. | Made runtime dependency audit required in release/CI validation and installed the built wheel into a temp target before auditing. Accepted the unavoidable local-package skip until the package is published or internal advisory tooling exists. | SDK release validator passed with `ophanix-tool-gateway-sdk` skipped as not found on PyPI and no dependency vulnerability failure. | Local package advisory matching remains unavailable before publication. | Still mildly caps supply-chain score. |
| SDK-AUDIT-014: Source-tree SDK version reports 0.0.0 | Low | DX / diagnostics | Fixed | SDK source and tests | Version lookup only used installed metadata. | Added source-tree pyproject fallback so diagnostics report package version during local development. | SDK phase tests passed; source import smoke printed `0.1.0`. | None identified. | Improves diagnostics. |
| SDK-AUDIT-015: Injected HTTP client type is not validated | Medium | API / runtime | Fixed | SDK source and tests | Constructors accepted incompatible sync/async clients and failed later. | Added constructor-time validation for required sync/async client methods and clearer errors. | SDK phase tests passed. | Structural validation cannot prove every third-party client semantic. | Improves runtime safety and DX. |
| SDK-AUDIT-016: StaticTokenProvider does not validate token type | Low | API / DX | Fixed | SDK source and tests | Static provider returned whatever it was constructed with. | Added token type and blank-string validation through shared token checks. | SDK phase tests passed. | None identified. | Improves early error quality. |
| SDK-AUDIT-017: Redaction leaks colon-bearing bearer token suffixes | High | Security | Fixed | SDK source and tests | Bearer-token regex stopped too early for colon-bearing tokens. | Hardened authorization/token redaction patterns and added regression tests for colon-bearing bearer material. | SDK phase tests passed. | Pattern-based redaction is best-effort for unknown secret formats. | Removes proven token-leak bug. |
| SDK-AUDIT-018: Malformed discovery description silently coerced | Medium | Runtime contract | Fixed | SDK source and tests | Parser coerced non-string fields, hiding malformed gateway responses. | Added strict type validation for optional discovery strings. | SDK phase tests passed. | None identified. | Improves contract correctness. |
| SDK-AUDIT-019: reason_code not type-validated | Low | Runtime contract | Fixed | SDK source and tests | Optional error fields were accepted without type checks. | Added string validation for optional response fields including `reason_code`. | SDK phase tests passed. | None identified. | Improves typed error reliability. |
| SDK-AUDIT-020: Frozen SDK result raw dicts are mutable | Low | API design | Fixed | SDK source and tests | Frozen dataclasses still exposed mutable nested raw mappings. | Wrapped raw mappings in immutable mapping proxies. | SDK phase tests passed. | Nested non-mapping values are not deep-frozen beyond sanitizer behavior. | Improves API immutability. |
| SDK-AUDIT-021: Error sanitizer lacks recursion depth cap | Medium | Reliability / security | Fixed | SDK source and tests | Recursive sanitizer could traverse arbitrarily deep malformed responses. | Added bounded sanitizer depth and diagnostic truncation. | SDK phase tests passed. | None identified. | Removes malformed-response reliability risk. |
| SDK-AUDIT-022: Non-JSON response reads full text | Medium | Reliability / security | Fixed | SDK source and tests | Error diagnostics could include unbounded non-JSON response text. | Added bounded non-JSON error excerpts. | SDK phase tests passed. | Underlying HTTP client still buffers the response it receives. | Reduces memory and data-exposure risk. |
| SDK-AUDIT-023: SDK has no payload size cap | Medium | Reliability | Fixed | SDK source, README files, tests | SDK validated JSON shape but not serialized payload size. | Added configurable `max_payload_bytes` defaulting to 1,000,000 bytes and documented it. | SDK phase tests passed. | Consumers may need lower limits for specific deployments. | Improves client-side reliability. |
| SDK-AUDIT-024: Tool invocation lacks idempotency contract | Medium | Reliability / API | Deferred with rationale | SDK README, product-platform README, remediation log | Safe invocation retries need a server/API idempotency-key contract and per-tool idempotency semantics. | Documented that invocation retries are intentionally not automatic without idempotency metadata. Deferred full contract to API design because a client-only retry would risk duplicate side effects. | Docs reviewed; SDK release validation passed. | Duplicate side effects remain possible if consumers retry non-idempotent calls externally. | Caps security/reliability below 8. |
| SDK-AUDIT-025: Discovery cache lacks TTL/synchronization | Medium | Reliability / DX | Fixed | SDK source, README files, tests | Cache entries could live indefinitely and were not protected for shared clients. | Added credential-partitioned cache TTL and lock-protected cache access. | SDK phase tests passed. | Cache remains process-local by design. | Improves correctness for rotation and multi-threaded use. |
| SDK-AUDIT-026: `list_tools(status=...)` is misleading | Low | API / DX | Fixed | SDK source and tests | API appeared to accept arbitrary statuses while gateway only exposed active listings. | Restricted the parameter to `Literal["active"] | None` and rejected other values. | SDK phase tests passed. | Future gateway statuses will need intentional API expansion. | Improves API clarity. |
| SDK-AUDIT-027: Auth failures lack typed SDK error | Medium | API / DX | Fixed | SDK source, exports, README files, tests | 401 responses were generic gateway errors. | Added `ToolAuthenticationError`, exported it from public namespaces, and documented handling. | SDK phase tests and package smoke passed. | None identified. | Improves integration ergonomics. |
| SDK-AUDIT-028: SDK lacks telemetry hooks | Low | Operability | Fixed | SDK source, README files, tests | Consumers had no safe callback for operation-level observability. | Added optional immutable, token-free event hook events for start, success, denial, and error; hook failures are swallowed. | SDK phase tests passed. | Hooks are local callbacks, not full metrics/tracing integration. | Improves operability without leaking secrets. |
| SDK-AUDIT-029: Gateway auth bypass pattern too broad | High | Security / routing | Fixed | `api/app.py`, auth tests | Middleware bypass matched broad gateway prefixes. | Replaced broad prefix bypass with exact runtime route allowlist. | Gateway auth phase tests and full product suite passed. | Future routes must be added deliberately. | Removes auth-bypass risk. |
| SDK-AUDIT-030: Invocation validates schema before authz | High | Security | Fixed | `api/app.py`, invocation tests | Request schema validation ran before policy authorization. | Moved policy decision before tool lookup/schema validation for runtime invocation. | Invocation phase tests and full product suite passed. | None identified. | Removes data oracle and wasted work risk. |
| SDK-AUDIT-031: Invocation reveals active tool existence before authz | High | Security | Fixed | `api/app.py`, invocation tests | Missing-tool and unauthorized paths were distinguishable before policy evaluation. | Normalized ordering so policy decision runs first and missing/unauthorized behavior no longer reveals schema/tool state before authorization. | Invocation phase tests and full product suite passed. | Authorized callers still receive actionable missing-tool errors where appropriate. | Removes enumeration risk. |
| SDK-AUDIT-032: Default executor creates unclosed clients | High | Reliability | Fixed | `api/app.py`, `invocation.py` | Executor created HTTP clients without an owned lifecycle. | Added owned-client tracking and application shutdown cleanup. | Full product suite passed; no new resource warnings tied to gateway client ownership. | Deployment lifecycle still depends on ASGI shutdown running. | Removes high resource leak risk. |
| SDK-AUDIT-033: Manual health checker creates unclosed clients | Medium | Reliability | Fixed | `health.py` | Health checker owned clients without close support. | Added owned-client close support. | Full product suite passed. | Same ASGI/process lifecycle caveat as other owned clients. | Improves reliability. |
| SDK-AUDIT-034: Upstream `auth_mode` accepted but unused | High | Runtime / security | Fixed | `models.py`, `invocation.py`, README files, upstream tests | API accepted modes that runtime did not implement, creating false security expectations. | Restricted supported upstream auth modes to `none` and made runtime fail closed for persisted unsupported modes until secret-backed auth exists. | Upstream tests and full product suite passed. | Real upstream credential injection remains a future feature. | Removes misleading unsafe auth behavior. |
| SDK-AUDIT-035: Upstream URL validation allows arbitrary HTTP(S) | High | Security / SSRF | Fixed | `models.py`, README files, upstream tests | Target URLs allowed credentials, fragments, private IP ranges, metadata hosts, and non-local plain HTTP. | Added URL trust-boundary validation for host, scheme, userinfo, query/fragment, private/metadata addresses, and HTTP locality. | Upstream tests and full product suite passed. | DNS rebinding and network egress policy should also be handled at infrastructure level. | Reduces SSRF exposure substantially. |
| SDK-AUDIT-036: GET/DELETE upstream calls send JSON body | Medium | Runtime correctness | Fixed | `invocation.py`, forwarding tests | Executor used JSON body semantics for all methods. | Changed GET/DELETE forwarding to query params and kept body methods as JSON. | Forwarding tests and full product suite passed. | Complex payloads in GET query strings remain constrained by URL limits. | Fixes protocol correctness. |
| SDK-AUDIT-037: Failed upstream responses bypass policy | Critical | Security / reliability | Fixed | `response.py`, `api/app.py`, response tests | Response policy was only applied to success paths. | Applied response policy to failed and succeeded upstream responses while keeping output-schema validation success-only. | Response phase tests and full product suite passed. | None identified. | Removes critical policy-bypass cap. |
| SDK-AUDIT-038: `store_full_response` not honored | High | Privacy / runtime | Fixed | `api/app.py`, `response.py`, response tests | Runtime summaries ignored configured response storage policy. | Enforced `store_full_response`; summaries omit body when false and store redacted body only when true. | Response phase tests and full product suite passed. | Existing previously stored records are not rewritten. | Removes privacy/retention mismatch. |
| SDK-AUDIT-039: Redaction regex unvalidated and compiled per response | High | Security / reliability | Fixed | `models.py`, `response.py`, response tests | Invalid or pathological regex could fail at response time and patterns were repeatedly compiled. | Validated redaction rules on policy write and compiled/cached normalized rules for response processing. | Response tests and full product suite passed. | Regexes can still be expensive if accepted by Python but are bounded by policy validation and response caps. | Removes high runtime failure risk. |
| SDK-AUDIT-040: Response key redaction over-redacts by substring | Low | Correctness / DX | Fixed | `response.py`, response tests | Key matching used broad substring semantics. | Switched to normalized exact/suffix matching. | Response tests and full product suite passed. | Users may need to add explicit keys for custom nested names. | Improves redaction precision. |
| SDK-AUDIT-041: Runtime summaries lack global caps | Medium | Reliability / data | Fixed | `decision.py`, runtime tests | Payload summaries could grow with nested input. | Added depth, item, string, and total-character caps to summaries. | Decision tests and full product suite passed. | Caps are generic and may need tuning from production telemetry. | Reduces storage/logging risk. |
| SDK-AUDIT-042: No Tool Gateway rate limiting | High | Reliability / security | Fixed | `api/app.py`, `settings.py`, README files, auth tests | Runtime endpoints had no application-level request-rate guard. | Added lightweight in-process rate limiter keyed by credential fingerprint or client host, configurable by environment. | Auth phase tests and full product suite passed. | In-process limits are not a distributed edge-rate-limit replacement. | Improves abuse resistance but not enough for score 9. |
| SDK-AUDIT-043: No gateway request body size limit | High | Reliability / security | Fixed | `api/app.py`, `settings.py`, README files, auth tests | Invocation request bodies were not capped at the gateway boundary. | Added content-length validation and receive-time body byte limiting with 400/413 responses. | Auth phase tests and full product suite passed. | Upstream ASGI/server limits should also be configured. | Removes high memory exhaustion risk. |
| SDK-AUDIT-044: CORS broad with credentials | Medium | Security config | Fixed | `api/app.py`, auth tests, README files | Production could allow wildcard origins with credentials. | Added production guard rejecting wildcard credentialed CORS outside dev/test/local and narrowed methods/headers. | Auth phase tests and full product suite passed. | Operators must configure explicit origins in production. | Improves secure defaults. |
| SDK-AUDIT-045: Token hashing lacks entropy documentation/enforcement | Medium | Security | Fixed | README files, credential/auth context | Stable SHA-256 lookup is safe only for high-entropy bearer tokens, but docs did not state that clearly. | Documented high-entropy token requirement, local-only fixture tokens, HTTPS expectation, and Product Platform/AgentMesh credential issuance path. Existing issuer produces random credential material; low-level fixture APIs remain for tests. | Docs reviewed; full product suite passed. | Low-level repository fixture helpers can still insert weak local tokens and must not be used for production issuance. | Reduces security ambiguity; no remaining score cap by itself. |
| SDK-AUDIT-046: Schema validation messages can expose values | Medium | Security / data exposure | Fixed | `api/app.py`, schema/invocation tests | Agent-facing schema errors could include raw instance details. | Replaced exposed validation detail with generic schema failure messages at gateway boundary. | Invocation tests and full product suite passed. | Server-side internal diagnostics may still need structured private logging later. | Removes data exposure risk. |
| SDK-AUDIT-047: JSON Schema validators instantiated on every validation | Low | Performance | Fixed | `schemas.py`, tests | Validators were rebuilt per validation. | Added canonical-schema validator cache. | Full product suite passed. | Cache has no explicit size bound; schema set is expected to be operator-controlled. | Improves runtime efficiency. |
| SDK-AUDIT-048: Direct HTTP example is less safe than SDK | Low | Docs/examples | Fixed | `direct_http_examples.py`, direct HTTP tests, README files | Example encouraged raw HTTP without the SDK safeguards. | Hardened direct HTTP helpers/tests and documented direct HTTP as local/demo-only, with SDK preferred for production. | Direct HTTP tests and full product suite passed. | Raw HTTP remains possible for advanced users. | Improves adoption safety. |
| SDK-AUDIT-049: Token issuance/setup underdocumented | Medium | Docs / DX | Fixed | Product README, SDK README | Consumers lacked a clear credential setup model. | Added token issuance, secret storage, rotation/401 handling, and local fixture warnings. | Docs reviewed; SDK release validator passed. | Full external onboarding guide can still be expanded. | Raises ease-of-use score. |
| SDK-AUDIT-050: Install docs assume public package availability | Medium | Docs / release | Fixed | SDK README | README assumed package availability without describing source install/current status. | Documented source-install/publication status and release validation path. | Docs reviewed; SDK package smoke passed. | Actual public package publication remains outside this pass. | Removes install-path confusion. |
| SDK-AUDIT-051: No SDK changelog/migration/security policy | Medium | Docs / governance | Fixed | SDK `CHANGELOG.md`, `SECURITY.md`, README | Package lacked governance docs. | Added changelog and security policy with initial release notes and reporting guidance. | SDK release validator includes docs in artifacts. | Deprecation/migration policy should mature with public releases. | Improves governance. |
| SDK-AUDIT-052: Source files lack license headers | Low | Compliance | Fixed | SDK source files and scripts | Package source did not carry clear license headers. | Added SPDX headers to SDK package files and validator checks. | Compileall and SDK release validator passed. | Non-SDK product files were not made part of this package-header policy. | Improves compliance. |
| SDK-AUDIT-053: Product-platform lacks sdist include/exclude policy | Medium | Packaging | Fixed | `packages/product-platform/pyproject.toml` | Product package relied on implicit artifact selection. | Added explicit wheel/sdist include/exclude rules. | Product-platform package build passed; forbidden artifact list empty. | Policy should be maintained when new generated assets appear. | Raises implementation/release confidence. |
| SDK-AUDIT-054: Broad dependency ranges not locked for release | Medium | Supply chain | Deferred with rationale | SDK release validator, CI, package metadata | Dependency version strategy is an organization/release policy decision and cannot be safely replaced by ad hoc pins in this pass. | Added required runtime dependency audit in release validation and CI. Deferred lock/min-latest matrix or constraints policy to release engineering. | SDK release validator passed dependency audit for runtime deps. | Broad compatible ranges remain; no lockfile/SBOM/min-latest matrix yet. | Caps implementation/security below 9 and contributes to cap below 8. |
| SDK-AUDIT-055: Tests miss proven negative cases | High | Testing | Fixed | SDK/gateway test suites | Known failure modes lacked regression coverage. | Added negative-path tests for auth errors, payload caps, type validation, redaction, unauthorized invalid payloads, body/rate limits, SSRF, unsupported auth modes, response policy, and storage semantics. | SDK phase tests passed 85 tests; tool gateway phase tests passed 223 tests; full product suite passed 726 tests. | True installed-wheel live gateway test remains deferred under SDK-AUDIT-012. | Removes broad test-gap cap. |
| SDK-AUDIT-056: Server tests do not cover failed-response policy bypass | High | Testing / security | Fixed | `test_tool_gateway_response_phase3.py`, response/app code | Critical failed-response policy path had no regression test. | Added failed-response redaction/hiding tests and storage-policy tests. | Response tests and full product suite passed. | None identified. | Removes critical regression gap. |
| SDK-AUDIT-057: No production adoption checklist | Medium | Docs / adoption | Fixed | SDK README, product README | External teams lacked a concise production-readiness checklist. | Added production adoption checklist covering tokens, HTTPS, limits, caches, telemetry, release validation, and gateway config. | Docs reviewed; package validator included README in artifacts. | Checklist should be revisited after public package release. | Raises ease-of-use/adoption score. |
| SDK-AUDIT-058: Local validation is not equivalent to release validation | High | Process / release | Fixed | `.github/workflows/ci.yml`, `.github/workflows/publish.yml`, SDK release validator | Critical checks only existed locally or in notes. | Moved SDK typecheck, release validator, dependency audit, and package build checks into CI/publish workflow definitions where practical. | Workflow static review; local release validator, mypy, package builds, and full tests passed. | GitHub Actions must still run after commit. | Removes local-only validation cap. |

### Changed Files Summary

- SDK package: `packages/ophanix-tool-gateway-sdk/{pyproject.toml,README.md,LICENSE,CHANGELOG.md,SECURITY.md,scripts/validate_release.py,src/ophanix_tool_gateway/*,tests/test_package_smoke.py}`.
- Product SDK namespace and exports: `packages/product-platform/src/ophanix_tool_gateway/*`, `packages/product-platform/src/product_platform/tool_gateway/sdk.py`, `packages/product-platform/src/product_platform/tool_gateway/__init__.py`, `packages/product-platform/src/product_platform/py.typed`.
- Gateway runtime/security/reliability: `api/app.py`, `api/settings.py`, `tool_gateway/{auth.py,decision.py,direct_http_examples.py,health.py,invocation.py,models.py,repository.py,response.py,schemas.py}`.
- Packaging/release: `.gitignore`, `.github/workflows/ci.yml`, `.github/workflows/publish.yml`, `packages/product-platform/pyproject.toml`, staged removal of `packages/product-platform/ophanix_product.db`.
- Documentation: `packages/product-platform/README.md`, SDK README/governance docs, this remediation log.
- Tests: SDK phase tests, auth/invocation/forwarding/response/upstream/decision/direct HTTP tests, standalone SDK smoke test.

### Validation Evidence

- `PYTHONPATH=src python3 -m unittest discover -s tests -v` in `packages/product-platform`: passed, 726 tests in 117.100s.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_*phase*.py' -v` in `packages/product-platform`: passed, 223 tests.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_sdk_phase*.py' -v` in `packages/product-platform`: passed, 85 tests.
- `PYTHONPATH=src python3 -m unittest discover -s tests -v` in `packages/ophanix-tool-gateway-sdk`: passed, 1 test.
- `python3 -m compileall -q packages/product-platform/src/ophanix_tool_gateway packages/product-platform/src/product_platform/tool_gateway packages/product-platform/src/product_platform/api packages/ophanix-tool-gateway-sdk/scripts`: passed.
- `/tmp/ophanix-sdk-remediation-venv/bin/python -m mypy src/ophanix_tool_gateway` in `packages/ophanix-tool-gateway-sdk`: passed with no issues.
- `/tmp/ophanix-sdk-remediation-venv/bin/python scripts/validate_release.py --out-dir /tmp/ophanix-sdk-release-check-final --require-dependency-audit`: passed. `twine` checks passed; installed-wheel smoke passed; runtime dependency audit completed. `pip-audit` reported the expected local-package skip because `ophanix-tool-gateway-sdk` is not on PyPI.
- Product-platform package build from repository root failed because the repository root has no `pyproject.toml`; this was an operator working-directory error, not a package failure. The corrected command from `packages/product-platform` passed and produced `ophanix_product_platform-0.1.0.tar.gz` and `.whl` with forbidden artifact list `[]`.
- `find packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway packages/product-platform/src/ophanix_tool_gateway -type l -print`: no SDK symlinks.
- `python3` with `yaml.safe_load` parsed `.github/workflows/ci.yml` and `.github/workflows/publish.yml` successfully.
- Final `git status --short` has no `??` untracked entries; remediation files are staged, with no unstaged diff remaining.

### Remaining Unresolved Issues

| Issue ID | Status | Rationale | Required future work |
| --- | --- | --- | --- |
| SDK-AUDIT-012 | Deferred with rationale | Installed-wheel import smoke and source-level gateway contract tests now pass, but there is still no true installed-wheel-to-running-gateway CI test. | Add a CI job that builds the SDK wheel, installs it into a clean environment, starts/seeds product-platform, and performs authenticated discovery/invocation through the installed wheel. |
| SDK-AUDIT-024 | Deferred with rationale | Automatic invocation retries without idempotency metadata could duplicate side effects. | Design and implement server-side idempotency keys, per-tool idempotency metadata, retry-safe SDK behavior, and regression tests. |
| SDK-AUDIT-054 | Deferred with rationale | Dependency locking/min-latest policy is a release-engineering decision. Runtime dependency auditing is now required, but broad ranges remain. | Add constraints or lockfile policy, min/latest dependency matrix, SBOM/provenance, and scheduled dependency update validation. |
| SDK-AUDIT-013 | Accepted remaining risk | Runtime dependencies are audited, but `pip-audit` skips the unpublished local project itself. | Publish package or integrate an internal advisory/provenance scanner that can evaluate local project metadata. |

### Updated Scoring Matrix

| Category | Previous audit score | Updated score | Direction | Exact reason | Remaining score cap |
| --- | --- | --- | --- | --- | --- |
| Implementation quality | 6.0 / 10 | 7.5 / 10 | Raised | Critical packaging/CI/artifact blockers are fixed or staged, SDK/runtime correctness issues are covered by tests, mypy passes, and product-platform plus SDK builds validate. Score is capped by the deferred installed-wheel running-gateway contract test and unresolved dependency release policy. | 7.5 to 8.0 until SDK-AUDIT-012 and SDK-AUDIT-054 are closed. |
| Ease of use | 6.0 / 10 | 8.0 / 10 | Raised | Setup, token handling, typed auth errors, package-publication status, troubleshooting, telemetry hooks, cache/payload behavior, and production checklist are now documented and tested where applicable. Score is capped by package not yet being publicly released and lack of generated API reference/deeper onboarding. | 8.0 until public release/onboarding docs mature. |
| Security and reliability | 5.0 / 10 | 7.5 / 10 | Raised | Critical failed-response policy bypass, DB artifact leak, token redaction leak, broad auth bypass, authz/schema ordering, SSRF controls, rate/body limits, CORS guard, resource cleanup, and response storage semantics were remediated with regression tests. Score is capped by deferred idempotency contract, in-process-only rate limiting, local-package audit limitation, and dependency policy gap. | 7.5 to 8.0 until SDK-AUDIT-024, distributed/edge rate-limit posture, and supply-chain policy are closed. |

### What Must Be Fixed To Reach The Next Score

- Add the true installed-wheel running-gateway CI contract test.
- Define and implement invocation idempotency semantics instead of relying on consumer discipline.
- Add dependency constraints/min-latest/SBOM/provenance policy beyond runtime vulnerability audit.
- Run the updated CI and publish workflows in GitHub after committing these changes.

### What Must Be Fixed To Reach 8 Out Of 10

- Close SDK-AUDIT-012 with a clean wheel-install e2e against a seeded live gateway.
- Close SDK-AUDIT-024 with server and SDK idempotency behavior and tests.
- Close SDK-AUDIT-054 with a documented and enforced dependency release strategy.
- Confirm GitHub Actions CI/publish checks pass from a clean branch.

### What Must Be Fixed To Reach 9 Out Of 10

- Add SBOM, provenance/signing, and stronger package-publication controls.
- Add distributed or edge-enforced rate limiting and operational runbooks.
- Add a formal threat model and security regression checklist for gateway invocation and upstream forwarding.
- Add generated API reference, richer examples, and a public support/deprecation policy.
- Add broader integration matrix coverage across supported Python/httpx versions and clean install environments.

### Recommended Remediation Order

1. Build the installed-wheel live-gateway CI harness.
2. Design and implement invocation idempotency keys and per-tool idempotency metadata.
3. Establish dependency constraints, SBOM/provenance, and min/latest dependency matrix policy.
4. Run the new CI and publish workflows in GitHub and fix any environment-specific failures.
5. Add distributed rate limiting/observability guidance for production deployments.

### Final Strict Assessment

This pass resolves the critical data-leak, policy-bypass, packaging, CI, SDK
runtime, and documentation blockers identified by the audit. Production adoption
is now defensible for controlled teams that can accept the documented remaining
risks and run the new validation gates, but broad external production adoption is
not yet defensible until the installed-wheel live gateway contract test,
idempotency contract, and supply-chain release policy are complete.

## 2026-05-11 V2 Production-Readiness Remediation Pass

Pass name: V2 exhaustive issue-register remediation execution.

Starting repository state:

- Worktree had no tracked staged or unstaged changes.
- One untracked audit artifact existed:
  `docs/product-platform-worktree/execution-logs/06-tool-gateway-logs/15-sdk-production-readiness-audit-v2.md`.
- This pass uses the V2 audit issue register from
  `15-sdk-production-readiness-audit-v2.md` as the source of issue IDs.
- This section was appended before runtime/source-code edits for this pass.

### Initial Remediation Tracking Table

| Issue ID | Title | Severity | Category | Current status | Planned action | Files likely affected | Validation required | Score impact |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SDK-AUDIT-001 | Hidden principal probe endpoint exposes credential context | High | Security/API | Pending | Remove or hard-gate route | `api/app.py`, auth tests | Route unavailable/admin-only test | Security/reliability |
| SDK-AUDIT-002 | Upstream URL validation permits loopback and DNS-private SSRF | Critical | Security/SSRF | Pending | Block local/private/DNS-private targets by default | `tool_gateway/models.py`, upstream tests, docs | SSRF URL validation tests | Security/reliability |
| SDK-AUDIT-003 | Blocking upstream HTTP calls run inside async endpoint | High | Runtime/Reliability | Pending | Add async executor path or safe bounded dispatch | `tool_gateway/invocation.py`, `api/app.py`, forwarding tests | Async invocation/load-focused tests | Implementation/reliability |
| SDK-AUDIT-004 | Shared SQLite connection and transaction handling are not production-safe | High | Runtime/Reliability | Pending | Serialize SQLite transaction access or defer real DB pooling | `db/connection.py`, DB tests | Concurrent transaction test | Implementation/reliability |
| SDK-AUDIT-005 | App can fall back to an in-memory seeded demo database | High | Runtime/Deployment | Pending | Fail closed outside dev/test when DB missing | `api/app.py`, settings/tests/docs | Production-mode startup test | Implementation/reliability |
| SDK-AUDIT-006 | Upstream authentication supports only auth_mode none | High | Security/Adoption | Pending | Implement minimal secret-backed bearer/API-key auth or defer larger auth modes | `tool_gateway/models.py`, `invocation.py`, migrations/tests/docs | Upstream auth integration tests | DX/security |
| SDK-AUDIT-007 | Tool invocation lacks idempotency and safe retry contract | High | Reliability/API | Pending | Add idempotency key contract or defer with explicit design note | `api/app.py`, `invocation.py`, repository/migrations/SDK/docs/tests | Replay/duplicate tests | Reliability/DX |
| SDK-AUDIT-008 | Gateway and SDK parse response bodies without pre-parse byte cap | High | Reliability/Security | Pending | Enforce content-length/read caps before JSON parse | SDK, `invocation.py`, response tests | Oversized response tests | Security/reliability |
| SDK-AUDIT-009 | Secret and security scans are advisory, not blocking | High | CI/Supply Chain | Pending | Make scanners blocking with allowlist path | GitHub workflows | Static workflow validation | Security/reliability |
| SDK-AUDIT-010 | Permission expiration is accepted as arbitrary text | High | Authorization/Data Integrity | Pending | Canonical datetime validation | `tool_gateway/models.py`, repository tests | Malformed/past/future tests | Security/reliability |
| SDK-AUDIT-011 | Gateway token hashes use plain SHA-256 without pepper | Medium | Security/Credential Storage | Pending | Add optional peppered HMAC path or document migration | `agents/credentials.py`, `auth.py`, settings/tests/docs | Hash verification tests | Security |
| SDK-AUDIT-012 | Runtime rate limiter is process-local and unbounded | Medium | Reliability/Security | Pending | Bound memory and document distributed limiter need | `api/app.py`, settings/tests/docs | Eviction/high-cardinality tests | Reliability |
| SDK-AUDIT-013 | Correlation and request IDs are caller-controllable | Medium | Audit Integrity | Pending | Validate and separate caller/server IDs | `api/app.py`, `invocation.py`, tests | Invalid ID tests | Security/reliability |
| SDK-AUDIT-014 | Allow decisions are persisted before schema validation | Medium | Audit/Correctness | Pending | Reorder validation or record validation-failed action | `api/app.py`, invocation/audit tests | Invalid payload audit test | Implementation |
| SDK-AUDIT-015 | Response policy status appears ignored | Medium | Runtime/Security | Pending | Enforce active policy status | `response.py`, repository/tests | Disabled policy test | Security/reliability |
| SDK-AUDIT-016 | Failed upstream response bodies can be returned to agents | Medium | Security/Data Exposure | Pending | Hide or sanitize failed upstream bodies by default | `api/app.py`, `invocation.py`, response tests | Upstream 500 secret test | Security |
| SDK-AUDIT-017 | HTTP 3xx upstream responses are treated as success | Medium | Runtime Correctness | Pending | Treat redirects as failure unless explicitly allowed | `invocation.py`, forwarding tests | 3xx tests | Reliability |
| SDK-AUDIT-018 | GET and DELETE payloads are serialized into query parameters | Medium | Security/API Ergonomics | Pending | Constrain query mapping and document/defer schema placement | `invocation.py`, docs/tests | Sensitive query tests | Security/DX |
| SDK-AUDIT-019 | Redaction regexes are not sufficiently ReDoS-safe | Medium | Security/Reliability | Pending | Strengthen regex rejection and cap text processed | `response.py`, tests | ReDoS pattern tests | Security/reliability |
| SDK-AUDIT-020 | Payload and audit summaries redact by key, not by value | Medium | Data Protection | Pending | Add value-pattern redaction | `decision.py`, runtime audit tests | Secret-like value tests | Security |
| SDK-AUDIT-021 | Credential scope issuance does not validate resource references | Medium | Authorization | Pending | Validate resource type/id against known tenant resources | `agents/credentials.py`, tests | Invalid resource tests | Security/DX |
| SDK-AUDIT-022 | Credential scope uniqueness can be bypassed for NULL resource IDs | Low | Data Integrity/Authz | Pending | Add normalized sentinel or duplicate check | migrations/repository/tests | Duplicate wildcard test | Minor |
| SDK-AUDIT-023 | Runtime latency type mismatch between DB and models | Low | Correctness/Portability | Pending | Align schema/model typing | migration/model/tests | Fractional latency test | Minor |
| SDK-AUDIT-024 | SDK does not extract top-level gateway error codes | Medium | SDK DX/Error Handling | Pending | Parse top-level error code/message safely | SDK/tests | Error-code tests | DX/reliability |
| SDK-AUDIT-025 | SDK maps every invocation HTTP 403 to ToolDeniedError | Medium | SDK Correctness/DX | Pending | Require structured denial reason | SDK/tests | Generic 403 test | DX/reliability |
| SDK-AUDIT-026 | SDK cache returns mutable nested schema data | Medium | SDK Correctness | Pending | Deep-copy/freeze cached definitions | SDK/tests | Mutation isolation test | Implementation |
| SDK-AUDIT-027 | SDK payload validation has no cycle protection | Low | SDK Correctness | Pending | Add cycle detection | SDK/tests | Cyclic payload test | Minor |
| SDK-AUDIT-028 | SDK discovery caches are unbounded | Low | SDK Reliability | Pending | Add bounded cache size | SDK/tests | Eviction test | Minor |
| SDK-AUDIT-029 | list_tools(status=active) exposes a misleading parameter | Low | SDK API Ergonomics | Pending | Document or deprecate parameter without breaking API | SDK README/tests | Docs/API check | DX |
| SDK-AUDIT-030 | SDK event hook exceptions are swallowed silently | Low | SDK Observability | Pending | Add optional hook error callback/logging | SDK/tests/docs | Hook error test | DX |
| SDK-AUDIT-031 | SDK errors do not expose retry metadata | Low | SDK Reliability/DX | Pending | Add retry-after metadata to errors where available | SDK/tests/docs | 429/503 metadata tests | DX/reliability |
| SDK-AUDIT-032 | Direct HTTP callers bypass SDK payload hardening | Medium | API/Security | Pending | Apply server-side payload constraints | `api/app.py`/schemas/tests | Direct HTTP invalid payload tests | Security/reliability |
| SDK-AUDIT-033 | Standalone SDK package has only a smoke test | Medium | Testing | Pending | Add standalone behavioral tests or share suite | SDK tests | Standalone test suite | Implementation |
| SDK-AUDIT-034 | No convincing production-like concurrency/load/SSRF integration tests | Medium | Testing/Reliability | Pending | Add focused concurrency/SSRF/integration tests where feasible | product tests | New integration tests | Reliability |
| SDK-AUDIT-035 | CI matrix appears to test SDK on unsupported Python 3.10 | Medium | CI/Packaging | Pending | Fix matrix exclusion | `.github/workflows/ci.yml` | Workflow static validation | CI |
| SDK-AUDIT-036 | Dependabot omits product-platform and standalone SDK Python packages | Medium | Supply Chain | Pending | Add package directories | `.github/dependabot.yml` | Config review | Security |
| SDK-AUDIT-037 | Product-platform wheel lacks included license file | Low | Packaging/Compliance | Pending | Include license file in package metadata | product pyproject/LICENSE | Wheel metadata test | Packaging |
| SDK-AUDIT-038 | Local database artifacts exist in product-platform package directory | Low | Repo Hygiene/Packaging | Pending | Remove ignored local DB artifacts and enforce ignore | package root/.gitignore/tests | Git status/package content test | Packaging |
| SDK-AUDIT-039 | Release validator does not enforce clean worktree or tag/version match | Low | Release | Pending | Add strict release checks | SDK release validator/tests/docs | Validator tests | Release |
| SDK-AUDIT-040 | Product-platform README has stale test instructions | Low | Documentation/DX | Pending | Update README test commands | product README | Doc review | DX |
| SDK-AUDIT-041 | Documentation understates upstream URL and SSRF risk | Medium | Documentation/Security | Pending | Update docs to match hardened behavior | product README/SDK README | Doc review | Security/DX |
| SDK-AUDIT-042 | SDK SECURITY.md is minimal | Low | Documentation/Security Process | Pending | Expand security policy | SDK SECURITY.md | Doc review | DX/security |
| SDK-AUDIT-043 | Deterministic local fixture tokens appear in docs/examples | Low | Security/DX | Pending | Strengthen fixture warnings | examples/docs | Doc/example tests | DX/security |
| SDK-AUDIT-044 | Local release validation has dependency friction | Low | Release/DX | Pending | Improve preflight messaging | SDK validator/README | Validator preflight test | DX |
| SDK-AUDIT-045 | Actual publishing path is opaque in repo | Medium | Release/Adoption | Pending | Document publishing controls or defer external pipeline | publish workflow/docs | Doc review | Release/DX |
| SDK-AUDIT-046 | SDK source is duplicated between standalone package and product-platform | Medium | Maintainability/Release | Pending | Add CI/source parity check or refactor source ownership | CI/tests/scripts | Drift test | Implementation |
| SDK-AUDIT-047 | API docs and OpenAPI appear enabled unconditionally | Low | Security/Deployment | Pending | Gate docs by env setting | `api/app.py`, settings/tests/docs | Production docs disabled test | Security |
| SDK-AUDIT-048 | Development defaults are not fail-closed | Medium | Security/Deployment | Pending | Add production startup validation | settings/app/tests/docs | Production config tests | Security |
| SDK-AUDIT-049 | Bearer token parsing is permissive | Low | Security/Auth | Pending | Enforce token format | `auth.py`, tests | Malformed bearer tests | Security |
| SDK-AUDIT-050 | Public SDK remains pre-1.0/beta for production adoption | Low | API Stability/DX | Pending | Document stability policy, keep version unless release decision made | SDK pyproject/docs | Metadata/doc review | DX |

### Final V2 Remediation Status

Processed issue count: 50.

Status counts:

- Fixed: 45.
- Already resolved: 0.
- Invalid finding: 0.
- Deferred with rationale: 3.
- Accepted remaining risk: 2.

This table supersedes the initial pending table above. All issue IDs from the V2
audit register were triaged. Prior remediation claims were not treated as proof;
each disposition below is based on the current source, tests, packaging, docs, or
explicit remaining-risk decision from this pass.

| Issue ID | Original severity/category | Final status | Files changed or checked | Root cause/current evidence | Fix implemented and production-grade rationale | Tests/validation evidence | Remaining risk | Score impact |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SDK-AUDIT-001 | High / Security/API | Fixed | `api/app.py`, `test_tool_gateway_auth_phase3.py` | The principal probe route exposed credential context through the gateway auth path. | Removed the runtime probe route and excluded it from gateway runtime auth classification; discovery remains available through the authenticated tools route. | Focused auth tests and full product suite passed. | None known. | Raises security/reliability. |
| SDK-AUDIT-002 | Critical / Security/SSRF | Fixed | `models.py`, `test_tool_gateway_upstream_phase1.py`, product README | URL validation allowed loopback, private, link-local, metadata, and DNS-private targets. | Upstream targets must use HTTPS and reject forbidden hostnames, forbidden IP literals, and DNS resolutions to forbidden addresses. Docs now call out egress controls as the final SSRF boundary. | SSRF validation tests, full gateway suite, full product suite, ruff. | DNS names that cannot resolve at registration time still require runtime network egress policy. | Removes critical score cap; residual infra risk remains. |
| SDK-AUDIT-003 | High / Runtime/Reliability | Fixed | `invocation.py`, `api/app.py`, forwarding tests | Async FastAPI route used a blocking HTTP executor. | Added async upstream executor using `httpx.AsyncClient`, awaitable execution handling, and shutdown cleanup for owned clients. | Forwarding phase 3 tests, full gateway suite, full product suite. | No load test proving event-loop behavior under production traffic. | Raises implementation/reliability. |
| SDK-AUDIT-004 | High / Runtime/Reliability | Fixed | `db/connection.py`, full DB/product tests | Shared SQLite transaction usage could interleave across threads. | Added transaction serialization around the shared SQLite connection, preserving current SQLite architecture without pretending it is a production DB pool. | Full product suite including DB tests passed. | Real multi-instance production still needs a production database/pool architecture. | Raises implementation; residual architecture caveat. |
| SDK-AUDIT-005 | High / Runtime/Deployment | Fixed | `api/app.py`, cloud readiness tests, auth tests, README | Non-local app creation could drift into demo/in-memory behavior. | Non-local startup fails when only the default DB URL is present; configured DB URLs are used lazily without demo seeding outside local/test. | Production startup tests, cloud readiness tests, full product suite. | Operators must still provide a real supported DB configuration. | Raises implementation/reliability. |
| SDK-AUDIT-006 | High / Security/Adoption | Deferred with rationale | `models.py`, `invocation.py`, README | Upstream auth remains intentionally unsupported beyond `auth_mode="none"`. | Deferred because secret-backed upstream auth requires product design for secret storage, rotation, per-tool auth material, audit, and migration. Current behavior stays fail-closed for non-`none` auth modes and docs state the limitation. | Existing unsupported-auth tests and full gateway suite passed. | External adopters needing upstream bearer/API-key auth cannot use this path without a product feature. | Caps ease of use and security/reliability. |
| SDK-AUDIT-007 | High / Reliability/API | Deferred with rationale | SDK README, runtime code checked | Automatic invocation retries remain unsafe for mutating tools without idempotency semantics. | Deferred because durable idempotency needs server-side idempotency keys, per-tool mutability metadata, persistence, replay behavior, and SDK contract updates. SDK docs explicitly avoid automatic invocation retries. | Discovery retry tests pass; full SDK and product suites pass. | Consumers must implement their own idempotency discipline for mutating tools. | Caps implementation and reliability. |
| SDK-AUDIT-008 | High / Reliability/Security | Fixed | SDK `sdk.py`, `invocation.py`, SDK/forwarding tests | Gateway and SDK parsed response bodies before bounding bytes. | Added configurable pre-parse response caps for SDK gateway responses and upstream executor responses using `Content-Length`/content byte checks. | Oversized SDK and upstream response tests, full gateway suite, standalone SDK tests. | Streaming response enforcement is still not implemented. | Raises security/reliability. |
| SDK-AUDIT-009 | High / CI/Supply Chain | Fixed | `.github/workflows/secret-scanning.yml`, `.github/workflows/security-scan.yml` | Secret/security scans were advisory via non-blocking behavior. | Removed advisory continuation and made high-entropy findings emit CI errors. | Workflow diff review, `git diff --check`, full test suite unaffected. | CI must run in GitHub to prove environment-specific behavior. | Raises security/reliability. |
| SDK-AUDIT-010 | High / Authorization/Data Integrity | Fixed | `models.py`, permissions tests | Permission expiration accepted arbitrary text. | Expiration fields are parsed as timezone-aware datetimes and normalized to UTC ISO text. | Permission expiration rejection/normalization tests, full gateway suite. | None known. | Raises auth correctness. |
| SDK-AUDIT-011 | Medium / Security/Credential Storage | Fixed | `agents/credentials.py`, `auth.py`, auth tests | Gateway token hashes used plain SHA-256 only. | Added optional HMAC-SHA256 pepper support with legacy hash lookup compatibility for rotation. | Peppered-hash verification tests and full gateway suite. | Production must set `OPHANIX_GATEWAY_TOKEN_HASH_PEPPER`; legacy hashes remain accepted during migration. | Raises security, with configuration caveat. |
| SDK-AUDIT-012 | Medium / Reliability/Security | Fixed | `settings.py`, `api/app.py`, auth tests, README | Rate limiter was process-local and key storage unbounded. | Added max-key bound and fail-closed behavior when high-cardinality keys exceed capacity; documented distributed limiter need. | Rate-limit bounded-key test, full product suite. | Process-local rate limiting is not a distributed production control. | Raises reliability; residual infra cap remains. |
| SDK-AUDIT-013 | Medium / Audit Integrity | Fixed | `api/app.py`, `invocation.py`, auth tests | Caller-supplied request/correlation IDs could become trusted audit IDs. | Added strict trusted ID validation and replacement for malformed IDs; SDK validates correlation ID characters and length. | Invalid request/correlation ID tests and full gateway suite. | Valid-looking caller IDs are still accepted as correlation context. | Raises audit reliability. |
| SDK-AUDIT-014 | Medium / Audit/Correctness | Fixed | `api/app.py`, `runtime_audit.py`, invocation tests | Allowed runtime action was persisted before payload schema validation. | Schema failures now persist explicit `validation_failed` runtime actions and events after authorization instead of masquerading as allowed executions. | Validation-failed audit test and full gateway suite. | None known. | Raises implementation correctness. |
| SDK-AUDIT-015 | Medium / Runtime/Security | Fixed | `response.py`, response tests | Response policy status was not enforced. | Disabled/non-active response policies are ignored; active policies still apply. | Disabled policy test and full gateway suite. | None known. | Raises security/reliability. |
| SDK-AUDIT-016 | Medium / Security/Data Exposure | Fixed | `api/app.py`, response/forwarding tests | Failed upstream response bodies could be returned to agents. | Failed upstream invocation responses now hide result bodies from agents and mark them not exposed. | Upstream 500 response tests and full gateway suite. | Audit/debug storage policy should be revisited if upstream failures include sensitive payloads. | Raises security. |
| SDK-AUDIT-017 | Medium / Runtime Correctness | Fixed | `invocation.py`, forwarding tests | 3xx upstream responses were treated as success. | Upstream success is now limited to HTTP 2xx. | Redirect failure test and full gateway suite. | None known. | Raises reliability. |
| SDK-AUDIT-018 | Medium / Security/API Ergonomics | Fixed | `invocation.py`, forwarding tests | GET/DELETE payloads became query params, including path params and possible secrets. | Path params are excluded from query serialization, credential-like query keys are rejected, and non-scalar query values fail clearly. | Query param exclusion and unsafe-query tests, full gateway suite. | There is still no formal per-tool query/body schema split. | Raises security/DX. |
| SDK-AUDIT-019 | Medium / Security/Reliability | Fixed | `models.py`, `response.py`, response tests | Redaction regexes could be pathological and applied to unbounded strings. | Added pattern length/nesting/wildcard checks and caps for redaction string processing. | ReDoS pattern tests and full gateway suite. | Regex safety is heuristic, not a formal safe-regex engine. | Raises security/reliability. |
| SDK-AUDIT-020 | Medium / Data Protection | Fixed | `decision.py`, decision tests | Secret-like values could leak when keys were benign. | Added value-pattern redaction for bearer/token-like strings in payload summaries. | Secret-like value summary test and full gateway suite. | Heuristic redaction may miss novel secret formats. | Raises data protection. |
| SDK-AUDIT-021 | Medium / Authorization | Fixed | `agents/credentials.py`, credential tests | Tool-scoped credential issuance did not validate referenced resources. | Tool resource scopes now require a resource id and active same-org/env tool by id or name. | Credential scope resource validation test and full product suite. | Other resource types still rely on existing validation model. | Raises authorization safety. |
| SDK-AUDIT-022 | Low / Data Integrity/Authz | Fixed | migrations `0056`, DB tests | NULL resource IDs could bypass uniqueness. | Added normalized unique index using `COALESCE(resource_id,'')`. | Migration apply/rollback tests and full product suite. | Existing duplicate data in deployed DBs would need pre-migration cleanup if present. | Minor score lift. |
| SDK-AUDIT-023 | Low / Correctness/Portability | Fixed | migration `0055`, migration `0057`, DB tests | Model allowed fractional latency but DB column was integer. | New installations and migrated existing installations use `REAL` latency column; rollback migration provided. | Migration apply/rollback tests and full product suite. | Existing deployments need migration rollout. | Minor score lift. |
| SDK-AUDIT-024 | Medium / SDK DX/Error Handling | Fixed | standalone and vendored SDK, SDK tests | SDK ignored top-level gateway error codes. | Gateway errors now preserve top-level `code` and `message` forms where present. | Product SDK and standalone SDK tests. | None known. | Raises ease of use. |
| SDK-AUDIT-025 | Medium / SDK Correctness/DX | Fixed | standalone and vendored SDK, SDK tests | Every invocation 403 became `ToolDeniedError`. | SDK only raises `ToolDeniedError` for structured policy denials and leaves generic 403s as `ToolGatewayError`. | Generic 403 test and SDK suites. | None known. | Raises DX/reliability. |
| SDK-AUDIT-026 | Medium / SDK Correctness | Fixed | standalone and vendored SDK, SDK tests | Cached tool definitions exposed mutable nested schemas. | Cache stores and returns cloned tool definitions with deep-copied schemas/raw mappings. | Mutation isolation tests in product and standalone SDK suites. | None known. | Raises implementation. |
| SDK-AUDIT-027 | Low / SDK Correctness | Fixed | standalone and vendored SDK, SDK tests | Payload validator had no cycle protection. | JSON payload validation tracks seen containers and rejects cycles. | Cyclic payload tests and SDK suites. | None known. | Minor score lift. |
| SDK-AUDIT-028 | Low / SDK Reliability | Fixed | standalone and vendored SDK, SDK tests | Discovery caches were unbounded. | Added `max_cache_entries` configuration and LRU-style trimming for discovery caches. | Cache bound tests and SDK suites. | None known. | Minor reliability lift. |
| SDK-AUDIT-029 | Low / SDK API Ergonomics | Fixed | SDK README | `list_tools(status="active")` was easy to misread because gateway only returns active callable tools. | Documented active-only behavior and compatibility purpose of the parameter without breaking API. | Doc review, SDK tests. | API remains for compatibility. | DX lift. |
| SDK-AUDIT-030 | Low / SDK Observability | Fixed | standalone and vendored SDK | Event hook failures were silently swallowed. | Hook exceptions are now logged at debug level with traceback while preserving SDK call behavior. | SDK tests and ruff/mypy validation. | No dedicated hook-error unit test was added. | Small DX/observability lift. |
| SDK-AUDIT-031 | Low / SDK Reliability/DX | Fixed | standalone and vendored SDK, SDK README, SDK tests | Gateway errors lacked retry metadata. | `ToolGatewayError` now exposes `retry_after_seconds` from `Retry-After` on invocation/discovery gateway errors. | Product SDK retry-after test, standalone SDK retry-after test, mypy, ruff. | Date-form `Retry-After` is not parsed; numeric seconds are supported. | DX/reliability lift. |
| SDK-AUDIT-032 | Medium / API/Security | Fixed | `invocation.py`, SDK and invocation tests | Direct HTTP callers could send payloads the SDK would reject. | Server-side invocation request model now rejects non-JSON values, non-finite numbers, cycles, excessive nesting, and invalid correlation IDs. | Direct HTTP NaN/correlation tests, full gateway suite. | Payload depth limit is coarse and may need tuning. | Raises security/reliability. |
| SDK-AUDIT-033 | Medium / Testing | Fixed | `packages/ophanix-tool-gateway-sdk/tests/test_sdk_behavior.py` | Standalone package only had smoke coverage. | Added standalone behavioral tests for calls, cache isolation, top-level error codes, and retry metadata. | Standalone SDK suite passed. | Standalone suite is still smaller than vendored SDK suite. | Raises implementation confidence. |
| SDK-AUDIT-034 | Medium / Testing/Reliability | Deferred with rationale | SSRF/concurrency areas tested; no load harness added | Audit asked for production-like concurrency/load/SSRF integration coverage. | Added focused SSRF, async executor, rate-limit, and full-suite regression tests, but deferred true load/concurrency integration harness because it needs a running service environment and operational test target. | Full product suite, full gateway suite, focused SSRF tests. | No production-like load or multi-worker integration proof yet. | Caps reliability score. |
| SDK-AUDIT-035 | Medium / CI/Packaging | Fixed | `.github/workflows/ci.yml` | CI matrix included unsupported Python 3.10 for SDK/product packages. | Matrix excludes product-platform and SDK from Python 3.10. | Workflow diff review and package test suites. | GitHub CI must run after commit. | Raises CI/package confidence. |
| SDK-AUDIT-036 | Medium / Supply Chain | Fixed | `.github/dependabot.yml` | Dependabot omitted package directories. | Added pip update entries for product-platform and standalone SDK. | Config review, `git diff --check`. | Dependabot behavior must be observed in GitHub. | Raises supply-chain posture. |
| SDK-AUDIT-037 | Low / Packaging/Compliance | Fixed | `packages/product-platform/LICENSE`, product `pyproject.toml` | Product wheel lacked an included license file. | Added MIT license file and package metadata inclusion. | Product wheel build and wheel-content check show license included. | None known. | Packaging/compliance lift. |
| SDK-AUDIT-038 | Low / Repo Hygiene/Packaging | Accepted remaining risk | product package root checked | Local DB artifacts still exist in the package directory. | Accepted because deleting local DB/backups could destroy user/developer state; packaging excludes DB artifacts and wheel-content validation confirms package contents are clean. | Wheel-content check; git status still shows local DB files are not newly tracked. | Repo working directory remains visually noisy until owner removes or relocates artifacts. | Low packaging/repo hygiene cap. |
| SDK-AUDIT-039 | Low / Release | Fixed | `scripts/validate_release.py`, SDK README | Release validator did not enforce clean worktree/tag match. | Added `--strict-git` and expected tag/version checks; non-strict release validation still builds and checks artifacts. | `validate_release.py` passed; strict mode fails on dirty worktree as expected. | Strict validation cannot pass until changes are committed and tagged. | Release confidence lift. |
| SDK-AUDIT-040 | Low / Documentation/DX | Fixed | product README | Product README test instructions were stale. | Updated pytest/unittest-oriented validation commands. | Doc review, full product suite. | None known. | DX lift. |
| SDK-AUDIT-041 | Medium / Documentation/Security | Fixed | product README, SDK README | Docs understated upstream URL/SSRF risk. | Documented HTTPS-only upstream URLs, blocked host classes, DNS behavior, and egress firewall requirement. | Doc review and SSRF tests. | Docs still depend on operators enforcing egress policy. | Security/DX lift. |
| SDK-AUDIT-042 | Low / Documentation/Security Process | Fixed | SDK `SECURITY.md` | Security policy was minimal. | Expanded supported versions, reporting process, SLA targets, disclosure guidance, and security expectations. | Doc review. | No external security contact workflow has been exercised. | Security process lift. |
| SDK-AUDIT-043 | Low / Security/DX | Fixed | direct HTTP example README | Deterministic fixture tokens could be mistaken for real credentials. | Strengthened local-only fixture token warnings and rotation guidance. | Doc/example review. | Fixture tokens remain present for deterministic local demos. | Security/DX lift. |
| SDK-AUDIT-044 | Low / Release/DX | Fixed | SDK `validate_release.py`, SDK README | Release validation failed opaquely when release deps were missing. | Validator now emits actionable release-extra guidance; after installing release tools, artifact validation passes. | `validate_release.py` passed. | Developers still must install release extras locally. | DX lift. |
| SDK-AUDIT-045 | Medium / Release/Adoption | Fixed | SDK README | Publishing path/provenance was unclear. | Documented local validation, strict git mode, release artifacts, and publishing expectations. | Doc review and release validator pass. | Actual publish workflow still must be executed in CI/release environment. | Release/DX lift. |
| SDK-AUDIT-046 | Medium / Maintainability/Release | Fixed | product SDK copy, standalone SDK, `test_tool_gateway_sdk_package.py` | SDK source was duplicated with drift risk. | Kept copies synchronized and added a parity test proving vendored copy matches standalone source. | Parity test and SDK suites passed. | Duplication remains; parity test catches drift but does not remove it. | Raises maintainability confidence. |
| SDK-AUDIT-047 | Low / Security/Deployment | Fixed | `settings.py`, `api/app.py`, auth tests, README | API docs/OpenAPI were enabled unconditionally. | Docs/OpenAPI are enabled by default only in local/test, configurable via settings/env. | Production docs disabled test and full product suite. | Operators can still explicitly enable docs. | Security deployment lift. |
| SDK-AUDIT-048 | Medium / Security/Deployment | Fixed | `settings.py`, `api/app.py`, auth/cloud tests, README | Development defaults were not fail-closed in non-local environments. | Production validation rejects default session secret, dev login, and default DB URL outside local/test. | Production guard tests, cloud readiness tests, full product suite. | More production config checks could be added for token pepper and CORS policy. | Raises security/reliability. |
| SDK-AUDIT-049 | Low / Security/Auth | Fixed | `auth.py`, auth tests | Bearer token parser allowed whitespace/control ambiguity. | Parser rejects empty, leading/trailing/internal whitespace, and unsupported characters. | Malformed bearer tests and full gateway suite. | Allowed character set may need adjustment for future token formats. | Security lift. |
| SDK-AUDIT-050 | Low / API Stability/DX | Accepted remaining risk | SDK `pyproject.toml`, README | SDK remains `0.1.0` beta. | Accepted as a product/release decision; docs describe behavior and validation, but version was not bumped to 1.0 in this remediation pass. | SDK package build/release validation passed. | External adopters may treat beta status as a production adoption blocker. | Caps ease of use/adoption confidence. |

### Changed Files Summary

Primary runtime and SDK changes:

- Hardened Tool Gateway auth, request context, production startup guards, rate limiting, async upstream execution, schema-validation audit behavior, failed-upstream response exposure, and shutdown cleanup.
- Hardened upstream target validation, payload validation, redaction, decision summaries, credential token hashing, credential scope validation, and bearer parsing.
- Added migrations `0056` and `0057`, adjusted migration expectations, and aligned latency storage type.
- Updated standalone SDK and product-platform vendored SDK together, including response caps, cache isolation/bounds, retry metadata, safer 403 typing, top-level error code handling, cyclic payload detection, and hook-error logging.
- Updated CI/security/dependabot config, package metadata, license inclusion, release validation, README/SECURITY docs, and example warnings.
- Added or updated product-platform, standalone SDK, DB, cloud readiness, and packaging tests.

Additional lint cleanup:

- Removed pre-existing unused imports/variables surfaced by ruff in `api/app.py`,
  `discovery/findings.py`, `tool_gateway/repository.py`, `trust/pipeline.py`, and
  `test_policy_bindings_phase2.py`.

### Validation Evidence

Commands run and final results:

- `env PYTHONPATH=src python3 -m pytest tests/test_tool_gateway_auth_phase1.py ... tests/test_tool_gateway_sdk_package.py -q --tb=short` from `packages/product-platform`: 139 passed.
- `env PYTHONPATH=src python3 -m pytest tests/test_tool_gateway_*.py -q --tb=short` from `packages/product-platform`: 257 passed.
- `env PYTHONPATH=src python3 -m pytest tests -q --tb=short` from `packages/product-platform`: 754 passed, 47 warnings.
- `env PYTHONPATH=src python3 -m pytest tests/test_tool_gateway_*.py tests/test_db_phase1.py tests/test_mvp_cloud_deployment_phase2.py -q --tb=short` from `packages/product-platform`: 268 passed.
- `env PYTHONPATH=src python3 -m pytest tests/test_tool_gateway_sdk_phase1.py tests/test_tool_gateway_sdk_phase2.py tests/test_tool_gateway_sdk_phase3.py tests/test_tool_gateway_sdk_package.py -q --tb=short` from `packages/product-platform`: 95 passed.
- `env PYTHONPATH=src python3 -m pytest tests -q --tb=short` from `packages/ophanix-tool-gateway-sdk`: 5 passed.
- `python3 -m ruff check .` from `packages/product-platform`: passed.
- `python3 -m ruff check .` from `packages/ophanix-tool-gateway-sdk`: passed.
- `python3 -m mypy src tests` from `packages/ophanix-tool-gateway-sdk`: passed.
- `python3 -m compileall -q packages/product-platform/src/product_platform packages/product-platform/src/ophanix_tool_gateway packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway packages/ophanix-tool-gateway-sdk/scripts`: passed.
- `python3 -m pip wheel . --no-deps --wheel-dir /tmp/ophanix-sdk-wheel-remediation` from `packages/ophanix-tool-gateway-sdk`: built `ophanix_tool_gateway_sdk-0.1.0-py3-none-any.whl`.
- `python3 -m pip wheel . --no-deps --wheel-dir /tmp/ophanix-product-wheel-remediation` from `packages/product-platform`: built `ophanix_product_platform-0.1.0-py3-none-any.whl`.
- Wheel-content check: SDK wheel includes `LICENSE` and `ophanix_tool_gateway/sdk.py`; product wheel includes `LICENSE`, `ophanix_tool_gateway/sdk.py`, and migrations `0056`/`0057`.
- `python3 scripts/validate_release.py` from `packages/ophanix-tool-gateway-sdk`: built sdist/wheel and twine check passed.
- `python3 scripts/validate_release.py --strict-git` from `packages/ophanix-tool-gateway-sdk`: failed as expected because the SDK package worktree is dirty during this remediation pass.
- `python3 -m pip check`: passed.
- `git diff --check`: passed.

Validation caveats:

- GitHub Actions workflows were edited and statically checked, but not executed in
  GitHub from this environment.
- Strict release validation cannot pass until the SDK changes are committed and
  the release tag/version state is clean.
- No production-like load or multi-worker integration harness was added.

### Remaining Unresolved Issues

| Issue ID | Status | Rationale | Required future work |
| --- | --- | --- | --- |
| SDK-AUDIT-006 | Deferred with rationale | Secret-backed upstream auth needs product design for storage, rotation, audit, and per-tool binding. | Implement upstream bearer/API-key/OAuth auth modes backed by a secret provider and migration path. |
| SDK-AUDIT-007 | Deferred with rationale | Safe automatic invocation retries require idempotency semantics to avoid duplicate side effects. | Add server-side idempotency keys, persistence, replay behavior, SDK support, and tests. |
| SDK-AUDIT-034 | Deferred with rationale | Focused tests were added, but no production-like load/multi-worker harness exists. | Add live gateway integration/load tests covering async forwarding, SSRF controls, rate limits, and failure modes. |
| SDK-AUDIT-038 | Accepted remaining risk | Local DB artifacts were not deleted to avoid destroying developer state; package excludes them. | Move/remove local DB artifacts through an explicit repo-owner cleanup step. |
| SDK-AUDIT-050 | Accepted remaining risk | SDK remains pre-1.0 beta as a release/product decision. | Define stability policy and versioning criteria for a 1.0 production SDK release. |

### Updated Scoring Matrix

| Category | Previous V2 audit score | Updated score | Direction | Exact reason | Remaining score cap |
| --- | --- | --- | --- | --- | --- |
| Implementation quality | 6 / 10 | 7 / 10 | Raised | The critical runtime, SDK, migration, packaging, and test gaps are substantially remediated and the full product suite passes. Score is capped by deferred invocation idempotency, duplicated SDK source ownership, and lack of production-like load/multi-worker validation. | 7 until SDK-AUDIT-007 and SDK-AUDIT-034 are closed. |
| Ease of use | 6 / 10 | 7 / 10 | Raised | Error typing, retry metadata, docs, release validation, setup guidance, security policy, SDK behavior, and packaging are materially clearer. Score is capped by unsupported upstream auth, beta SDK status, and remaining release-environment proof. | 7 until SDK-AUDIT-006 and SDK-AUDIT-050 are closed. |
| Security and reliability | 5 / 10 | 6 / 10 | Raised | Critical SSRF, demo DB fallback, token parsing, failed-response leakage, redaction, response caps, production defaults, scanner blocking, and authz/resource validation were improved with tests. Score remains capped by high unresolved upstream auth/idempotency gaps, process-local rate limiting, and missing production-like validation. | 6 until SDK-AUDIT-006, SDK-AUDIT-007, and SDK-AUDIT-034 are closed. |

### Score Cap Explanation

- Any claim above 7 for implementation would be too lenient while invocation
  idempotency and production-like load/multi-worker testing remain open.
- Any claim above 7 for ease of use would be too lenient while upstream auth is
  unsupported and the SDK is still beta.
- Any claim above 6 for security/reliability would be too lenient while two high
  reliability/security adoption gaps remain deferred and rate limiting is still
  process-local.

### Required Fixes To Reach Production Readiness

1. Implement secret-backed upstream authentication for at least bearer/API-key
   modes with rotation, audit, docs, and tests.
2. Implement invocation idempotency semantics across API, persistence, SDK, docs,
   and replay/duplicate tests.
3. Add live gateway integration/load tests that prove async forwarding, SSRF
   blocking, rate limiting, malformed responses, timeouts, and partial failures
   under realistic concurrency.
4. Move/remove local DB artifacts through an explicit cleanup step and keep
   package-content checks in CI.
5. Run GitHub Actions CI/security/release workflows from a clean branch.

### Required Fixes To Reach 8 Out Of 10

1. Close SDK-AUDIT-006 and SDK-AUDIT-007 with validated production behavior.
2. Close SDK-AUDIT-034 with a repeatable integration/load harness.
3. Add distributed or edge-enforced rate limiting guidance/implementation for
   multi-worker production deployments.
4. Commit/tag cleanly and prove strict SDK release validation passes.
5. Decide SDK stability/version policy and document support commitments.

### Required Fixes To Reach 9 Out Of 10

1. Remove SDK source duplication or replace it with generated/vendor sync tooling
   beyond parity tests.
2. Add SBOM/provenance/signing and a stronger supply-chain release policy.
3. Add formal threat model coverage for Tool Gateway invocation and upstream
   forwarding.
4. Add generated API reference and broader consumer onboarding examples.
5. Add Python/httpx version matrix coverage and clean install/live gateway CI.

### Recommended Remediation Order

1. Design upstream auth and idempotency together so auth material, retries, and
   audit semantics do not conflict.
2. Implement and migrate upstream auth modes.
3. Implement server and SDK idempotency keys.
4. Build the live gateway integration/load harness and wire it into CI.
5. Clean local DB artifacts and prove strict release validation on a clean tag.
6. Decide the SDK 1.0 support policy.

### Final Strict Assessment

This pass materially improves the SDK and Tool Gateway production posture and
closes most actionable V2 findings with tests, docs, package validation, and
runtime hardening. Controlled production adoption is now more defensible for
teams that only need `auth_mode="none"` upstream targets and can accept manual
idempotency discipline. Broad external production adoption is still not
defensible until upstream auth, invocation idempotency, and production-like
multi-worker/load validation are complete.

---

## 2026-05-11 - V3 Audit Remediation Execution Pass

Pass name: `SDK-AUDIT-001` through `SDK-AUDIT-058` production-readiness remediation execution.

### Starting Repository State Summary

- Starting branch state was clean except for the newly produced V3 audit artifact:
  `docs/product-platform-worktree/execution-logs/06-tool-gateway-logs/16-sdk-production-readiness-audit-v3.md`.
- No source, test, CI, package, or documentation fixes had been applied for this pass before creating this tracking table.
- The V3 audit register contains 58 issue IDs. This pass tracks every ID below before editing source files.

### Initial Remediation Tracking Table

| Issue ID | Title | Severity | Category | Current status | Planned action | Files likely affected | Validation required | Score impact |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SDK-AUDIT-001 | Manual upstream health check uses async HTTP client in synchronous checker | High | Runtime/reliability | Pending | Fix route/checker async behavior and add route-level regression test | `app.py`, `health.py`, upstream tests | Focused upstream health tests, gateway tests | Implementation/reliability |
| SDK-AUDIT-002 | Tool invocation holds DB transaction open across upstream network call | High | Runtime/reliability | Pending | Split invocation into short DB transactions around network call | `app.py`, runtime audit tests | Invocation/forwarding/runtime audit tests | Implementation/reliability |
| SDK-AUDIT-003 | Product runtime database layer is SQLite-only with one shared connection | High | Architecture/reliability | Pending | Triage for production guard/defer full DB backend if too large | DB/settings/app/docs | Production settings tests, docs | Implementation/reliability |
| SDK-AUDIT-004 | Production guard accepts arbitrary SQLite URLs | Medium | Deployment safety | Pending | Fail closed for SQLite in non-local mode unless explicit override | `settings.py`, `app.py`, cloud/readiness tests, README | Production settings tests | Reliability/security |
| SDK-AUDIT-005 | Upstream authentication unsupported beyond none | High | API/security/adoption | Pending | Triage feasibility; implement or document as deferred architecture work | tool gateway models/invocation/docs | Upstream auth tests if implemented | Ease/security |
| SDK-AUDIT-006 | No server-side idempotency or safe retry contract | High | Reliability/API | Pending | Triage feasibility; implement durable contract or document deferred design | API/repository/migrations/SDK/docs | Invocation replay tests if implemented | Implementation/reliability |
| SDK-AUDIT-007 | Upstream URL DNS failure and rebinding gaps | High | Security/SSRF | Pending | Harden unresolved-host production behavior and document runtime egress boundary | `models.py`, settings/docs/tests | SSRF validation tests | Security/reliability |
| SDK-AUDIT-008 | Response byte caps checked after HTTPX materializes bodies | High | Reliability/resource safety | Pending | Add streaming/byte-counting reads where feasible; docs if residual | SDK, invocation, tests/docs | Oversized chunked response tests | Reliability |
| SDK-AUDIT-009 | Inactive response policy can bypass redaction while storing full response | High | Security/data handling | Pending | Gate full-response persistence on active response policy/redaction | `response.py`, `app.py`, response tests | Response policy tests | Security |
| SDK-AUDIT-010 | OpenAPI alias exposed when docs disabled | Medium | Security/docs consistency | Pending | Gate alias on API docs setting | `app.py`, README/tests | Production docs route tests | Security/DX |
| SDK-AUDIT-011 | System config advertises docs URL when disabled | Low | Docs/runtime consistency | Pending | Return `None` when docs disabled | `app.py`, tests | System config tests | DX |
| SDK-AUDIT-012 | Production safety limits can be disabled | Medium | Deployment/reliability | Pending | Validate positive bounded limits in production | `settings.py`, `app.py`, README/tests | Production settings tests | Reliability/security |
| SDK-AUDIT-013 | Gateway rate limiter is process-local | Medium | Reliability/security | Pending | Document/defer distributed limiter or add config guard | docs/settings/tests | Docs/readiness validation | Reliability |
| SDK-AUDIT-014 | Rate limiter dictionary has no concurrency guard | Low | Reliability/correctness | Pending | Add lock around limiter state | `app.py`, tests | Concurrent/rate-limit tests | Reliability |
| SDK-AUDIT-015 | Request body limiter monkeypatches private `_receive` | Medium | Maintainability/runtime | Pending | Triage ASGI middleware replacement or document accepted framework risk | `app.py`, tests | Body limit tests | Implementation |
| SDK-AUDIT-016 | SDK broadly maps 403 to `ToolDeniedError` | Medium | API/error semantics | Pending | Require policy-denial shape before `ToolDeniedError` | SDK copies/tests | SDK behavior tests | DX/reliability |
| SDK-AUDIT-017 | Frozen SDK dataclasses shallowly immutable | Low | API/maintainability | Pending | Deep-copy/freeze returned mappings where compatible and document residual | SDK copies/tests/docs | SDK mutation tests | DX |
| SDK-AUDIT-018 | Standalone SDK tests thin | Medium | Testing | Pending | Add standalone behavior tests for fixed SDK semantics | SDK tests | Standalone SDK tests | Implementation |
| SDK-AUDIT-019 | No live installed-wheel-to-running-gateway test | Medium | Testing/release | Pending | Add feasible smoke script or defer full live harness with rationale | tests/scripts/CI/docs | Release validation/integration docs | Reliability |
| SDK-AUDIT-020 | No production-like load or multi-worker validation | High | Testing/reliability | Pending | Defer if no safe harness in pass; document exact future harness | docs/tests/CI | Documentation/log evidence | Reliability |
| SDK-AUDIT-021 | Product-platform lacks type-checking gate | Medium | Maintainability/CI | Pending | Add product gateway type-check gate if feasible | CI, pyproject | mypy focused command | Implementation |
| SDK-AUDIT-022 | CI dependency safety check non-blocking | Medium | Security/CI | Pending | Make security audit fail required job or replace with blocking audit | CI | Workflow static validation | Security |
| SDK-AUDIT-023 | CI lint excludes tests/scripts/examples | Low | CI/maintainability | Pending | Broaden package lint for SDK/product where safe | CI | Ruff checks | Implementation |
| SDK-AUDIT-024 | CI install step masks dependency/extra problems | Medium | CI/packaging | Pending | Remove fallbacks for SDK/product and add explicit extras | CI/pyproject | Package install/tests | Release |
| SDK-AUDIT-025 | Publish workflow references missing PyPI docs/pipeline | High | Release/supply chain | Pending | Fix broken references and document actual remaining external release dependency | publish workflow/docs | Link/static validation | Release/security |
| SDK-AUDIT-026 | Publish hash-checked build install incomplete | Medium | Release/CI | Pending | Replace with complete install strategy | publish workflow/requirements | Workflow static validation | Release |
| SDK-AUDIT-027 | SDK release validator install smoke uses `--no-deps` | Low | Packaging/release | Pending | Install wheel with dependencies for smoke | `validate_release.py` | Release validator | Release |
| SDK-AUDIT-028 | SDK strict git ignores vendored copy | Low | Release/consistency | Pending | Add parity validation | SDK release validator/tests | Release validator | Release |
| SDK-AUDIT-029 | Product package lacks equivalent release validator | Medium | Packaging/release | Pending | Add product release validator and CI hook | product scripts/CI | Product validator/build | Release |
| SDK-AUDIT-030 | Product package metadata sparse | Low | Packaging/DX | Pending | Add package metadata and extras | product `pyproject.toml` | Build/metadata check | DX/release |
| SDK-AUDIT-031 | SDK/product remain beta `0.1.0` | Medium | API stability/adoption | Pending | Document stability policy or accept product versioning risk | docs/changelog/pyproject | Docs review | Ease |
| SDK-AUDIT-032 | Ignored local DB artifacts remain | Low | Repo hygiene/data | Pending | Do not delete user data without approval; document accepted risk or move default path | docs/settings | Package validation | Security/release |
| SDK-AUDIT-033 | Token hash pepper not required in production | Medium | Security/credential storage | Pending | Require pepper in non-local mode | `settings.py`, `app.py`, credential tests/docs | Production settings tests | Security |
| SDK-AUDIT-034 | Legacy SHA-256 hashes accepted indefinitely | Medium | Security/migration | Pending | Add explicit legacy-acceptance opt-in/cutoff | credentials/tests/docs | Credential tests | Security |
| SDK-AUDIT-035 | Pepper rotation lacks key ID/multi-pepper model | Medium | Security/operations | Pending | Add key-id/current/previous pepper support if feasible | credentials/tests/docs | Credential tests | Security |
| SDK-AUDIT-036 | Metadata raw-token guard exact-string only | Low | Security/data handling | Pending | Add sensitive-key/value guard | credentials/tests | Credential tests | Security |
| SDK-AUDIT-037 | Credential scope resource type open-ended | Medium | Authorization/API | Pending | Enumerate/validate supported credential resource types | agent models/credentials/tests | Credential scope tests | Security |
| SDK-AUDIT-038 | Gateway auth failure exposes reason codes | Low | Security/info disclosure | Pending | Return generic external 401 while preserving audit reason | `app.py`, auth tests | Gateway auth tests | Security |
| SDK-AUDIT-039 | Caller-controlled trace IDs forwarded as trusted | Low | Observability/trust boundary | Pending | Add server-generated internal request id metadata or document boundary | `app.py`, invocation/tests/docs | Request context tests | Reliability/security |
| SDK-AUDIT-040 | Redaction regexes recompiled every response | Low | Performance/reliability | Pending | Cache compiled redaction rules | `response.py`, tests | Response tests/benchmark light | Reliability |
| SDK-AUDIT-041 | Regex redaction safety heuristic only | Medium | Security/reliability | Pending | Add timeout/safe engine if feasible or document residual risk | response/models/docs/tests | ReDoS tests | Security |
| SDK-AUDIT-042 | GET/DELETE query serialization heuristic secret detection | Medium | Security/API | Pending | Add explicit query allowlist or stronger schema docs/validation | invocation/models/tests/docs | Forwarding tests | Security |
| SDK-AUDIT-043 | Health checker persists arbitrary exception summaries | Low | Security/observability | Pending | Sanitize health error summaries | `health.py`, tests | Upstream health tests | Security |
| SDK-AUDIT-044 | Discovery pagination skip/duplicate under changes | Low | Reliability/API | Pending | Add cursor/snapshot or document semantics | repository/SDK/docs/tests | SDK/repository tests | Reliability |
| SDK-AUDIT-045 | `list_all_tools()` has no total cap | Low | SDK resource usage | Pending | Add optional `max_total` compatible parameter | SDK copies/tests/docs | SDK tests | Reliability/DX |
| SDK-AUDIT-046 | API app monolith | Medium | Maintainability/architecture | Pending | Defer broad refactor unless safe; document | remediation log | N/A | Maintainability |
| SDK-AUDIT-047 | SDK source duplicated | Medium | Maintainability/release | Pending | Add parity validation, consider source unification later | release validator/CI | Parity/release validation | Release |
| SDK-AUDIT-048 | SDK lacks generated API reference | Low | Docs/DX | Pending | Add docs stub or defer generated site | README/docs | Docs review | DX |
| SDK-AUDIT-049 | Credential issuance path under-documented | Medium | Docs/adoption | Pending | Add issuance/rotation guide | SDK/product README/docs | Docs review | Ease/security |
| SDK-AUDIT-050 | Security policy lacks private intake contact | Low | Security/governance | Pending | Add concrete private reporting guidance | SECURITY.md | Docs review | Security/DX |
| SDK-AUDIT-051 | Docs overstate response cap strength | Medium | Docs/reliability | Pending | Align docs to streaming cap behavior/residual risk | READMEs | Docs review | Reliability/DX |
| SDK-AUDIT-052 | Docs claim OpenAPI gated but alias contradicts | Medium | Docs/consistency | Pending | Fix runtime/doc mismatch with SDK-AUDIT-010 | app/docs/tests | Production docs tests | Security/DX |
| SDK-AUDIT-053 | Direct HTTP fixture tokens remain in source | Low | Security/examples | Pending | Validate local-only behavior and strengthen docs if needed | examples/tests/docs | Direct HTTP tests | Security |
| SDK-AUDIT-054 | Dependency range compatibility not proven | Low | Packaging/compatibility | Pending | Add matrix/docs or defer broader CI matrix | CI/docs | Workflow static validation | Release |
| SDK-AUDIT-055 | Release process lacks SDK SBOM | Medium | Supply chain/release | Pending | Add SBOM generation/verification if feasible | CI/publish/docs | Workflow static validation | Security/release |
| SDK-AUDIT-056 | Product deprecation warning debt | Low | Maintainability/future compatibility | Pending | Fix targeted warnings or document debt | source/tests | Full/focused tests | Maintainability |
| SDK-AUDIT-057 | SDK telemetry hook failures only debug-logged | Low | Observability/DX | Pending | Document hook failure semantics or add error hook | SDK README/tests | SDK tests/docs | DX |
| SDK-AUDIT-058 | `status` argument only accepts active | Low | API/DX | Pending | Add deprecation guidance or warning without breaking API | SDK docs/tests | SDK tests/docs | DX |

### Final Remediation Evidence

Date: 2026-05-11.

Final repository state summary:

- This pass processed all 58 findings from `16-sdk-production-readiness-audit-v3.md`.
- Final disposition: 45 fixed, 0 already resolved, 0 invalidated, 11 deferred with rationale, 2 accepted remaining risks.
- A first broad product validation run found one stale test expectation for the newly generic gateway auth error. The test was updated, targeted regressions passed, and the full product suite was rerun successfully.
- The untracked `packages/product-platform/src/product_platform/artifacts/` source package is intentionally now visible because `.gitignore` was narrowed from `artifacts/` to `/artifacts/`; package validation requires this source package to be included.

Validation command references:

| Code | Command | Result |
| --- | --- | --- |
| V1 | `env PYTHONPATH=src python3 -m pytest tests -q --tb=short` in `packages/product-platform` | Passed: 768 passed in 96.18s |
| V2 | `env PYTHONPATH=src python3 -m pytest tests -q --tb=short` in `packages/ophanix-tool-gateway-sdk` | Passed: 10 passed |
| V3 | `python3 -m mypy src/product_platform/tool_gateway src/ophanix_tool_gateway` in `packages/product-platform` | Passed: 14 files |
| V4 | `python3 -m mypy src/ophanix_tool_gateway` in `packages/ophanix-tool-gateway-sdk` | Passed: 2 files |
| V5 | `python3 -m ruff check ... --select E,F,W --ignore E501` over touched product, SDK, AgentMesh, and AgentOS files | Passed; ruff also warned that `packages/agent-mesh/pyproject.toml` uses deprecated top-level ruff config |
| V6 | `python3 -m compileall -q ...` over touched product, SDK, AgentMesh, and AgentOS packages | Passed |
| V7 | `python3 scripts/validate_release.py --out-dir /tmp/ophanix-sdk-remediation-release-final` in `packages/ophanix-tool-gateway-sdk` | Passed: sdist and wheel built, `twine check` passed, SDK validator passed |
| V8 | `python3 scripts/validate_release.py --out-dir /tmp/ophanix-product-remediation-release-final` in `packages/product-platform` | Passed: sdist and wheel built, `twine check` passed, product validator passed |
| V9 | Python `yaml.safe_load` over `.github/workflows/ci.yml` and `.github/workflows/publish.yml` | Passed |
| V10 | Focused warning/auth regression slice: product invocation, agent registration, handshake, trust-card tests plus selected `-W error::DeprecationWarning` tests | Passed: 25 passed, then 5 passed with warnings-as-errors |

Final issue tracking table:

| Issue ID | Title | Severity | Category | Status | Files changed | Root cause | Fix implemented and why production-grade | Tests / validation | Remaining risk | Score impact |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SDK-AUDIT-001 | Manual upstream health check uses async HTTP client in synchronous checker | High | Runtime/reliability | Fixed | `health.py`, `app.py`, `tests/test_tool_gateway_upstream_phase2.py` | Sync health path called async HTTP behavior incorrectly | Added async health-check execution path and route handling with sanitized summaries; proves the default app can run manual checks without coroutine misuse | V1, V5, V6, focused upstream tests | None known | Raises implementation/reliability under remaining high caps |
| SDK-AUDIT-002 | Tool invocation holds DB transaction open across upstream network call | High | Runtime/reliability | Fixed | `app.py`, `invocation.py`, forwarding/runtime tests | Network I/O was coupled to the main SQLite transaction scope | Split invocation into short preload and post-call update transactions; network call now runs outside the primary transaction, reducing lock contention and partial-failure blast radius | V1, V5, V6 | SQLite architecture still deferred in SDK-AUDIT-003 | Raises implementation/reliability but not beyond cap |
| SDK-AUDIT-003 | Product runtime database layer is SQLite-only with one shared connection | High | Architecture/reliability | Deferred with rationale | `settings.py`, `app.py`, README, deployment tests | Storage backend architecture is broader than a safe SDK remediation pass | Added production fail-closed guard for SQLite unless explicitly overridden and documented the unsupported production posture; durable fix requires a real pooled production database backend and migration strategy | V1, V8 | Broad production still blocked without a production DB backend | Caps implementation and reliability at 6 |
| SDK-AUDIT-004 | Production guard accepts arbitrary SQLite URLs | Medium | Deployment safety | Fixed | `settings.py`, `app.py`, product README, deployment tests | Production checks only covered the default local DB path | Non-local environments now reject SQLite by default unless explicitly allowed, which makes unsafe storage an intentional operator decision | V1, V8 | SQLite override remains an operator escape hatch | Raises reliability/security |
| SDK-AUDIT-005 | Upstream authentication unsupported beyond none | High | API/security/adoption | Deferred with rationale | Product README, runtime docs | Secure upstream auth needs secret storage, target-specific policy, rotation, and test fixtures | Documented `auth_mode="none"` support boundary and left protected-upstream auth as explicit architecture work instead of pretending unsupported modes are production-grade | V1 docs/runtime validation | Protected upstream adoption remains blocked | Caps ease/security |
| SDK-AUDIT-006 | No server-side idempotency or safe retry contract | High | Reliability/API | Deferred with rationale | Product README/remediation log | Idempotency requires API contract, persistence schema, replay semantics, and SDK integration | Documented residual risk and future required design; no shallow retry/idempotency workaround was introduced | V1 | Retry ambiguity remains for mutating upstream tools | Caps implementation/reliability |
| SDK-AUDIT-007 | Upstream URL DNS failure and rebinding gaps | High | Security/SSRF | Fixed | `models.py`, `invocation.py`, `tests/test_tool_gateway_upstream_phase1.py`, forwarding tests | URL validation allowed unresolved hosts in production and did not revalidate at runtime | Production now fails closed on unresolved upstream hosts unless explicitly allowed, and runtime execution revalidates URLs before calls; this materially hardens SSRF boundaries | V1, V5, V6 | Network-layer egress controls are still recommended | Raises security/reliability |
| SDK-AUDIT-008 | Response byte caps checked after HTTPX materializes bodies | High | Reliability/resource safety | Fixed | SDK copies, `invocation.py`, SDK/product tests, READMEs | `response.content` materialized large bodies before cap enforcement | Default SDK and gateway executors now stream response chunks and enforce incremental byte caps before full parse/materialization | V1, V2, V3, V4, V5, V6 | Custom injected clients/executors must preserve equivalent behavior | Raises reliability |
| SDK-AUDIT-009 | Inactive response policy can bypass redaction while storing full response | High | Security/data handling | Fixed | `app.py`, `response.py`, `tests/test_tool_gateway_response_phase3.py` | Persistence logic could store raw bodies when policy was inactive | Full-response persistence now requires an active response policy; disabled policy no longer stores unredacted runtime bodies | V1, V5, V6 | Disabled policy still means response payload is not redacted for caller by design | Raises security |
| SDK-AUDIT-010 | OpenAPI alias exposed when docs disabled | Medium | Security/docs consistency | Fixed | `app.py`, product README, auth tests | Alias route was not gated with the docs flag | `/api/openapi.json` now follows docs/OpenAPI gating consistently | V1, V9 | None known | Raises security/DX |
| SDK-AUDIT-011 | System config advertises docs URL when disabled | Low | Docs/runtime consistency | Fixed | `api/models.py`, `app.py`, tests | Public config used a static docs URL regardless of runtime docs setting | Config now returns `docs_url=None` when docs are disabled, matching actual behavior | V1 | None known | Raises DX consistency |
| SDK-AUDIT-012 | Production safety limits can be disabled | Medium | Deployment/reliability | Fixed | `settings.py`, `app.py`, deployment tests, README | Non-positive limits were accepted in production-like modes | Production startup validation now rejects disabled/non-positive body and response caps and related unsafe safety limits | V1, V8 | Operators can still choose large but positive limits | Raises reliability/security |
| SDK-AUDIT-013 | Gateway rate limiter is process-local | Medium | Reliability/security | Deferred with rationale | Product README/remediation log | Distributed rate limiting needs shared state such as Redis, gateway edge controls, or load-balancer integration | Documented process-local scope and production requirement for distributed throttling; implemented locking under SDK-AUDIT-014 but not a distributed limiter | V1 | Multi-worker/global abuse control remains incomplete | Caps reliability |
| SDK-AUDIT-014 | Rate limiter dictionary has no concurrency guard | Low | Reliability/correctness | Fixed | `app.py`, auth tests | Mutable limiter state was updated without synchronization | Added lock-protected limiter updates, avoiding state races in concurrent request handling | V1, V5, V6 | Process-local scope remains SDK-AUDIT-013 | Raises reliability |
| SDK-AUDIT-015 | Request body limiter monkeypatches private `_receive` | Medium | Maintainability/runtime | Deferred with rationale | Remediation log | Replacing the private receive wrapper with a full ASGI middleware is broader and risks regressions late in the pass | Existing body cap behavior remains validated; ASGI middleware rewrite is deferred as targeted framework work | V1 | Private Starlette/FastAPI receive internals remain a maintenance risk | Caps implementation polish |
| SDK-AUDIT-016 | SDK broadly maps 403 to `ToolDeniedError` | Medium | API/error semantics | Fixed | SDK copies, SDK tests, product SDK tests | SDK classified all 403 responses as policy denials | SDK now requires a structured denial shape before raising `ToolDeniedError`; generic 403 remains a gateway API error | V1, V2, V3, V4 | None known | Raises DX/reliability |
| SDK-AUDIT-017 | Frozen SDK dataclasses shallowly immutable | Low | API/maintainability | Fixed | SDK copies, SDK tests, README | Returned mappings/lists remained mutable through frozen dataclasses | SDK deep-freezes/deep-copies public result payloads so consumers cannot mutate cached SDK state accidentally | V1, V2, V3, V4 | None known | Raises DX correctness |
| SDK-AUDIT-018 | Standalone SDK tests thin | Medium | Testing | Fixed | `tests/test_sdk_behavior.py` | Standalone SDK behavior coverage did not exercise hardened semantics | Added tests for 403 mapping, `max_total`, streaming caps, and deprecation behavior | V2 | No live running-gateway test, tracked separately | Raises implementation confidence |
| SDK-AUDIT-019 | No live installed-wheel-to-running-gateway test | Medium | Testing/release | Deferred with rationale | SDK/product release validators, CI docs | A true live gateway harness requires orchestration, seeded credentials, network fixtures, and CI runtime support | Wheel install smoke and package validators were strengthened, but the live installed-wheel-to-running-gateway contract test remains deferred | V7, V8 | Real gateway compatibility is not proven end to end | Caps reliability/release confidence |
| SDK-AUDIT-020 | No production-like load or multi-worker validation | High | Testing/reliability | Deferred with rationale | README/remediation log | Load and multi-worker validation needs a repeatable harness and production-like backing services | Documented required future harness; no synthetic local test was counted as production load evidence | V1 | Broad production reliability remains unproven | Caps implementation/reliability at 6 |
| SDK-AUDIT-021 | Product-platform lacks type-checking gate | Medium | Maintainability/CI | Fixed | `.github/workflows/ci.yml`, product `pyproject.toml` | CI lacked a product gateway mypy gate | Added focused product mypy configuration and CI gate for gateway/SDK surfaces | V3, V9 | Type coverage is focused, not whole-repo | Raises implementation |
| SDK-AUDIT-022 | CI dependency safety check non-blocking | Medium | Security/CI | Fixed | `.github/workflows/ci.yml` | Security audit was advisory and could be bypassed | CI now runs blocking `pip-audit` for the audited package installs | V9 | Actual CI execution still depends on remote environment | Raises security/release |
| SDK-AUDIT-023 | CI lint excludes tests/scripts/examples | Low | CI/maintainability | Fixed | `.github/workflows/ci.yml` | Lint coverage was source-only | CI lint surface now includes product/SDK tests and scripts where safe | V5, V9 | Whole monorepo lint debt remains outside this SDK pass | Raises maintainability |
| SDK-AUDIT-024 | CI install step masks dependency/extra problems | Medium | CI/packaging | Fixed | `.github/workflows/ci.yml` | Fallback install paths could hide broken extras/dependencies | Product and SDK CI install paths now fail directly instead of silently falling back | V7, V8, V9 | Full hosted CI still needs to run | Raises release confidence |
| SDK-AUDIT-025 | Publish workflow references missing PyPI docs/pipeline | High | Release/supply chain | Fixed | `.github/workflows/publish.yml`, `docs/internal/pypi-publishing.md` | Publish workflow pointed to missing release documentation | Added internal publishing documentation and fixed workflow references so release operators have an auditable path | V9 | Actual publishing credentials and repository policy are external | Raises release/security |
| SDK-AUDIT-026 | Publish hash-checked build install incomplete | Medium | Release/CI | Fixed | `.github/workflows/publish.yml` | Incomplete hash-checked install created false supply-chain confidence | Replaced with complete pinned build/twine install flow that can actually execute | V9 | Hash pinning can be further tightened later | Raises release |
| SDK-AUDIT-027 | SDK release validator install smoke uses `--no-deps` | Low | Packaging/release | Fixed | SDK `scripts/validate_release.py` | Validator skipped dependency resolution | Wheel smoke install now installs dependencies, proving consumer install viability more accurately | V7 | None known | Raises release confidence |
| SDK-AUDIT-028 | SDK strict git ignores vendored copy | Low | Release/consistency | Fixed | SDK `scripts/validate_release.py` | Release validator did not verify product-vendored SDK parity | Validator compares standalone SDK source with vendored product copy before release | V7 | Source duplication still tracked by SDK-AUDIT-047 | Raises consistency |
| SDK-AUDIT-029 | Product package lacks equivalent release validator | Medium | Packaging/release | Fixed | Product `scripts/validate_release.py`, CI, pyproject | Product package had no equivalent artifact validation | Added product release validator with artifact denylist, metadata/import checks, wheel install smoke, and CI hook | V8, V9 | None known | Raises release |
| SDK-AUDIT-030 | Product package metadata sparse | Low | Packaging/DX | Fixed | Product `pyproject.toml` | Package metadata lacked classifiers, URLs, extras, maintainer fields | Added metadata, optional dependencies, hatch build controls, package includes/excludes, and typing classifier | V8 | Version remains beta by SDK-AUDIT-031 | Raises DX/release |
| SDK-AUDIT-031 | SDK/product remain beta `0.1.0` | Medium | API stability/adoption | Accepted remaining risk | READMEs, pyproject metadata | Project is still pre-GA and API stability is not yet proven | Documented beta/stability status rather than renumbering without release authority | V7, V8 | External adopters must treat API as beta | Caps ease of use at 7 |
| SDK-AUDIT-032 | Ignored local DB artifacts remain | Low | Repo hygiene/data | Accepted remaining risk | `.gitignore`, product pyproject, product validator | Local artifacts may be user data; deleting them without approval would be destructive | Package excludes and release validator denylist prevent DB artifacts from shipping; local cleanup is intentionally not performed in this pass | V8 | Local workspace can still contain ignored DB files | Low release/security residual |
| SDK-AUDIT-033 | Token hash pepper not required in production | Medium | Security/credential storage | Fixed | `settings.py`, `app.py`, credential tests, README | Production mode allowed unpeppered token hashes | Non-local startup now requires token-hash pepper configuration | V1 | Pepper custody is still an operator secret-management responsibility | Raises security |
| SDK-AUDIT-034 | Legacy SHA-256 hashes accepted indefinitely | Medium | Security/migration | Fixed | `credentials.py`, credential tests, README | Legacy hashes were accepted without explicit migration gate | Legacy hash acceptance now requires explicit opt-in, enabling migration without indefinite silent weak mode | V1, V5, V6 | Existing legacy deployments need planned migration | Raises security |
| SDK-AUDIT-035 | Pepper rotation lacks key ID/multi-pepper model | Medium | Security/operations | Fixed | `credentials.py`, credential tests, README | Hash records did not identify pepper version or support previous peppers | Added key-id/current/previous pepper handling so rotation can verify old tokens while issuing new keyed hashes | V1, V5, V6 | External secret rotation process remains operator-owned | Raises security |
| SDK-AUDIT-036 | Metadata raw-token guard exact-string only | Low | Security/data handling | Fixed | `credentials.py`, credential tests | Metadata guard only caught exact raw token values | Added sensitive key normalization and value-pattern checks to reject common secret-bearing metadata | V1 | Heuristics cannot prove arbitrary secret absence | Raises security |
| SDK-AUDIT-037 | Credential scope resource type open-ended | Medium | Authorization/API | Fixed | `agents/models.py`, credential tests | Credential scopes accepted arbitrary resource types | Added supported resource type validation for `agent`, `claim`, and `tool` scopes | V1 | Future resource types require deliberate schema extension | Raises authorization confidence |
| SDK-AUDIT-038 | Gateway auth failure exposes reason codes | Low | Security/info disclosure | Fixed | `app.py`, auth/invocation tests, SDK tests | External 401 body included internal auth reason details | Gateway now returns generic external auth failure while preserving structured internal/audit reason handling | V1, V2 | Operators must use logs/audit for detailed diagnosis | Raises security |
| SDK-AUDIT-039 | Caller-controlled trace IDs forwarded as trusted | Low | Observability/trust boundary | Fixed | `api/models.py`, `app.py`, invocation/runtime tests | Client request ID doubled as trusted internal request identity | Added server-generated request identity alongside caller-provided request/correlation IDs | V1 | Cross-service propagation policy can be further formalized | Raises observability reliability |
| SDK-AUDIT-040 | Redaction regexes recompiled every response | Low | Performance/reliability | Fixed | `response.py`, response tests | Regex rules were compiled repeatedly during response processing | Added cached compiled redaction rule handling to reduce per-response overhead | V1, V5, V6 | Regex safety still tracked by SDK-AUDIT-041 | Raises reliability/performance |
| SDK-AUDIT-041 | Regex redaction safety heuristic only | Medium | Security/reliability | Deferred with rationale | Remediation log, response docs | Robust regex timeouts/safe-regex engine require dependency and API decisions | Compile caching remains, but safe-regex enforcement/timeout is deferred with explicit residual risk | V1 | ReDoS risk from pathological accepted regexes remains bounded only by validation heuristics | Caps security/reliability |
| SDK-AUDIT-042 | GET/DELETE payload query serialization heuristic secret detection | Medium | Security/API | Deferred with rationale | README/remediation log | Explicit query allowlists require API/model changes for target parameter schemas | Existing secret heuristics remain; durable allowlist model is deferred | V1 | Secret-bearing GET/DELETE payload risk remains if users bypass heuristics | Caps security |
| SDK-AUDIT-043 | Health checker persists arbitrary exception summaries | Low | Security/observability | Fixed | `health.py`, upstream health tests | Exception strings could include sensitive URLs or internal details | Health summaries now sanitize URLs and error messages before persistence/response | V1, V5, V6 | Third-party exception text can still be semantically revealing | Raises security |
| SDK-AUDIT-044 | Discovery pagination skip/duplicate under changes | Low | Reliability/API | Deferred with rationale | SDK README/remediation log | Stable cursor/snapshot pagination requires repository/API contract changes | Documented current offset semantics; added `max_total` for unbounded collection risk under SDK-AUDIT-045 | V1, V2 | Concurrent catalog mutation can still skip/duplicate across pages | Low reliability residual |
| SDK-AUDIT-045 | `list_all_tools()` has no total cap | Low | SDK resource usage | Fixed | SDK copies, SDK tests, README/API reference | SDK accumulated pages until exhaustion with no caller cap | Added compatible `max_total` parameter to bound total accumulated tool records | V1, V2, V3, V4 | Offset semantics remain SDK-AUDIT-044 | Raises DX/reliability |
| SDK-AUDIT-046 | API app monolith | Medium | Maintainability/architecture | Deferred with rationale | Remediation log | Large route/app refactor is broad and high-risk relative to remediation scope | No superficial split was made; future work should modularize gateway routes/services after behavior is stable | V1 | Maintainability risk remains | Caps implementation polish |
| SDK-AUDIT-047 | SDK source duplicated | Medium | Maintainability/release | Fixed | SDK validator, SDK/product SDK copies, CI | Standalone and vendored SDK copies can drift | Added release-time parity validation and synchronized copies; source unification remains future architecture work | V7, V8 | Duplication still exists, but release drift is guarded | Raises release confidence |
| SDK-AUDIT-048 | SDK lacks generated API reference | Low | Docs/DX | Fixed | `API_REFERENCE.md`, SDK pyproject, README | SDK package had no packaged API reference | Added API reference document and included it in release artifacts | V7 | Not generated from code yet | Raises DX |
| SDK-AUDIT-049 | Credential issuance path under-documented | Medium | Docs/adoption | Fixed | SDK README, product README | Consumers lacked production credential issuance/rotation guidance | Added credential issuance, pepper, legacy migration, and rotation documentation | V1 docs validation, V7, V8 | Full operator runbook can be expanded | Raises ease/security |
| SDK-AUDIT-050 | Security policy lacks private intake contact | Low | Security/governance | Fixed | SDK `SECURITY.md` | Private vulnerability reporting target was vague | Added concrete GitHub private advisory intake URL | Docs review, V7 | Depends on repository security configuration | Raises governance |
| SDK-AUDIT-051 | Docs overstate response cap strength | Medium | Docs/reliability | Fixed | SDK README, product README, SDK/API tests | Docs claimed cap behavior stronger than implementation | Implementation now streams before materialization by default and docs describe residual custom-client expectations | V1, V2, V7, V8 | Custom clients can still violate cap expectations | Raises reliability/DX |
| SDK-AUDIT-052 | Docs claim OpenAPI gated but runtime alias contradicts | Medium | Docs/consistency | Fixed | `app.py`, README, tests | Runtime contradicted documentation | Fixed runtime alias gating and kept docs aligned | V1, V9 | None known | Raises security/DX |
| SDK-AUDIT-053 | Direct HTTP fixture tokens remain in source | Low | Security/examples | Fixed | Product README, direct HTTP example tests/docs | Fixture tokens could be mistaken for real credentials | Validated local-only fixtures and strengthened docs that they are deterministic demo tokens only | V1 | Demo tokens still exist as test fixtures by design | Low security/DX residual |
| SDK-AUDIT-054 | Dependency range compatibility not proven | Low | Packaging/compatibility | Fixed | CI workflow, README, pyproject metadata | Compatibility range was declared without clear matrix evidence | CI/docs now declare supported Python/runtime matrix and package validators prove current local build/install compatibility | V7, V8, V9 | Full dependency-min/max matrix still desirable | Raises release confidence |
| SDK-AUDIT-055 | Release process lacks SDK SBOM | Medium | Supply chain/release | Fixed | Publish workflow, publishing docs | Publish workflow produced no SBOM evidence | Added SBOM generation steps for SDK and product package release paths | V9 | SBOM provenance/signing policy remains external | Raises security/release |
| SDK-AUDIT-056 | Product deprecation warning debt | Low | Maintainability/future compatibility | Fixed | AgentMesh identity/trust files, AgentOS AMB models, product pyproject, warning tests | Product tests emitted deprecated `datetime.utcnow()` and Pydantic serializer/config warnings | Replaced touched warning sources with timezone-aware helpers/field serializers and pinned pytest-asyncio fixture loop scope; full product suite now runs without warning summary | V1, V5, V6, V10 | Some unrelated monorepo warning debt may remain outside product SDK surface | Raises maintainability |
| SDK-AUDIT-057 | SDK telemetry hook failures only debug-logged | Low | Observability/DX | Fixed | SDK README | Hook failure semantics were implicit | Documented that telemetry hook exceptions are swallowed/debug-logged so hooks cannot break SDK calls | V2, V7 | No separate hook-error callback | Raises DX clarity |
| SDK-AUDIT-058 | `status` argument only accepts active | Low | API/DX | Fixed | SDK copies, SDK tests, README/API reference | Compatibility parameter looked like a real filter | Added deprecation warning/docs while preserving API compatibility | V1, V2, V3, V4 | Parameter remains until a future breaking release | Raises DX |

Changed file summary:

- Runtime/security: `packages/product-platform/src/product_platform/api/app.py`, `api/models.py`, `api/settings.py`, `tool_gateway/health.py`, `tool_gateway/invocation.py`, `tool_gateway/models.py`, `tool_gateway/response.py`, `agents/credentials.py`, `agents/models.py`.
- SDK: both SDK copies under `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py` and `packages/product-platform/src/ophanix_tool_gateway/sdk.py`, plus standalone SDK tests and API reference.
- Tests: gateway auth, forwarding, invocation, response policy, upstream health/SSRF, credential, SDK behavior, deployment settings, and warning regression coverage.
- Packaging/release/CI: `.github/workflows/ci.yml`, `.github/workflows/publish.yml`, `.gitignore`, product/SDK `pyproject.toml`, SDK/product release validators, `docs/internal/pypi-publishing.md`.
- Warning cleanup: AgentMesh identity/trust timestamp helpers and AgentOS AMB Pydantic serializer updates.

Remaining unresolved issues:

- Deferred with rationale: SDK-AUDIT-003, SDK-AUDIT-005, SDK-AUDIT-006, SDK-AUDIT-013, SDK-AUDIT-015, SDK-AUDIT-019, SDK-AUDIT-020, SDK-AUDIT-041, SDK-AUDIT-042, SDK-AUDIT-044, SDK-AUDIT-046.
- Accepted remaining risks: SDK-AUDIT-031, SDK-AUDIT-032.
- Invalid findings: none.
- Already resolved without changes: none.

Updated scoring matrix:

| Category | Previous V3 score | Updated score | Raised/lowered/upheld | Reason | Remaining score cap | Blocking next score | Blocking 8 / 10 | Blocking 9 / 10 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Implementation quality | 6 / 10 | 6 / 10 | Upheld | Major runtime, package, CI, type, and test issues are fixed, and 768 product tests now pass. The score remains capped because SQLite-only runtime architecture, missing idempotency, missing live installed-wheel gateway test, missing load/multi-worker validation, and app monolith risks remain. | 6 | Resolve SDK-AUDIT-003, SDK-AUDIT-006, SDK-AUDIT-019, SDK-AUDIT-020 | Add production DB/pooling, idempotency schema/API, live gateway harness, multi-worker/load evidence | Modularize API app, remove SDK duplication, prove full-package CI/release on hosted runners |
| Ease of use | 7 / 10 | 7 / 10 | Upheld | API reference, docs, credential guidance, deprecation notes, and release docs improved. It remains capped by beta status, unsupported protected-upstream auth, and lack of true external onboarding/live-gateway proof. | 7 | Resolve SDK-AUDIT-005 and SDK-AUDIT-031 or publish explicit GA contract | Implement upstream auth, publish GA stability/migration docs, add live external quickstart validation | Add generated docs, migration guides, richer examples, and proven external adopter workflow |
| Security and reliability | 5 / 10 | 6 / 10 | Raised | Streaming caps, response-policy storage, SSRF fail-closed behavior, production safety guards, pepper requirement/rotation, generic auth errors, sanitized health errors, and blocking audit/SBOM workflow materially reduce risk. Multiple high/medium unresolved reliability/security items still cap the score. | 6 | Resolve SDK-AUDIT-003, SDK-AUDIT-005, SDK-AUDIT-006, SDK-AUDIT-013, SDK-AUDIT-020, SDK-AUDIT-041, SDK-AUDIT-042 | Add upstream auth, idempotency, distributed rate limiting, safe regex/timeouts, explicit query allowlists, production DB/load evidence | Formal threat model, chaos/failure tests, provenance/signing, production operational runbooks |

Required fixes to reach production readiness:

1. Replace or augment SQLite-only runtime storage with a supported production database/backend, migration strategy, and multi-worker validation.
2. Implement protected upstream authentication with secret storage, rotation, target policy, and end-to-end tests.
3. Add server-side idempotency and retry semantics for tool invocation.
4. Add distributed rate limiting or documented edge-enforced throttling with automated validation.
5. Add live installed-wheel-to-running-gateway integration tests and production-like load/multi-worker tests.
6. Replace private request receive monkeypatching with durable ASGI middleware.
7. Add safe regex timeout/engine controls and explicit GET/DELETE query allowlists.

Required fixes to reach 8 out of 10:

- Complete all production-readiness fixes above, publish a stable upstream-auth/idempotency API, prove live package integration, and make production docs/onboarding externally repeatable.

Required fixes to reach 9 out of 10:

- Add GA-level compatibility policy, generated API docs, migration notes, provenance/SBOM signing, complete threat model, chaos/load evidence, and remove major maintainability liabilities such as app monolith and duplicated SDK source ownership.

Recommended remediation order:

1. Production database backend and multi-worker transaction model.
2. Upstream auth and secret-backed target execution.
3. Idempotency and retry contract.
4. Live installed-wheel gateway harness plus load validation.
5. Distributed rate limiting and request/body middleware rewrite.
6. Regex/query allowlist hardening.
7. API modularization and SDK source unification.

Final strict assessment:

The remediation pass substantially improved the SDK and gateway surface, and all implemented fixes are validated by focused and broad commands. Broad external production adoption is still not defensible because several high-severity architecture and reliability issues were intentionally deferred rather than papered over. Constrained internal adoption is defensible only for single-process or explicitly guarded deployments that use `auth_mode="none"` upstream targets, accept beta API status, operate with documented idempotency discipline, and keep production safety guards enabled.

---

## 2026-05-11 - V3 Continuation Remediation Pass

Pass name: `SDK-AUDIT-001` through `SDK-AUDIT-058` continuation remediation after the first V3 execution pass.

### Starting Repository State Summary

- Current worktree already contains the prior V3 remediation changes and the untracked V3 audit artifact.
- Prior V3 final disposition was 45 fixed, 11 deferred with rationale, and 2 accepted remaining risks.
- This continuation pass re-tracks all 58 IDs before any further edits, with current status based on the previously validated repository state rather than the original audit assumptions.
- Current uncommitted source surface includes CI, release validators, product gateway runtime, SDK copies, docs, tests, package metadata, AgentMesh warning cleanup, AgentOS AMB warning cleanup, the new SDK API reference, product release script, and unignored product `artifacts` source package.

### Continuation Remediation Tracking Table

| Issue ID | Title | Severity | Category | Current status | Planned action | Files likely affected | Validation required | Score impact |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SDK-AUDIT-001 | Manual upstream health check uses async HTTP client in synchronous checker | High | Runtime/reliability | Fixed | Re-validate only unless regression found | `health.py`, upstream tests | Focused upstream tests, full suite | Implementation/reliability |
| SDK-AUDIT-002 | Tool invocation holds DB transaction open across upstream network call | High | Runtime/reliability | Fixed | Re-validate only unless regression found | `app.py`, `invocation.py`, forwarding tests | Invocation/forwarding tests | Implementation/reliability |
| SDK-AUDIT-003 | Product runtime database layer is SQLite-only with one shared connection | High | Architecture/reliability | Deferred with rationale | Re-evaluate feasibility; keep production guard if full backend remains out of safe scope | DB/settings/docs/tests | Production settings tests, package validation | Implementation/reliability |
| SDK-AUDIT-004 | Production guard accepts arbitrary SQLite URLs | Medium | Deployment safety | Fixed | Re-validate only unless regression found | `settings.py`, `app.py`, deployment tests | Production settings tests | Reliability/security |
| SDK-AUDIT-005 | Upstream authentication unsupported beyond none | High | API/security/adoption | Deferred with rationale | Re-open runtime model to see whether a minimal secret-backed auth mode can be safely implemented | upstream models/invocation/docs/tests | Upstream auth tests, forwarding tests | Ease/security |
| SDK-AUDIT-006 | No server-side idempotency or safe retry contract | High | Reliability/API | Deferred with rationale | Re-open invocation/repository schema; implement if possible without unsafe replay semantics, otherwise document product design requirement | API/repository/migrations/SDK/docs | Invocation replay tests if implemented | Implementation/reliability |
| SDK-AUDIT-007 | Upstream URL DNS failure and rebinding gaps | High | Security/SSRF | Fixed | Re-validate only unless regression found | `models.py`, `invocation.py`, SSRF tests | SSRF tests | Security/reliability |
| SDK-AUDIT-008 | Response byte caps checked after HTTPX materializes bodies | High | Reliability/resource safety | Fixed | Re-validate only unless regression found | SDK/invocation/tests/docs | Oversized streaming response tests | Reliability |
| SDK-AUDIT-009 | Inactive response policy can bypass redaction while storing full response | High | Security/data handling | Fixed | Re-validate only unless regression found | `response.py`, `app.py`, response tests | Response policy tests | Security |
| SDK-AUDIT-010 | OpenAPI alias exposed when docs disabled | Medium | Security/docs consistency | Fixed | Re-validate only unless regression found | `app.py`, README/tests | Production docs route tests | Security/DX |
| SDK-AUDIT-011 | System config advertises docs URL when disabled | Low | Docs/runtime consistency | Fixed | Re-validate only unless regression found | `app.py`, tests | System config tests | DX |
| SDK-AUDIT-012 | Production safety limits can be disabled | Medium | Deployment/reliability | Fixed | Re-validate only unless regression found | `settings.py`, `app.py`, README/tests | Production settings tests | Reliability/security |
| SDK-AUDIT-013 | Gateway rate limiter is process-local | Medium | Reliability/security | Deferred with rationale | Re-evaluate config guard/docs; distributed limiter likely remains external architecture | docs/settings/tests | Docs/readiness validation | Reliability |
| SDK-AUDIT-014 | Rate limiter dictionary has no concurrency guard | Low | Reliability/correctness | Fixed | Re-validate only unless regression found | `app.py`, tests | Rate-limit tests | Reliability |
| SDK-AUDIT-015 | Request body limiter monkeypatches private `_receive` | Medium | Maintainability/runtime | Deferred with rationale | Replace with durable ASGI middleware if feasible | `app.py`, middleware/tests | Body limit tests, full suite | Implementation |
| SDK-AUDIT-016 | SDK broadly maps 403 to `ToolDeniedError` | Medium | API/error semantics | Fixed | Re-validate only unless regression found | SDK copies/tests | SDK behavior tests | DX/reliability |
| SDK-AUDIT-017 | Frozen SDK dataclasses shallowly immutable | Low | API/maintainability | Fixed | Re-validate only unless regression found | SDK copies/tests/docs | SDK mutation tests | DX |
| SDK-AUDIT-018 | Standalone SDK tests thin | Medium | Testing | Fixed | Re-validate only unless regression found | SDK tests | Standalone SDK tests | Implementation |
| SDK-AUDIT-019 | No live installed-wheel-to-running-gateway test | Medium | Testing/release | Deferred with rationale | Explore adding a hermetic smoke script; defer only if process startup/seeding is too brittle for this pass | tests/scripts/CI/docs | Release validation/integration smoke | Reliability |
| SDK-AUDIT-020 | No production-like load or multi-worker validation | High | Testing/reliability | Deferred with rationale | Explore bounded local concurrency test; true load harness likely remains deferred | docs/tests/CI | Focused concurrency tests if added | Reliability |
| SDK-AUDIT-021 | Product-platform lacks type-checking gate | Medium | Maintainability/CI | Fixed | Re-validate only unless regression found | CI, pyproject | mypy focused command | Implementation |
| SDK-AUDIT-022 | CI dependency safety check non-blocking | Medium | Security/CI | Fixed | Re-validate only unless regression found | CI | Workflow static validation | Security |
| SDK-AUDIT-023 | CI lint excludes tests/scripts/examples | Low | CI/maintainability | Fixed | Re-validate only unless regression found | CI | Ruff checks | Implementation |
| SDK-AUDIT-024 | CI install step masks dependency/extra problems | Medium | CI/packaging | Fixed | Re-validate only unless regression found | CI/pyproject | Package install/tests | Release |
| SDK-AUDIT-025 | Publish workflow references missing PyPI docs/pipeline | High | Release/supply chain | Fixed | Re-validate only unless regression found | publish workflow/docs | Link/static validation | Release/security |
| SDK-AUDIT-026 | Publish hash-checked build install incomplete | Medium | Release/CI | Fixed | Re-validate only unless regression found | publish workflow/requirements | Workflow static validation | Release |
| SDK-AUDIT-027 | SDK release validator install smoke uses `--no-deps` | Low | Packaging/release | Fixed | Re-validate only unless regression found | `validate_release.py` | Release validator | Release |
| SDK-AUDIT-028 | SDK strict git ignores vendored copy | Low | Release/consistency | Fixed | Re-validate only unless regression found | SDK release validator/tests | Release validator | Release |
| SDK-AUDIT-029 | Product package lacks equivalent release validator | Medium | Packaging/release | Fixed | Re-validate only unless regression found | product scripts/CI | Product validator/build | Release |
| SDK-AUDIT-030 | Product package metadata sparse | Low | Packaging/DX | Fixed | Re-validate only unless regression found | product `pyproject.toml` | Build/metadata check | DX/release |
| SDK-AUDIT-031 | SDK/product remain beta `0.1.0` | Medium | API stability/adoption | Accepted remaining risk | Re-evaluate whether a release/stability policy doc can reduce adoption risk without fake GA versioning | docs/changelog/pyproject | Docs/release validation | Ease |
| SDK-AUDIT-032 | Ignored local DB artifacts remain | Low | Repo hygiene/data | Accepted remaining risk | Verify package exclusion; do not delete user DB artifacts without explicit product decision | docs/settings/package validator | Package validation | Security/release |
| SDK-AUDIT-033 | Token hash pepper not required in production | Medium | Security/credential storage | Fixed | Re-validate only unless regression found | `settings.py`, `app.py`, credential tests/docs | Production settings tests | Security |
| SDK-AUDIT-034 | Legacy SHA-256 hashes accepted indefinitely | Medium | Security/migration | Fixed | Re-validate only unless regression found | credentials/tests/docs | Credential tests | Security |
| SDK-AUDIT-035 | Pepper rotation lacks key ID/multi-pepper model | Medium | Security/operations | Fixed | Re-validate only unless regression found | credentials/tests/docs | Credential tests | Security |
| SDK-AUDIT-036 | Metadata raw-token guard exact-string only | Low | Security/data handling | Fixed | Re-validate only unless regression found | credentials/tests | Credential tests | Security |
| SDK-AUDIT-037 | Credential scope resource type open-ended | Medium | Authorization/API | Fixed | Re-validate only unless regression found | agent models/credentials/tests | Credential scope tests | Security |
| SDK-AUDIT-038 | Gateway auth failure exposes reason codes | Low | Security/info disclosure | Fixed | Re-validate only unless regression found | `app.py`, auth tests | Gateway auth tests | Security |
| SDK-AUDIT-039 | Caller-controlled trace IDs forwarded as trusted | Low | Observability/trust boundary | Fixed | Re-validate only unless regression found | `app.py`, invocation/tests/docs | Request context tests | Reliability/security |
| SDK-AUDIT-040 | Redaction regexes recompiled every response | Low | Performance/reliability | Fixed | Re-validate only unless regression found | `response.py`, tests | Response tests | Reliability |
| SDK-AUDIT-041 | Regex redaction safety heuristic only | Medium | Security/reliability | Deferred with rationale | Strengthen validation/caps if feasible without adding unsafe dependency | response/models/docs/tests | ReDoS tests | Security |
| SDK-AUDIT-042 | GET/DELETE payload query serialization heuristic secret detection | Medium | Security/API | Deferred with rationale | Explore explicit target-level allowlist with safe compatibility defaults | invocation/models/tests/docs | Forwarding tests | Security |
| SDK-AUDIT-043 | Health checker persists arbitrary exception summaries | Low | Security/observability | Fixed | Re-validate only unless regression found | `health.py`, tests | Upstream health tests | Security |
| SDK-AUDIT-044 | Discovery pagination skip/duplicate under changes | Low | Reliability/API | Deferred with rationale | Explore snapshot/cursor field compatibility; otherwise document offset semantics | repository/SDK/docs/tests | SDK/repository tests | Reliability |
| SDK-AUDIT-045 | `list_all_tools()` has no total cap | Low | SDK resource usage | Fixed | Re-validate only unless regression found | SDK copies/tests/docs | SDK tests | Reliability/DX |
| SDK-AUDIT-046 | API app monolith | Medium | Maintainability/architecture | Deferred with rationale | Do not broad-refactor unless a small safe route extraction is clearly isolated | remediation log/source if safe | Full suite | Maintainability |
| SDK-AUDIT-047 | SDK source duplicated | Medium | Maintainability/release | Fixed | Re-validate only unless regression found | release validator/CI | Parity/release validation | Release |
| SDK-AUDIT-048 | SDK lacks generated API reference | Low | Docs/DX | Fixed | Re-validate only unless regression found | README/docs | Docs/release validation | DX |
| SDK-AUDIT-049 | Credential issuance path under-documented | Medium | Docs/adoption | Fixed | Re-validate only unless regression found | SDK/product README/docs | Docs review | Ease/security |
| SDK-AUDIT-050 | Security policy lacks private intake contact | Low | Security/governance | Fixed | Re-validate only unless regression found | SECURITY.md | Docs review | Security/DX |
| SDK-AUDIT-051 | Docs overstate response cap strength | Medium | Docs/reliability | Fixed | Re-validate only unless regression found | READMEs | Docs review | Reliability/DX |
| SDK-AUDIT-052 | Docs claim OpenAPI gated but alias contradicts | Medium | Docs/consistency | Fixed | Re-validate only unless regression found | app/docs/tests | Production docs tests | Security/DX |
| SDK-AUDIT-053 | Direct HTTP fixture tokens remain in source | Low | Security/examples | Fixed | Re-validate only unless regression found | examples/tests/docs | Direct HTTP tests | Security |
| SDK-AUDIT-054 | Dependency range compatibility not proven | Low | Packaging/compatibility | Fixed | Re-validate only unless regression found | CI/docs | Workflow/static validation | Release |
| SDK-AUDIT-055 | Release process lacks SDK SBOM | Medium | Supply chain/release | Fixed | Re-validate only unless regression found | CI/publish/docs | Workflow/static validation | Security/release |
| SDK-AUDIT-056 | Product deprecation warning debt | Low | Maintainability/future compatibility | Fixed | Re-validate only unless regression found | source/tests | Full/focused tests | Maintainability |
| SDK-AUDIT-057 | SDK telemetry hook failures only debug-logged | Low | Observability/DX | Fixed | Re-validate only unless regression found | SDK README/tests | SDK tests/docs | DX |
| SDK-AUDIT-058 | `status` argument only accepts active | Low | API/DX | Fixed | Re-validate only unless regression found | SDK docs/tests | SDK tests/docs | DX |

### Continuation Remediation Evidence

Date: 2026-05-11.

Final continuation disposition:

- Issues processed: 58.
- Fixed: 48.
- Already resolved: 0.
- Invalidated: 0.
- Deferred with rationale: 8.
- Accepted remaining risks: 2.
- Changed since the first V3 pass: SDK-AUDIT-005, SDK-AUDIT-015, and SDK-AUDIT-042 moved from deferred to fixed.

Validation command references:

| Code | Command | Result |
| --- | --- | --- |
| CV1 | `env PYTHONPATH=src python3 -m pytest tests/test_tool_gateway_upstream_phase1.py tests/test_tool_gateway_upstream_phase3.py tests/test_tool_gateway_forwarding_phase2.py tests/test_tool_gateway_forwarding_phase3.py tests/test_tool_gateway_auth_phase3.py -q --tb=short` | Passed: 52 passed |
| CV2 | `env PYTHONPATH=src python3 -m pytest tests/test_db_phase1.py tests/test_db_phase2.py tests/test_db_phase3.py tests/test_db_phase4.py tests/test_tool_gateway_upstream_phase1.py tests/test_tool_gateway_upstream_phase2.py tests/test_tool_gateway_upstream_phase3.py tests/test_tool_gateway_forwarding_phase1.py tests/test_tool_gateway_forwarding_phase2.py tests/test_tool_gateway_forwarding_phase3.py tests/test_tool_gateway_auth_phase3.py tests/test_tool_gateway_response_phase3.py tests/test_mvp_cloud_deployment_phase2.py -q --tb=short` | Passed: 95 passed |
| CV3 | `env PYTHONPATH=src python3 -m pytest tests -q --tb=short` in `packages/product-platform` | Passed: 774 passed in 87.78s |
| CV4 | `env PYTHONPATH=src python3 -m pytest tests -q --tb=short` in `packages/ophanix-tool-gateway-sdk` | Passed: 10 passed |
| CV5 | `python3 -m mypy src/product_platform/tool_gateway src/ophanix_tool_gateway` in `packages/product-platform` | Passed: 14 files |
| CV6 | `python3 -m ruff check ... --select E,F,W --ignore E501` over touched gateway/API/tests | Passed |
| CV7 | `python3 -m compileall -q ...` over touched API, gateway, DB, and tests | Passed |
| CV8 | Python `yaml.safe_load` over `.github/workflows/ci.yml` and `.github/workflows/publish.yml` | Passed |
| CV9 | `python3 scripts/validate_release.py --out-dir /tmp/ophanix-product-remediation-continuation-release` in `packages/product-platform` | Passed: sdist and wheel built, `twine check` passed |
| CV10 | `python3 scripts/validate_release.py --out-dir /tmp/ophanix-sdk-remediation-continuation-release` in `packages/ophanix-tool-gateway-sdk` | Passed: sdist and wheel built, `twine check` passed |

Continuation issue evidence table:

| Issue ID | Severity / Category | Status | Files changed | Root cause / current evidence | Fix implemented and production-grade rationale | Tests / validation | Remaining risk | Score impact |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SDK-AUDIT-001 | High / Runtime/reliability | Fixed | No new continuation change | Prior async health fix remains present. | Revalidated with full suite; no regression. | CV3, CV6, CV7 | None known | Supports implementation/reliability. |
| SDK-AUDIT-002 | High / Runtime/reliability | Fixed | No new continuation change | Prior transaction-scope split remains present. | Revalidated with full suite; upstream call remains outside primary transaction. | CV3, CV6, CV7 | SQLite architecture remains SDK-AUDIT-003. | Supports implementation/reliability. |
| SDK-AUDIT-003 | High / Architecture/reliability | Deferred with rationale | No new code change | Product runtime still uses SQLite connection manager; full production backend is architectural work. | Production SQLite guard remains; no fake DB abstraction was added. Durable fix requires real production DB/pooling/migrations/load proof. | CV2, CV3, CV9 | Broad production still blocked by storage architecture. | Caps implementation/reliability at 6. |
| SDK-AUDIT-004 | Medium / Deployment safety | Fixed | No new continuation change | Production SQLite guard still active. | Revalidated with deployment tests. | CV2, CV3 | Operator override remains intentional escape hatch. | Supports security/reliability. |
| SDK-AUDIT-005 | High / API/security/adoption | Fixed | `models.py`, `repository.py`, `invocation.py`, `app.py`, migration `0058`, upstream/forwarding tests, product README | Runtime only supported `auth_mode="none"` and rejected protected upstreams. | Added secret-reference `bearer` and `api_key` upstream auth modes, persisted opaque `auth_config_json`, retrieves secrets through the configured secret provider at invocation, fails closed when missing, and never returns `secret_ref` in target read responses. OAuth remains future work. | CV1, CV2, CV3, CV5, CV6, CV9 | Requires operator-managed secret provider entries; OAuth/dynamic auth not implemented. | Removes a high ease/security blocker. |
| SDK-AUDIT-006 | High / Reliability/API | Deferred with rationale | No new code change | Safe idempotency requires durable request hashing, replay storage, TTL, conflict behavior, and response data-retention policy. | Still deferred rather than adding unsafe automatic retries or response persistence. | CV3 | Mutating tool retries remain caller/product-contract responsibility. | Caps implementation/reliability at 6. |
| SDK-AUDIT-007 | High / Security/SSRF | Fixed | No new continuation change | Prior fail-closed DNS/runtime validation remains present. | Revalidated through upstream/forwarding suites. | CV1, CV2, CV3 | Egress firewall still required. | Supports security/reliability. |
| SDK-AUDIT-008 | High / Reliability/resource safety | Fixed | No new continuation change | Streaming cap remains present in SDK/server executors. | Revalidated by forwarding and full suites. | CV1, CV3, CV4 | Custom clients must preserve streaming semantics. | Supports reliability. |
| SDK-AUDIT-009 | High / Security/data handling | Fixed | No new continuation change | Inactive policy no longer stores full raw response. | Revalidated by response policy tests. | CV2, CV3 | Disabled policy intentionally disables redaction for caller response. | Supports security. |
| SDK-AUDIT-010 | Medium / Security/docs consistency | Fixed | No new continuation change | OpenAPI alias remains gated. | Revalidated by full suite and workflow/docs consistency. | CV3, CV8 | None known. | Supports DX/security. |
| SDK-AUDIT-011 | Low / Docs/runtime consistency | Fixed | No new continuation change | System config docs URL remains nullable when docs disabled. | Revalidated by full suite. | CV3 | None known. | Supports DX. |
| SDK-AUDIT-012 | Medium / Deployment/reliability | Fixed | No new continuation change | Positive production safety-limit guard remains active. | Revalidated by deployment tests. | CV2, CV3 | Operators can still choose large positive values. | Supports reliability/security. |
| SDK-AUDIT-013 | Medium / Reliability/security | Deferred with rationale | No new code change | Limiter is still process-local. | Kept documented requirement for ingress/shared distributed limits; no pretend distributed limiter was added. | CV3 | Multi-worker/global abuse control remains incomplete. | Caps reliability. |
| SDK-AUDIT-014 | Low / Reliability/correctness | Fixed | No new continuation change | Lock around process-local limiter remains present. | Revalidated by auth/rate-limit tests. | CV2, CV3 | Process-local scope remains SDK-AUDIT-013. | Supports reliability. |
| SDK-AUDIT-015 | Medium / Maintainability/runtime | Fixed | `app.py`, auth tests | Prior body cap monkeypatched private `Request._receive`. | Replaced private request mutation with `ToolGatewayBodyLimitMiddleware`, an ASGI receive wrapper that buffers only up to the configured cap, returns 413 before route parsing, and handles streaming bodies without `Content-Length`. | CV1, CV2, CV3, CV6, CV7 | Gateway body is buffered up to the configured cap by design. | Removes maintainability/runtime cap. |
| SDK-AUDIT-016 | Medium / API/error semantics | Fixed | No new continuation change | Structured 403 mapping remains present. | Revalidated by SDK/product suites. | CV3, CV4 | None known. | Supports DX/reliability. |
| SDK-AUDIT-017 | Low / API/maintainability | Fixed | No new continuation change | Deep-frozen SDK result behavior remains present. | Revalidated by SDK suites. | CV3, CV4 | None known. | Supports DX. |
| SDK-AUDIT-018 | Medium / Testing | Fixed | No new continuation change | Standalone SDK behavior tests remain present. | Revalidated by standalone SDK suite. | CV4 | No live gateway wheel test, SDK-AUDIT-019. | Supports implementation confidence. |
| SDK-AUDIT-019 | Medium / Testing/release | Deferred with rationale | No new code change | Release validators prove built artifacts/imports, not installed wheel against a live gateway process. | Kept deferred; a durable live harness must start/seed product-platform and call it from the built SDK wheel in CI. | CV4, CV9, CV10 | End-to-end installed-wheel gateway behavior remains unproven. | Caps implementation/release confidence. |
| SDK-AUDIT-020 | High / Testing/reliability | Deferred with rationale | No new code change | No production-like load or multi-worker harness exists. | Full unit/integration suite is clean, but this does not substitute for load/multi-worker validation. | CV3 | Broad production reliability remains unproven. | Caps implementation/reliability at 6. |
| SDK-AUDIT-021 | Medium / Maintainability/CI | Fixed | No new continuation change | Product gateway mypy gate remains configured. | Revalidated locally. | CV5, CV8 | Type coverage remains focused. | Supports implementation. |
| SDK-AUDIT-022 | Medium / Security/CI | Fixed | No new continuation change | Blocking dependency audit workflow remains configured. | Workflow YAML parsed; release validators pass. | CV8, CV9, CV10 | Hosted CI still must execute after commit. | Supports security/release. |
| SDK-AUDIT-023 | Low / CI/maintainability | Fixed | No new continuation change | Broadened lint coverage remains configured. | Touched-surface ruff passed. | CV6, CV8 | Whole-monorepo lint debt remains out of scope. | Supports maintainability. |
| SDK-AUDIT-024 | Medium / CI/packaging | Fixed | No new continuation change | CI install fallbacks remain removed for SDK/product. | Release validators passed. | CV8, CV9, CV10 | Hosted CI still must execute after commit. | Supports release. |
| SDK-AUDIT-025 | High / Release/supply chain | Fixed | No new continuation change | Publishing docs/workflow references remain present. | Workflow YAML and release validators passed. | CV8, CV9, CV10 | External credentials/policy remain outside repo. | Supports release/security. |
| SDK-AUDIT-026 | Medium / Release/CI | Fixed | No new continuation change | Build/twine install path remains executable. | Release validators passed. | CV9, CV10 | Hash pinning can be strengthened later. | Supports release. |
| SDK-AUDIT-027 | Low / Packaging/release | Fixed | No new continuation change | SDK wheel smoke installs dependencies. | SDK validator passed. | CV10 | None known. | Supports release. |
| SDK-AUDIT-028 | Low / Release/consistency | Fixed | No new continuation change | SDK parity validation remains present. | SDK validator passed. | CV10 | Source duplication remains guarded, not removed. | Supports consistency. |
| SDK-AUDIT-029 | Medium / Packaging/release | Fixed | No new continuation change | Product validator remains present. | Product validator passed with migration 0058 included. | CV9 | None known. | Supports release. |
| SDK-AUDIT-030 | Low / Packaging/DX | Fixed | No new continuation change | Product metadata remains expanded. | Product validator passed. | CV9 | Beta status remains SDK-AUDIT-031. | Supports DX/release. |
| SDK-AUDIT-031 | Medium / API stability/adoption | Accepted remaining risk | No new code change | Project is still beta/pre-GA. | Kept accepted; no fake GA version bump was made without release authority. | CV9, CV10 | External adopters may reject beta SDK. | Caps ease of use at 8. |
| SDK-AUDIT-032 | Low / Repo hygiene/data | Accepted remaining risk | No new code change | Local DB artifacts may be developer state. | Package validators continue excluding DB artifacts; local deletion remains owner decision. | CV9 | Local workspace can remain noisy. | Low release/security residual. |
| SDK-AUDIT-033 | Medium / Security/credential storage | Fixed | No new continuation change | Production pepper requirement remains active. | Revalidated by full suite. | CV3 | Operator must manage pepper secrecy. | Supports security. |
| SDK-AUDIT-034 | Medium / Security/migration | Fixed | No new continuation change | Legacy token hash opt-in remains explicit. | Revalidated by full suite. | CV3 | Legacy deployments need migration. | Supports security. |
| SDK-AUDIT-035 | Medium / Security/operations | Fixed | No new continuation change | Pepper key ID/current/previous support remains present. | Revalidated by full suite. | CV3 | External rotation procedure remains operator-owned. | Supports security. |
| SDK-AUDIT-036 | Low / Security/data handling | Fixed | No new continuation change | Credential metadata secret guard remains present. | Revalidated by full suite. | CV3 | Heuristic secret detection may miss unknown forms. | Supports security. |
| SDK-AUDIT-037 | Medium / Authorization/API | Fixed | No new continuation change | Credential scope resource types remain enumerated. | Revalidated by full suite. | CV3 | Future resource types require schema extension. | Supports authorization. |
| SDK-AUDIT-038 | Low / Security/info disclosure | Fixed | No new continuation change | Generic gateway auth failures remain present. | Revalidated by full suite. | CV3 | Detailed diagnosis remains in audit/logs. | Supports security. |
| SDK-AUDIT-039 | Low / Observability/trust boundary | Fixed | No new continuation change | Server request ID separation remains present. | Revalidated by full suite. | CV3 | Correlation policy can be further formalized. | Supports observability. |
| SDK-AUDIT-040 | Low / Performance/reliability | Fixed | No new continuation change | Cached regex compilation remains present. | Revalidated by response tests. | CV2, CV3 | Safe-regex timeout remains SDK-AUDIT-041. | Supports reliability/performance. |
| SDK-AUDIT-041 | Medium / Security/reliability | Deferred with rationale | No new code change | Redaction still uses Python `re` with validation/caps, not a formal safe-regex engine or timeout. | Kept deferred; a production-grade closure needs a safe-regex dependency/timeout policy and dependency review. | CV2, CV3 | Pathological accepted regex risk remains mitigated but not eliminated. | Caps security/reliability. |
| SDK-AUDIT-042 | Medium / Security/API | Fixed | `models.py`, `repository.py`, `invocation.py`, migration `0058`, forwarding tests, README | GET/DELETE payload fields were serialized by heuristic secret detection only. | Added explicit `query_parameter_allowlist` persisted on upstream targets; GET/DELETE now fail closed for non-path payload fields unless allowed, and credential-like names remain rejected even when listed. | CV1, CV2, CV3, CV5, CV6, CV9 | Existing GET/DELETE integrations must add allowlists for intended query fields. | Removes security/API cap. |
| SDK-AUDIT-043 | Low / Security/observability | Fixed | No new continuation change | Health error sanitization remains present. | Revalidated by upstream tests. | CV2, CV3 | Third-party error semantics can still reveal broad class. | Supports security. |
| SDK-AUDIT-044 | Low / Reliability/API | Deferred with rationale | No new code change | Discovery still uses offset pagination. | Kept deferred; stable cursor/snapshot pagination requires API/SDK contract expansion. | CV3, CV4 | Concurrent catalog mutation can still skip/duplicate pages. | Low reliability residual. |
| SDK-AUDIT-045 | Low / SDK resource usage | Fixed | No new continuation change | `list_all_tools(max_total=...)` remains present. | Revalidated by SDK suites. | CV3, CV4 | Offset semantics remain SDK-AUDIT-044. | Supports reliability/DX. |
| SDK-AUDIT-046 | Medium / Maintainability/architecture | Deferred with rationale | No new code change | API app remains large. | Kept deferred; no broad route refactor was attempted during security/runtime remediation. | CV3 | Maintainability risk remains. | Caps implementation polish. |
| SDK-AUDIT-047 | Medium / Maintainability/release | Fixed | No new continuation change | SDK parity guard remains present. | SDK/product validators passed. | CV9, CV10 | Duplication is guarded, not removed. | Supports release confidence. |
| SDK-AUDIT-048 | Low / Docs/DX | Fixed | No new continuation change | SDK API reference remains packaged. | SDK validator passed. | CV10 | Reference is manual, not generated. | Supports DX. |
| SDK-AUDIT-049 | Medium / Docs/adoption | Fixed | Product README updated for upstream auth/query controls | Credential/upstream setup docs needed to match behavior. | Docs now cover secret-reference upstream auth and query allowlists in addition to credential issuance/rotation. | CV9, docs review | Full operator runbook can still expand. | Supports ease/security. |
| SDK-AUDIT-050 | Low / Security/governance | Fixed | No new continuation change | Security intake remains concrete. | SDK validator passed. | CV10 | Depends on repository security configuration. | Supports governance. |
| SDK-AUDIT-051 | Medium / Docs/reliability | Fixed | Product README updated for ASGI body cap wording | Docs needed to match cap implementation. | Docs now describe ASGI request cap and streaming upstream response cap accurately. | CV9 | Custom executors still need equivalent limits. | Supports reliability/DX. |
| SDK-AUDIT-052 | Medium / Docs/consistency | Fixed | No new continuation change | Runtime/docs OpenAPI gating remains aligned. | Revalidated by full suite. | CV3 | None known. | Supports DX/security. |
| SDK-AUDIT-053 | Low / Security/examples | Fixed | No new continuation change | Fixture token local-only docs remain present. | Revalidated by direct HTTP example tests in full suite. | CV3 | Demo tokens remain as fixtures by design. | Low security/DX residual. |
| SDK-AUDIT-054 | Low / Packaging/compatibility | Fixed | No new continuation change | Compatibility docs/CI matrix remain present. | Validators passed. | CV8, CV9, CV10 | Full min/latest dependency matrix still desirable. | Supports release. |
| SDK-AUDIT-055 | Medium / Supply chain/release | Fixed | No new continuation change | SBOM workflow remains configured. | Workflow YAML parsed. | CV8 | Signing/provenance policy remains external. | Supports security/release. |
| SDK-AUDIT-056 | Low / Maintainability/future compatibility | Fixed | No new continuation change | Warning cleanup remains effective in full suite. | Full product suite passed without warning summary. | CV3 | Unrelated monorepo warning debt may remain. | Supports maintainability. |
| SDK-AUDIT-057 | Low / Observability/DX | Fixed | No new continuation change | Telemetry hook failure semantics remain documented. | SDK tests/validator passed. | CV4, CV10 | No separate hook-error callback. | Supports DX. |
| SDK-AUDIT-058 | Low / API/DX | Fixed | No new continuation change | `status` deprecation warning/docs remain present. | SDK/product suites passed. | CV3, CV4 | Parameter remains until future breaking release. | Supports DX. |

Changed files in continuation:

- Runtime/API: `packages/product-platform/src/product_platform/api/app.py`.
- Gateway models/execution/persistence: `tool_gateway/models.py`, `tool_gateway/invocation.py`, `tool_gateway/repository.py`.
- Migrations: `0058_tool_upstream_auth_and_query_controls.up.sql`, `0058_tool_upstream_auth_and_query_controls.down.sql`.
- Tests: `test_db_phase1.py`, `test_tool_gateway_auth_phase3.py`, `test_tool_gateway_forwarding_phase2.py`, `test_tool_gateway_upstream_phase1.py`, `test_tool_gateway_upstream_phase3.py`.
- Docs: `packages/product-platform/README.md`.

Remaining unresolved issues after continuation:

- Deferred with rationale: SDK-AUDIT-003, SDK-AUDIT-006, SDK-AUDIT-013, SDK-AUDIT-019, SDK-AUDIT-020, SDK-AUDIT-041, SDK-AUDIT-044, SDK-AUDIT-046.
- Accepted remaining risks: SDK-AUDIT-031, SDK-AUDIT-032.
- Invalid findings: none.
- Already resolved without changes: none.

Updated scoring matrix after continuation:

| Category | Previous score | Updated score | Raised/lowered/upheld | Reason | Remaining score cap | Blocking next score | Blocking 8 / 10 | Blocking 9 / 10 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Implementation quality | 6 / 10 | 6 / 10 | Upheld | The continuation closed concrete runtime/API gaps and full product tests increased to 774 passing. Implementation remains capped by SQLite-only production storage, missing idempotency/replay contract, missing live installed-wheel gateway test, missing load/multi-worker evidence, and app monolith. | 6 | SDK-AUDIT-003, SDK-AUDIT-006, SDK-AUDIT-019, SDK-AUDIT-020, SDK-AUDIT-046 | Production DB/pooling, idempotency schema/API, live wheel-to-gateway CI, multi-worker/load harness | Modularized gateway app, source ownership cleanup, hosted CI/release evidence, only low residual risks |
| Ease of use | 7 / 10 | 8 / 10 | Raised | Secret-reference bearer/API-key upstream auth and explicit query allowlists remove a major adoption blocker; docs now match runtime behavior. Score remains capped by beta status, no OAuth/dynamic upstream auth, no live external onboarding proof, and no idempotency contract. | 8 | SDK-AUDIT-006, SDK-AUDIT-019, SDK-AUDIT-031 | Stable idempotency semantics, live installed-wheel quickstart, explicit GA/stability policy | Generated docs, migration guides, richer examples, proven external adopter workflow |
| Security and reliability | 6 / 10 | 6 / 10 | Upheld | Upstream auth, query allowlists, and ASGI body limiting improve the security posture, but unresolved high reliability architecture issues still cap the category. | 6 | SDK-AUDIT-003, SDK-AUDIT-006, SDK-AUDIT-013, SDK-AUDIT-020, SDK-AUDIT-041 | Production DB, idempotency/replay, distributed rate limiting, safe-regex timeout/engine, load/multi-worker evidence | Formal threat model, chaos/failure tests, provenance/signing, production runbooks |

Required fixes to reach production readiness remain:

1. Production-supported database backend and multi-worker transaction model.
2. Server-side idempotency key/replay contract with data-retention rules.
3. Distributed or edge-enforced rate limiting.
4. Live installed-wheel-to-running-gateway CI harness.
5. Production-like load and multi-worker validation.
6. Safe regex engine or timeout-backed redaction policy enforcement.
7. Gateway API modularization after behavior stabilizes.

Final strict assessment after continuation:

The continuation pass closed three previously deferred, actionable runtime/API issues without widening the public SDK surface unsafely. Protected upstreams can now use secret-reference bearer or API-key auth, GET/DELETE query serialization is explicit and fail-closed, and gateway body limits no longer rely on private Starlette request mutation. Broad external production adoption is still not defensible until production storage, idempotency, distributed rate limiting, live wheel integration, and production-like load validation are in place. Constrained internal adoption is more defensible than the prior pass, including protected upstreams, as long as operators configure secret-provider entries and accept the remaining idempotency/storage/load constraints.

## Pass 18: V4 Exhaustive Remediation Execution

Date: 2026-05-11

Pass name: V4 exhaustive issue-register remediation execution.

Starting repository state:

- `git status --short` showed only the newly created V4 audit artifact as untracked: `docs/product-platform-worktree/execution-logs/06-tool-gateway-logs/17-sdk-production-readiness-audit-v4.md`.
- No staged changes were present.
- The V4 audit issue register contained 60 issues, `SDK-AUDIT-001` through `SDK-AUDIT-060`.
- This tracking table was created before implementation edits in this pass.

Initial remediation tracking table:

| Issue ID | Title | Severity | Category | Current status | Planned action | Files likely affected | Validation required | Score impact |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SDK-AUDIT-001 | Product gateway persistence remains SQLite-only | High | Runtime architecture / persistence | Pending | Defer full production DB backend with explicit rationale; tighten production safety docs/guards where possible. | DB layer, settings, docs | Production config tests, full suite | Caps implementation/reliability |
| SDK-AUDIT-002 | Production startup still permits SQLite through an escape hatch | High | Runtime configuration / production safety | Pending | Remove production SQLite escape hatch from default production path or restrict it to non-production test override. | `api/app.py`, `settings.py`, tests, README | Deployment/settings tests, full suite | Raises reliability if fixed |
| SDK-AUDIT-003 | Upstream secret provider is still an in-memory demo provider by default | High | Security / secret management | Pending | Add production-capable environment secret provider wiring and fail production when demo provider is configured. | `integrations/secrets.py`, `api/app.py`, settings, tests, docs | Secret-provider tests, production config tests | Raises security/reliability |
| SDK-AUDIT-004 | No invocation idempotency or replay-protection contract | High | Reliability / API contract | Pending | Defer if full durable replay semantics cannot be implemented safely; document exact requirements. | Invocation route, repository, migrations, SDK/docs | Contract tests if implemented | Caps implementation/reliability |
| SDK-AUDIT-005 | Runtime rate limiting is process-local and not production-distributed | High | Reliability / abuse resistance | Pending | Keep distributed limiter as deferred infrastructure work; improve server headers and invalid-token limiter behavior locally. | `api/app.py`, tests, README | Rate-limit tests | Caps reliability until distributed |
| SDK-AUDIT-006 | Rate limiter can be exhausted by distinct invalid authorization keys | Medium | Reliability / abuse resistance | Pending | Change unauthenticated/invalid-token limiter key strategy so invalid bearer values do not consume distinct credential buckets. | `api/app.py`, tests | Rate-limit abuse tests | Raises reliability |
| SDK-AUDIT-007 | Gateway rate-limit responses omit `Retry-After` | Medium | Reliability / protocol ergonomics | Pending | Add `Retry-After` header to runtime limiter responses. | `api/app.py`, tests | Rate-limit tests | Raises DX/reliability |
| SDK-AUDIT-008 | SSRF defenses remain vulnerable to DNS rebinding and time-of-use changes | High | Security / SSRF | Pending | Add production host allowlist and stronger docs; defer network-layer egress enforcement as deployment requirement. | `models.py`, settings, docs, tests | URL validation tests | Caps security until egress proof |
| SDK-AUDIT-009 | Unresolved upstream hosts can be allowed in production by environment variable | Medium | Security / configuration | Pending | Reject unresolved-host bypass in production. | `models.py`, tests, docs | URL validation tests | Raises security |
| SDK-AUDIT-010 | Real secret-manager setup is not documented or enforced enough for upstream auth | Medium | Security / developer experience | Pending | Pair with SDK-AUDIT-003: implement env provider wiring and document production setup. | Secrets, app, README | Secret-provider tests, docs review | Raises DX/security |
| SDK-AUDIT-011 | Legacy unpeppered gateway token hash acceptance can be enabled in production | Medium | Security / credential storage | Pending | Reject legacy token hash acceptance in production. | `api/app.py`, credential tests | Production config tests | Raises security |
| SDK-AUDIT-012 | Runtime response storage can persist sensitive upstream data | Medium | Security / data handling | Pending | Tighten safe defaults/docs; add retention or storage guard if feasible. | Response policy, repository/docs/tests | Response storage tests | Raises security |
| SDK-AUDIT-013 | Disabled response policy bypasses validation and redaction | Medium | Security / response handling | Pending | Apply safe default response processing when no policy exists, or document accepted risk if breaking. | `response.py`, tests, docs | Response tests | Raises security |
| SDK-AUDIT-014 | Runtime audit summaries are not PII-aware and have no retention policy | Medium | Security / privacy / operations | Pending | Add retention configuration and docs; improve PII minimization where feasible. | Runtime audit, repository, settings, docs | Audit tests | Raises security |
| SDK-AUDIT-015 | Offset pagination can miss or duplicate tools during concurrent changes | Medium | API correctness / runtime behavior | Pending | Add SDK de-duplication and defer full cursor API if contract change is too broad. | SDK, tests, docs | SDK pagination tests | Raises reliability |
| SDK-AUDIT-016 | No background health-check scheduler for upstream targets | Medium | Reliability / operations | Pending | Add scheduler if app lifecycle permits; otherwise document deferred worker requirement. | `app.py`, `health.py`, tests, docs | Health tests | Raises reliability |
| SDK-AUDIT-017 | Invocation fail-closed health behavior can rely on stale unhealthy state | Medium | Reliability / runtime behavior | Pending | Add stale-health handling or clearer expiry behavior. | Invocation/app/repository, tests | Health invocation tests | Raises reliability |
| SDK-AUDIT-018 | No upstream circuit breaker or adaptive backpressure | Medium | Reliability / resilience | Pending | Defer full circuit breaker; document required design. | Invocation/runtime docs | Failure tests if implemented | Caps reliability |
| SDK-AUDIT-019 | Standalone SDK local tests fail without installation or `PYTHONPATH` | Low | Developer experience / testing | Pending | Add pytest source path config. | SDK pyproject | Plain pytest command | Raises DX |
| SDK-AUDIT-020 | Product-platform local tests fail without installation or `PYTHONPATH` | Low | Developer experience / testing | Pending | Add pytest source path config. | Product pyproject | Plain pytest command | Raises DX |
| SDK-AUDIT-021 | Standalone SDK package has very thin independent test coverage | Medium | Testing | Pending | Add standalone SDK tests for new API/lifecycle behavior. | SDK tests | SDK pytest | Raises implementation confidence |
| SDK-AUDIT-022 | No live installed-wheel SDK to running-gateway contract test | High | Testing / integration | Pending | Defer or add harness if feasible; document exact missing CI. | CI/tests/docs | Live integration test | Caps implementation |
| SDK-AUDIT-023 | No production-like load, concurrency, or multi-worker validation | High | Testing / reliability | Pending | Defer with explicit load-harness requirements. | CI/docs | Load test plan | Caps reliability |
| SDK-AUDIT-024 | Product mypy coverage is narrow and configured to skip imports | Low | Maintainability / testing | Pending | Tighten focused typing where safe or document staged rollout. | Product pyproject/CI | Mypy | Slight implementation impact |
| SDK-AUDIT-025 | Release strict-git validation is not enforced in CI or publish workflow | Medium | Packaging / release | Pending | Enforce strict-git on release builds. | CI/publish workflow | Workflow parse/release validator | Raises release confidence |
| SDK-AUDIT-026 | Publish workflow validates artifacts but does not publish to an index | Medium | Packaging / release | Pending | Defer actual publishing credentials; document accepted release handoff or add template. | Publish workflow/docs | Workflow parse/docs | Caps ease/release |
| SDK-AUDIT-027 | Workflow dispatch package selector does not limit Python package matrix | Low | CI / release ergonomics | Pending | Filter matrix by dispatch input. | Publish workflow | Workflow parse | Raises release DX |
| SDK-AUDIT-028 | SDK remains beta/pre-1.0 with no explicit compatibility matrix | Medium | API stability / documentation | Pending | Add compatibility/stability matrix without fake GA claim. | SDK docs/changelog | Docs review/package validation | Raises DX |
| SDK-AUDIT-029 | API reference omits deprecated `status` parameter that the SDK still accepts | Low | Documentation / API consistency | Pending | Document deprecated parameter. | API reference/README | Docs review | Raises DX |
| SDK-AUDIT-030 | SDK does not reject accidental `Bearer ` token prefixes early | Low | Developer experience / auth input validation | Pending | Add SDK token-format validation and tests. | SDK source/tests | SDK tests/product parity | Raises DX/security |
| SDK-AUDIT-031 | SDK cache fingerprint uses unsalted SHA-256 of the bearer token | Low | Security / diagnostics | Pending | Switch to process-local HMAC fingerprint. | SDK source/tests | SDK tests/product parity | Raises security hygiene |
| SDK-AUDIT-032 | SDK `get_tool()` not-found error includes caller-supplied lookup text | Low | Security / logging hygiene | Pending | Sanitize/truncate lookup text. | SDK source/tests | SDK tests | Raises security hygiene |
| SDK-AUDIT-033 | SDK clients have no explicit closed-state guard | Low | Runtime behavior / developer experience | Pending | Add closed-state checks for sync/async clients. | SDK source/tests | SDK tests | Raises DX |
| SDK-AUDIT-034 | Sync and async SDK paths still duplicate substantial logic | Low | Maintainability | Pending | Defer broad refactor; add parity tests where useful. | SDK source/tests | SDK tests | Slight implementation impact |
| SDK-AUDIT-035 | Injected custom HTTP clients can bypass streaming response caps | Medium | Reliability / integration safety | Pending | Require streaming custom clients by default or explicit unsafe opt-in. | SDK source/tests/docs | SDK tests | Raises reliability |
| SDK-AUDIT-036 | SDK event hook failures are swallowed | Low | Observability / developer experience | Pending | Add optional strict hook error mode or failure callback. | SDK source/tests/docs | SDK tests | Raises observability |
| SDK-AUDIT-037 | Wildcard tool credential scopes are supported without strong operational guardrails | Medium | Authorization / least privilege | Pending | Add production guardrails/docs and explicit wildcard audit behavior if feasible. | Credentials/auth/docs/tests | Auth tests | Raises security |
| SDK-AUDIT-038 | Credential scope issuance does not verify referenced tool existence or required-scope match | Medium | Authorization / developer experience | Pending | Add issuance-time validation where repository context is available or document API limitation. | Credentials/repository/tests | Auth/credential tests | Raises security/DX |
| SDK-AUDIT-039 | Agent-tool permission grants defer required-scope mismatch to runtime | Medium | Authorization / operations | Pending | Add grant-time validation if safe. | Repository/tests | Permission tests | Raises operations/DX |
| SDK-AUDIT-040 | Upstream auth header prefix validation is permissive | Low | Security / input validation | Pending | Restrict prefix grammar. | Models/tests | Model/upstream tests | Raises security hygiene |
| SDK-AUDIT-041 | URL validation depends on DNS resolution at configuration time | Medium | Reliability / developer experience | Pending | Pair with allowlist/unresolved-host fixes and docs. | Models/docs/tests | URL validation tests | Raises reliability |
| SDK-AUDIT-042 | OAuth, mTLS, and dynamic per-tenant upstream auth are not implemented | Medium | Feature completeness / adoption | Pending | Defer as product roadmap unless small doc/API prep is safe. | Docs/models | Docs review | Caps adoption |
| SDK-AUDIT-043 | Query allowlists reduce risk but do not cap URL/path expansion separately | Low | Runtime behavior / input validation | Pending | Add final URL length cap. | Invocation/tests/docs | Invocation tests | Raises reliability |
| SDK-AUDIT-044 | SDK raises built-in `ValueError` for many boundary errors instead of SDK-specific exceptions | Low | Public API / developer experience | Pending | Add SDK validation/configuration exception subclasses preserving `ValueError`. | SDK source/tests/docs | SDK tests | Raises DX |
| SDK-AUDIT-045 | SDK redaction is pattern-based and incomplete by design | Medium | Security / logging | Pending | Add custom redactor hook/docs or accepted-risk documentation. | SDK/docs/tests | SDK tests/docs | Raises security |
| SDK-AUDIT-046 | Response redaction defaults are not domain-PII aware | Medium | Security / privacy | Pending | Add PII presets/docs where feasible. | Response/docs/tests | Response tests/docs | Raises security |
| SDK-AUDIT-047 | No formal threat model is present for the Tool Gateway trust boundaries | Medium | Security / documentation | Pending | Add threat model document. | Docs | Docs review | Raises security governance |
| SDK-AUDIT-048 | No operational runbook for gateway production incidents | Medium | Operations / documentation | Pending | Add production runbook. | Docs | Docs review | Raises operations/DX |
| SDK-AUDIT-049 | Changelog does not reflect the breadth of security/runtime remediation | Low | Documentation / release | Pending | Expand changelog. | SDK changelog | Package validation/docs review | Raises release DX |
| SDK-AUDIT-050 | Package install docs reference PyPI before publication is proven | Medium | Documentation / packaging | Pending | Make unpublished/internal install status explicit. | SDK README/docs | Docs review | Raises DX |
| SDK-AUDIT-051 | Stale execution-log docs can contradict current package/API story | Low | Documentation consistency | Pending | Add execution-log index/current-status pointer. | Execution-log docs | Docs review | Raises reviewer DX |
| SDK-AUDIT-052 | Product package still vendors the SDK source, creating release/source ownership risk | Low | Packaging / maintainability | Pending | Enforce parity in CI/release and document source of truth. | CI/validators/docs | Parity validation | Raises maintainability |
| SDK-AUDIT-053 | Security dependency audit path is not fully reproducible from the default local validation flow | Low | Supply chain / validation | Pending | Improve validator message or add wrapper docs. | Validator/README | Release validator | Raises release DX |
| SDK-AUDIT-054 | CI security scanning is present but not enough to prove package-level advisory coverage before publication | Medium | Supply chain / release | Pending | Defer until package publication/internal advisory; document gap. | Docs/CI | Docs/workflow parse | Caps supply-chain confidence |
| SDK-AUDIT-055 | Direct HTTP examples and seed helpers use deterministic local tokens | Low | Security / examples | Pending | Add production guard/warnings for fixture tokens if feasible. | Examples/auth/docs/tests | Example/auth tests | Raises security hygiene |
| SDK-AUDIT-056 | No final URL/domain allowlist for upstream invocation | Medium | Security / governance | Pending | Implement configurable host allowlist or document deployment requirement. | Settings/models/docs/tests | URL tests | Raises security |
| SDK-AUDIT-057 | Gateway discovery exposes callable tool catalog to wildcard credentials | Low | Security / information disclosure | Pending | Add docs/guardrails for wildcard discovery. | Docs/auth tests if needed | Docs review | Slight security impact |
| SDK-AUDIT-058 | Built artifacts are validated, but release evidence is not archived in a reviewable manifest | Low | Release / governance | Pending | Add release manifest generation to validators. | Release validators | Validator runs | Raises release confidence |
| SDK-AUDIT-059 | No consumer-facing migration guide for compatibility import removal | Low | Documentation / API lifecycle | Pending | Add migration/deprecation docs. | SDK docs/API reference | Docs review | Raises DX |
| SDK-AUDIT-060 | Production readiness depends on external ingress limits that are documented but not verified | Medium | Reliability / operations | Pending | Add deployment conformance checklist/script where feasible; otherwise document external requirement. | Docs/scripts | Docs/script validation | Caps operations confidence |

Final outcome for Pass 18:

This outcome table supersedes the initial `Pending` statuses above. All 60 V4 issue IDs were processed.

Counts:

- Fixed: 32
- Already resolved: 0
- Invalid finding: 0
- Deferred with rationale: 24
- Accepted remaining risk: 4

Validation evidence legend:

- V1: Standalone SDK validation passed: `python3 -m ruff check src tests scripts`, `python3 -m mypy src/ophanix_tool_gateway tests`, `python3 -m pytest tests -q --tb=short` with 16 passed, `python3 -m compileall -q src tests scripts`, and `python3 scripts/validate_release.py --skip-twine-check --out-dir /tmp/ophanix-sdk-release-check`.
- V2: Focused Tool Gateway product validation passed: gateway/auth/upstream/forwarding/secret-provider focused suites passed; broader `tests/test_tool_gateway_*.py tests/test_provider_secrets_health_phase1.py` passed with 290 tests.
- V3: Full product test suite passed: `python3 -m pytest tests -q --tb=short` with 788 passed in 93.94 seconds.
- V4: Product lint passed: `python3 -m ruff check src tests scripts --select E,F,W --ignore E501`.
- V5: Touched Tool Gateway typecheck passed: `python3 -m mypy src/product_platform/api/app.py src/product_platform/api/settings.py src/product_platform/integrations/secrets.py src/product_platform/tool_gateway/models.py src/product_platform/tool_gateway/invocation.py src/ophanix_tool_gateway tests/test_provider_secrets_health_phase1.py tests/test_tool_gateway_auth_phase3.py tests/test_tool_gateway_forwarding_phase2.py tests/test_tool_gateway_upstream_phase1.py tests/test_tool_gateway_upstream_phase3.py`.
- V6: Full product typecheck remains a repository-wide gap: `python3 -m mypy src tests` still fails with 171 errors outside the cleaned touched Tool Gateway surface, including missing PyYAML stubs, nullable row assertions, and non-gateway typing debt.
- V7: Product release validator passed: `python3 scripts/validate_release.py --skip-twine-check --out-dir /tmp/ophanix-product-release-check`.
- V8: Release/workflow hygiene passed: `.github/workflows/publish.yml` parsed with PyYAML, `git diff --check` passed, and standalone/vendored SDK `sdk.py` and `__init__.py` parity checks passed.
- V9: Post-typing focused regression passed: `python3 -m pytest tests/test_tool_gateway_auth_phase3.py tests/test_tool_gateway_forwarding_phase2.py -q --tb=short` with 33 passed.

Full issue outcome table:

| Issue ID | Original severity / category | Status | Files changed | Root cause | Fix implemented or rationale | Why production-grade / sufficiency | Tests and validation | Remaining risk | Score impact |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SDK-AUDIT-001 | High / Runtime architecture and persistence | Deferred with rationale | `api/app.py`, README/docs only as guardrail | The gateway still uses SQLite-backed repository assumptions. | Full production DB backend was not attempted in this pass; SDK-AUDIT-002 now blocks SQLite in production so the unsafe path fails fast. | Sufficient as a guardrail, not a full fix. A durable backend needs schema, pooling, transaction, migration, and multi-worker validation work. | V2, V3, V5, V7 | Production adoption still lacks supported DB runtime evidence. | Caps implementation and reliability at 6. |
| SDK-AUDIT-002 | High / Runtime configuration and production safety | Fixed | `packages/product-platform/src/product_platform/api/app.py`; `tests/test_tool_gateway_auth_phase3.py`; README | Production startup trusted an escape hatch that could allow SQLite. | Production validation now rejects SQLite regardless of `allow_sqlite_in_production`; docs describe the hard failure. | Fail-fast startup guard prevents accidental unsafe production boot and has regression tests. | V2, V3, V5, V9 | Underlying production DB work remains SDK-AUDIT-001. | Raises security/reliability but does not remove DB score cap. |
| SDK-AUDIT-003 | High / Security and secret management | Fixed | `integrations/secrets.py`; `api/app.py`; settings; `tests/test_provider_secrets_health_phase1.py`; README/runbook | Only a demo in-memory provider was wired by default and production was not forced to use a real provider. | Added environment-backed secret provider refs, production supported-ref validation, and docs for env secret setup. | Production now fails closed if no supported secret provider is configured; demo provider remains local/test only. | V2, V3, V5 | External cloud secret-manager adapters are still future work. | Raises security/reliability. |
| SDK-AUDIT-004 | High / Reliability and API contract | Deferred with rationale | Log only | No durable request idempotency schema or replay contract exists. | Deferred because a safe fix requires API contract, storage model, retention rules, conflict behavior, and SDK docs. | No partial code fix would be production-grade without durable semantics. | V3 as regression only | Duplicate side effects remain possible on retrying non-idempotent tools. | Caps implementation and reliability at 6. |
| SDK-AUDIT-005 | High / Reliability and abuse resistance | Deferred with rationale | `api/app.py`; tests/docs for partial local hardening | Limiter state is process-local memory. | Added `Retry-After` and invalid-key-budget hardening, but deferred distributed limiter to infrastructure design. | Local behavior improved, but multi-worker/global abuse protection needs Redis/edge/service limiter. | V2, V3, V5 | Multi-process and multi-region rate limits are not enforced. | Caps reliability at 6. |
| SDK-AUDIT-006 | Medium / Reliability and abuse resistance | Fixed | `api/app.py`; `tests/test_tool_gateway_auth_phase3.py` | Distinct malformed auth values could consume distinct limiter keys and deny legitimate clients. | Invalid Authorization syntax shares a client invalid-auth bucket; key-budget overflow no longer returns 429 for unseen keys. | Prevents caller-controlled key-budget denial while preserving limits for established keys. | V2, V3, V5, V9 | Distributed limiter remains SDK-AUDIT-005. | Improves reliability/DX. |
| SDK-AUDIT-007 | Medium / Reliability and protocol ergonomics | Fixed | `api/app.py`; `tests/test_tool_gateway_auth_phase3.py`; README | 429 responses did not tell consumers when to retry. | Runtime limiter now returns `Retry-After` based on the remaining window. | Standard protocol hint is deterministic and covered by tests. | V2, V3, V5, V9 | None specific beyond process-local limiting. | Improves reliability/DX. |
| SDK-AUDIT-008 | High / Security and SSRF | Deferred with rationale | `settings.py`; `models.py`; `invocation.py`; tests; threat model/runbook | DNS validation at write time cannot fully prevent rebinding or network-path bypass. | Added production upstream host allowlist and runtime revalidation; deferred final network egress enforcement to deployment controls. | Stronger app-layer guard is tested, but production-grade SSRF defense still needs egress firewall/proxy enforcement. | V2, V3, V5 | DNS rebinding and network route changes remain deployment-bound risks. | Caps security/reliability at 6. |
| SDK-AUDIT-009 | Medium / Security configuration | Fixed | `models.py`; `api/app.py`; `tests/test_tool_gateway_upstream_phase1.py`; README | `OPHANIX_ALLOW_UNRESOLVED_UPSTREAM_HOSTS` could weaken production validation. | Production rejects unresolved-host bypass at startup, and URL validation ignores the bypass outside local/test. | Fail-closed behavior is environment-scoped and tested. | V2, V3, V5 | DNS time-of-use remains SDK-AUDIT-008. | Improves security. |
| SDK-AUDIT-010 | Medium / Security and DX | Fixed | `integrations/secrets.py`; `api/app.py`; tests; README/runbook | Real secret-provider setup was neither documented nor enforced. | Added env provider refs, startup enforcement, and operational setup docs. | Consumers now get a concrete non-demo path with failure before serving traffic. | V2, V3, V5 | Managed cloud providers are not implemented. | Improves security/DX. |
| SDK-AUDIT-011 | Medium / Security and credential storage | Fixed | `api/app.py`; `tests/test_tool_gateway_auth_phase3.py`; README | Legacy unpeppered token hashes could still be accepted in production. | Production startup rejects legacy hash acceptance. | Fail-fast config guard prevents accidental weak credential mode. | V2, V3, V5, V9 | Existing legacy hashes need migration before production. | Improves security. |
| SDK-AUDIT-012 | Medium / Security and data handling | Deferred with rationale | Threat model/runbook | Response persistence may store sensitive upstream data. | Deferred because safe remediation needs product-level retention, per-tool storage policy, and redaction semantics. | Documentation names the risk, but code behavior is not fully remediated. | V3 as regression only | Sensitive response data may persist if policies are misconfigured. | Caps security/DX. |
| SDK-AUDIT-013 | Medium / Security and response handling | Deferred with rationale | Threat model/runbook | Disabled response policy bypasses validation/redaction behavior. | Deferred because changing disabled-policy semantics can break existing tool integrations and needs migration design. | Not production-grade yet; requires explicit default policy contract and tests. | V3 as regression only | Redaction/validation may be absent for disabled policies. | Caps security. |
| SDK-AUDIT-014 | Medium / Security, privacy, operations | Deferred with rationale | Threat model/runbook | Runtime audit summaries are not domain-PII aware and lack retention policy. | Deferred pending privacy policy, retention config, and data-classification requirements. | Documentation is a governance improvement, not a behavioral fix. | V3 as regression only | Audit data may retain sensitive summaries too long. | Caps security/compliance. |
| SDK-AUDIT-015 | Medium / API correctness and runtime behavior | Deferred with rationale | `sdk.py`; SDK tests/docs | Offset pagination can still miss records during concurrent mutation. | Added SDK de-duplication to prevent duplicate entries; deferred cursor/snapshot API as a broader contract change. | Duplicate mitigation is tested, but miss-free pagination requires server contract. | V1 | Concurrent insert/delete windows can still skip tools. | Caps implementation at 7. |
| SDK-AUDIT-016 | Medium / Reliability and operations | Deferred with rationale | Log only | No background scheduler actively refreshes upstream health. | Deferred because scheduler lifecycle, locking, deployment topology, and backoff need design. | No code fix attempted; current manual health checks remain. | V3 as regression only | Health status can age without worker/scheduler execution. | Caps reliability. |
| SDK-AUDIT-017 | Medium / Reliability and runtime behavior | Deferred with rationale | Log only | Fail-closed behavior can rely on stale unhealthy state. | Deferred pending freshness semantics and stale-status expiry contract. | Needs repository and invocation behavior changes with migration tests. | V3 as regression only | Healthy upstreams can remain blocked after stale failure records. | Caps reliability/DX. |
| SDK-AUDIT-018 | Medium / Reliability and resilience | Deferred with rationale | Log only | No circuit breaker or adaptive backpressure exists. | Deferred to resilience design covering thresholds, half-open probes, and operator overrides. | Partial retries alone would not be sufficient. | V3 as regression only | Repeated upstream failures can continue consuming resources. | Caps reliability. |
| SDK-AUDIT-019 | Low / Developer experience and testing | Fixed | SDK `pyproject.toml` | Local SDK tests required install/PYTHONPATH. | Added pytest source path config. | Plain local pytest now works in the SDK package. | V1 | None. | Improves DX/testability. |
| SDK-AUDIT-020 | Low / Developer experience and testing | Fixed | Product `pyproject.toml` | Product tests required install/PYTHONPATH in some local flows. | Added pytest source path config. | Plain local pytest now resolves sources consistently. | V2, V3 | None. | Improves DX/testability. |
| SDK-AUDIT-021 | Medium / Testing | Fixed | SDK `tests/test_sdk_behavior.py`; `tests/test_package_smoke.py` | Standalone SDK package had thin independent tests. | Added behavior tests for token validation, cache hygiene, closed clients, custom clients, hook errors, pagination de-dupe, and exports. | Tests exercise consumer-visible behavior without requiring product package. | V1 | No live gateway integration remains SDK-AUDIT-022. | Raises implementation confidence. |
| SDK-AUDIT-022 | High / Testing and integration | Deferred with rationale | Log only | No CI harness installs the wheel and talks to a running gateway. | Deferred because it needs a live service fixture, package install step, credentials, and release CI plumbing. | Existing SDK unit/package tests are not a substitute for live contract tests. | V1, V3 as partial regression | Installed-wheel/runtime API drift can still escape. | Caps implementation at 6. |
| SDK-AUDIT-023 | High / Testing and reliability | Deferred with rationale | Log only | No production-like load, concurrency, or multi-worker test exists. | Deferred pending load harness, DB backend, distributed limiter, and deployment topology. | Full unit suite is useful but not production-like stress evidence. | V3 | Race, scaling, and latency behavior remains unproven. | Caps reliability at 6. |
| SDK-AUDIT-024 | Low / Maintainability and testing | Deferred with rationale | Touched tests only | Product-wide mypy coverage has broad existing failures and skipped-import debt. | Cleaned touched Tool Gateway surface; deferred full repo mypy cleanup as separate staged work. | Touched files typecheck, but whole repo does not. | V5 passed; V6 failed with 171 errors | Monorepo type debt remains. | Slight implementation cap; blocks score 9. |
| SDK-AUDIT-025 | Medium / Packaging and release | Fixed | `.github/workflows/publish.yml` | Release strict-git validation was not enforced on release builds. | Release event validator now passes `--strict-git --expected-tag`. | Release artifacts are checked against tag cleanliness before publish-stage evidence. | V8 | Actual publication remains SDK-AUDIT-026. | Improves release confidence. |
| SDK-AUDIT-026 | Medium / Packaging and release | Deferred with rationale | `.github/workflows/publish.yml`; `docs/internal/pypi-publishing.md` | Workflow validates artifacts but does not upload to a package index. | Deferred because real publishing requires index choice, credentials, environment approvals, and rollback policy; docs now require manifest evidence. | Validation is stronger, but no production package publication exists. | V7, V8 | Consumers still lack proven index installation path. | Caps ease/release at 7. |
| SDK-AUDIT-027 | Low / CI and release ergonomics | Fixed | `.github/workflows/publish.yml` | Manual package selector did not constrain package-specific Python steps. | Added package-selection conditions to build/validate/SBOM/sign/attest/upload steps. | Manual dispatch now executes the selected package path more predictably. | V8 | Matrix readability could still improve. | Improves release DX. |
| SDK-AUDIT-028 | Medium / API stability and documentation | Fixed | SDK README; API reference; changelog | SDK beta status lacked an explicit compatibility matrix. | Added stability/compatibility matrix and beta expectations without claiming GA. | Consumers can assess support and breakage risk before adoption. | V1, docs review | Beta/pre-1.0 status remains. | Raises ease of use to 7. |
| SDK-AUDIT-029 | Low / Documentation and API consistency | Fixed | SDK API reference; README | Deprecated `status` parameter existed in code but not docs. | Documented deprecated `status`, including accepted value and replacement direction. | Docs now match runtime/API behavior. | V1 | Parameter remains for compatibility. | Improves DX. |
| SDK-AUDIT-030 | Low / DX and auth input validation | Fixed | SDK `sdk.py`; SDK tests; README; vendored SDK | SDK accepted raw token strings that already included `Bearer `. | Added raw-token format validation rejecting prefix, whitespace, and unsupported chars. | Prevents common integration error before sending a request; exported behavior is tested in standalone and vendored parity. | V1, V8 | None. | Improves DX/security hygiene. |
| SDK-AUDIT-031 | Low / Security diagnostics | Fixed | SDK `sdk.py`; tests/docs; vendored SDK | Discovery cache fingerprint used deterministic unsalted token hash. | Switched to process-local HMAC token fingerprint. | Cache partitioning no longer creates a stable offline token oracle. | V1, V8 | Fingerprint is still process-local, so cache is not shared across processes. | Improves security hygiene. |
| SDK-AUDIT-032 | Low / Security logging hygiene | Fixed | SDK `sdk.py`; tests/docs; vendored SDK | `get_tool()` not-found error could include arbitrary lookup text. | Sanitized/truncated lookup text in not-found errors. | Reduces accidental log injection or secret echo while keeping useful diagnostics. | V1, V8 | Caller logging can still leak data outside SDK control. | Improves security hygiene. |
| SDK-AUDIT-033 | Low / Runtime behavior and DX | Fixed | SDK `sdk.py`; tests/docs; vendored SDK | Clients had no explicit closed-state guard. | Sync and async clients now raise `ToolGatewayError(code="client_closed")` after close. | Predictable lifecycle errors replace accidental lower-level client failures. | V1, V8 | None. | Improves DX. |
| SDK-AUDIT-034 | Low / Maintainability | Deferred with rationale | Log only | Sync and async SDK implementations still duplicate logic. | Deferred because broad refactor risks behavior regressions during remediation; parity tests and vendored parity checks remain. | Not fixed; should be a dedicated refactor with exhaustive SDK tests. | V1, V8 as regression | Maintenance cost remains. | Blocks score 9, not production blocker alone. |
| SDK-AUDIT-035 | Medium / Reliability and integration safety | Fixed | SDK `sdk.py`; tests/docs; vendored SDK | Injected custom HTTP clients could bypass streaming response caps. | Custom clients must expose `stream()` by default; buffered clients require explicit `allow_buffered_custom_http_client=True`. | Safe default preserves response caps unless caller opts into responsibility. | V1, V8 | Opt-in buffered clients can still be unsafe if misused. | Improves reliability. |
| SDK-AUDIT-036 | Low / Observability and DX | Fixed | SDK `sdk.py`; tests/docs; vendored SDK | Event hook failures were always swallowed. | Added `raise_event_hook_errors=True` strict mode. | Default remains backward-compatible; strict consumers can fail closed and test hook wiring. | V1, V8 | No separate hook-error callback yet. | Improves observability/DX. |
| SDK-AUDIT-037 | Medium / Authorization and least privilege | Deferred with rationale | Threat model/runbook | Wildcard scopes remain supported and operational guardrails are mostly documentation. | Deferred because changing wildcard semantics can break credential models; docs now call out least-privilege guidance. | Documentation is not equivalent to authorization enforcement. | V3 as regression only | Overbroad wildcard credentials can expose too much catalog/action surface. | Caps security. |
| SDK-AUDIT-038 | Medium / Authorization and DX | Deferred with rationale | Log only | Credential issuance does not validate tool existence/required-scope match. | Deferred pending repository/service-layer validation design and migration for existing credentials. | Needs write-path validation plus backward-compatible error handling. | V3 as regression only | Bad scopes fail later at runtime instead of issuance time. | Caps security/DX. |
| SDK-AUDIT-039 | Medium / Authorization and operations | Deferred with rationale | Log only | Agent-tool permission grants defer required-scope mismatch to runtime. | Deferred pending grant-time validation semantics and UI/API compatibility. | Needs tests for grant mutation, tool updates, and required-scope drift. | V3 as regression only | Misconfigured grants can reach production and fail at invocation. | Caps DX/security. |
| SDK-AUDIT-040 | Low / Security input validation | Fixed | `models.py`; `tests/test_tool_gateway_upstream_phase1.py` | Upstream auth header prefix accepted permissive strings. | Prefix must now be a single auth-scheme token. | Rejects malformed or injection-prone prefixes at the model boundary. | V2, V3, V5 | None. | Improves security hygiene. |
| SDK-AUDIT-041 | Medium / Reliability and DX | Deferred with rationale | `models.py`; `invocation.py`; settings/docs/tests for partial mitigation | URL validation depends partly on DNS at configuration time. | Added allowlist and runtime revalidation; deferred complete DNS pinning/egress enforcement. | Partial mitigation is tested; final production-grade fix is infrastructure and resolver strategy. | V2, V3, V5 | DNS changes between validation and invocation can still matter. | Caps reliability/security. |
| SDK-AUDIT-042 | Medium / Feature completeness and adoption | Deferred with rationale | README/threat model/runbook | OAuth, mTLS, and dynamic per-tenant upstream auth are not implemented. | Deferred as product roadmap; current supported auth modes and limitations are documented. | Honest docs reduce surprise but do not add capability. | V3 as regression only | Some production upstreams remain unsupported. | Caps adoption/ease. |
| SDK-AUDIT-043 | Low / Runtime behavior and input validation | Fixed | `invocation.py`; `tests/test_tool_gateway_forwarding_phase2.py`; README | Query allowlists did not separately cap final expanded URL size. | Added final upstream URL byte-length cap with `upstream_url_too_large`. | Prevents unbounded path/query expansion before network request. | V2, V3, V5, V9 | Limit may need tuning for specific partners. | Improves reliability/security hygiene. |
| SDK-AUDIT-044 | Low / Public API and DX | Fixed | SDK `sdk.py`; `__init__.py`; tests/docs; vendored SDK | Boundary errors used plain `ValueError`. | Added exported `ToolGatewayValidationError(ValueError)` and converted SDK validation failures. | Preserves backward compatibility while giving consumers an SDK-specific catch point. | V1, V8 | Existing callers catching only `ValueError` still work. | Improves DX/API clarity. |
| SDK-AUDIT-045 | Medium / Security and logging | Accepted remaining risk | README/API docs only | SDK redaction remains pattern-based and cannot understand every domain secret. | Accepted for now; docs state limits and no sensitive request tokens are exposed by SDK hooks. | Pattern redaction plus token-free hooks are useful but incomplete by design. | V1 | Application logs outside SDK may still leak domain secrets. | Caps security at 6. |
| SDK-AUDIT-046 | Medium / Security and privacy | Deferred with rationale | Threat model/runbook | Response redaction defaults are not domain-PII aware. | Deferred pending product PII taxonomy and response-policy presets. | Needs real policy design, tests, and migration docs. | V3 as regression only | PII can survive default redaction depending on payload shape. | Caps security/compliance. |
| SDK-AUDIT-047 | Medium / Security documentation | Fixed | `docs/product-platform-worktree/tool-gateway-threat-model.md`; README link | No formal threat model described Tool Gateway boundaries. | Added threat model covering assets, trust boundaries, threats, mitigations, and open risks. | Gives reviewers/operators an explicit security model and risk register. | Docs review; V8 | Threat model must be kept current. | Improves security governance. |
| SDK-AUDIT-048 | Medium / Operations documentation | Fixed | `docs/product-platform-worktree/tool-gateway-production-runbook.md`; README link | No production incident runbook existed. | Added runbook for startup safety, incidents, secrets, rate limits, upstream failures, rollback, and release evidence. | Operators have concrete steps and required config references. | Docs review; V8 | Runbook has not been exercised in a live incident drill. | Improves operations/DX. |
| SDK-AUDIT-049 | Low / Documentation and release | Fixed | SDK `CHANGELOG.md`; README/API docs | Changelog under-described security/runtime remediation. | Expanded changelog with hardening and release notes. | Release readers can trace behavior changes. | V1 | Future changes still need discipline. | Improves release DX. |
| SDK-AUDIT-050 | Medium / Documentation and packaging | Fixed | SDK README; package docs | Install docs implied PyPI availability before publication proof. | Docs now describe unpublished/internal install status and artifact validation path. | Avoids misleading consumers and supports pre-publication package testing. | V1, V7 | Actual package publication remains SDK-AUDIT-026. | Raises ease of use. |
| SDK-AUDIT-051 | Low / Documentation consistency | Fixed | `docs/product-platform-worktree/execution-logs/06-tool-gateway-logs/README.md` | Execution logs could contradict current package/API state. | Added log index/current-status pointer. | Reviewers get a clear current source among historical logs. | Docs review | Historical logs remain historical evidence. | Improves reviewer DX. |
| SDK-AUDIT-052 | Low / Packaging and maintainability | Fixed | Standalone and vendored SDK `sdk.py`/`__init__.py`; validators/docs | Product package vendors SDK source, risking drift. | Synced vendored source and validated parity; release validators include parity/evidence checks. | Parity checks make drift visible during release validation. | V1, V7, V8 | Single-source packaging would be cleaner long term. | Improves maintainability. |
| SDK-AUDIT-053 | Low / Supply chain validation | Accepted remaining risk | `docs/internal/pypi-publishing.md`; validators indirectly | Dependency audit remains outside the default local validation command. | Accepted for this pass; release docs and validators point to security extras, but no one-command local audit wrapper was added. | Not fully sufficient; a reproducible dependency-audit script remains desirable. | V1, V7 | Local contributors can skip advisory audit unless following release docs. | Blocks score 9 supply-chain maturity. |
| SDK-AUDIT-054 | Medium / Supply chain and release | Deferred with rationale | Log/docs only | Package-level advisory coverage before publication is not proven. | Deferred until package is published or internal advisory scanning is wired to artifacts. | Cannot prove advisory coverage without index/package policy integration. | V1, V7 | Supply-chain evidence remains incomplete. | Caps release/security confidence. |
| SDK-AUDIT-055 | Low / Security examples | Accepted remaining risk | README/runbook docs | Local fixtures use deterministic tokens. | Accepted because deterministic values are confined to local tests/docs; production guards require real secrets and token pepper. | Safe if docs are followed; no production code path should use fixture tokens. | V2, V3 | Copy/paste misuse remains possible. | Minor security hygiene risk. |
| SDK-AUDIT-056 | Medium / Security governance | Fixed | `settings.py`; `models.py`; `invocation.py`; `api/app.py`; tests; README/runbook | No final host/domain allowlist existed at invocation time. | Added `OPHANIX_TOOL_GATEWAY_UPSTREAM_HOST_ALLOWLIST`; write and runtime invocation reject hosts outside exact/wildcard allowlist in production. | Defense is fail-closed, runtime-enforced, documented, and tested. | V2, V3, V5 | Egress firewall still required for final SSRF boundary. | Raises security/reliability. |
| SDK-AUDIT-057 | Low / Security information disclosure | Accepted remaining risk | Threat model/runbook/README | Wildcard credentials can discover callable tool catalog. | Accepted for now as part of current credential model; docs require least privilege and mention catalog exposure. | Documentation only; stronger enforcement needs auth model change. | V3 as regression only | Broad credentials can expose more metadata than ideal. | Minor security cap. |
| SDK-AUDIT-058 | Low / Release governance | Fixed | SDK and product `scripts/validate_release.py`; `docs/internal/pypi-publishing.md` | Release evidence did not include a manifest. | Validators now write `release-manifest.json` with package/version/artifact filename/hash/size; docs require it. | Auditable artifact metadata is generated by release validation. | V1, V7 | Manifest is local until archived by CI/release. | Improves release confidence. |
| SDK-AUDIT-059 | Low / Documentation and API lifecycle | Fixed | SDK `MIGRATION.md`; `pyproject.toml`; README/API docs | No consumer-facing migration guide existed for compatibility import lifecycle. | Added migration guide and included it in the package sdist. | Consumers get explicit compatibility/import migration path. | V1 | Future breaking changes need updated guide. | Improves DX. |
| SDK-AUDIT-060 | Medium / Reliability and operations | Deferred with rationale | Production runbook | Production readiness relies on external ingress/body limits and deployment controls not verified by code. | Added runbook/checklist coverage; deferred executable deployment conformance script. | Documentation is helpful but not proof. | V3, V8 | Ingress, WAF, egress, and body-limit controls can drift outside tests. | Caps operations/reliability. |

Summary of changed files:

- Runtime/config/security: `packages/product-platform/src/product_platform/api/app.py`, `api/settings.py`, `integrations/secrets.py`, `tool_gateway/models.py`, `tool_gateway/invocation.py`.
- SDK source and exports: `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py`, `__init__.py`, and the vendored copies under `packages/product-platform/src/ophanix_tool_gateway/`.
- Tests: SDK behavior/package tests and product auth/upstream/forwarding/secret-provider tests.
- Release/packaging: both package `pyproject.toml` files, both `scripts/validate_release.py` files, `.github/workflows/publish.yml`, and `docs/internal/pypi-publishing.md`.
- Documentation: SDK README/API reference/changelog/migration guide, product README, Tool Gateway threat model, production runbook, and execution-log README.

Remaining unresolved issues:

- Deferred with rationale: SDK-AUDIT-001, SDK-AUDIT-004, SDK-AUDIT-005, SDK-AUDIT-008, SDK-AUDIT-012, SDK-AUDIT-013, SDK-AUDIT-014, SDK-AUDIT-015, SDK-AUDIT-016, SDK-AUDIT-017, SDK-AUDIT-018, SDK-AUDIT-022, SDK-AUDIT-023, SDK-AUDIT-024, SDK-AUDIT-026, SDK-AUDIT-034, SDK-AUDIT-037, SDK-AUDIT-038, SDK-AUDIT-039, SDK-AUDIT-041, SDK-AUDIT-042, SDK-AUDIT-046, SDK-AUDIT-054, SDK-AUDIT-060.
- Accepted remaining risks: SDK-AUDIT-045, SDK-AUDIT-053, SDK-AUDIT-055, SDK-AUDIT-057.
- Already resolved: none.
- Invalid findings: none.

Updated scoring matrix:

| Category | Previous V4 score | Updated score | Raised/lowered/upheld | Exact reason | Remaining score cap | Preventing next score | Preventing 8 / 10 | Preventing 9 / 10 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Implementation quality | 6 / 10 | 6 / 10 | Upheld | Substantial SDK/runtime defects were fixed and full tests pass, but high architecture/testing gaps remain: production DB backend, idempotency, live installed-wheel contract test, load/multi-worker validation, and broad product mypy debt. | 6 | SDK-AUDIT-001, 004, 022, 023, 024 | Production DB, idempotency, live wheel-to-gateway CI, load/multi-worker harness, cleaner typing baseline | Modular gateway ownership, sync/async refactor, package publication evidence, only low residual debt |
| Ease of use | 6 / 10 | 7 / 10 | Raised | Setup friction, token validation, SDK-specific validation errors, docs, migration guide, compatibility matrix, and release docs improved. It remains beta and lacks live installed-wheel onboarding and actual index publication. | 7 | SDK-AUDIT-015, 022, 026, 038, 039, 042 | Proven install-from-index flow, live quickstart, cursor pagination/idempotency docs, grant/scope validation | GA stability policy, richer examples, generated API docs, low-only adoption concerns |
| Security and reliability | 5 / 10 | 6 / 10 | Raised | Production now rejects SQLite, demo secrets, legacy token hashes, unresolved-host bypass, and missing allowlists; SDK token/logging hygiene and runtime allowlists improved. Score remains capped by distributed limiter, SSRF egress/DNS residual risk, idempotency, response/PII policy gaps, and no load evidence. | 6 | SDK-AUDIT-004, 005, 008, 012, 013, 014, 023, 037, 041, 046, 060 | Distributed limiter, durable idempotency, egress enforcement, response/PII defaults, production-like failure tests | Formal security validation in CI, package advisory evidence, incident drill evidence, only low residual accepted risks |

Required fixes to reach production readiness:

1. Implement and validate a production database backend with pooling, migrations, transaction semantics, and multi-worker behavior.
2. Add a durable invocation idempotency and replay-protection contract across API, persistence, SDK/docs, and tests.
3. Replace process-local rate limiting with a distributed or edge-enforced limiter.
4. Add live installed-wheel SDK-to-running-gateway CI coverage.
5. Add production-like load, concurrency, and multi-worker validation.
6. Add deployable SSRF egress controls or a conformance script proving egress/WAF/ingress limits.
7. Define response storage, redaction, PII, and audit retention policies with tests.
8. Validate credential scope issuance and permission grants before runtime.

Required fixes to reach 8 out of 10:

- Close all high-severity deferred issues: SDK-AUDIT-001, 004, 005, 008, 022, 023.
- Publish or internally host the SDK package with verifiable install evidence.
- Add live quickstart/integration validation from the built wheel.
- Convert the remaining medium security policy gaps into explicit code-backed defaults or accepted product decisions.
- Establish a clean enough type/lint/test baseline that important SDK/gateway behavior is continuously checked.

Required fixes to reach 9 out of 10:

- Reduce remaining issues to low/nit only.
- Prove package advisory, SBOM, provenance, and release publication end to end.
- Exercise the runbook in an incident drill or staging game day.
- Replace vendored SDK source ownership with a cleaner single-source package dependency or mandatory automated sync check in CI.
- Refactor sync/async SDK duplication only after coverage is strong enough to prove parity.

Recommended remediation order:

1. Production DB backend and multi-worker validation.
2. Distributed rate limiting and idempotency/replay contract.
3. Live installed-wheel integration and package publication.
4. SSRF egress conformance and response/PII retention policies.
5. Authorization grant/scope write-path validation.
6. Product-wide mypy debt and SDK maintainability refactors.

Final strict assessment:

This pass materially improves the SDK and Tool Gateway production posture, especially around production startup safety, secret-provider enforcement, host allowlists, token handling, release evidence, and consumer documentation. It does not make broad external production adoption fully defensible. Constrained internal or pilot adoption is more defensible if operators accept the documented remaining risks and enforce external DB, egress, ingress, and release controls. Broad production adoption remains blocked by the deferred high-severity architecture, reliability, and integration-test items listed above.
