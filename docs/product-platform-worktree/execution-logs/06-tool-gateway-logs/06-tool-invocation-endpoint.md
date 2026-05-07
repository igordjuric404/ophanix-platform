# Phase 6: Tool Invocation Endpoint Execution Log

## Phase Overview

| # | Phase name | Goal | Status | Biggest checklist items |
|---|---|---|---|---|
| 1 | Tool Contract Registry | Persist, version, validate, and expose callable tool contracts. | Done | Tool definition migrations; repository CRUD and name lookup; schema validation; API routes; lifecycle audit events; registry tests. |
| 2 | Upstream Target Health | Register upstream business API targets and persist health state. | Done | Target and health-check migrations; target repository; health probe adapter; target APIs; health tests. |
| 3 | Gateway Token Verification | Authenticate external agent bearer tokens and resolve a gateway principal. | Done | Authorization parser; token hashing; credential lookup; agent lifecycle checks; safe verification events. |
| 4 | Agent Tool Permission Bindings | Grant, list, pause, revoke, and expire agent-to-tool permissions. | Done | Permission migrations; active lookup; API routes; reasoned lifecycle changes; expiration handling. |
| 5 | Tool Policy Decision | Produce deterministic allow/deny decisions and persist reasoned decision records. | Done | Decision models; payload summarization; deterministic checks; policy hook; decision tests. |
| 6 | Tool Invocation Endpoint | Add the external `/api/v1/tools/{tool_name}/invoke` contract. | Done | Gateway auth dependency; payload validation; policy call; mock executor; denied-call behavior. |
| 7 | Upstream Forwarding Adapter | Forward allowed invocations to registered upstream HTTP targets. | Not Started | Executor interface; target resolution; URL building; timeout/error handling; HTTP mock tests. |
| 8 | Response Handling And Redaction | Validate, size-limit, redact, and shape upstream responses. | Not Started | Response policy store; output validation; redaction; visibility controls; response tests. |
| 9 | Runtime Action Audit Store | Persist gateway runtime actions and event timelines. | Not Started | Runtime action migrations; write paths from gateway; read API; filters; security assertions. |
| 10 | Tool Decision Feed UI | Render operator-visible gateway decisions with filters and detail drawer. | Not Started | Navigation; API client; dense table; filters; drawer; component tests. |
| 11 | Python SDK Wrapper | Provide a thin typed Python client for calling the Tool Gateway. | Not Started | Client config; token provider; `call_tool`; error mapping; discovery helpers; SDK tests. |
| 12 | Direct HTTP Integration Examples | Provide tested direct HTTP examples and demo fixtures. | Not Started | Demo seed fixtures; curl examples; Python requests example; audit verification smoke tests. |

## Detailed Checklist

- [x] Read prior logs before starting.
- [x] Add invocation request/response models.
- [x] Add route `POST /api/v1/tools/{tool_name}/invoke`.
- [x] Allow this route to use gateway bearer auth without product-session middleware blocking it.
- [x] Propagate/create request id and correlation id.
- [x] Resolve active tool and validate payload against input schema.
- [x] Return safe `422` and unknown-tool responses.
- [x] Call the decision service before execution.
- [x] Add mock executor and ensure denied calls never execute.
- [x] Add API tests for auth, correlation, validation, allowed execution, denied execution, and decision persistence.

## Implementation Notes

- Reviewed Phase 5 handoff before starting. The endpoint must call `ToolPolicyDecisionService.evaluate_tool_call(...)` after gateway bearer auth and payload validation.
- Phase 6 plan path: `docs/product-platform-worktree/implementation-plans/07-tool-gateway/03-gateway-runtime/01-tool-invocation-endpoint.md`.
- Added `product_platform.tool_gateway.invocation` with `ToolInvocationRequest` and `ToolInvocationResponse`.
- Added `POST /api/v1/tools/{tool_name}/invoke` using the reusable gateway bearer dependency. Unknown or inactive tools currently return safe `404 Tool not found.`; execution remains intentionally stubbed until the decision/mock-executor slice.
- Invocation route now resolves active tools, validates `payload` against the persisted input schema via `validate_payload`, and calls `ToolPolicyDecisionService.evaluate_tool_call(...)` before execution. Denied decisions return a structured `403` envelope with decision and reason code; executor path remains stubbed until the mock-execution slice.
- Added `InMemoryToolInvocationExecutor` as the default local executor and support for `app.state.tool_gateway_executor` in tests/future adapters.
- Allowed decisions return `200` with executor result in the stable invocation envelope; denied decisions return before executor lookup/call.

## Commands

- `sed -n '1,260p' docs/product-platform-worktree/execution-logs/06-tool-gateway-logs/05-tool-policy-decision.md`: passed; decision service handoff loaded.
- `sed -n '1,260p' docs/product-platform-worktree/execution-logs/06-tool-gateway-logs/06-tool-invocation-endpoint.md`: passed; Phase 6 checklist loaded.
- `sed -n '1,220p' docs/product-platform-worktree/implementation-plans/07-tool-gateway/03-gateway-runtime/01-tool-invocation-endpoint.md`: passed; invocation endpoint plan loaded.
- `sed -n '1,220p' packages/product-platform/src/product_platform/tool_gateway/schemas.py`: passed; payload validator available as `validate_payload`.
- `sed -n '1,220p' packages/product-platform/src/product_platform/tool_gateway/auth.py`: passed; gateway principal dependency already exists in app.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_invocation_phase1.py' -v`: failed as expected before route implementation; missing token returned route-level 404 and valid-token unknown tool returned generic `Not Found`.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_invocation_phase1.py' -v`: passed; 3 tests verified missing-token 401, valid-token route handling, and request/correlation id propagation.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_invocation_phase2.py' -v`: failed as expected; active-tool requests still hit the 501 stub, so schema validation and decision calls are not wired yet.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_invocation_phase2.py' -v`: passed; 3 tests verified valid payload reaches decision, missing required payload field returns schema `422`, and unknown tools return safe `404`.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_invocation_phase3.py' -v`: partially passed; denied calls returned `403` and did not execute, but allowed calls still returned the intentional `501` stub.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_invocation_phase3.py' -v`: passed; 4 tests verified allowed execution, denied non-execution, denial reason code, and decision records for allowed/denied calls.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_invocation_phase*.py' -v`: passed; 10 Phase 6 tests verified auth, correlation, validation, decision, mock execution, denied non-execution, and decision persistence together.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_*.py' -v`: passed; 77 Tool Gateway tests verified Phases 1-6 together.

## Issues And Resolutions

- None yet.

## Next Phase Handoff

- Phase 7 should replace or extend the `app.state.tool_gateway_executor`/`InMemoryToolInvocationExecutor` path with an upstream HTTP forwarding adapter.
- The invocation route already authenticates, validates payloads, calls `ToolPolicyDecisionService`, denies before execution, and returns a stable response envelope.
- No known remaining work for Phase 6.
