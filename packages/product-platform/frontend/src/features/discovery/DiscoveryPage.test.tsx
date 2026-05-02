import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithQueryClient } from "../../test/test-utils";
import { DiscoveryPage } from "./DiscoveryPage";

const scanner = {
  id: "scanner_config",
  scanner_type: "config",
  name: "Config Scanner",
  description: "Find configuration files",
  status: "available",
  available: true,
  required_config: ["paths"],
  optional_config: ["max_depth"]
};

const target = {
  id: "target_1",
  scanner_type: "config",
  target_type: "filesystem",
  target_value: "/repo",
  schedule_mode: "hourly",
  schedule_enabled: true,
  next_run_at: "2026-04-30T12:00:00+00:00",
  enabled: true
};

const runs = [
  {
    id: "run_1",
    scanner_type: "config",
    target_id: "target_1",
    status: "succeeded",
    started_at: "2026-04-30T11:00:00+00:00",
    finished_at: "2026-04-30T11:00:03+00:00",
    error_message: null,
    raw_finding_count: 1,
    high_risk_count: 0,
    summary_json: { raw_finding_count: 1 },
    raw_findings: [
      {
        id: "raw_1",
        fingerprint: "abc123",
        raw_payload_json: {
          name: "agt agent at agentmesh.yaml",
          agent_type: "agt",
          confidence: 0.95
        },
        created_at: "2026-04-30T11:00:03+00:00"
      }
    ]
  },
  {
    id: "run_failed",
    scanner_type: "config",
    target_id: "target_1",
    status: "failed",
    started_at: "2026-04-30T11:10:00+00:00",
    finished_at: "2026-04-30T11:10:01+00:00",
    error_message: "Not a directory",
    raw_finding_count: 0,
    high_risk_count: 0,
    raw_findings: []
  }
];

const highRiskFinding = {
  id: "finding_1",
  fingerprint: "fp_high",
  detected_name: "Shadow Crew",
  agent_type: "crewai",
  source: "/repo/agentmesh.yaml",
  owner_hint: null,
  registry_agent_id: null,
  status: "shadow_candidate",
  risk_score: 85,
  risk_level: "critical",
  risk_factors: ["No assigned owner", "Agent status: shadow"],
  first_seen_at: "2026-04-30T10:00:00+00:00",
  last_seen_at: "2026-04-30T10:00:00+00:00",
  evidence: [
    {
      id: "evd_1",
      evidence_type: "config_file",
      evidence_value: "/repo/agentmesh.yaml",
      confidence: 0.95,
      created_at: "2026-04-30T10:00:00+00:00"
    }
  ]
};

const suppressedFinding = {
  ...highRiskFinding,
  id: "finding_suppressed",
  detected_name: "Suppressed Crew",
  status: "suppressed"
};

describe("DiscoveryPage", () => {
  beforeEach(() => {
    mockDiscoveryFetch();
  });

  it("renders scan runs, raw finding detail, failed errors, and high-risk finding detail", async () => {
    renderWithQueryClient(<DiscoveryPage />);

    expect(await screen.findByText("Config Scanner")).toBeInTheDocument();
    expect(screen.getByText("/repo")).toBeInTheDocument();
    expect(screen.getByText("run_1")).toBeInTheDocument();
    expect(screen.getByText("3s")).toBeInTheDocument();
    expect(screen.getByText(/agt agent at agentmesh.yaml/)).toBeInTheDocument();
    expect(screen.getByText("Not a directory")).toBeInTheDocument();
    expect(screen.getAllByText("Shadow Crew").length).toBeGreaterThan(0);
    expect(screen.getAllByText("critical").length).toBeGreaterThan(0);
    expect(screen.getByText("85")).toBeInTheDocument();
    expect(screen.getByText("No assigned owner")).toBeInTheDocument();
    expect(screen.getByText("config_file")).toBeInTheDocument();
    expect(screen.queryByText("Suppressed Crew")).not.toBeInTheDocument();
  });

  it("runs discovery actions and exposes finding filter parameters", async () => {
    const calls = mockDiscoveryFetch();
    renderWithQueryClient(<DiscoveryPage />);

    expect(await screen.findByText("Config Scanner")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Run now/ }));
    expect(await screen.findByText("Discovery run started")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Reconcile selected/ }));
    expect(await screen.findByText("Run reconciled")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Risk"), { target: { value: "critical" } });
    fireEvent.change(screen.getByLabelText("Status"), { target: { value: "suppressed" } });
    fireEvent.change(screen.getByLabelText("Owner"), { target: { value: "team-a" } });
    fireEvent.change(screen.getByLabelText("Source"), { target: { value: "agentmesh.yaml" } });
    fireEvent.change(screen.getByLabelText("Registry"), { target: { value: "unmatched" } });
    fireEvent.click(screen.getByLabelText("Suppressed"));
    fireEvent.click(screen.getByRole("button", { name: /Filter findings/ }));

    await waitFor(() =>
      expect(calls).toContain(
        "/api/v1/discovery/findings?risk_level=critical&status=suppressed&source=agentmesh.yaml&owner=team-a&registry_match=unmatched&include_suppressed=true"
      )
    );
    expect(await screen.findByText("Suppressed Crew")).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText("Confirm"), { target: { value: "SUPPRESS" } });
    fireEvent.change(screen.getByPlaceholderText("Reason"), { target: { value: "accepted" } });
    fireEvent.click(screen.getByRole("button", { name: "Suppress" }));
    expect(await screen.findByText("Finding suppressed")).toBeInTheDocument();

    expect(calls).toContain("/api/v1/discovery/runs");
    expect(calls).toContain("/api/v1/discovery/reconcile-run/run_1");
    expect(calls).toContain("/api/v1/discovery/findings/finding_1/suppress");
  });
});

function mockDiscoveryFetch() {
  const calls: string[] = [];
  vi.stubGlobal("fetch", async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const parsed = new URL(url, "http://test.local");
    const path = `${parsed.pathname}${parsed.search}`;
    calls.push(path);

    if (path === "/api/v1/discovery/scanners") {
      return json([scanner]);
    }
    if (path === "/api/v1/discovery/targets") {
      return json([target]);
    }
    if (path === "/api/v1/discovery/runs" && init?.method === "POST") {
      return json(runs[0]);
    }
    if (path === "/api/v1/discovery/runs") {
      return json(runs);
    }
    if (path.startsWith("/api/v1/discovery/findings?")) {
      return json([highRiskFinding, suppressedFinding]);
    }
    if (path === "/api/v1/discovery/findings") {
      return json([highRiskFinding, suppressedFinding]);
    }
    if (path === "/api/v1/discovery/reconcile-run/run_1") {
      return json({ reconciled: 1 });
    }
    if (path === "/api/v1/discovery/findings/finding_1/suppress") {
      return json({ ...highRiskFinding, status: "suppressed" });
    }
    if (path.includes("/discovery/findings/")) {
      return json(highRiskFinding);
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
