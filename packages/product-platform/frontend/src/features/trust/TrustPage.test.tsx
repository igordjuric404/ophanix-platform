import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DetailDrawerProvider } from "../../app/drawerContext";
import { renderWithQueryClient } from "../../test/test-utils";
import {
  TrustPage,
  trustThresholdPatchPayloadFromForm,
  trustThresholdPayloadFromForm
} from "./TrustPage";

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

const trustRule = {
  id: "trule_1",
  event_type: "policy.decision.allow",
  dimension: "policy_compliance",
  delta: 8,
  min_delta: -50,
  max_delta: 50,
  enabled: true
};

const trustCard = {
  id: "tcard_1",
  agent_id: "agent_1",
  issuer: "ophanix-demo",
  status: "active",
  signature: "signature_1234567890",
  valid_from: "2026-05-01T00:00:00+00:00",
  valid_until: "2026-06-01T00:00:00+00:00",
  issued_at: "2026-05-01T00:00:00+00:00",
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

describe("TrustPage", () => {
  beforeEach(() => {
    window.history.replaceState(null, "", "/trust");
    mockTrustFetch();
  });

  it("renders trust scores, events, cards, thresholds, handshakes, and rules", async () => {
    renderTrustPage();

    expect(await screen.findByText("Agent Trust Scores")).toBeInTheDocument();
    expect((await screen.findAllByText("Claims Agent")).length).toBeGreaterThan(0);
    expect(screen.getByText("Score Movement")).toBeInTheDocument();
    expect(screen.getByText("Score Events")).toBeInTheDocument();
    expect(screen.getByText("Card Inventory")).toBeInTheDocument();
    fireEvent.click(within(trustCardRow("tcard_1")).getByRole("button", { name: "Open" }));
    expect(await screen.findByText("did:mesh:claims")).toBeInTheDocument();
    expect(screen.getByText("Protected Actions")).toBeInTheDocument();
    expect(screen.getByText("Peer Attempts")).toBeInTheDocument();
    expect(screen.getByText("Signal Mapping")).toBeInTheDocument();
    expect(screen.getAllByText("low_trust").length).toBeGreaterThan(0);
  });

  it("filters, mutates, verifies, opens audit detail, and simulates handshakes", async () => {
    const calls = mockTrustFetch();
    renderTrustPage();

    expect(await screen.findByText("Agent Trust Scores")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Recalculate" }));
    await waitFor(() => expect(calls).toContain("/api/v1/trust/recalculate:POST"));

    const scoreEventsPanel = document.querySelector("[data-trust-score-events]") as HTMLElement;
    fireEvent.change(within(scoreEventsPanel).getByLabelText("Dimension"), {
      target: { value: "security_posture" }
    });
    fireEvent.click(within(scoreEventsPanel).getByRole("button", { name: "Filter" }));
    await waitFor(() =>
      expect(calls).toContain("/api/v1/trust/events?dimension=security_posture:GET")
    );
    expect(await screen.findByText("MCP call blocked.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "evt_2" }));
    expect(await screen.findByText("Audit Event")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "Evidence" }));
    expect(await screen.findByText("Valid hash chain, 0 event(s) checked.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Close detail drawer" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());

    fireEvent.change(screen.getByLabelText("Card Agent"), { target: { value: "agent_1" } });
    fireEvent.click(screen.getByRole("button", { name: "Issue" }));
    await waitFor(() => expect(calls).toContain("/api/v1/trust/cards:POST"));

    fireEvent.click(within(trustCardRow("tcard_1")).getByRole("button", { name: "Open" }));
    fireEvent.click(screen.getByRole("button", { name: "Verify" }));
    expect(await screen.findByText("Verified signature_valid")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Revocation Reason"), {
      target: { value: "retired" }
    });
    fireEvent.click(screen.getByRole("button", { name: "Revoke" }));
    await waitFor(() => expect(calls).toContain("/api/v1/trust/cards/tcard_1/revoke:POST"));

    fireEvent.change(screen.getByLabelText("Threshold Type"), {
      target: { value: "protocol_bridge_use" }
    });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));
    await waitFor(() => expect(calls).toContain("/api/v1/trust/thresholds:POST"));

    const thresholdRow = document.querySelector("[data-trust-threshold-row='tthr_1']") as HTMLElement;
    fireEvent.change(within(thresholdRow).getByLabelText("tthr_1 score"), {
      target: { value: "710" }
    });
    fireEvent.click(within(thresholdRow).getByRole("button", { name: "Save" }));
    await waitFor(() => expect(calls).toContain("/api/v1/trust/thresholds/tthr_1:PATCH"));

    fireEvent.change(screen.getByLabelText("Sim Source"), { target: { value: "source_low" } });
    fireEvent.change(screen.getByLabelText("Sim Target"), { target: { value: "target_high" } });
    fireEvent.click(screen.getByRole("button", { name: "Simulate" }));
    expect(await screen.findByText("allowed trust_threshold_satisfied")).toBeInTheDocument();
  });

  it("rejects invalid trust threshold scores", () => {
    expect(() =>
      trustThresholdPayloadFromForm(
        formWithValues({
          min_score: "trusted",
          required_tier: "trusted",
          target_type: "environment",
          threshold_type: "handoff"
        })
      )
    ).toThrow("Minimum Score must be a valid integer.");

    expect(() =>
      trustThresholdPatchPayloadFromForm(
        formWithValues({
          enabled: "on",
          min_score: "1001",
          required_tier: "trusted"
        })
      )
    ).toThrow("Minimum Score must be at most 1000.");
  });
});

function renderTrustPage() {
  return renderWithQueryClient(
    <DetailDrawerProvider>
      <TrustPage />
    </DetailDrawerProvider>
  );
}

function mockTrustFetch() {
  const calls: string[] = [];
  vi.stubGlobal("fetch", async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const parsed = new URL(url, "http://test.local");
    const path = `${parsed.pathname}${parsed.search}`;
    calls.push(`${path}:${init?.method ?? "GET"}`);

    if (path === "/api/v1/trust/scores") {
      return json([trustScore]);
    }
    if (path.startsWith("/api/v1/trust/events")) {
      return json(
        parsed.searchParams.get("dimension") === "security_posture"
          ? [trustEvents[1]]
          : trustEvents
      );
    }
    if (path === "/api/v1/trust/rules") {
      return json([trustRule]);
    }
    if (path === "/api/v1/trust/cards") {
      if (init?.method === "POST") {
        return json({ ...trustCard, id: "tcard_2" }, 201);
      }
      return json([trustCard]);
    }
    if (path === "/api/v1/trust/cards/tcard_1") {
      return json(trustCard);
    }
    if (path === "/api/v1/trust/cards/tcard_2") {
      return json({ ...trustCard, id: "tcard_2" });
    }
    if (path === "/api/v1/trust/cards/tcard_1/verify") {
      return json({
        trust_card_id: "tcard_1",
        agent_id: "agent_1",
        status: "active",
        verified: true,
        reason: "signature_valid",
        checked_at: "2026-05-01T00:00:00+00:00"
      });
    }
    if (path === "/api/v1/trust/cards/tcard_1/revoke") {
      return json({ ...trustCard, status: "revoked", revocation_reason: "retired" });
    }
    if (path === "/api/v1/trust/thresholds") {
      if (init?.method === "POST") {
        return json({ ...trustThreshold, id: "tthr_2", threshold_type: "protocol_bridge_use" }, 201);
      }
      return json([trustThreshold]);
    }
    if (path === "/api/v1/trust/thresholds/tthr_1") {
      return json({ ...trustThreshold, min_score: 710 });
    }
    if (path === "/api/v1/trust/handshakes") {
      return json([deniedHandshake]);
    }
    if (path === "/api/v1/trust/handshakes/simulate") {
      return json({ ...deniedHandshake, id: "hshake_2", result: "allowed", reason: "trust_threshold_satisfied" }, 201);
    }
    if (path === "/api/v1/trust/recalculate") {
      return json({ id: "trun_1", status: "completed", started_at: "now", summary: {} }, 201);
    }
    if (path === "/api/v1/trust/rules/trule_1") {
      return json({ ...trustRule, enabled: false });
    }
    if (path === "/api/v1/audit/events/evt_1") {
      return json({
        id: "evt_1",
        event_type: "trust.change",
        source_component: "trust",
        severity: "info",
        correlation_id: "corr-trust",
        payload_json: { reason: "Policy decision allowed." },
        created_at: "2026-05-01T00:00:00+00:00"
      });
    }
    if (path === "/api/v1/audit/events/evt_2") {
      return json({
        id: "evt_2",
        event_type: "trust.change",
        source_component: "trust",
        severity: "warning",
        correlation_id: "corr-trust-2",
        payload_json: { reason: "MCP call blocked." },
        created_at: "2026-05-01T00:01:00+00:00"
      });
    }
    if (path === "/api/v1/audit/events/evt_1/verify") {
      return json({ valid: true, reason: "hash_match" });
    }
    if (path === "/api/v1/audit/events/evt_2/verify") {
      return json({ valid: true, reason: "hash_match" });
    }
    if (path === "/api/v1/audit/events?correlation_id=corr-trust") {
      return json([]);
    }
    if (path === "/api/v1/audit/events?correlation_id=corr-trust-2") {
      return json([]);
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

function trustCardRow(cardId: string) {
  const row = document.querySelector(`[data-trust-card-row="${cardId}"]`);
  expect(row).not.toBeNull();
  return row as HTMLElement;
}

function formWithValues(values: Record<string, string>) {
  const form = document.createElement("form");
  for (const [name, value] of Object.entries(values)) {
    const input = document.createElement("input");
    input.name = name;
    input.value = value;
    form.append(input);
  }
  return form;
}
