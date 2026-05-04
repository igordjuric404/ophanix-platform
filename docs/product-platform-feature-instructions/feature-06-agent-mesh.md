# Feature 06: Agent Mesh

## Feature Goal and Expected User Outcome

Validate that an operator can inspect mesh topology, register protocol bridges, add bridge routes, run bridge health checks, review message flow, and inspect task handoffs.

The expected outcome is visible mesh topology state, persisted bridge and route records, health-check output, and message or handoff records when mesh APIs are exercised.

## Implementation Surface

- Frontend route: `/mesh`.
- Frontend page: `frontend/src/features/mesh/MeshPage.tsx`.
- API endpoints include:
  - `GET /api/v1/mesh/topology`
  - `GET /api/v1/mesh/messages`
  - `POST /api/v1/mesh/messages`
  - `GET /api/v1/mesh/handoffs`
  - `POST /api/v1/mesh/handoffs`
  - `GET /api/v1/mesh/protocol-bridges`
  - `POST /api/v1/mesh/protocol-bridges`
  - `GET /api/v1/mesh/protocol-bridges/{bridge_id}`
  - `PATCH /api/v1/mesh/protocol-bridges/{bridge_id}`
  - `GET /api/v1/mesh/protocol-bridges/{bridge_id}/routes`
  - `POST /api/v1/mesh/protocol-bridges/{bridge_id}/routes`
  - `POST /api/v1/mesh/protocol-bridges/{bridge_id}/health-check`
- Domain modules: `mesh/repository.py`, `mesh/topology.py`, `mesh/bridges.py`.
- Migration: `0012_mesh_topology.up.sql`.
- Tests: `test_mesh_topology_*.py`, `test_protocol_bridge_configuration_*.py`, `frontend/src/features/mesh/MeshPage.test.tsx`.

## Prerequisites and Required Test Data

- Sign in as `admin@example.com` with `Platform Admin`.
- Use environment `Development`.
- Create at least two agents from Feature 02 if validating real source and target IDs.
- Suggested bridge values:
  - `Name`: `MCP Claims Bridge`
  - `Type`: `MCP`
  - `Endpoint`: `https://mcp.local/rpc`
  - `Secret ID`: `secret/demo-mcp`
  - `Status`: `configured`

## UI Validation Steps

1. Click `Mesh` in the left navigation.
2. Expected URL change: current route changes to `/mesh`.
3. Confirm page title `Mesh` and description `Agent mesh topology, message flow, handoffs, and protocol bridge controls.`
4. Confirm summary metrics:
   - `Nodes`
   - `Messages`
   - `Blocked Flow`
   - `Limited Bridges`
5. In `Live Edges`, enter optional filters:
   - `Start Time`: leave blank for all messages.
   - `End Time`: leave blank for all messages.
   - Click `Filter`.
6. Expected UI response:
   - If no messages exist, topology shows `No topology` and `Mesh messages will create nodes and edges.`
   - If messages exist, nodes and edges render from source and target IDs.
7. In `Bridge Control`, fill:
   - `Name`: `MCP Claims Bridge`
   - `Type`: `MCP`
   - `Endpoint`: `https://mcp.local/rpc`
   - `Secret ID`: `secret/demo-mcp`
   - `Status`: `configured`
8. Click `Register`.
9. Expected UI response: bridge row appears in the table.
10. Filter bridge rows if needed:
    - `Bridge Type`: `MCP`
    - `Bridge Status`: `configured`
    - Click `Filter`.
11. Open the bridge detail.
12. Expected UI response:
    - Detail shows bridge name, status, endpoint, health, and updated time.
    - The UI displays a limited-runtime warning: `Limited runtime: AgentMesh bridge adapters are placeholder/pass-through implementations, so runtime delivery is limited and not reported as healthy.`
13. Click `Run Check`.
14. Expected UI response: health-check status and message update. In local placeholder mode, do not expect a production-healthy bridge unless the adapter and endpoint are configured.
15. In the bridge edit form, set:
    - `Edit Name`: `MCP Claims Bridge Validation`
    - `Edit Status`: `active`
16. Click `Save`.
17. Expected UI response: bridge row updates with the new name and status.
18. In `Routes`, add a route:
    - `Source Protocol`: `A2A`
    - `Target Protocol`: `MCP`
    - `Source Agent`: source agent ID from Feature 02
    - `Target Agent`: target agent ID or MCP server ID, depending on the route being modeled
    - `Policy Binding`: leave blank unless you created a relevant policy binding
19. Click `Add Route`.
20. Expected UI response: route row appears in the bridge route table.
21. In `Message Feed`, filter:
    - `Message Source`: source agent ID
    - `Message Target`: target agent ID
    - `Protocol`: `A2A`
    - `Decision`: leave blank or choose a known decision
    - `Action`: leave blank or enter a known action
    - Click `Filter`
22. Expected UI response:
    - Matching messages appear with route, protocol, decision, latency, and detail.
    - If no messages exist, the empty state `No messages` is visible.
23. Open a message detail if present.
24. Expected UI response: detail shows action, route, protocol, correlation, and payload JSON.
25. In `Task Transfers`, filter:
    - `Handoff Source`: source agent ID
    - `Handoff Target`: target agent ID
    - `Status`: leave blank or choose a known status
    - Click `Filter`
26. Expected UI response:
    - Matching handoffs appear with route, task, trust-policy, status, and detail.
    - If no handoffs exist, the empty state `No handoffs` is visible.
27. Open a handoff detail if present.
28. Expected UI response: detail shows route, reason, correlation, capabilities, and metadata.

## Expected Backend Effects

- Bridge registration creates a protocol bridge record with type, endpoint, secret reference, and status.
- Bridge patch updates persisted name or status.
- Health check records latest bridge health status and timestamp.
- Route creation creates a bridge route connecting source protocol, target protocol, source agent, target agent, and optional policy binding.
- Posted mesh messages create message records and update topology output.
- Posted handoffs create handoff records and can participate in trust or policy validation depending on payload.

## Programmatic Verification

```bash
API=http://127.0.0.1:8088
COOKIE=/tmp/ophanix.cookies

curl -s -c "$COOKIE" \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.com","roles":["Platform Admin"]}' \
  "$API/api/v1/auth/dev-login" >/dev/null

SOURCE_AGENT=$(curl -s -b "$COOKIE" -H 'X-Environment-ID: env_default' "$API/api/v1/agents" | jq -r '.[0].id')
TARGET_AGENT=$(curl -s -b "$COOKIE" -H 'X-Environment-ID: env_default' "$API/api/v1/agents" | jq -r '.[1].id // .[0].id')
```

Create a bridge and route:

```bash
BRIDGE_JSON=$(curl -s -b "$COOKIE" \
  -H 'Content-Type: application/json' \
  -H 'X-Environment-ID: env_default' \
  -d '{
    "name":"MCP Claims Bridge API",
    "bridge_type":"MCP",
    "status":"configured",
    "config":{"endpoint_url":"https://mcp.local/rpc","secret_id":"secret/demo-mcp"}
  }' \
  "$API/api/v1/mesh/protocol-bridges")

echo "$BRIDGE_JSON" | jq
BRIDGE_ID=$(echo "$BRIDGE_JSON" | jq -r '.id')

curl -s -b "$COOKIE" -H 'Content-Type: application/json' -H 'X-Environment-ID: env_default' \
  -d "{
    \"source_protocol\":\"A2A\",
    \"target_protocol\":\"MCP\",
    \"source_agent_id\":\"$SOURCE_AGENT\",
    \"target_agent_id\":\"$TARGET_AGENT\"
  }" \
  "$API/api/v1/mesh/protocol-bridges/$BRIDGE_ID/routes" | jq

curl -s -b "$COOKIE" -H 'Content-Type: application/json' -H 'X-Environment-ID: env_default' \
  -d '{}' "$API/api/v1/mesh/protocol-bridges/$BRIDGE_ID/health-check" | jq
```

Create and inspect message and handoff records:

```bash
curl -s -b "$COOKIE" -H 'Content-Type: application/json' -H 'X-Environment-ID: env_default' \
  -d "{
    \"source_agent_id\":\"$SOURCE_AGENT\",
    \"target_agent_id\":\"$TARGET_AGENT\",
    \"protocol\":\"A2A\",
    \"action\":\"claims.transfer\",
    \"decision\":\"allowed\",
    \"latency_ms\":25,
    \"correlation_id\":\"mesh-validation\",
    \"payload_summary\":{\"claim_id\":\"claim_123\"}
  }" \
  "$API/api/v1/mesh/messages" | jq

curl -s -b "$COOKIE" -H 'Content-Type: application/json' -H 'X-Environment-ID: env_default' \
  -d "{
    \"source_agent_id\":\"$SOURCE_AGENT\",
    \"target_agent_id\":\"$TARGET_AGENT\",
    \"task_type\":\"claims.transfer\",
    \"required_capabilities\":[\"claims:read\"],
    \"trust_result\":\"allowed\",
    \"policy_result\":\"allowed\",
    \"status\":\"requested\",
    \"reason\":\"validation handoff\",
    \"correlation_id\":\"mesh-validation\",
    \"metadata\":{\"purpose\":\"guide\"}
  }" \
  "$API/api/v1/mesh/handoffs" | jq

curl -s -b "$COOKIE" -H 'X-Environment-ID: env_default' "$API/api/v1/mesh/topology" | jq
curl -s -b "$COOKIE" -H 'X-Environment-ID: env_default' "$API/api/v1/mesh/messages?source_agent_id=$SOURCE_AGENT" | jq
curl -s -b "$COOKIE" -H 'X-Environment-ID: env_default' "$API/api/v1/mesh/handoffs?source_agent_id=$SOURCE_AGENT" | jq
```

Focused automated tests:

```bash
cd packages/product-platform
PYTHONPATH=src python3 -m unittest \
  tests.test_mesh_topology_overall \
  tests.test_protocol_bridge_configuration_overall \
  -v

cd frontend
npm test -- MeshPage.test.tsx
```

## Edge Cases and Alternative Flows

- No messages: topology intentionally shows `No topology`.
- Bridge health unhealthy: expected in local placeholder/pass-through mode unless a real adapter is configured.
- Missing target agent: route creation may fail validation or create a route to an unresolved target depending on payload; verify the API response.
- Empty handoffs: `Task Transfers` should show `No handoffs`.
- Disabled bridge: set status to `disabled` and confirm it still appears with disabled status but should not be treated as active.

## Integration Setup Required: Live Protocol Bridges

The implemented bridge controls include a warning that AgentMesh bridge adapters are placeholder/pass-through implementations. To validate a real bridge:

1. Provision the protocol endpoint for MCP, A2A, IATP, ACP, or a custom bridge.
2. Store any shared secret or client credential and capture the secret ID.
3. Register the bridge with the live endpoint and secret ID.
4. Run `Run Check`.
5. Confirm the health result reports a healthy adapter, not the placeholder warning.
6. Send a real message through the protocol bridge and verify it appears in `Message Feed`.

Needs verification: production delivery semantics and bridge health success depend on external adapter implementation.

## Troubleshooting

- Bridge row does not appear: query `GET /api/v1/mesh/protocol-bridges` with `X-Environment-ID: env_default`.
- Health check always reports limited or unhealthy: this is expected unless the real adapter is configured.
- Route creation fails: confirm protocol values are valid and source/target IDs are not empty.
- Topology missing a node: confirm at least one message exists with that agent as source or target.
