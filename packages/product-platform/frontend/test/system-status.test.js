import assert from "node:assert/strict";
import test from "node:test";

import { ApiClientError } from "../src/apiClient.js";
import { renderShell } from "../src/render.js";
import {
  createInitialAppState,
  createSystemStatus,
  loadSystemStatus,
  withSystemStatus
} from "../src/state.js";

const version = {
  app: "Ophanix Test Platform",
  version: "0.1.0",
  build_sha: "test-sha",
  build_time: "2026-04-30T00:00:00Z",
  environment: "test"
};

test("component render shows healthy system status with version details", () => {
  const state = withSystemStatus(
    createInitialAppState(),
    createSystemStatus({
      version,
      dependencies: [{ name: "database", status: "healthy", required: true }]
    })
  );
  const html = renderShell({ currentPath: "/overview", state });

  assert.match(html, /status-healthy/);
  assert.match(html, /Healthy/);
  assert.match(html, /Ophanix Test Platform/);
  assert.match(html, /database/);
});

test("component render shows degraded system status for unhealthy dependency", () => {
  const state = withSystemStatus(
    createInitialAppState(),
    createSystemStatus({
      version,
      dependencies: [
        { name: "database", status: "healthy", required: true },
        { name: "redis", status: "unhealthy", required: false }
      ]
    })
  );
  const html = renderShell({ currentPath: "/overview", state });

  assert.match(html, /status-degraded/);
  assert.match(html, /Degraded/);
  assert.match(html, /redis/);
});

test("api error state displays non-blocking warning", async () => {
  const status = await loadSystemStatus({
    apiClient: {
      listSystemDependencies: async () => {
        throw new ApiClientError("Dependency endpoint unavailable.", {
          status: 503,
          payload: {}
        });
      },
      getVersion: async () => version
    }
  });
  const html = renderShell({
    currentPath: "/overview",
    state: withSystemStatus(createInitialAppState(), status)
  });

  assert.equal(status.status, "warning");
  assert.match(html, /status-warning/);
  assert.match(html, /Dependency endpoint unavailable/);
});

test("notification center renders empty state", () => {
  const html = renderShell({ currentPath: "/overview", state: createInitialAppState() });

  assert.match(html, /aria-label="Notifications"/);
  assert.match(html, /No notifications/);
});
