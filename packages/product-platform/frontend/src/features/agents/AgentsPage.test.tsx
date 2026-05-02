import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DetailDrawerProvider } from "../../app/drawerContext";
import { renderWithQueryClient } from "../../test/test-utils";
import { AgentsPage } from "./AgentsPage";

const agents = [
  {
    id: "agent_1",
    name: "Claims Assistant",
    status: "active",
    framework: "langgraph",
    owner_user_id: "owner_1",
    sponsor_user_id: "sponsor_1",
    trust_tier: "standard",
    credential_status: "active",
    last_heartbeat_at: "2026-04-30T10:00:00+00:00",
    capability_count: 2
  },
  {
    id: "agent_pending",
    name: "Pending Agent",
    status: "pending_approval",
    framework: "crewai",
    owner_user_id: "owner_2",
    sponsor_user_id: "sponsor_2",
    capability_count: 1
  },
  {
    id: "agent_orphan",
    name: "Orphan Agent",
    status: "orphaned",
    framework: "custom",
    owner_user_id: null,
    sponsor_user_id: "sponsor_3",
    capability_count: 0
  }
];

const detail = {
  summary: agents[0],
  identity: {
    did: "did:mesh:abc",
    public_key_fingerprint: "fingerprint_1",
    key_type: "ed25519",
    identity_status: "active"
  },
  capabilities: [{ capability_name: "claims:read", resource_type: "claim", status: "approved" }],
  latest_heartbeat: { observed_at: "2026-04-30T10:00:00+00:00" },
  lifecycle_events: [
    {
      id: "life_1",
      previous_state: "pending_approval",
      next_state: "active",
      reason: "approved",
      created_at: "2026-04-30T10:01:00+00:00"
    }
  ],
  auditEvents: [
    {
      id: "evt_agent_1",
      event_type: "agent.lifecycle",
      severity: "info",
      created_at: "2026-04-30T10:01:00+00:00"
    }
  ]
};

const credentials = [
  {
    id: "cred_1",
    agent_id: "agent_1",
    credential_type: "bearer",
    issuer: "local-agentmesh",
    status: "active",
    issued_at: "2026-04-30T00:00:00+00:00",
    expires_at: "2026-04-30T12:00:00+00:00",
    scopes: [{ scope: "claims:read", resource_type: "claim", resource_id: "claim/*" }]
  }
];

describe("AgentsPage", () => {
  beforeEach(() => {
    window.history.replaceState(null, "", "/agents");
    mockAgentFetch();
  });

  it("renders registration, inventory, lifecycle, detail, credentials, and audit drawer flows", async () => {
    renderWithQueryClient(
      <DetailDrawerProvider>
        <AgentsPage />
      </DetailDrawerProvider>
    );

    expect((await screen.findAllByText("Claims Assistant")).length).toBeGreaterThan(0);
    for (const step of [
      "Agent Details",
      "Runtime And Framework",
      "Identity",
      "Capabilities",
      "Policies",
      "Bootstrap"
    ]) {
      expect(screen.getAllByText(step).length).toBeGreaterThan(0);
    }
    expect(screen.getAllByText("Pending Agent").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Orphan Agent").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Suspend").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Decommission").length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("tab", { name: "Identity" }));
    expect(await screen.findByText("did:mesh:abc")).toBeInTheDocument();
    expect(screen.getByText("fingerprint_1")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "Credentials" }));
    expect(await screen.findByText("cred_1")).toBeInTheDocument();
    expect(screen.getByText("claims:read")).toBeInTheDocument();
    expect(screen.getByText("Rotation Queue")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "Audit" }));
    fireEvent.click(await screen.findByText("agent.lifecycle"));
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("Audit Event")).toBeInTheDocument();
  });

  it("submits registration drafts and applies inventory filters", async () => {
    const calls = mockAgentFetch();
    renderWithQueryClient(
      <DetailDrawerProvider>
        <AgentsPage />
      </DetailDrawerProvider>
    );

    expect((await screen.findAllByText("Claims Assistant")).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: /Create draft/ }));
    expect(await screen.findByText("Registration draft agent_new created")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Status"), { target: { value: "active" } });
    fireEvent.change(screen.getByPlaceholderText("claims:read"), { target: { value: "claims:read" } });
    fireEvent.click(screen.getByRole("button", { name: "Filter" }));

    await waitFor(() =>
      expect(calls).toContain("/api/v1/agents?status=active&capability=claims%3Aread&sort=-last_heartbeat")
    );
    expect(calls).toContain("/api/v1/agents/registration-drafts");
  });
});

function mockAgentFetch() {
  const calls: string[] = [];
  vi.stubGlobal("fetch", async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const parsed = new URL(url, "http://test.local");
    const path = `${parsed.pathname}${parsed.search}`;
    calls.push(path);

    if (path.startsWith("/api/v1/agents?")) {
      return json(agents);
    }
    if (path === "/api/v1/agents/registration-drafts" && init?.method === "POST") {
      return json({ id: "agent_new", name: "Claims Assistant", status: "draft" });
    }
    if (path === "/api/v1/agents/agent_1") {
      return json(detail);
    }
    if (path === "/api/v1/agents/agent_1/timeline") {
      return json(detail.lifecycle_events);
    }
    if (path === "/api/v1/agents/agent_1/audit") {
      return json(detail.auditEvents);
    }
    if (path === "/api/v1/agents/agent_1/credentials") {
      return json(credentials);
    }
    if (path === "/api/v1/credentials/expiring?threshold_hours=24") {
      return json([{ ...credentials[0], status: "expiring_soon" }]);
    }
    if (path === "/api/v1/audit/events/evt_agent_1") {
      return json({
        id: "evt_agent_1",
        event_type: "agent.lifecycle",
        correlation_id: "corr_1",
        payload_json: { reason: "approved" }
      });
    }
    if (path === "/api/v1/audit/events/evt_agent_1/verify") {
      return json({ valid: true, checked_count: 1 });
    }
    if (path === "/api/v1/audit/events?correlation_id=corr_1") {
      return json([]);
    }
    return json({});
  });
  return calls;
}

function json(body: unknown, status = 200) {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      headers: { "Content-Type": "application/json" },
      status
    })
  );
}
