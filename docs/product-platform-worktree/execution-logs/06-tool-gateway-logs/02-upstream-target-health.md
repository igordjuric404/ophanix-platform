# Phase 2: Upstream Target Health Execution Log

## Phase Overview

| # | Phase name | Goal | Status | Biggest checklist items |
|---|---|---|---|---|
| 1 | Tool Contract Registry | Persist, version, validate, and expose callable tool contracts. | Done | Tool definition migrations; repository CRUD and name lookup; schema validation; API routes; lifecycle audit events; registry tests. |
| 2 | Upstream Target Health | Register upstream business API targets and persist health state. | Done | Target and health-check migrations; target repository; health probe adapter; target APIs; health tests. |
| 3 | Gateway Token Verification | Authenticate external agent bearer tokens and resolve a gateway principal. | In Progress | Authorization parser; token hashing; credential lookup; agent lifecycle checks; safe verification events. |
| 4 | Agent Tool Permission Bindings | Grant, list, pause, revoke, and expire agent-to-tool permissions. | Not Started | Permission migrations; active lookup; API routes; reasoned lifecycle changes; expiration handling. |
| 5 | Tool Policy Decision | Produce deterministic allow/deny decisions and persist reasoned decision records. | Not Started | Decision models; payload summarization; deterministic checks; policy hook; decision tests. |
| 6 | Tool Invocation Endpoint | Add the external `/api/v1/tools/{tool_name}/invoke` contract. | Not Started | Gateway auth dependency; payload validation; policy call; mock executor; denied-call behavior. |
| 7 | Upstream Forwarding Adapter | Forward allowed invocations to registered upstream HTTP targets. | Not Started | Executor interface; target resolution; URL building; timeout/error handling; HTTP mock tests. |
| 8 | Response Handling And Redaction | Validate, size-limit, redact, and shape upstream responses. | Not Started | Response policy store; output validation; redaction; visibility controls; response tests. |
| 9 | Runtime Action Audit Store | Persist gateway runtime actions and event timelines. | Not Started | Runtime action migrations; write paths from gateway; read API; filters; security assertions. |
| 10 | Tool Decision Feed UI | Render operator-visible gateway decisions with filters and detail drawer. | Not Started | Navigation; API client; dense table; filters; drawer; component tests. |
| 11 | Python SDK Wrapper | Provide a thin typed Python client for calling the Tool Gateway. | Not Started | Client config; token provider; `call_tool`; error mapping; discovery helpers; SDK tests. |
| 12 | Direct HTTP Integration Examples | Provide tested direct HTTP examples and demo fixtures. | Not Started | Demo seed fixtures; curl examples; Python requests example; audit verification smoke tests. |

## Detailed Checklist

- [x] Read completed Phase 1 log before starting.
- [x] Confirm active tool registry lookup is available.
- [x] Add target and health-check migrations.
- [x] Add target repository methods for create, get, patch, active resolve by tool, and health state fetch.
- [x] Validate HTTP method and URL shape.
- [x] Ensure one active/configured target per tool/environment.
- [x] Add health probe adapter with timeout, expected status, persisted status/error, and fail-closed exception behavior.
- [x] Add API request/response models and routes.
- [x] Emit audit events for target changes.
- [x] Add integration and unit tests from the plan.

## Implementation Notes

- Added migration `0051_tool_gateway_upstreams.up.sql` with `tool_upstream_targets` and `tool_upstream_health_checks`.
- Added rollback migration `0051_tool_gateway_upstreams.down.sql`.
- Updated `tests/test_db_phase1.py` to track Tool Gateway feature migrations via `FEATURE_MIGRATIONS = ["0050", "0051"]`.
- Extended `tool_gateway.models` with upstream target create/patch/response models and HTTP URL/method/auth/status validation.
- Extended `ToolRegistryRepository` with upstream target create/get/patch, health fetch, active target resolve by tool, active target resolve by active tool name, and health-result persistence.
- Added `tests/test_tool_gateway_upstream_phase1.py` covering target creation, duplicate active-target rejection, invalid URL validation, and target resolution by tool name.
- Added `tool_gateway.health.ToolUpstreamHealthChecker` with injectable HTTP client support.
- Added `tests/test_tool_gateway_upstream_phase2.py` covering healthy, unexpected status, timeout, and exception health results.
- Added upstream target API routes in `product_platform/api/app.py`: create/get target, patch target, manual health check, and get health.
- Added audit events for target creation and update.
- Added `tests/test_tool_gateway_upstream_phase3.py` covering API creation, disabled-tool rejection, manual health persistence, write RBAC, and target audit events.
- Phase 2 Definition of Done is satisfied: tools can be mapped to upstream targets, target health is persisted/visible, and later runtime phases can resolve targets without parsing metadata.

## Commands

- `sed -n '1,260p' docs/product-platform-worktree/execution-logs/06-tool-gateway-logs/01-tool-contract-registry.md`: passed; confirmed Phase 1 completed and noted repository/API handoff.
- `sed -n '1,260p' docs/product-platform-worktree/implementation-plans/07-tool-gateway/01-tool-registry/02-upstream-target-health.md`: passed earlier during planning; Phase 2 implementation plan ready to re-check before edits.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p test_db_phase1.py -v`: passed; 4 migration smoke tests verified `0051`.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p test_tool_gateway_upstream_phase1.py -v`: passed; 4 target store tests.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p test_tool_gateway_upstream_phase2.py -v`: passed; 4 health probe tests.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p test_tool_gateway_upstream_phase3.py -v`: passed; 5 target API tests.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_upstream_phase*.py' -v`: passed; 13 upstream target tests.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_*.py' -v`: passed; 28 Tool Gateway tests across registry and upstream phases.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p test_db_phase1.py -v`: passed after Phase 2 API implementation; 4 migration smoke tests.

## Issues And Resolutions

- No implementation blockers.

## Next Phase Handoff

- Phase 3 can use `ToolRegistryRepository.resolve_upstream_target_by_tool_name` for active tool target resolution in later runtime phases.
- `ToolUpstreamHealthChecker` supports injected clients through `app.state.tool_gateway_http_client`, which later tests can reuse.
- Target write routes require `security:manage`; reads require `agent:read`.
