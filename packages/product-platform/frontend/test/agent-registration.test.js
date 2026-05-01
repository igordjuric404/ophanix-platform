import assert from "node:assert/strict";
import test from "node:test";

import { createApiClient } from "../src/apiClient.js";
import {
  renderAgentInventory,
  renderAgentDetail,
  renderCredentialActionModal,
  renderCredentialWorkspace,
  renderLifecycleActionModal,
  renderLifecycleWorkspace,
  renderAgentRegistrationWizard,
  renderAgentsPage
} from "../src/agents.js";
import { renderShell } from "../src/render.js";
import { createInitialAppState } from "../src/state.js";

test("component renders all registration wizard steps", () => {
  const html = renderAgentRegistrationWizard(createInitialAppState());

  for (const step of [
    "Agent Details",
    "Runtime And Framework",
    "Identity",
    "Capabilities",
    "Policies",
    "Bootstrap"
  ]) {
    assert.match(html, new RegExp(step));
  }
  assert.match(html, /data-agent-registration-form/);
  assert.match(html, /name="capability_name"/);
});

test("agents route renders registration wizard instead of placeholder", () => {
  const html = renderShell({ currentPath: "/agents", state: createInitialAppState() });

  assert.match(html, /data-route-page="\/agents"/);
  assert.match(html, /data-agent-registration-form/);
  assert.doesNotMatch(html, /Primary Workspace/);
});

test("api client registration methods call expected endpoints", async () => {
  const calls = [];
  const client = createApiClient({
    fetchImpl: async (url, init = {}) => {
      calls.push([url, init.method ?? "GET"]);
      return {
        ok: true,
        status: 200,
        headers: new Map([["content-type", "application/json"]]),
        json: async () => ({ id: "agent_1", identity: { did: "did:mesh:test" } })
      };
    }
  });

  await client.createAgentRegistrationDraft({ name: "A" });
  await client.updateAgentRegistrationDraft("agent_1", { capabilities: [] });
  await client.createAgentIdentity("agent_1");
  await client.simulateAgentRegistrationDraft("agent_1");
  await client.submitAgentRegistrationDraft("agent_1");
  await client.approveAgent("agent_1");
  await client.activateAgent("agent_1");

  assert.deepEqual(calls, [
    ["/api/v1/agents/registration-drafts", "POST"],
    ["/api/v1/agents/registration-drafts/agent_1", "PATCH"],
    ["/api/v1/agents/registration-drafts/agent_1/identity", "POST"],
    ["/api/v1/agents/registration-drafts/agent_1/simulate", "POST"],
    ["/api/v1/agents/registration-drafts/agent_1/submit", "POST"],
    ["/api/v1/agents/agent_1/approve", "POST"],
    ["/api/v1/agents/agent_1/activate", "POST"]
  ]);
});

test("agents page includes approval queue context", () => {
  const html = renderAgentsPage(createInitialAppState());

  assert.match(html, /data-agent-approval-queue/);
  assert.match(html, /Credential tasks/);
});

test("component renders an inventory row with actions", () => {
  const html = renderAgentInventory([
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
    }
  ]);

  assert.match(html, /data-agent-row="agent_1"/);
  assert.match(html, /Claims Assistant/);
  assert.match(html, /Suspend/);
  assert.match(html, /Decommission/);
});

test("api client list agents sends filter query params", async () => {
  const calls = [];
  const client = createApiClient({
    fetchImpl: async (url, init = {}) => {
      calls.push([url, init.method ?? "GET"]);
      return {
        ok: true,
        status: 200,
        headers: new Map([["content-type", "application/json"]]),
        json: async () => []
      };
    }
  });

  await client.listAgents({ status: "active", capability: "claims:read", sort: "-last_heartbeat" });

  assert.deepEqual(calls, [
    ["/api/v1/agents?status=active&capability=claims%3Aread&sort=-last_heartbeat", "GET"]
  ]);
});

test("inventory empty state suggests registration", () => {
  const html = renderAgentInventory([]);

  assert.match(html, /data-agent-inventory-empty/);
  assert.match(html, /Register Agent/);
});

const detail = {
  summary: {
    id: "agent_1",
    name: "Claims Assistant",
    status: "active",
    trust_tier: "standard",
    owner_user_id: "owner_1",
    sponsor_user_id: "sponsor_1",
    credential_status: "active",
    last_heartbeat_at: "2026-04-30T10:00:00+00:00"
  },
  identity: {
    did: "did:mesh:abc",
    public_key_fingerprint: "fingerprint_1",
    key_type: "ed25519",
    identity_status: "active"
  },
  capabilities: [{ capability_name: "claims:read" }],
  latest_heartbeat: { observed_at: "2026-04-30T10:00:00+00:00" },
  auditEvents: [
    {
      id: "evt_agent_1",
      event_type: "agent.lifecycle",
      severity: "info",
      created_at: "2026-04-30T10:01:00+00:00"
    }
  ]
};

test("component renders agent detail overview tab", () => {
  const html = renderAgentDetail(detail, "overview");

  assert.match(html, /data-agent-overview/);
  assert.match(html, /Claims Assistant/);
  assert.match(html, /owner_1/);
  assert.match(html, /2026-04-30T10:00:00/);
});

test("component renders agent identity DID", () => {
  const html = renderAgentDetail(detail, "identity");

  assert.match(html, /data-agent-identity/);
  assert.match(html, /did:mesh:abc/);
  assert.match(html, /fingerprint_1/);
});

test("component audit tab exposes shared drawer event buttons", () => {
  const html = renderAgentDetail(detail, "audit");

  assert.match(html, /data-agent-audit-events/);
  assert.match(html, /data-related-event-id="evt_agent_1"/);
});

test("component runtime tab links to runtime controls", () => {
  const html = renderAgentDetail(detail, "runtime");

  assert.match(html, /data-agent-runtime-tab/);
  assert.match(html, /Open Runtime/);
  assert.match(html, /data-route="\/runtime"/);
});

test("component lifecycle approval queue renders pending agents", () => {
  const html = renderLifecycleWorkspace({
    agents: [
      { id: "agent_pending", name: "Pending Agent", status: "pending_approval", framework: "langgraph" },
      { id: "agent_active", name: "Active Agent", status: "active", framework: "langgraph" }
    ]
  });

  assert.match(html, /data-approval-queue/);
  assert.match(html, /Pending Agent/);
  assert.match(html, /data-lifecycle-funnel/);
});

test("component suspend action requires reason", () => {
  const html = renderLifecycleActionModal({ id: "agent_active" }, "suspend");

  assert.match(html, /data-lifecycle-action="suspend"/);
  assert.match(html, /name="reason" required/);
});

test("component orphan table links to agent detail", () => {
  const html = renderLifecycleWorkspace({
    orphanCandidates: [
      { id: "agent_orphan", name: "Orphan Agent", last_heartbeat_at: "2026-04-01T00:00:00+00:00" }
    ]
  });

  assert.match(html, /data-orphan-candidates/);
  assert.match(html, /href="\/agents\?agent_id=agent_orphan"/);
});

test("component credential table renders status and expiry", () => {
  const html = renderCredentialWorkspace({
    credentials: [
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
    ],
    expiringCredentials: []
  });

  assert.match(html, /data-agent-credentials-table/);
  assert.match(html, /cred_1/);
  assert.match(html, /active/);
  assert.match(html, /2026-04-30T12:00:00/);
  assert.match(html, /claims:read/);
});

test("api client credential lifecycle methods call expected endpoints", async () => {
  const calls = [];
  const client = createApiClient({
    fetchImpl: async (url, init = {}) => {
      calls.push([url, init.method ?? "GET", init.body ? JSON.parse(init.body) : null]);
      return {
        ok: true,
        status: 200,
        headers: new Map([["content-type", "application/json"]]),
        json: async () => ({ ok: true })
      };
    }
  });

  await client.listAgentCredentials("agent_1", { status: "active" });
  await client.issueAgentCredential("agent_1", { scopes: [] });
  await client.rotateCredential("cred_1", { reason: "scheduled" });
  await client.revokeCredential("cred_1", { reason: "compromised" });
  await client.verifyCredential("cred_1", { token: "secret" });
  await client.listExpiringCredentials({ threshold_hours: 24 });

  assert.deepEqual(calls, [
    ["/api/v1/agents/agent_1/credentials?status=active", "GET", null],
    ["/api/v1/agents/agent_1/credentials", "POST", { scopes: [] }],
    ["/api/v1/credentials/cred_1/rotate", "POST", { reason: "scheduled" }],
    ["/api/v1/credentials/cred_1/revoke", "POST", { reason: "compromised" }],
    ["/api/v1/credentials/cred_1/verify", "POST", { token: "secret" }],
    ["/api/v1/credentials/expiring?threshold_hours=24", "GET", null]
  ]);
});

test("component revoke credential modal requires reason", () => {
  const html = renderCredentialActionModal({ id: "cred_1" }, "revoke");

  assert.match(html, /data-credential-action="revoke"/);
  assert.match(html, /name="reason" required/);
});

test("component credential workspace renders lifecycle state changes", () => {
  const html = renderCredentialWorkspace({
    credentials: [
      {
        id: "cred_old",
        credential_type: "bearer",
        issuer: "local-agentmesh",
        status: "revoked",
        expires_at: "2026-04-30T12:00:00+00:00",
        scopes: [{ scope: "claims:read", resource_type: "claim" }]
      },
      {
        id: "cred_new",
        credential_type: "bearer",
        issuer: "local-agentmesh",
        status: "active",
        expires_at: "2026-04-30T18:00:00+00:00",
        scopes: [{ scope: "claims:read", resource_type: "claim" }]
      }
    ],
    expiringCredentials: [
      {
        id: "cred_new",
        status: "expiring_soon",
        expires_at: "2026-04-30T18:00:00+00:00"
      }
    ]
  });

  assert.match(html, /cred_old/);
  assert.match(html, /revoked/);
  assert.match(html, /cred_new/);
  assert.match(html, /Rotation Queue/);
});
