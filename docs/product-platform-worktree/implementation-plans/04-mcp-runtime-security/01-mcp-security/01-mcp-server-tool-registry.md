# MCP Server And Tool Registry

## Feature Scope

Create the product registry for MCP servers and tools. Users can register servers, ingest tool definitions, track schema versions, assign owners, bind policies, and see tool risk status.

## Existing Repo Assets To Reuse

- MCP gateway from `packages/agent-os/src/agent_os/mcp_gateway.py`.
- MCP security scanner from `packages/agent-os/src/agent_os/mcp_security.py`.
- MCP examples under `packages/agent-mesh/examples` and `examples/mcp-trust-verified-server`.

## Out Of Scope

- Security scanning implementation. Covered separately.
- Proxy traffic and approvals. Covered separately.

## Data Model

Tables:

- `mcp_servers`: id, organization_id, environment_id, name, endpoint_url, owner_user_id, auth_type, status, policy_pack_id, created_at.
- `mcp_tools`: id, server_id, name, description, current_version_id, risk_level, status, created_at.
- `mcp_tool_versions`: id, tool_id, schema_json, schema_hash, definition_json, discovered_at, scan_status.

## API Surface

Implement:

- `POST /api/v1/mcp/servers`
- `GET /api/v1/mcp/servers`
- `GET /api/v1/mcp/servers/{id}`
- `PATCH /api/v1/mcp/servers/{id}`
- `POST /api/v1/mcp/servers/{id}/discover-tools`
- `GET /api/v1/mcp/tools`
- `GET /api/v1/mcp/tools/{id}`

## UI Surface

MCP Security -> Servers.

MCP Security -> Tools.

Tool detail drawer.

## Implementation Phases

### Phase 1: Server Registry

Steps:

1. Create MCP server table.
2. Add create, list, get, update API.
3. Validate endpoint URL and owner.
4. Emit audit event for create/update/status changes.

Tests:

- API test creates MCP server.
- API test invalid endpoint rejected.
- API test server is environment-scoped.
- Integration test audit event emitted.

### Phase 2: Tool Discovery Contract

Steps:

1. Define tool discovery adapter interface.
2. Implement local/demo MCP discovery adapter.
3. Normalize tool definitions into name, description, schema, definition.
4. Calculate schema hash.

Tests:

- Unit test schema hash is stable.
- Unit test tool definition normalization.
- API test discover tools creates tool versions.

### Phase 3: Tool Versioning

Steps:

1. Store every changed schema as new version.
2. Keep current version pointer on tool.
3. Mark tool as changed when schema hash differs.
4. Emit audit event for tool schema changes.

Tests:

- Integration test unchanged schema does not create duplicate version.
- Integration test changed schema creates new version.
- API test current version points to newest discovered version.

### Phase 4: UI

Steps:

1. Build server table with status, owner, tools, last discovery.
2. Build register server form.
3. Build tools table with schema hash, risk, policy status.
4. Build tool detail drawer with schema and versions.

Tests:

- Component test server table renders.
- Component test discover tools action calls API.
- Component test tool detail shows schema version history.

## Overall Validation

- Register local demo MCP server.
- Discover tools.
- Change one demo tool schema and rediscover.
- Confirm version history and audit event.

## Dependencies

- Event pipeline.
- Agent inventory for owner references.
- Policy bindings for policy status display.

## Definition Of Done

- MCP servers and tools are product resources with owners, versions, and audit history.
