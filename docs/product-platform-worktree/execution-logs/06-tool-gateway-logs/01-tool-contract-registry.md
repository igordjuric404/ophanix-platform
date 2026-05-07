# Phase 1: Tool Contract Registry Execution Log

## Phase Overview

| # | Phase name | Goal | Status | Biggest checklist items |
|---|---|---|---|---|
| 1 | Tool Contract Registry | Persist, version, validate, and expose callable tool contracts. | Done | Tool definition migrations; repository CRUD and name lookup; schema validation; API routes; lifecycle audit events; registry tests. |
| 2 | Upstream Target Health | Register upstream business API targets and persist health state. | In Progress | Target and health-check migrations; target repository; health probe adapter; target APIs; health tests. |
| 3 | Gateway Token Verification | Authenticate external agent bearer tokens and resolve a gateway principal. | Not Started | Authorization parser; token hashing; credential lookup; agent lifecycle checks; safe verification events. |
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

### Phase 1.1: Registry Store

- [x] Add migration `0050_tool_gateway_registry.up.sql` with `tool_definitions` and `tool_definition_versions`.
- [x] Add matching rollback migration `0050_tool_gateway_registry.down.sql`.
- [x] Enforce unique active/non-retired tool names by organization and environment.
- [x] Implement `product_platform.tool_gateway` package with models, validation helpers, and repository.
- [x] Add repository methods for create, list, get, patch, activate, disable, versions, and active lookup by name.
- [x] Save initial `tool_definition_versions` row when a tool is created.
- [x] Add repository tests for create, duplicate same-environment rejection, same-name different-environment allowance, and status filtering.
- [x] Run targeted Phase 1.1 tests and inspect output.

### Phase 1.2: Schema Validation

- [x] Validate `input_schema_json` against JSON Schema Draft 2020-12.
- [x] Validate optional `output_schema_json` against JSON Schema Draft 2020-12.
- [x] Store tools in draft even when schemas are missing, but reject activation if input schema is absent or invalid.
- [x] Return clear schema validation errors through API error responses.
- [x] Add unit tests for valid schemas, invalid schemas, and activation failure with invalid/missing schema.
- [x] Run targeted Phase 1.2 tests and inspect output.

### Phase 1.3: API Routes

- [x] Add request/response models for create, list, get, patch, activate, disable, and versions.
- [x] Add API routes for `POST /api/v1/tools`, `GET /api/v1/tools`, `GET /api/v1/tools/{id}`, `PATCH /api/v1/tools/{id}`, `POST /api/v1/tools/{id}/activate`, `POST /api/v1/tools/{id}/disable`, and `GET /api/v1/tools/{id}/versions`.
- [x] Scope all routes by authenticated organization and selected environment.
- [x] Emit audit events for create, update, activate, and disable.
- [x] Add API tests for create/retrieve, status and owner filters, patch versioning, invalid activation, and audit events.
- [x] Run all Tool Contract Registry tests and inspect output.

## Implementation Notes

- Added Tool Gateway registry migration `0050_tool_gateway_registry.up.sql`.
- Added rollback migration `0050_tool_gateway_registry.down.sql`.
- Updated the database migration smoke test to include `0050` while preserving legacy rollback assertions.
- Added `product_platform.tool_gateway` package with `models.py`, `schemas.py`, and `repository.py`.
- Added `jsonschema>=4.22.0,<5.0` to product platform dependencies because registry schema validation uses `Draft202012Validator.check_schema`.
- Added `tests/test_tool_gateway_registry_phase1.py` covering repository creation, duplicate rejection, same-name different-environment allowance, status filtering, and active name lookup.
- Added `tests/test_tool_gateway_registry_phase2.py` covering JSON Schema validation helpers, invalid-schema create rejection, missing-input activation failure, and invalid persisted-schema activation failure.
- Added Tool Gateway API routes in `product_platform/api/app.py` for create, list, get, patch, activate, disable, and version listing.
- Added `tests/test_tool_gateway_registry_phase3.py` covering route behavior, schema error details, lifecycle audit events, and versioning from contract patches.
- Phase 1 Definition of Done is satisfied: tool definitions are persisted/versioned, schemas are validated before activation, lifecycle changes are audited, and active tool name lookup is available for later gateway phases.

## Commands

- `pwd`: passed; confirmed workspace root.
- `rg --files docs/product-platform-worktree/implementation-plans/07-tool-gateway`: passed; identified all Tool Gateway plans.
- `sed` plan reads: passed; extracted recommended build order and Phase 1 requirements.
- Web docs lookup: passed; found `jsonschema` and HTTPX docs relevant to schema validation and later forwarding.
- `python3 -m pytest tests/test_db_phase1.py`: failed because the active Python interpreter does not have `pytest`; switched to the documented unittest runner.
- `PYTHONPATH=src python3 -m unittest tests.test_db_phase1 -v`: failed because the `tests` directory is not importable as a package; switched to unittest discovery.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p test_db_phase1.py -v`: failed once because chained rollback expectations still assumed the old final migration, then passed after updating the test.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p test_tool_gateway_registry_phase1.py -v`: passed; 4 tests verified repository Phase 1.1 behavior.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p test_tool_gateway_registry_phase2.py -v`: passed; 5 tests verified schema validation and activation fail-closed behavior.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p test_tool_gateway_registry_phase3.py -v`: passed; 6 tests verified API routes, versioning, validation errors, and audit events.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_registry_phase*.py' -v`: passed; 15 Tool Contract Registry tests.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p test_db_phase1.py -v`: passed; 4 migration smoke tests after registry migration addition.

## Issues And Resolutions

- Test environment uses `unittest`, not `pytest`; resolved by following `README.md`.
- Adding migration `0050` required keeping the old `EXPECTED_MIGRATIONS` list for legacy rollback assertions and introducing `ALL_EXPECTED_MIGRATIONS` for apply-all assertions.

## Next Phase Handoff

- Phase 2 can use `ToolRegistryRepository.get_tool`, `get_tool_by_name(active_only=True)`, `list_tools`, and active/draft lifecycle endpoints.
- Tool registry API writes require `security:manage`; reads require `agent:read`.
- Tool names are unique for open statuses (`draft`, `active`, `disabled`) per organization/environment.
- Schemas are stored canonically as JSON text and serialized back as dictionaries in API responses.
