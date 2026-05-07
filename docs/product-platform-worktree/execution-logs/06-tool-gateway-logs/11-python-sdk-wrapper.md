# Phase 11: Python SDK Wrapper Execution Log

## Phase Overview

| # | Phase name | Goal | Status | Biggest checklist items |
|---|---|---|---|---|
| 1 | Tool Contract Registry | Persist, version, validate, and expose callable tool contracts. | Done | Tool definition migrations; repository CRUD and name lookup; schema validation; API routes; lifecycle audit events; registry tests. |
| 2 | Upstream Target Health | Register upstream business API targets and persist health state. | Done | Target and health-check migrations; target repository; health probe adapter; target APIs; health tests. |
| 3 | Gateway Token Verification | Authenticate external agent bearer tokens and resolve a gateway principal. | Done | Authorization parser; token hashing; credential lookup; agent lifecycle checks; safe verification events. |
| 4 | Agent Tool Permission Bindings | Grant, list, pause, revoke, and expire agent-to-tool permissions. | Done | Permission migrations; active lookup; API routes; reasoned lifecycle changes; expiration handling. |
| 5 | Tool Policy Decision | Produce deterministic allow/deny decisions and persist reasoned decision records. | Done | Decision models; payload summarization; deterministic checks; policy hook; decision tests. |
| 6 | Tool Invocation Endpoint | Add the external `/api/v1/tools/{tool_name}/invoke` contract. | Done | Gateway auth dependency; payload validation; policy call; mock executor; denied-call behavior. |
| 7 | Upstream Forwarding Adapter | Forward allowed invocations to registered upstream HTTP targets. | Done | Executor interface; target resolution; URL building; timeout/error handling; HTTP mock tests. |
| 8 | Response Handling And Redaction | Validate, size-limit, redact, and shape upstream responses. | Done | Response policy store; output validation; redaction; visibility controls; response tests. |
| 9 | Runtime Action Audit Store | Persist gateway runtime actions and event timelines. | Done | Runtime action migrations; write paths from gateway; read API; filters; security assertions. |
| 10 | Tool Decision Feed UI | Render operator-visible gateway decisions with filters and detail drawer. | Done | Navigation; API client; dense table; filters; drawer; component tests. |
| 11 | Python SDK Wrapper | Provide a thin typed Python client for calling the Tool Gateway. | Done | Client config; token provider; `call_tool`; error mapping; discovery helpers; SDK tests. |
| 12 | Direct HTTP Integration Examples | Provide tested direct HTTP examples and demo fixtures. | In Progress | Demo seed fixtures; curl examples; Python requests example; audit verification smoke tests. |

## Detailed Checklist

- [x] Read prior logs before starting.
- [x] Phase 1: Add SDK module using product-platform Python packaging patterns.
- [x] Phase 1: Define client configuration with base URL normalization, timeout default, and token provider.
- [x] Phase 1: Add `TokenProvider`, static token provider, `ToolCallResult`, `ToolDefinition`, `ToolGatewayError`, and `ToolDeniedError`.
- [x] Phase 1: Add configuration validation tests for required base URL, timeout defaults, and static token provider.
- [x] Phase 1: Run focused SDK tests and fix skeleton failures.
- [x] Phase 2: Implement `call_tool` with bearer auth and request body mapping.
- [x] Phase 2: Send `X-Correlation-ID` header and request body correlation id when provided.
- [x] Phase 2: Map `403` responses to `ToolDeniedError` with reason code and request/correlation ids.
- [x] Phase 2: Map gateway/upstream/network failures to typed `ToolGatewayError`.
- [x] Phase 2: Add tests for success, denied responses, per-request token provider calls, correlation header, and typed error mapping.
- [x] Phase 2: Run focused SDK tests and fix call failures.
- [x] Phase 3: Implement `list_tools`.
- [x] Phase 3: Implement `get_tool` using the existing `/api/v1/tools` list contract and name/id matching.
- [x] Phase 3: Keep discovery cache disabled by default and only cache when explicitly configured.
- [x] Phase 3: Add tests for tool discovery mapping, not found handling, and cache default.
- [x] Phase 3: Run focused SDK tests and the Tool Gateway regression suite.

## Implementation Notes

- Reviewed prior execution logs through Phase 10 before starting.
- Phase 11 plan path: `docs/product-platform-worktree/implementation-plans/07-tool-gateway/05-sdk-integration/01-python-sdk-wrapper.md`.
- Placement decision: implement the SDK as `product_platform.tool_gateway.sdk` instead of adding a new package, because `packages/product-platform` already owns the gateway contract, is packaged from `src/product_platform`, and already depends on `httpx`.
- Official HTTPX docs consulted: client instances provide connection pooling and shared request configuration; HTTPX enforces default timeouts and supports client-level timeout configuration.
- Added `product_platform.tool_gateway.sdk` with a small synchronous client shell, `TokenProvider` protocol, `StaticTokenProvider`, typed call/tool dataclasses, typed error classes, base URL normalization, timeout validation, optional injected `httpx.Client`, and context-manager close support.
- Added Phase 1 SDK tests for required base URL validation, timeout default/base URL normalization, and static token provider behavior.
- Added `call_tool`, including bearer auth, request body mapping, optional correlation header/body forwarding, gateway JSON parsing, typed success mapping, `403` to `ToolDeniedError`, non-2xx gateway/upstream failures to `ToolGatewayError`, and HTTPX transport failures to `ToolGatewayError(code="transport_error")`.
- Added Phase 2 SDK tests using `httpx.MockTransport` for successful tool calls, denial mapping, per-request token provider calls, correlation metadata, gateway failure mapping, and transport failure mapping.
- Added `list_tools` and `get_tool` discovery helpers. `list_tools` calls `/api/v1/tools` with bearer auth and typed query parameters, maps JSON objects into `ToolDefinition`, and caches list results only when `cache_tools=True`. `get_tool` resolves by tool name or id from the list contract and raises `ToolGatewayError(code="tool_not_found", status_code=404)` when absent.
- Added Phase 3 SDK tests for list response mapping, `get_tool` matching, not-found handling, default no-cache behavior, and explicit cache reuse.
- Added package-level exports from `product_platform.tool_gateway` for the SDK client, providers, result types, and errors, with a test proving the public namespace works.

## Commands

- `sed -n '1,260p' docs/product-platform-worktree/implementation-plans/07-tool-gateway/05-sdk-integration/01-python-sdk-wrapper.md`: passed; Phase 11 SDK plan loaded.
- `sed -n '1,260p' docs/product-platform-worktree/execution-logs/06-tool-gateway-logs/11-python-sdk-wrapper.md`: passed; stale Phase 11 status table loaded for correction.
- `rg --files packages/product-platform | rg 'sdk|client|pyproject|test_tool_gateway|README|examples'`: passed; confirmed no existing SDK module and located test/package conventions.
- `sed -n '1,240p' packages/product-platform/pyproject.toml`: passed; confirmed `httpx` dependency and `src/product_platform` wheel package.
- `rg --files packages/product-platform/src/product_platform | sed -n '1,240p'`: passed; confirmed `product_platform.tool_gateway` is the appropriate colocated module namespace.
- `sed -n '2890,3245p' packages/product-platform/src/product_platform/api/app.py`: passed; invocation endpoint response contract inspected.
- `sed -n '5130,5190p' packages/product-platform/src/product_platform/api/app.py`: passed; tool list/get API contracts inspected.
- `PYTHONPATH=src python3 -m unittest tests.test_tool_gateway_sdk_phase1 -v`: failed before test import because `tests` is not an importable package in this repo; switched to unittest discovery.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_sdk_phase1.py' -v`: failed as expected before implementation with `ModuleNotFoundError: No module named 'product_platform.tool_gateway.sdk'`.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_sdk_phase1.py' -v`: passed after adding the SDK skeleton; 3 tests passed.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_sdk_phase2.py' -v`: failed as expected before implementation with six `AttributeError` failures because `OphanixToolGatewayClient.call_tool` was missing.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_sdk_phase2.py' -v`: passed after implementing `call_tool`; 6 tests passed.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_sdk_phase3.py' -v`: failed as expected before implementation with five missing-method errors for `list_tools` and `get_tool`.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_sdk_phase3.py' -v`: passed after implementing discovery helpers; 5 tests passed.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_sdk_phase*.py' -v`: passed before the public export polish; 14 tests passed.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_*.py' -v`: passed before the public export polish; 127 tests passed.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_sdk_phase1.py' -v`: failed after adding the public namespace import test because `product_platform.tool_gateway` did not yet re-export the SDK symbols.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_sdk_phase1.py' -v`: passed after exporting SDK symbols from `tool_gateway/__init__.py`; 4 tests passed.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_sdk_phase*.py' -v`: passed after the public export polish; 15 tests passed.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_*.py' -v`: passed after the public export polish; 128 tests passed.

## Issues And Resolutions

- None yet.

## Next Phase Handoff

- Phase 11 is complete. Phase 12 can use the tested SDK (`product_platform.tool_gateway.sdk` or package-level imports) and the direct HTTP gateway contract for integration examples.
