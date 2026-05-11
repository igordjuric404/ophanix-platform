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
