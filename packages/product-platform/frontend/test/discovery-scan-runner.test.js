import assert from "node:assert/strict";
import test from "node:test";

import { createApiClient } from "../src/apiClient.js";
import {
  renderDiscoveryPage,
  renderDiscoveryRunDetail,
  renderDiscoveryRunTable
} from "../src/discovery.js";
import { renderShell } from "../src/render.js";
import { createInitialAppState } from "../src/state.js";

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

const run = {
  id: "run_1",
  scanner_type: "config",
  target_id: "target_1",
  status: "succeeded",
  started_at: "2026-04-30T11:00:00+00:00",
  finished_at: "2026-04-30T11:00:03+00:00",
  error_message: null,
  raw_finding_count: 1,
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
};

test("discovery route renders scan workspace instead of placeholder", () => {
  const html = renderShell({
    currentPath: "/discovery",
    state: createInitialAppState({
      discoveryScanners: [scanner],
      discoveryTargets: [target],
      discoveryRuns: [run]
    })
  });

  assert.match(html, /data-route-page="\/discovery"/);
  assert.match(html, /data-discovery-workspace/);
  assert.doesNotMatch(html, /Primary Workspace/);
});

test("component run table renders status counts and duration", () => {
  const html = renderDiscoveryRunTable([run]);

  assert.match(html, /data-discovery-run-row="run_1"/);
  assert.match(html, /succeeded/);
  assert.match(html, /1 raw/);
  assert.match(html, /0 high/);
  assert.match(html, /3s/);
});

test("component run detail renders raw findings", () => {
  const html = renderDiscoveryRunDetail(run);

  assert.match(html, /data-discovery-run-detail="run_1"/);
  assert.match(html, /agt agent at agentmesh.yaml/);
  assert.match(html, /abc123/);
  assert.match(html, /Reconciliation/);
});

test("component error state is visible for failed scans", () => {
  const html = renderDiscoveryPage({
    discoveryScanners: [scanner],
    discoveryTargets: [target],
    discoveryRuns: [
      {
        ...run,
        id: "run_failed",
        status: "failed",
        error_message: "Not a directory",
        raw_finding_count: 0,
        raw_findings: []
      }
    ]
  });

  assert.match(html, /data-discovery-run-error/);
  assert.match(html, /Not a directory/);
});

test("api client discovery methods call expected endpoints", async () => {
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

  await client.listDiscoveryScanners();
  await client.listDiscoveryTargets();
  await client.createDiscoveryTarget({ scanner_type: "config" });
  await client.patchDiscoveryTargetSchedule("target_1", { mode: "hourly" });
  await client.createDiscoveryRun({ target_id: "target_1" });
  await client.listDiscoveryRuns();
  await client.getDiscoveryRun("run_1");

  assert.deepEqual(calls, [
    ["/api/v1/discovery/scanners", "GET", null],
    ["/api/v1/discovery/targets", "GET", null],
    ["/api/v1/discovery/targets", "POST", { scanner_type: "config" }],
    ["/api/v1/discovery/targets/target_1/schedule", "PATCH", { mode: "hourly" }],
    ["/api/v1/discovery/runs", "POST", { target_id: "target_1" }],
    ["/api/v1/discovery/runs", "GET", null],
    ["/api/v1/discovery/runs/run_1", "GET", null]
  ]);
});
