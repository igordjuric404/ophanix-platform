# Phase 4: Agent Tool Permission Bindings Execution Log

## Phase Overview

| # | Phase name | Goal | Status | Biggest checklist items |
|---|---|---|---|---|
| 1 | Tool Contract Registry | Persist, version, validate, and expose callable tool contracts. | Done | Tool definition migrations; repository CRUD and name lookup; schema validation; API routes; lifecycle audit events; registry tests. |
| 2 | Upstream Target Health | Register upstream business API targets and persist health state. | Done | Target and health-check migrations; target repository; health probe adapter; target APIs; health tests. |
| 3 | Gateway Token Verification | Authenticate external agent bearer tokens and resolve a gateway principal. | Done | Authorization parser; token hashing; credential lookup; agent lifecycle checks; safe verification events. |
| 4 | Agent Tool Permission Bindings | Grant, list, pause, revoke, and expire agent-to-tool permissions. | Done | Permission migrations; active lookup; API routes; reasoned lifecycle changes; expiration handling. |
| 5 | Tool Policy Decision | Produce deterministic allow/deny decisions and persist reasoned decision records. | Not Started | Decision models; payload summarization; deterministic checks; policy hook; decision tests. |
| 6 | Tool Invocation Endpoint | Add the external `/api/v1/tools/{tool_name}/invoke` contract. | Not Started | Gateway auth dependency; payload validation; policy call; mock executor; denied-call behavior. |
| 7 | Upstream Forwarding Adapter | Forward allowed invocations to registered upstream HTTP targets. | Not Started | Executor interface; target resolution; URL building; timeout/error handling; HTTP mock tests. |
| 8 | Response Handling And Redaction | Validate, size-limit, redact, and shape upstream responses. | Not Started | Response policy store; output validation; redaction; visibility controls; response tests. |
| 9 | Runtime Action Audit Store | Persist gateway runtime actions and event timelines. | Not Started | Runtime action migrations; write paths from gateway; read API; filters; security assertions. |
| 10 | Tool Decision Feed UI | Render operator-visible gateway decisions with filters and detail drawer. | Not Started | Navigation; API client; dense table; filters; drawer; component tests. |
| 11 | Python SDK Wrapper | Provide a thin typed Python client for calling the Tool Gateway. | Not Started | Client config; token provider; `call_tool`; error mapping; discovery helpers; SDK tests. |
| 12 | Direct HTTP Integration Examples | Provide tested direct HTTP examples and demo fixtures. | Not Started | Demo seed fixtures; curl examples; Python requests example; audit verification smoke tests. |

## Detailed Checklist

- [x] Read prior logs before starting.
- [x] Add permission and permission-history migrations.
- [x] Add grant/list/update/pause/revoke/active lookup repository methods.
- [x] Enforce one active agent-tool permission per environment.
- [x] Reject retired/decommissioned agents and retired tools.
- [x] Add API request/response models and routes.
- [x] Require reasons for pause and revoke.
- [x] Emit audit events for permission changes.
- [x] Support `expires_at`, inactive expired lookups, and stale-expiration marking.
- [x] Add repository and API tests for grants, duplicate rejection, retired resources, revocation, listing, and expiration.

## Implementation Notes

- Added `0052_tool_gateway_permissions` migrations:
  - `agent_tool_permissions` stores tenant/environment-scoped agent-tool bindings with scope, lifecycle status, grant/revoke metadata, and optional `expires_at`.
  - `agent_tool_permission_history` stores lifecycle/action history for each permission.
  - Added a partial unique index on `(organization_id, environment_id, agent_id, tool_id)` for `active` and `paused` permissions so revoked/expired bindings do not block future grants.
  - Added agent, tool, and expiry indexes for list and expiration queries.
- Updated the DB migration smoke test to expect migration `0052`, assert the new tables exist after apply, and assert rollback removes only the permission tables while leaving prior Tool Gateway upstream tables intact.
- Added initial repository behavior tests in `test_tool_gateway_permissions_phase1.py` covering active grants, duplicate rejection, retired-tool rejection, inactive-agent rejection, revoke history, and active lookup ignoring revoked permissions.
- Added permission request/response/history models and repository methods:
  - `grant_agent_tool_permission`, `get_agent_tool_permission`, `list_agent_tool_permissions`, `find_active_agent_tool_permission`, `update_agent_tool_permission`, `pause_agent_tool_permission`, `revoke_agent_tool_permission`, and `list_agent_tool_permission_history`.
  - Grant requires both the agent and tool to be visible in the current tenant/environment and `active`.
  - Duplicate active/paused permissions surface as `DuplicateAgentToolPermissionError`.
  - Permission rows are joined with agent/tool metadata for API responses and list views.
  - Lifecycle changes write `agent_tool_permission_history`.
- Added permission API routes:
  - `POST /api/v1/agents/{agent_id}/tool-permissions`
  - `GET /api/v1/agents/{agent_id}/tool-permissions`
  - `GET /api/v1/tools/{tool_id}/agent-permissions`
  - `PATCH /api/v1/agent-tool-permissions/{permission_id}`
  - `POST /api/v1/agent-tool-permissions/{permission_id}/pause`
  - `POST /api/v1/agent-tool-permissions/{permission_id}/revoke`
- Write routes require `security:manage`; list routes require `agent:read`.
- Pause and revoke use `AgentToolPermissionActionRequest`, making a nonblank `reason` mandatory.
- Permission writes emit audit events from `tool-gateway-permissions` with resource type `agent_tool_permission` and agent/tool metadata in the payload.
- Expiration handling:
  - `expires_at` is accepted on grant and returned by repository/API responses.
  - `find_active_agent_tool_permission` ignores permissions whose `expires_at` is at or before the comparison time.
  - `mark_expired_agent_tool_permissions` marks stale active/paused permissions as `expired` and records an `expired` history event with actor `system`.
  - List endpoints can filter and return `expired` permissions.

## Commands

- `sed -n '1,260p' docs/product-platform-worktree/execution-logs/06-tool-gateway-logs/01-tool-contract-registry.md`: passed previously; registry handoff available.
- `sed -n '1,260p' docs/product-platform-worktree/execution-logs/06-tool-gateway-logs/02-upstream-target-health.md`: passed previously; upstream handoff available.
- `sed -n '1,260p' docs/product-platform-worktree/execution-logs/06-tool-gateway-logs/03-gateway-token-verification.md`: passed; gateway auth handoff available.
- `PYTHONPATH=src python3 -m unittest tests.test_db_phase1 -v`: failed because `tests` is not an importable package in this repo.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_db_phase1.py' -v`: passed; 4 tests verified migration apply and rollback including the new permission tables.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_permissions_phase1.py' -v`: failed as expected before implementation because `AgentToolPermissionGrantRequest` and repository permission surface do not exist yet.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_permissions_phase1.py' -v`: passed; 5 tests verified grant, duplicate rejection, retired-tool rejection, inactive-agent rejection, revoke history, and active lookup behavior.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_permissions_phase2.py' -v`: failed as expected with six `404 Not Found` responses because the permission API routes were not implemented yet.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_permissions_phase2.py' -v`: passed; 6 tests verified grant/list routes, tool/agent metadata, revoke reason validation, RBAC, and audit event ordering/payloads.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_permissions_phase3.py' -v`: partially passed; active lookup ignored an expired timestamp, but two tests failed because `mark_expired_agent_tool_permissions` is not implemented yet.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_permissions_phase3.py' -v`: failed once after implementation because expiration history used the simulated comparison timestamp and sorted behind the grant event.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_permissions_phase3.py' -v`: passed; 3 tests verified active lookup expiration behavior, stale expiration marking, history, and API exposure of expired status.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_permissions_phase*.py' -v`: passed; 14 Phase 4 tests verified repository, API, RBAC, audit, revoke, listing, and expiration behavior together.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_*.py' -v`: passed; 55 Tool Gateway tests verified Phases 1-4 together.

## Issues And Resolutions

- The first DB test command used module import syntax and failed with `ModuleNotFoundError: No module named 'tests.test_db_phase1'`. Reran via unittest discovery, which is the established test invocation for this repo.
- Expiration history initially used the deterministic comparison timestamp as `created_at`, which could sort behind the grant event. Changed history `created_at` to the actual write time while keeping expiration comparison deterministic.

## Next Phase Handoff

- Phase 5 can use `ToolRegistryRepository.find_active_agent_tool_permission(agent_id=..., tool_id=..., scope=..., now=...)` to resolve active, unexpired bindings.
- Phase 5 can call `mark_expired_agent_tool_permissions(now=...)` before decision checks if it needs persisted expired state; active lookup already treats stale permissions as inactive even before marking.
- Permission API/audit routes are implemented and tested; no known remaining work for Phase 4.
