import assert from "node:assert/strict";
import test from "node:test";

import { createApiClient } from "../src/apiClient.js";
import {
  discoveryFindingParamsFromValues,
  renderDiscoveryFindingDetail,
  renderDiscoveryFindingsTable,
  renderDiscoveryPage
} from "../src/discovery.js";

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

test("component high-risk finding renders", () => {
  const html = renderDiscoveryPage({ discoveryFindings: [highRiskFinding] });

  assert.match(html, /data-discovery-findings/);
  assert.match(html, /Shadow Crew/);
  assert.match(html, /critical/);
  assert.match(html, /85/);
});

test("component finding detail renders evidence and risk factors", () => {
  const html = renderDiscoveryFindingDetail(highRiskFinding);

  assert.match(html, /data-discovery-finding-detail="finding_1"/);
  assert.match(html, /No assigned owner/);
  assert.match(html, /config_file/);
  assert.match(html, /\/repo\/agentmesh.yaml/);
});

test("component action requires confirmation", () => {
  const html = renderDiscoveryFindingDetail(highRiskFinding);

  assert.match(html, /data-discovery-action="suppress"/);
  assert.match(html, /name="confirm" required/);
  assert.match(html, /data-discovery-action="register-agent"/);
});

test("component suppressed finding is hidden by default but can be filtered", () => {
  const suppressed = { ...highRiskFinding, id: "finding_suppressed", status: "suppressed" };

  const defaultHtml = renderDiscoveryFindingsTable([highRiskFinding, suppressed]);
  const filteredHtml = renderDiscoveryFindingsTable([highRiskFinding, suppressed], {
    includeSuppressed: true
  });

  assert.match(defaultHtml, /finding_1/);
  assert.doesNotMatch(defaultHtml, /finding_suppressed/);
  assert.match(filteredHtml, /finding_suppressed/);
});

test("component findings table exposes registry filter params", () => {
  const html = renderDiscoveryFindingsTable([highRiskFinding]);
  const params = discoveryFindingParamsFromValues({
    risk_level: "critical",
    status: "suppressed",
    owner: "team-a",
    source: "agentmesh.yaml",
    registry_match: "unmatched"
  });

  assert.match(html, /name="registry_match"/);
  assert.deepEqual(params, {
    risk_level: "critical",
    status: "suppressed",
    owner: "team-a",
    source: "agentmesh.yaml",
    registry_match: "unmatched",
    include_suppressed: true
  });
});

test("api client reconciliation methods call expected endpoints", async () => {
  const calls = [];
  const client = createApiClient({
    fetchImpl: async (url, init = {}) => {
      calls.push([url, init.method ?? "GET", init.body ? JSON.parse(init.body) : null]);
      return {
        ok: true,
        status: 200,
        headers: new Map([["content-type", "application/json"]]),
        json: async () => ({ id: "ok" })
      };
    }
  });

  await client.listDiscoveryFindings({ risk_level: "critical" });
  await client.getDiscoveryFinding("finding_1");
  await client.reconcileDiscoveryRun("run_1");
  await client.assignDiscoveryFindingOwner("finding_1", { owner_user_id: "owner_1" });
  await client.registerDiscoveryFindingAgent("finding_1", { owner_user_id: "owner_1" });
  await client.suppressDiscoveryFinding("finding_1", { reason: "accepted" });
  await client.markDiscoveryFindingDecommissioned("finding_1");

  assert.deepEqual(calls, [
    ["/api/v1/discovery/findings?risk_level=critical", "GET", null],
    ["/api/v1/discovery/findings/finding_1", "GET", null],
    ["/api/v1/discovery/reconcile-run/run_1", "POST", null],
    [
      "/api/v1/discovery/findings/finding_1/assign-owner",
      "POST",
      { owner_user_id: "owner_1" }
    ],
    [
      "/api/v1/discovery/findings/finding_1/register-agent",
      "POST",
      { owner_user_id: "owner_1" }
    ],
    ["/api/v1/discovery/findings/finding_1/suppress", "POST", { reason: "accepted" }],
    ["/api/v1/discovery/findings/finding_1/mark-decommissioned", "POST", null]
  ]);
});
