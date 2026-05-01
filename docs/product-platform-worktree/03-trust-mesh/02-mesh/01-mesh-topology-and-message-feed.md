# Mesh Topology And Message Feed

## Feature Scope

Build the live mesh topology and message feed. The feature stores inter-agent messages and handoffs, renders topology, and lets users inspect communication decisions and trust context.

## Existing Repo Assets To Reuse

- AgentMesh event bus concepts.
- Trust handshake events.
- Framework integration adapters as message emitters.
- Existing dashboard topology ideas from Streamlit demos.

## Out Of Scope

- Protocol bridge configuration.
- Implementing every framework SDK hook in this feature.

## Data Model

Tables:

- `mesh_messages`: id, organization_id, environment_id, source_agent_id, target_agent_id, protocol, action, decision, latency_ms, correlation_id, payload_summary_json, created_at.
- `mesh_handoffs`: id, source_agent_id, target_agent_id, task_type, required_capabilities_json, trust_result, policy_result, status, correlation_id, created_at.
- `mesh_topology_snapshots`: id, organization_id, environment_id, time_bucket, nodes_json, edges_json, created_at.

## API Surface

Implement:

- `POST /api/v1/mesh/messages`
- `GET /api/v1/mesh/messages`
- `POST /api/v1/mesh/handoffs`
- `GET /api/v1/mesh/handoffs`
- `GET /api/v1/mesh/topology`

## UI Surface

Mesh -> Topology.

Mesh -> Messages.

Mesh -> Handoffs.

Agent Detail -> Mesh activity section.

## Implementation Phases

### Phase 1: Message Ingestion

Steps:

1. Create message and handoff tables.
2. Add ingestion endpoint for SDKs/adapters.
3. Validate source and target agents.
4. Emit audit event for blocked or escalated messages.

Tests:

- API test ingests message.
- API test unknown source agent is rejected.
- API test blocked message emits audit event.

### Phase 2: Message Feed API

Steps:

1. Add query filters for source, target, protocol, decision, action, time range.
2. Add pagination.
3. Join trust score and agent names.
4. Support correlation id lookup.

Tests:

- API test filters by protocol.
- API test filters by source agent.
- API test correlation id lookup returns matching message.

### Phase 3: Topology Snapshot

Steps:

1. Aggregate messages into nodes and edges for selected time range.
2. Calculate edge volume, deny rate, average latency.
3. Include node status and trust tier.
4. Cache short-lived topology response.

Tests:

- Unit test aggregation creates expected edge.
- Unit test deny rate calculation.
- API test topology includes trust tier.

### Phase 4: UI

Steps:

1. Build topology graph with filters.
2. Build messages table.
3. Build handoff table.
4. Use shared drawers for message and handoff detail.

Tests:

- Component test topology renders nodes and edges.
- Component test message table filters by protocol.
- Component test blocked handoff shows reason.

## Overall Validation

- Run demo agent handoff.
- Confirm message appears in feed.
- Confirm topology edge appears.
- Confirm blocked handoff links to trust and policy reason.

## Dependencies

- Agent inventory.
- Trust thresholds.
- Event pipeline.
- Frontend shell.

## Definition Of Done

- Inter-agent communication is visible as live product state, not simulated graph data.
