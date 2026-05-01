import assert from "node:assert/strict";
import test from "node:test";

import { createApiClient } from "../src/apiClient.js";
import { renderAgentDetail } from "../src/agents.js";
import { renderShell } from "../src/render.js";
import { createInitialAppState } from "../src/state.js";
import {
  renderTrustPage,
  renderTrustCardDetail,
  renderTrustCardsPanel,
  renderTrustHandshakesPanel,
  renderTrustScoreEvents,
  renderTrustThresholdsPanel,
  trustEventParamsFromValues,
  trustHandshakeParamsFromValues,
  trustThresholdPayloadFromValues
} from "../src/trust.js";

const trustScore = {
  id: "tscore_1",
  agent_id: "agent_1",
  agent_name: "Claims Agent",
  score: 735,
  tier: "trusted",
  dimensions: {
    policy_compliance: { score: 720, signal_count: 2 }
  },
  calculated_at: "2026-05-01T00:00:00+00:00"
};

const trustEvents = [
  {
    id: "tevt_1",
    agent_id: "agent_1",
    agent_name: "Claims Agent",
    dimension: "policy_compliance",
    delta: 8,
    reason: "Policy decision allowed.",
    score_before: 500,
    score_after: 508,
    source_event_id: "evt_1",
    created_at: "2026-05-01T00:00:00+00:00"
  },
  {
    id: "tevt_2",
    agent_id: "agent_1",
    agent_name: "Claims Agent",
    dimension: "security_posture",
    delta: -30,
    reason: "MCP call blocked.",
    score_before: 508,
    score_after: 478,
    source_event_id: "evt_2",
    created_at: "2026-05-01T00:01:00+00:00"
  }
];

const trustCard = {
  id: "tcard_1",
  agent_id: "agent_1",
  issuer: "ophanix-demo",
  status: "active",
  signature: "signature_1234567890",
  valid_until: "2026-06-01T00:00:00+00:00",
  card: {
    name: "Claims Agent",
    agent_did: "did:mesh:claims",
    capabilities: ["claims:read"],
    trust_score: 0.735,
    metadata: { trust_score: 735 }
  }
};

const trustThreshold = {
  id: "tthr_1",
  threshold_type: "handoff",
  target_type: "environment",
  target_id: null,
  min_score: 700,
  required_tier: "trusted",
  enabled: true
};

const deniedHandshake = {
  id: "hshake_1",
  source_agent_id: "source_low",
  target_agent_id: "target_high",
  purpose: "handoff",
  threshold_type: "handoff",
  target_type: "environment",
  target_id: null,
  required_score: 700,
  required_tier: "trusted",
  source_score: 420,
  target_score: 780,
  result: "denied",
  reason: "low_trust",
  metadata: { mode: "simulate" },
  created_at: "2026-05-01T00:00:00+00:00"
};

test("component leaderboard renders score and tier", () => {
  const html = renderTrustPage(
    createInitialAppState({
      trustScores: [trustScore],
      trustEvents,
      trustCards: [trustCard],
      trustThresholds: [trustThreshold],
      trustHandshakes: [deniedHandshake],
      trustRules: []
    })
  );

  assert.match(html, /data-trust-leaderboard/);
  assert.match(html, /Claims Agent/);
  assert.match(html, /735/);
  assert.match(html, /trusted/);
});

test("component score events filter by dimension", () => {
  const html = renderTrustScoreEvents({
    events: trustEvents,
    dimensionFilter: "security_posture"
  });

  assert.match(html, /data-trust-event-row="tevt_2"/);
  assert.match(html, /MCP call blocked/);
  assert.doesNotMatch(html, /data-trust-event-row="tevt_1"/);
  assert.deepEqual(trustEventParamsFromValues({ dimension: "policy_compliance" }), {
    dimension: "policy_compliance"
  });
});

test("component agent trust tab renders trend", () => {
  const html = renderAgentDetail(
    {
      summary: {
        id: "agent_1",
        name: "Claims Agent",
        status: "active",
        owner_user_id: "owner",
        sponsor_user_id: "sponsor"
      },
      trustScore,
      trustEvents,
      currentTrustCard: { agent_id: "agent_1", card: trustCard }
    },
    "trust"
  );

  assert.match(html, /data-agent-trust-tab/);
  assert.match(html, /data-trust-score-trend/);
  assert.match(html, /data-current-trust-card/);
  assert.match(html, /735/);
});

test("component card detail renders DID and score", () => {
  const html = renderTrustCardDetail({ card: trustCard });

  assert.match(html, /data-trust-card-detail="tcard_1"/);
  assert.match(html, /did:mesh:claims/);
  assert.match(html, /735/);
});

test("component revoked badge appears", () => {
  const html = renderTrustCardDetail({ card: { ...trustCard, status: "revoked" } });

  assert.match(html, /data-trust-card-revoked/);
  assert.match(html, /Revoked/);
});

test("component verify action shows result", () => {
  const html = renderTrustCardsPanel({
    cards: [trustCard],
    selectedCard: trustCard,
    verification: {
      trust_card_id: "tcard_1",
      verified: true,
      reason: "signature_valid"
    }
  });

  assert.match(html, /data-trust-card-verify="tcard_1"/);
  assert.match(html, /data-trust-card-verification/);
  assert.match(html, /Verified signature_valid/);
});

test("component threshold form validates score", () => {
  const html = renderTrustThresholdsPanel([trustThreshold]);

  assert.match(html, /data-trust-threshold-form/);
  assert.match(html, /name="min_score" type="number" min="0" max="1000"/);
  assert.deepEqual(trustThresholdPayloadFromValues({
    threshold_type: "protocol_bridge_use",
    target_type: "bridge",
    target_id: "bridge_alpha",
    min_score: "720",
    required_tier: "trusted"
  }), {
    threshold_type: "protocol_bridge_use",
    target_type: "bridge",
    target_id: "bridge_alpha",
    min_score: 720,
    required_tier: "trusted",
    enabled: true
  });
});

test("component handshake table renders failure reason", () => {
  const html = renderTrustHandshakesPanel({ handshakes: [deniedHandshake] });

  assert.match(html, /data-trust-handshake-row="hshake_1"/);
  assert.match(html, /low_trust/);
  assert.match(html, /data-handshake-detail-open="hshake_1"/);
  assert.deepEqual(trustHandshakeParamsFromValues({ result: "denied" }), {
    source_agent_id: "",
    target_agent_id: "",
    result: "denied"
  });
});

test("component simulate form shows result", () => {
  const html = renderTrustHandshakesPanel({
    handshakes: [deniedHandshake],
    simulation: { ...deniedHandshake, result: "allowed", reason: "trust_threshold_satisfied" }
  });

  assert.match(html, /data-trust-handshake-simulate-form/);
  assert.match(html, /data-trust-handshake-simulation/);
  assert.match(html, /allowed trust_threshold_satisfied/);
});

test("trust route renders product view instead of placeholder", () => {
  const html = renderShell({
    currentPath: "/trust",
    state: createInitialAppState({ trustScores: [trustScore], trustEvents })
  });

  assert.match(html, /data-route-page="\/trust"/);
  assert.match(html, /data-trust-leaderboard/);
  assert.doesNotMatch(html, /Primary Workspace/);
});

test("api client trust methods call expected endpoints", async () => {
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

  await client.listTrustScores();
  await client.getTrustScore("agent_1");
  await client.listTrustEvents({ dimension: "policy_compliance" });
  await client.recalculateTrust({ agent_id: "agent_1" });
  await client.listTrustRules({ enabled: true });
  await client.patchTrustRule("trule_1", { enabled: false });
  await client.listTrustThresholds();
  await client.createTrustThreshold({ threshold_type: "handoff", min_score: 700 });
  await client.patchTrustThreshold("tthr_1", { min_score: 710 });
  await client.listTrustHandshakes({ result: "denied" });
  await client.simulateTrustHandshake({ source_agent_id: "a", target_agent_id: "b" });
  await client.recordTrustHandshake({ source_agent_id: "a", target_agent_id: "b" });
  await client.issueTrustCard({ agent_id: "agent_1" });
  await client.listTrustCards({ agent_id: "agent_1" });
  await client.getTrustCard("tcard_1");
  await client.verifyTrustCard("tcard_1");
  await client.revokeTrustCard("tcard_1", { reason: "retired" });
  await client.getAgentTrustCard("agent_1");

  assert.deepEqual(calls, [
    ["/api/v1/trust/scores", "GET", null],
    ["/api/v1/trust/scores/agent_1", "GET", null],
    ["/api/v1/trust/events?dimension=policy_compliance", "GET", null],
    ["/api/v1/trust/recalculate", "POST", { agent_id: "agent_1" }],
    ["/api/v1/trust/rules?enabled=true", "GET", null],
    ["/api/v1/trust/rules/trule_1", "PATCH", { enabled: false }],
    ["/api/v1/trust/thresholds", "GET", null],
    ["/api/v1/trust/thresholds", "POST", { threshold_type: "handoff", min_score: 700 }],
    ["/api/v1/trust/thresholds/tthr_1", "PATCH", { min_score: 710 }],
    ["/api/v1/trust/handshakes?result=denied", "GET", null],
    ["/api/v1/trust/handshakes/simulate", "POST", { source_agent_id: "a", target_agent_id: "b" }],
    ["/api/v1/trust/handshakes/record", "POST", { source_agent_id: "a", target_agent_id: "b" }],
    ["/api/v1/trust/cards", "POST", { agent_id: "agent_1" }],
    ["/api/v1/trust/cards?agent_id=agent_1", "GET", null],
    ["/api/v1/trust/cards/tcard_1", "GET", null],
    ["/api/v1/trust/cards/tcard_1/verify", "POST", null],
    ["/api/v1/trust/cards/tcard_1/revoke", "POST", { reason: "retired" }],
    ["/api/v1/agents/agent_1/trust-card", "GET", null]
  ]);
});
