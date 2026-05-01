# MCP Server And Tool Registry Execution Log

Source plan: `docs/product-platform-worktree/04-mcp-runtime-security/01-mcp-security/01-mcp-server-tool-registry.md`

Official docs checked: MCP authorization/security guidance from `modelcontextprotocol.io` on 2026-05-01, especially least-privilege scopes, transport security, token/audience validation, sandboxing cautions, and audit-friendly authorization decisions.

## Phase Overview

| Phase | Goal | Status | Biggest Checklist Items |
| --- | --- | --- | --- |
| Phase 1: Server Registry | Persist MCP server records and expose tenant/environment-scoped create/list/get/update APIs. | Done | `mcp_servers` table; endpoint/owner validation; audit create/update/status changes; focused API tests. |
| Phase 2: Tool Discovery Contract | Normalize discovered MCP tool definitions through a demo/local adapter and calculate stable schema hashes. | Done | Discovery adapter interface; demo adapter; normalization; hash tests; discover API. |
| Phase 3: Tool Versioning | Persist schema versions, maintain current-version pointers, and audit schema changes. | Done | Changed-schema detection; no duplicate unchanged versions; current pointer; audit events. |
| Phase 4: UI | Build MCP Security server/tool views and tool detail drawer. | Done | Server table/form; tools table; discovery action; schema version drawer; component tests. |

## Detailed Checklist

### Phase 1: Server Registry

- [x] Re-read this execution log, previous `03-trust-mesh` logs, and the source plan before coding.
- [x] Inspect current product API, DB migration, repository, audit, tenancy, and frontend navigation patterns.
- [x] Add `mcp_servers` migration with tenant/environment scope, endpoint URL, owner, auth type, status, optional policy pack, created/updated timestamps if consistent with local patterns.
- [x] Add server request/response models.
- [x] Add tenant-scoped repository methods to create, list, get, and update MCP servers.
- [x] Validate endpoint URL is HTTP or HTTPS and structurally valid.
- [x] Validate owner exists in the scoped user/agent inventory model used by the product.
- [x] Validate status and auth type values conservatively.
- [x] Add `POST /api/v1/mcp/servers`.
- [x] Add `GET /api/v1/mcp/servers`.
- [x] Add `GET /api/v1/mcp/servers/{id}`.
- [x] Add `PATCH /api/v1/mcp/servers/{id}`.
- [x] Emit audit event for server create.
- [x] Emit audit event for updates, especially status changes.
- [x] Add API test that creates an MCP server.
- [x] Add API test that rejects an invalid endpoint.
- [x] Add API test that servers are environment-scoped.
- [x] Add integration test that create/update audit events are emitted.
- [x] Run focused Phase 1 backend tests until passing.
- [x] Update this log with files changed, commands, observed output, issues, and next action.

### Phase 2: Tool Discovery Contract

- [x] Re-read Phase 1 notes and the source plan before starting.
- [x] Define tool discovery adapter interface.
- [x] Implement local/demo MCP discovery adapter.
- [x] Normalize tool definitions into name, description, schema, and raw definition.
- [x] Calculate deterministic schema hash using canonical JSON.
- [x] Add `mcp_tools` and `mcp_tool_versions` migration if not already created in Phase 1.
- [x] Add repository methods for tool lookup, creation, and version creation.
- [x] Add `POST /api/v1/mcp/servers/{id}/discover-tools`.
- [x] Add `GET /api/v1/mcp/tools`.
- [x] Add `GET /api/v1/mcp/tools/{id}`.
- [x] Unit test stable schema hash.
- [x] Unit test tool definition normalization.
- [x] API test discover tools creates tool versions.
- [x] Run focused Phase 1-2 backend tests until passing.
- [x] Update this log with files changed, commands, observed output, issues, and next action.

### Phase 3: Tool Versioning

- [x] Re-read prior notes and the source plan before starting.
- [x] Ensure every changed schema creates a new `mcp_tool_versions` row.
- [x] Ensure unchanged schema does not create a duplicate version.
- [x] Keep `mcp_tools.current_version_id` pointed at the newest discovered version.
- [x] Mark tool risk/status as changed when schema hash differs.
- [x] Emit audit event for schema changes.
- [x] Integration test unchanged schema does not create duplicate version.
- [x] Integration test changed schema creates a new version.
- [x] API test current version points to newest discovered version.
- [x] Run all MCP registry backend tests until passing.
- [x] Update this log with files changed, commands, observed output, issues, and next action.

### Phase 4: UI

- [x] Re-read prior notes, the source plan, and frontend shell/navigation patterns before starting.
- [x] Add frontend API client methods for MCP server/tool endpoints.
- [x] Add MCP Security navigation entries for Servers and Tools.
- [x] Build server table with status, owner, tool count, and last discovery.
- [x] Build register server form.
- [x] Wire discover-tools action to the API.
- [x] Build tools table with schema hash, risk level, and policy status.
- [x] Build tool detail drawer with schema JSON and version history.
- [x] Component test server table renders.
- [x] Component test discover-tools action calls API.
- [x] Component test tool detail shows schema version history.
- [x] Run focused frontend tests until passing.
- [x] Run broader MCP registry backend/frontend validation.
- [x] Update this log with files changed, commands, observed output, issues, and next action.

## Overall Validation Checklist

- [x] Register a local/demo MCP server.
- [x] Discover tools.
- [x] Change one demo tool schema and rediscover.
- [x] Confirm version history.
- [x] Confirm audit events.
- [x] Confirm relevant UI views render and actions call the expected APIs.

## Progress Notes

- 2026-05-01: Created initial execution log from the implementation plan and checked current official MCP authorization/security docs for context. Next action: inspect existing product API/DB/audit patterns and implement Phase 1 Server Registry in the smallest tested slices.
- 2026-05-01: Re-read the MCP registry plan, the newly created execution log, the completed Protocol Bridge log, current API/audit/mesh repository patterns, migrations, seed data, and official MCP security docs. Added migration `0014_mcp_registry` with `mcp_servers`, tenant/environment scope, owner FK, auth/status fields, policy pack id, timestamps, and indexes. Updated DB migration expectations for the new migration. Next action: run focused DB migration tests.
- 2026-05-01: Ran `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_db_phase1.py' -v`; first run failed because `0014_mcp_registry.down.sql` did not remove its `schema_migrations` row, matching the local down-migration convention. Patched the down migration with `DELETE FROM schema_migrations WHERE version = '0014';` and reran the same command; result: 3 tests passed. Next action: add MCP registry models/repository/API and focused Phase 1 API tests.
- 2026-05-01: Added `product_platform.mcp` package with server request/response models, HTTP(S) endpoint validation, auth/status enum validation, and tenant-scoped repository methods for create/list/get/update. Owner validation requires an active user with active organization membership; optional policy pack validation accepts real policies or demo policy placeholders. Added `/api/v1/mcp/servers` create/list/get/patch routes and `mcp.server.created`/`mcp.server.updated` audit events. Added `tests/test_mcp_server_tool_registry_phase1.py` covering create/list/get/patch, invalid endpoint rejection, environment scoping, unknown owner rejection, and audit events. First run had 4 passing tests and 1 failure because `env_other` was not registered in the test `TenantStore`, causing middleware to return 403 before route scoping was exercised. Patched the test tenant store and reran `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_mcp_server_tool_registry_phase1.py' -v`; result: 5 tests passed. Next action: run DB plus MCP Phase 1 tests together before closing Phase 1.
- 2026-05-01: Phase 1 final verification passed. Commands: `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_db_phase1.py' -v` passed 3 tests, and `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_mcp_server_tool_registry_phase1.py' -v` passed 5 tests. Phase 1 Server Registry is complete. Next action: re-read this log and the source plan, then start Phase 2 Tool Discovery Contract.
- 2026-05-01: Started Phase 2. Re-read this execution log, Phase 1 notes, the source plan, the current MCP Tools specification, and local MCP example/gateway assets. Added migration `0015_mcp_tools` with `mcp_tools` and `mcp_tool_versions`, indexes for server/tool lookup and schema hashes, and updated migration expectations. Next action: run focused DB migration tests.
- 2026-05-01: Ran `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_db_phase1.py' -v`; result: 3 tests passed. Next action: implement discovery adapter, normalization/hash helpers, tool repository methods, and Phase 2 tests.
- 2026-05-01: Added `product_platform.mcp.discovery` with `MCPToolDiscoveryAdapter`, deterministic `DemoMCPToolDiscoveryAdapter`, MCP tool-name/schema normalization, and stable `sha256:` schema hashes over canonical JSON. Added tool/version response models, repository persistence for discovered tools and versions, server `tool_count`/`last_discovered_at`, and API routes for discover/list/get tools. Added `tests/test_mcp_server_tool_registry_phase2.py` covering stable hashes, normalization, and API discovery persistence. First run passed but emitted a Pydantic warning for field name `schema`; renamed the Python field to `input_schema` with serialized alias `schema`, then reran `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_mcp_server_tool_registry_phase2.py' -v`; result: 3 tests passed with no warning. Next action: run DB plus MCP Phase 1-2 tests together.
- 2026-05-01: Phase 2 final verification passed. Commands: `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_db_phase1.py' -v` passed 3 tests, and `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_mcp_server_tool_registry_phase*.py' -v` passed 8 tests across Phases 1-2. Phase 2 Tool Discovery Contract is complete. Next action: re-read this log and the source plan, then start Phase 3 Tool Versioning.
- 2026-05-01: Implemented Phase 3 schema versioning. `persist_discovered_tools` now compares the current version hash before creating a new version, skips duplicate version rows when the schema is unchanged, marks existing tools as `changed` when a new schema hash appears, updates `current_version_id` to the newest version, and returns schema-change metadata. The discover API now emits `mcp.tool.schema.changed` audit events for existing tools whose schema changed. Added `tests/test_mcp_server_tool_registry_phase3.py` covering unchanged rediscovery, changed schema via demo `?schema=v2`, newest current-version pointers, and audit payload/correlation. Ran `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_mcp_server_tool_registry_phase3.py' -v`; result: 3 tests passed. Next action: run all MCP registry backend tests with DB migration coverage.
- 2026-05-01: Phase 3 final backend verification passed. Commands: `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_db_phase1.py' -v` passed 3 tests, and `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_mcp_server_tool_registry_phase*.py' -v` passed 11 tests across Phases 1-3. Phase 3 Tool Versioning is complete. Next action: re-read this log and frontend shell patterns, then start Phase 4 UI.
- 2026-05-01: Implemented Phase 4 MCP registry UI. Added `frontend/src/mcp.js` with server registry panel, register form, discover action controls, tools table, tool detail drawer content, and form payload normalization. Wired MCP API client methods, `/mcp` shell rendering, route-load refresh, register/discover handlers, and tool detail drawer opening. Added MCP frontend styles and `frontend/test/mcp.test.js` covering server table rendering, MCP route rendering, tool detail/version history, payload normalization, and API endpoint paths. Ran `node --test test/mcp.test.js`; result: 5 tests passed. Next action: run frontend typecheck and validation.
- 2026-05-01: Ran frontend validation from `packages/product-platform/frontend`. `npm run typecheck` passed across source and tests, then `npm run validate` passed with lint ok, typecheck ok, and 105 frontend tests passing. Next action: add/run overall MCP registry backend validation for register, discover, changed schema rediscovery, version history, and audit events.
- 2026-05-01: Added `tests/test_mcp_server_tool_registry_overall.py` for the source plan overall validation: register a local/demo MCP server, discover tools, patch the demo endpoint to `?schema=v2`, rediscover, confirm changed version history/current pointer/server tool count, and confirm `mcp.tool.schema.changed` audit event with correlation id. Focused overall run passed 1 test. Final feature validation passed: `test_db_phase1.py` passed 3 tests; `test_mcp_server_tool_registry*.py` passed 12 tests; frontend `npm run validate` passed lint, typecheck, and 105 tests. MCP Server And Tool Registry is complete. Next action: start `02-mcp-security-scans.md`.
