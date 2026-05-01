# Protocol Bridge Configuration

## Feature Scope

Expose product configuration and health checks for protocol bridges such as A2A, MCP, IATP, and future adapters. This feature records bridge instances, allowed protocols, routing rules, and bridge health.

## Existing Repo Assets To Reuse

- `TrustBridge`, `ProtocolBridge`, `A2AAdapter`, and `MCPAdapter` from `packages/agent-mesh/src/agentmesh/trust/bridge.py`.
- MCP server registry.
- Mesh message ingestion.

## Out Of Scope

- Rewriting placeholder bridge methods.
- Building full protocol implementations. This plan configures and observes bridge instances.

## Data Model

Tables:

- `protocol_bridges`: id, organization_id, environment_id, name, bridge_type, status, config_json, created_at.
- `protocol_bridge_routes`: id, bridge_id, source_protocol, target_protocol, source_agent_id, target_agent_id, policy_binding_id, enabled.
- `protocol_bridge_health_checks`: id, bridge_id, status, latency_ms, message, checked_at.

## API Surface

Implement:

- `POST /api/v1/mesh/protocol-bridges`
- `GET /api/v1/mesh/protocol-bridges`
- `GET /api/v1/mesh/protocol-bridges/{id}`
- `PATCH /api/v1/mesh/protocol-bridges/{id}`
- `POST /api/v1/mesh/protocol-bridges/{id}/routes`
- `POST /api/v1/mesh/protocol-bridges/{id}/health-check`

## UI Surface

Mesh -> Protocol Bridges:

- Bridge list.
- Bridge detail.
- Route editor.
- Health status.

## Implementation Phases

### Phase 1: Bridge Registry

Steps:

1. Create bridge and route tables.
2. Add API to register bridge instance.
3. Validate bridge type against supported list.
4. Store config without secrets; reference secret ids where needed.

Tests:

- API test creates bridge.
- API test invalid bridge type rejected.
- Security test secrets are not persisted in config JSON.

### Phase 2: Route Configuration

Steps:

1. Add route creation endpoint.
2. Validate source/target protocols and agents.
3. Allow optional policy binding.
4. Emit audit event when route changes.

Tests:

- API test creates A2A to MCP route.
- API test route with unknown agent rejected.
- Integration test route change emits audit event.

### Phase 3: Health Checks

Steps:

1. Implement health check adapter for bridge type.
2. For placeholder bridge methods, report limited capability honestly.
3. Store health check results.
4. Expose current status in list.

Tests:

- Unit test health result for configured bridge.
- API test health check stores result.
- API test placeholder bridge reports limited capability, not healthy full-runtime status.

### Phase 4: UI

Steps:

1. Build bridge list table.
2. Build route editor.
3. Build health check panel.
4. Add warnings for bridge types backed by demo/placeholder implementations.

Tests:

- Component test bridge list renders status.
- Component test route editor validates protocol choices.
- Component test limited capability warning appears.

## Overall Validation

- Register a demo MCP bridge.
- Add route from support agent to MCP server.
- Run health check.
- Confirm route and health are visible and auditable.

## Dependencies

- Mesh message feed.
- Agent inventory.
- MCP server registry.
- Policy bindings.

## Definition Of Done

- Protocol bridge configuration is visible and honest about runtime capability.
- Routes can be managed without editing code.
