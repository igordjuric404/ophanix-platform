import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DetailDrawerProvider } from "../../app/drawerContext";
import { CurrentUserProvider } from "../../app/userContext";
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
  },
  {
    id: "agent_quarantined",
    name: "Quarantined Agent",
    status: "quarantined",
    framework: "custom",
    owner_user_id: "owner_4",
    sponsor_user_id: "sponsor_4",
    capability_count: 1
  },
  {
    id: "agent_revoked",
    name: "Revoked Agent",
    status: "revoked",
    framework: "custom",
    owner_user_id: "owner_5",
    sponsor_user_id: "sponsor_5",
    capability_count: 1
  }
];

const detail = {
  summary: agents[0],
  identity: {
    did: "did:mesh:abc",
    public_key_fingerprint: "fingerprint_1",
    key_type: "ed25519",
    identity_status: "active",
    proof_type: "agentmesh-local",
    issuer: "local-agentmesh",
    audience: "env_default",
    trusted_root_id: "local-agentmesh",
    trusted_root_version: "v1",
    verified_at: "2026-04-30T10:00:00+00:00"
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
    renderAgentsPage(["Platform Admin"]);

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
    expect(screen.getAllByText("Quarantined Agent").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Revoked Agent").length).toBeGreaterThan(0);
    expect(screen.getByText("1 quarantined")).toBeInTheDocument();
    expect(screen.getByText("1 revoked")).toBeInTheDocument();
    expect(screen.getAllByText("Suspend").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Decommission").length).toBeGreaterThan(0);
    expect(screen.getByText("First Governed Run")).toBeInTheDocument();
    expect(
      screen.getByText((content) => content.includes("OphanixToolGatewayClient.from_env()"))
    ).toBeInTheDocument();
    expect(screen.getByText((content) => content.includes("idempotency_key="))).toBeInTheDocument();

    fireEvent.click(within(agentRow("agent_1")).getByRole("button", { name: "Open" }));
    const guide = screen.getByText("First Governed Run").closest("section");
    expect(guide).not.toBeNull();
    expect(within(guide as HTMLElement).getByText("agent_1")).toBeInTheDocument();
    expect(within(guide as HTMLElement).getByRole("link", { name: "Tool Gateway decisions" })).toHaveAttribute(
      "href",
      "/tool-gateway/decisions?agent_id=agent_1&correlation_id=first-run-agent_1"
    );
    expect(within(guide as HTMLElement).getByRole("link", { name: "Runtime state" })).toHaveAttribute(
      "href",
      "/runtime?agent_id=agent_1"
    );
    expect(within(guide as HTMLElement).getByRole("link", { name: "Compliance evidence" })).toHaveAttribute(
      "href",
      "/compliance?agent_id=agent_1"
    );

    fireEvent.click(screen.getByRole("tab", { name: "Identity" }));
    expect(await screen.findByText("did:mesh:abc")).toBeInTheDocument();
    expect(screen.getByText("fingerprint_1")).toBeInTheDocument();
    expect(screen.getAllByText("local-agentmesh").length).toBeGreaterThan(0);
    expect(screen.getByText("env_default")).toBeInTheDocument();

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
    renderAgentsPage(["Platform Admin"]);

    expect((await screen.findAllByText("Claims Assistant")).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: /Register and activate/ }));
    expect(await screen.findByText("Agent agent_new activated")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Status"), { target: { value: "active" } });
    fireEvent.change(screen.getByPlaceholderText("claims:read"), { target: { value: "claims:read" } });
    fireEvent.click(screen.getByRole("button", { name: "Filter" }));

    await waitFor(() =>
      expect(calls).toContain("/api/v1/agents?status=active&capability=claims%3Aread&sort=-last_heartbeat")
    );
    expect(calls).toContain("/api/v1/agents/registration-drafts");
    expect(calls).toContain("/api/v1/agents/registration-drafts/agent_new/identity");
    expect(calls).toContain("/api/v1/agents/registration-drafts/agent_new/submit");
    expect(calls).toContain("/api/v1/agents/agent_new/approve");
    expect(calls).toContain("/api/v1/agents/agent_new/activate");
  });

  it("runs restricted lifecycle actions with a required reason", async () => {
    const calls = mockAgentFetch();
    renderAgentsPage(["Platform Admin"]);

    expect((await screen.findAllByText("Claims Assistant")).length).toBeGreaterThan(0);
    fireEvent.click(within(agentRow("agent_1")).getByRole("button", { name: "Open" }));
    fireEvent.click(screen.getByRole("tab", { name: "Lifecycle" }));

    const panel = await waitFor(() => {
      const lifecyclePanel = document.querySelector("[data-agent-lifecycle]");
      expect(lifecyclePanel).not.toBeNull();
      return lifecyclePanel as HTMLElement;
    });
    expect(within(panel).getByRole("button", { name: "Restrict" })).toBeEnabled();
    expect(within(panel).getByRole("button", { name: "Quarantine" })).toBeEnabled();
    expect(within(panel).getByRole("button", { name: "Revoke" })).toBeEnabled();
    expect(within(panel).getByRole("button", { name: "Archive" })).toBeDisabled();

    fireEvent.click(within(panel).getByRole("button", { name: "Quarantine" }));
    expect(calls).not.toContain("/api/v1/agents/agent_1/quarantine");

    fireEvent.change(within(panel).getByLabelText("Reason"), {
      target: { value: "incident response" }
    });
    fireEvent.click(within(panel).getByRole("button", { name: "Quarantine" }));

    expect(await screen.findByText("Agent quarantined")).toBeInTheDocument();
    expect(calls).toContain("/api/v1/agents/agent_1/quarantine");
  });

  it("disables agent write actions for read-only users", async () => {
    renderAgentsPage(["Viewer"]);

    expect(await screen.findByRole("button", { name: /Register and activate/ })).toBeDisabled();
    expect(await screen.findByText("Claims Assistant")).toBeInTheDocument();
    fireEvent.click(within(agentRow("agent_1")).getByRole("button", { name: "Open" }));
    fireEvent.click(screen.getByRole("tab", { name: "Credentials" }));

    expect(await screen.findByRole("button", { name: "Issue" })).toBeDisabled();
    for (const button of screen.getAllByRole("button", { name: "Rotate" })) {
      expect(button).toBeDisabled();
    }
    expect(screen.getByRole("button", { name: "Revoke" })).toBeDisabled();
  });
});

function renderAgentsPage(roles: string[]) {
  return renderWithQueryClient(
    <CurrentUserProvider
      user={{
        id: "user_test",
        email: "user@example.com",
        display_name: "Test User",
        roles
      }}
    >
      <DetailDrawerProvider>
        <AgentsPage />
      </DetailDrawerProvider>
    </CurrentUserProvider>
  );
}

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
      return json({
        id: "agent_new",
        name: "Claims Assistant",
        status: "draft",
        capabilities: [{ capability_name: "claims:read", resource_type: "claim", status: "pending" }]
      });
    }
    if (path === "/api/v1/agents/registration-drafts/agent_new/identity" && init?.method === "POST") {
      return json({
        identity: {
          did: "did:mesh:new",
          public_key_fingerprint: "fingerprint_new",
          key_type: "ed25519",
          identity_status: "active",
          issuer: "local-agentmesh",
          audience: "env_default",
          trusted_root_id: "local-agentmesh",
          trusted_root_version: "v1"
        }
      });
    }
    if (path === "/api/v1/agents/registration-drafts/agent_new/submit" && init?.method === "POST") {
      return json({ id: "agent_new", name: "Claims Assistant", status: "pending_approval" });
    }
    if (path === "/api/v1/agents/agent_new/approve" && init?.method === "POST") {
      return json({ id: "agent_new", name: "Claims Assistant", status: "provisioned" });
    }
    if (path === "/api/v1/agents/agent_new/activate" && init?.method === "POST") {
      return json({ id: "agent_new", name: "Claims Assistant", status: "active" });
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
    if (path === "/api/v1/agents/agent_1/quarantine" && init?.method === "POST") {
      return json({ ...agents[0], status: "quarantined" });
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

function agentRow(agentId: string) {
  const row = document.querySelector(`[data-agent-row="${agentId}"]`);
  expect(row).not.toBeNull();
  return row as HTMLElement;
}

function json(body: unknown, status = 200) {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      headers: { "Content-Type": "application/json" },
      status
    })
  );
}
