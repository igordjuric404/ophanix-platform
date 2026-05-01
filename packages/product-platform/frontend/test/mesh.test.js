import assert from "node:assert/strict";
import test from "node:test";

import { createApiClient } from "../src/apiClient.js";
import { renderAgentDetail } from "../src/agents.js";
import {
  meshMessageParamsFromValues,
  protocolBridgeRoutePayloadFromValues,
  renderMeshHandoffsTable,
  renderMeshMessagesTable,
  renderMeshPage,
  renderProtocolBridgesPanel,
  renderMeshTopologyGraph
} from "../src/mesh.js";

const topology = {
  nodes: [
    { agent_id: "agent_a", name: "Agent A", status: "active", trust_tier: "trusted", message_count: 2 },
    { agent_id: "agent_b", name: "Agent B", status: "active", trust_tier: "standard", message_count: 2 }
  ],
  edges: [
    {
      source_agent_id: "agent_a",
      target_agent_id: "agent_b",
      protocol: "a2a",
      volume: 2,
      denied_count: 1,
      deny_rate: 0.5,
      average_latency_ms: 35
    }
  ],
  message_count: 2
};

const message = {
  id: "mmsg_1",
  source_agent_id: "agent_a",
  target_agent_id: "agent_b",
  source_agent_name: "Agent A",
  target_agent_name: "Agent B",
  protocol: "mcp",
  action: "tool.call",
  decision: "deny",
  latency_ms: 42,
  payload_summary: { reason: "policy" }
};

const handoff = {
  id: "mhnd_1",
  source_agent_id: "agent_a",
  target_agent_id: "agent_b",
  source_agent_name: "Agent A",
  target_agent_name: "Agent B",
  task_type: "claim_review",
  trust_result: "denied",
  policy_result: "deny",
  status: "blocked",
  reason: "low_trust",
  metadata: {}
};

const protocolBridge = {
  id: "pbrg_1",
  name: "MCP Claims Bridge",
  bridge_type: "mcp",
  status: "limited",
  config: { endpoint: "https://mcp.local/rpc" },
  current_health: {
    id: "pbhc_1",
    bridge_id: "pbrg_1",
    status: "limited",
    latency_ms: 1,
    message: "AgentMesh bridge methods are placeholder/pass-through implementations.",
    checked_at: "2026-05-01T00:00:00Z"
  },
  routes: [
    {
      id: "pbrt_1",
      bridge_id: "pbrg_1",
      source_protocol: "a2a",
      target_protocol: "mcp",
      source_agent_id: "agent_a",
      target_agent_id: "agent_b",
      source_agent_name: "Agent A",
      target_agent_name: "Agent B",
      enabled: true
    }
  ]
};

test("component topology renders nodes and edges", () => {
  const html = renderMeshTopologyGraph(topology);

  assert.match(html, /data-topology-node="agent_a"/);
  assert.match(html, /data-topology-edge="agent_a:agent_b:a2a"/);
  assert.match(html, /50% denied/);
});

test("component message table filters by protocol", () => {
  const html = renderMeshMessagesTable({ messages: [message], filters: { protocol: "mcp" } });

  assert.match(html, /data-mesh-message-row="mmsg_1"/);
  assert.match(html, /value="mcp"/);
  assert.deepEqual(meshMessageParamsFromValues({ protocol: "mcp" }), {
    source_agent_id: "",
    target_agent_id: "",
    protocol: "mcp",
    decision: ""
  });
});

test("component blocked handoff shows reason", () => {
  const html = renderMeshHandoffsTable({ handoffs: [handoff] });

  assert.match(html, /data-mesh-handoff-row="mhnd_1"/);
  assert.match(html, /blocked/);
  assert.match(html, /low_trust/);
});

test("mesh route renders product view", () => {
  const html = renderMeshPage({
    meshTopology: topology,
    meshMessages: [message],
    meshHandoffs: [handoff],
    protocolBridges: [protocolBridge],
    selectedProtocolBridge: protocolBridge,
    protocolBridgeAgents: [
      { id: "agent_a", name: "Agent A" },
      { id: "agent_b", name: "Agent B" }
    ]
  });

  assert.match(html, /data-route-page="\/mesh"/);
  assert.match(html, /data-mesh-topology/);
  assert.match(html, /data-protocol-bridges/);
  assert.match(html, /data-mesh-messages/);
  assert.match(html, /data-mesh-handoffs/);
});

test("component protocol bridge list renders status", () => {
  const html = renderProtocolBridgesPanel({ bridges: [protocolBridge], selectedBridge: protocolBridge });

  assert.match(html, /data-protocol-bridge-row="pbrg_1"/);
  assert.match(html, /MCP Claims Bridge/);
  assert.match(html, /limited/);
  assert.match(html, /data-protocol-bridge-health-panel/);
});

test("component route editor validates protocol choices", () => {
  const html = renderProtocolBridgesPanel({
    bridges: [protocolBridge],
    selectedBridge: protocolBridge,
    agents: [{ id: "agent_a", name: "Agent A" }]
  });

  assert.match(html, /data-protocol-source-protocol/);
  assert.match(html, /<option value="a2a" selected>A2A<\/option>/);
  assert.match(html, /<option value="mcp" selected>MCP<\/option>/);
  assert.deepEqual(
    protocolBridgeRoutePayloadFromValues({
      source_protocol: "A2A",
      target_protocol: "MCP",
      source_agent_id: "agent_a",
      target_agent_id: "",
      policy_binding_id: ""
    }),
    {
      source_protocol: "a2a",
      target_protocol: "mcp",
      source_agent_id: "agent_a",
      target_agent_id: null,
      policy_binding_id: null,
      enabled: true
    }
  );
  assert.throws(() => protocolBridgeRoutePayloadFromValues({ source_protocol: "ftp", target_protocol: "mcp" }));
});

test("component limited capability warning appears", () => {
  const html = renderProtocolBridgesPanel({ bridges: [protocolBridge], selectedBridge: protocolBridge });

  assert.match(html, /data-protocol-bridge-limited-warning/);
  assert.match(html, /placeholder\/pass-through/);
  assert.match(html, /not reported as healthy/);
});

test("component agent detail mesh activity section renders", () => {
  const html = renderAgentDetail(
    {
      summary: {
        id: "agent_a",
        name: "Agent A",
        status: "active",
        owner_user_id: "owner",
        sponsor_user_id: "sponsor"
      },
      meshMessages: [message],
      meshHandoffs: [handoff]
    },
    "mesh"
  );

  assert.match(html, /data-agent-mesh-activity/);
  assert.match(html, /data-mesh-message-row="mmsg_1"/);
  assert.match(html, /data-mesh-handoff-row="mhnd_1"/);
});

test("api client mesh methods call expected endpoints", async () => {
  const calls = [];
  const client = createApiClient({
    fetchImpl: async (url, init = {}) => {
      calls.push([url, init.method ?? "GET", init.body ? JSON.parse(init.body) : null]);
      return {
        ok: true,
        status: 200,
        headers: new Map([["content-type", "application/json"]]),
        json: async () => ({ id: "ok" }),
        text: async () => ""
      };
    }
  });

  await client.createMeshMessage({ source_agent_id: "a", target_agent_id: "b" });
  await client.listMeshMessages({ protocol: "mcp" });
  await client.createMeshHandoff({ source_agent_id: "a", target_agent_id: "b" });
  await client.listMeshHandoffs({ status: "blocked" });
  await client.getMeshTopology();
  await client.createProtocolBridge({ name: "Bridge" });
  await client.listProtocolBridges({ status: "limited" });
  await client.getProtocolBridge("pbrg 1");
  await client.createProtocolBridgeRoute("pbrg 1", { source_protocol: "a2a", target_protocol: "mcp" });
  await client.runProtocolBridgeHealthCheck("pbrg 1");

  assert.deepEqual(calls, [
    ["/api/v1/mesh/messages", "POST", { source_agent_id: "a", target_agent_id: "b" }],
    ["/api/v1/mesh/messages?protocol=mcp", "GET", null],
    ["/api/v1/mesh/handoffs", "POST", { source_agent_id: "a", target_agent_id: "b" }],
    ["/api/v1/mesh/handoffs?status=blocked", "GET", null],
    ["/api/v1/mesh/topology", "GET", null],
    ["/api/v1/mesh/protocol-bridges", "POST", { name: "Bridge" }],
    ["/api/v1/mesh/protocol-bridges?status=limited", "GET", null],
    ["/api/v1/mesh/protocol-bridges/pbrg%201", "GET", null],
    [
      "/api/v1/mesh/protocol-bridges/pbrg%201/routes",
      "POST",
      { source_protocol: "a2a", target_protocol: "mcp" }
    ],
    ["/api/v1/mesh/protocol-bridges/pbrg%201/health-check", "POST", null]
  ]);
});
