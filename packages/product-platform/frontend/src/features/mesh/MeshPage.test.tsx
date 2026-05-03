import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithQueryClient } from "../../test/test-utils";
import { MeshPage } from "./MeshPage";

const topology = {
  nodes: [
    {
      agent_id: "agent_a",
      name: "Agent A",
      status: "active",
      trust_tier: "trusted",
      message_count: 2
    },
    {
      agent_id: "agent_b",
      name: "Agent B",
      status: "active",
      trust_tier: "standard",
      message_count: 2
    }
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
  message_count: 2,
  generated_at: "2026-05-01T00:00:00Z",
  cached: false
};

const meshMessage = {
  id: "mmsg_1",
  source_agent_id: "agent_a",
  target_agent_id: "agent_b",
  source_agent_name: "Agent A",
  target_agent_name: "Agent B",
  protocol: "mcp",
  action: "tool.call",
  decision: "deny",
  latency_ms: 42,
  correlation_id: "corr-mesh",
  payload_summary: { reason: "policy" },
  created_at: "2026-05-01T00:00:00Z"
};

const handoff = {
  id: "mhnd_1",
  source_agent_id: "agent_a",
  target_agent_id: "agent_b",
  source_agent_name: "Agent A",
  target_agent_name: "Agent B",
  task_type: "claim_review",
  required_capabilities: ["claims:read"],
  trust_result: "denied",
  policy_result: "deny",
  status: "blocked",
  reason: "low_trust",
  correlation_id: "corr-mesh",
  metadata: { threshold: 700 },
  created_at: "2026-05-01T00:00:00Z"
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
      enabled: true,
      created_at: "2026-05-01T00:00:00Z",
      updated_at: "2026-05-01T00:00:00Z"
    }
  ],
  created_at: "2026-05-01T00:00:00Z",
  updated_at: "2026-05-01T00:00:00Z"
};

describe("MeshPage", () => {
  beforeEach(() => {
    window.history.replaceState(null, "", "/mesh");
    mockMeshFetch();
  });

  it("renders topology, messages, handoffs, protocol bridges, and limited warnings", async () => {
    renderWithQueryClient(<MeshPage />);

    expect(await screen.findByText("Live Edges")).toBeInTheDocument();
    expect((await screen.findAllByText("Agent A")).length).toBeGreaterThan(0);
    expect(screen.getByText("1 (50%)")).toBeInTheDocument();
    expect(screen.getByText("Message Feed")).toBeInTheDocument();
    expect(screen.getByText("Task Transfers")).toBeInTheDocument();
    expect(screen.getByText("Bridge Control")).toBeInTheDocument();
    expect(screen.getAllByText("MCP Claims Bridge").length).toBeGreaterThan(0);
    expect(screen.getByText("tool.call")).toBeInTheDocument();
    expect(screen.getAllByText("claim_review").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/placeholder\/pass-through/).length).toBeGreaterThan(0);
  });

  it("filters feeds and mutates protocol bridge controls", async () => {
    const calls = mockMeshFetch();
    renderWithQueryClient(<MeshPage />);

    expect(await screen.findByText("Live Edges")).toBeInTheDocument();

    const topologyPanel = document.querySelector("[data-mesh-topology]") as HTMLElement;
    fireEvent.change(within(topologyPanel).getByLabelText("Start Time"), {
      target: { value: "2026-05-01T00:00:00Z" }
    });
    fireEvent.click(within(topologyPanel).getByRole("button", { name: "Filter" }));
    await waitFor(() =>
      expect(calls.some((call) => call.startsWith("/api/v1/mesh/topology?start_time="))).toBe(true)
    );

    const messagesPanel = document.querySelector("[data-mesh-messages]") as HTMLElement;
    fireEvent.change(within(messagesPanel).getByLabelText("Protocol"), {
      target: { value: "mcp" }
    });
    fireEvent.change(within(messagesPanel).getByLabelText("Decision"), {
      target: { value: "deny" }
    });
    fireEvent.click(within(messagesPanel).getByRole("button", { name: "Filter" }));
    await waitFor(() =>
      expect(calls).toContain("/api/v1/mesh/messages?protocol=mcp&decision=deny:GET")
    );
    expect(await within(messagesPanel).findByText("tool.call")).toBeInTheDocument();
    fireEvent.click(within(messagesPanel).getByRole("button", { name: "Details" }));
    expect(screen.getByText(/policy/)).toBeInTheDocument();

    const handoffsPanel = document.querySelector("[data-mesh-handoffs]") as HTMLElement;
    fireEvent.change(within(handoffsPanel).getByLabelText("Status"), {
      target: { value: "blocked" }
    });
    fireEvent.click(within(handoffsPanel).getByRole("button", { name: "Filter" }));
    await waitFor(() => expect(calls).toContain("/api/v1/mesh/handoffs?status=blocked:GET"));
    await waitFor(() =>
      expect(within(handoffsPanel).getAllByText("claim_review").length).toBeGreaterThan(0)
    );
    fireEvent.click(within(handoffsPanel).getAllByRole("button", { name: "Details" })[0]);
    expect(screen.getByText("low_trust")).toBeInTheDocument();

    const bridgesPanel = document.querySelector("[data-protocol-bridges]") as HTMLElement;
    fireEvent.change(within(bridgesPanel).getByLabelText("Name"), {
      target: { value: "A2A Bridge" }
    });
    fireEvent.change(within(bridgesPanel).getByLabelText("Endpoint"), {
      target: { value: "https://a2a.local/rpc" }
    });
    fireEvent.click(within(bridgesPanel).getByRole("button", { name: "Register" }));
    await waitFor(() => expect(calls).toContain("/api/v1/mesh/protocol-bridges:POST"));

    fireEvent.change(within(bridgesPanel).getByLabelText("Bridge Status"), {
      target: { value: "limited" }
    });
    fireEvent.click(within(bridgesPanel).getByRole("button", { name: "Filter" }));
    await waitFor(() =>
      expect(calls).toContain("/api/v1/mesh/protocol-bridges?status=limited:GET")
    );

    fireEvent.click(within(bridgesPanel).getByRole("button", { name: "Run Check" }));
    await waitFor(() =>
      expect(calls).toContain("/api/v1/mesh/protocol-bridges/pbrg_2/health-check:POST")
    );
    expect(await screen.findByText("Bridge check completed.")).toBeInTheDocument();

    fireEvent.change(within(bridgesPanel).getByLabelText("Edit Name"), {
      target: { value: "MCP Claims Bridge v2" }
    });
    fireEvent.click(within(bridgesPanel).getByRole("button", { name: "Save" }));
    await waitFor(() => expect(calls).toContain("/api/v1/mesh/protocol-bridges/pbrg_2:PATCH"));

    fireEvent.change(within(bridgesPanel).getByLabelText("Source Agent"), {
      target: { value: "agent_a" }
    });
    fireEvent.change(within(bridgesPanel).getByLabelText("Target Agent"), {
      target: { value: "agent_b" }
    });
    fireEvent.click(within(bridgesPanel).getByRole("button", { name: "Add Route" }));
    await waitFor(() =>
      expect(calls).toContain("/api/v1/mesh/protocol-bridges/pbrg_2/routes:POST")
    );
  });
});

function mockMeshFetch() {
  const calls: string[] = [];
  vi.stubGlobal("fetch", async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const parsed = new URL(url, "http://test.local");
    const path = `${parsed.pathname}${parsed.search}`;
    calls.push(`${path}:${init?.method ?? "GET"}`);

    if (path.startsWith("/api/v1/mesh/topology")) {
      return json(topology);
    }
    if (path.startsWith("/api/v1/mesh/messages")) {
      return json([meshMessage]);
    }
    if (path.startsWith("/api/v1/mesh/handoffs")) {
      return json([handoff]);
    }
    if (path === "/api/v1/mesh/protocol-bridges") {
      if (init?.method === "POST") {
        return json({ ...protocolBridge, id: "pbrg_2", name: "A2A Bridge", bridge_type: "a2a" }, 201);
      }
      return json([protocolBridge]);
    }
    if (path.startsWith("/api/v1/mesh/protocol-bridges?")) {
      return json([protocolBridge]);
    }
    if (path === "/api/v1/mesh/protocol-bridges/pbrg_1") {
      if (init?.method === "PATCH") {
        return json({ ...protocolBridge, name: "MCP Claims Bridge v2" });
      }
      return json(protocolBridge);
    }
    if (path === "/api/v1/mesh/protocol-bridges/pbrg_2") {
      if (init?.method === "PATCH") {
        return json({ ...protocolBridge, id: "pbrg_2", name: "MCP Claims Bridge v2", bridge_type: "a2a" });
      }
      return json({ ...protocolBridge, id: "pbrg_2", name: "A2A Bridge", bridge_type: "a2a" });
    }
    if (path === "/api/v1/mesh/protocol-bridges/pbrg_1/routes") {
      return json(
        {
          id: "pbrt_2",
          bridge_id: "pbrg_1",
          source_protocol: "a2a",
          target_protocol: "mcp",
          source_agent_id: "agent_a",
          target_agent_id: "agent_b",
          policy_binding_id: null,
          enabled: true,
          created_at: "2026-05-01T00:00:00Z",
          updated_at: "2026-05-01T00:00:00Z"
        },
        201
      );
    }
    if (path === "/api/v1/mesh/protocol-bridges/pbrg_2/routes") {
      return json(
        {
          id: "pbrt_3",
          bridge_id: "pbrg_2",
          source_protocol: "a2a",
          target_protocol: "mcp",
          source_agent_id: "agent_a",
          target_agent_id: "agent_b",
          policy_binding_id: null,
          enabled: true,
          created_at: "2026-05-01T00:00:00Z",
          updated_at: "2026-05-01T00:00:00Z"
        },
        201
      );
    }
    if (path === "/api/v1/mesh/protocol-bridges/pbrg_1/health-check") {
      return json(
        {
          id: "pbhc_2",
          bridge_id: "pbrg_1",
          status: "limited",
          latency_ms: 2,
          message: "Bridge check completed.",
          checked_at: "2026-05-01T00:02:00Z"
        },
        201
      );
    }
    if (path === "/api/v1/mesh/protocol-bridges/pbrg_2/health-check") {
      return json(
        {
          id: "pbhc_3",
          bridge_id: "pbrg_2",
          status: "limited",
          latency_ms: 2,
          message: "Bridge check completed.",
          checked_at: "2026-05-01T00:02:00Z"
        },
        201
      );
    }
    if (path === "/api/v1/agents") {
      return json([
        { id: "agent_a", name: "Agent A", status: "active" },
        { id: "agent_b", name: "Agent B", status: "active" }
      ]);
    }

    return json({ detail: `Unhandled ${path}` }, 404);
  });
  return calls;
}

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" }
  });
}
