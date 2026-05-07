# Phase 5: Tool Policy Decision Execution Log

## Phase Overview

| # | Phase name | Goal | Status | Biggest checklist items |
|---|---|---|---|---|
| 1 | Tool Contract Registry | Persist, version, validate, and expose callable tool contracts. | Done | Tool definition migrations; repository CRUD and name lookup; schema validation; API routes; lifecycle audit events; registry tests. |
| 2 | Upstream Target Health | Register upstream business API targets and persist health state. | Done | Target and health-check migrations; target repository; health probe adapter; target APIs; health tests. |
| 3 | Gateway Token Verification | Authenticate external agent bearer tokens and resolve a gateway principal. | Done | Authorization parser; token hashing; credential lookup; agent lifecycle checks; safe verification events. |
| 4 | Agent Tool Permission Bindings | Grant, list, pause, revoke, and expire agent-to-tool permissions. | Done | Permission migrations; active lookup; API routes; reasoned lifecycle changes; expiration handling. |
| 5 | Tool Policy Decision | Produce deterministic allow/deny decisions and persist reasoned decision records. | Done | Decision models; payload summarization; deterministic checks; policy hook; decision tests. |
| 6 | Tool Invocation Endpoint | Add the external `/api/v1/tools/{tool_name}/invoke` contract. | Not Started | Gateway auth dependency; payload validation; policy call; mock executor; denied-call behavior. |
| 7 | Upstream Forwarding Adapter | Forward allowed invocations to registered upstream HTTP targets. | Not Started | Executor interface; target resolution; URL building; timeout/error handling; HTTP mock tests. |
| 8 | Response Handling And Redaction | Validate, size-limit, redact, and shape upstream responses. | Not Started | Response policy store; output validation; redaction; visibility controls; response tests. |
| 9 | Runtime Action Audit Store | Persist gateway runtime actions and event timelines. | Not Started | Runtime action migrations; write paths from gateway; read API; filters; security assertions. |
| 10 | Tool Decision Feed UI | Render operator-visible gateway decisions with filters and detail drawer. | Not Started | Navigation; API client; dense table; filters; drawer; component tests. |
| 11 | Python SDK Wrapper | Provide a thin typed Python client for calling the Tool Gateway. | Not Started | Client config; token provider; `call_tool`; error mapping; discovery helpers; SDK tests. |
| 12 | Direct HTTP Integration Examples | Provide tested direct HTTP examples and demo fixtures. | Not Started | Demo seed fixtures; curl examples; Python requests example; audit verification smoke tests. |

## Detailed Checklist

- [x] Read prior logs before starting.
- [x] Add decision persistence migration.
- [x] Define decision input/output models and stable reason codes.
- [x] Add safe payload summarization with secret redaction.
- [x] Add decision repository persistence/fetch methods.
- [x] Implement deterministic checks for agent, tool, permission, and scope.
- [x] Add simple policy hook interface with allow, deny, matched policy id, and fail-closed error behavior.
- [x] Add unit and integration tests for serialization, redaction, persistence, allow, denied reasons, and policy hook behavior.

## Implementation Notes

- Reviewed Phase 4 handoff before starting. The decision service should reuse `find_active_agent_tool_permission(...)` for active, unexpired binding resolution.
- Phase 5 plan path: `docs/product-platform-worktree/implementation-plans/07-tool-gateway/02-auth-policy/03-tool-policy-decision.md`.
- Added `0053_tool_policy_decisions` migrations:
  - Stores tenant/environment-scoped allow/deny decisions with optional agent/tool/permission references, stable reason code/message, optional matched policy id, request/correlation ids, redacted payload summary JSON, and creation time.
  - Added indexes for organization/environment chronology, agent chronology, tool chronology, and decision/reason filters.
- Updated DB migration smoke tests to expect `0053`, verify `tool_policy_decisions` exists after apply, and verify rollback removes only the decision table while leaving Phase 4 permission tables intact.
- Added `product_platform.tool_gateway.decision`:
  - `ToolPolicyDecisionCreate` validates `allow`/`deny` decisions and stable reason codes.
  - `ToolPolicyDecisionResult` serializes persisted decisions for services/API use.
  - `summarize_tool_payload` creates deterministic redacted summaries, redacting credential-like keys and truncating long strings.
  - `ToolPolicyDecisionRepository` persists and fetches decision records.
  - `tool_policy_decision_response` converts SQLite rows into typed results.
- Added `ToolPolicyDecisionService.evaluate_tool_call(...)` with ordered deterministic checks:
  - Missing/mismatched principal -> `agent_missing`.
  - Missing or inactive agent row -> `agent_missing` / `agent_inactive`.
  - Missing or inactive tool by name -> `tool_missing` / `tool_inactive`.
  - Missing active unexpired permission binding -> `permission_missing`.
  - Binding or credential scope mismatch with tool `required_scope` -> `scope_insufficient`.
  - Successful deterministic authorization -> `allowed`.
- Every decision path persists a `tool_policy_decisions` row with redacted payload summary, request id, and correlation id.
- Added policy hook support:
  - `ToolPolicyHookContext` passes agent, tool, binding, required scope, payload summary, and request context to hooks.
  - `ToolPolicyHookResult` supports `allow` or `deny`, optional matched policy id, and optional reason message.
  - Hook `allow` preserves the deterministic allow decision and persists matched policy id.
  - Hook `deny` returns `policy_denied` and persists matched policy id/reason.
  - Hook exceptions fail closed with `policy_error`.

## Commands

- `sed -n '1,220p' docs/product-platform-worktree/execution-logs/06-tool-gateway-logs/00-overview.md`: passed; overview shows Phases 1-4 done and Phase 5 next.
- `sed -n '1,260p' docs/product-platform-worktree/execution-logs/06-tool-gateway-logs/04-agent-tool-permission-bindings.md`: passed; active permission lookup and expiration handoff confirmed.
- `sed -n '1,260p' docs/product-platform-worktree/execution-logs/06-tool-gateway-logs/05-tool-policy-decision.md`: passed; Phase 5 checklist loaded.
- `sed -n '1,220p' docs/product-platform-worktree/implementation-plans/07-tool-gateway/02-auth-policy/03-tool-policy-decision.md`: passed; plan loaded.
- `sed -n '1,260p' packages/agent-os/src/agent_os/mcp_gateway.py`: passed; reused the existing fail-closed allow/deny gateway concept as design context.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_db_phase1.py' -v`: passed; 4 tests verified migration apply and rollback including `0053`.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_decision_phase1.py' -v`: failed as expected because `product_platform.tool_gateway.decision` does not exist yet.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_decision_phase1.py' -v`: failed after initial module implementation because the persistence fixture used fake FK ids and the redaction expectation did not match whole-value redaction for credential-like keys.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_decision_phase1.py' -v`: passed; 3 tests verified decision model serialization, payload redaction, and decision persistence/fetch.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_decision_phase2.py' -v`: failed as expected because `ToolPolicyDecisionService` is not implemented yet.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_decision_phase2.py' -v`: passed; 5 tests verified allow, suspended-agent deny, disabled-tool deny, missing-permission deny, and insufficient-scope deny.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_decision_phase3.py' -v`: failed as expected because policy hook context/result types are not implemented yet.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_decision_phase3.py' -v`: passed; 4 tests verified hook allow, hook deny override, hook fail-closed exception, and matched-policy persistence.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_decision_phase*.py' -v`: passed; 12 Phase 5 tests verified models, redaction, persistence, deterministic decisions, and policy hooks together.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_*.py' -v`: passed; 67 Tool Gateway tests verified Phases 1-5 together.

## Issues And Resolutions

- None yet.
- Initial decision persistence test used fake agent/tool/permission ids and hit SQLite FK enforcement. Adjusted the test to seed a real active agent, tool, and permission using Phase 4 repository APIs.
- Payload redaction intentionally redacts the entire value for credential-like keys such as `tokens`; adjusted the test to expect the safer whole-value redaction.

## Next Phase Handoff

- Phase 6 should call `ToolPolicyDecisionService.evaluate_tool_call(...)` after gateway auth and payload validation.
- The decision service persists every allow/deny path in `tool_policy_decisions` and returns `ToolPolicyDecisionResult`.
- Denied decisions use stable reason codes and already contain redacted payload summaries safe for runtime/audit use.
- No known remaining work for Phase 5.
