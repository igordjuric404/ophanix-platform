import assert from "node:assert/strict";
import test from "node:test";

import { createApiClient, ApiClientError } from "../src/apiClient.js";
import { renderShell } from "../src/render.js";
import {
  STORAGE_ENVIRONMENT_KEY,
  createAuthenticatedState,
  createMemoryStorage,
  createUnauthenticatedState,
  guardRoute,
  loadAppContext,
  tenantHeaders,
  updateSelectedEnvironment
} from "../src/state.js";

const currentUser = {
  id: "user_operator",
  display_name: "Operator User",
  email: "operator@example.com",
  roles: ["Operator"],
  organization_id: "org_default"
};

const organizations = [
  {
    id: "org_default",
    name: "Ophanix Demo",
    slug: "ophanix-demo"
  }
];

const environments = [
  {
    id: "env_default",
    organization_id: "org_default",
    name: "Development",
    slug: "development",
    type: "development"
  },
  {
    id: "env_staging",
    organization_id: "org_default",
    name: "Staging",
    slug: "staging",
    type: "staging"
  }
];

test("component render shows selected environment and current user", () => {
  const storage = createMemoryStorage({ [STORAGE_ENVIRONMENT_KEY]: "env_staging" });
  const state = createAuthenticatedState({
    currentUser,
    organizations,
    environments,
    storage
  });
  const html = renderShell({ currentPath: "/overview", state });

  assert.equal(state.selectedEnvironment.id, "env_staging");
  assert.match(html, /<option value="env_staging" selected>/);
  assert.match(html, /Operator User/);
});

test("api client includes selected organization and environment headers", async () => {
  const captured = {};
  const client = createApiClient({
    baseUrl: "/api/v1",
    getTenantContext: () => ({ organizationId: "org_default", environmentId: "env_staging" }),
    fetchImpl: async (url, init) => {
      captured.url = url;
      captured.headers = init.headers;
      return jsonResponse({ ok: true });
    }
  });

  await client.request("/environments");

  assert.equal(captured.url, "/api/v1/environments");
  assert.equal(captured.headers.get("X-Organization-ID"), "org_default");
  assert.equal(captured.headers.get("X-Environment-ID"), "env_staging");
  assert.equal(captured.headers.get("Accept"), "application/json");
});

test("route guard redirects unauthenticated users to login", () => {
  const state = createUnauthenticatedState();
  const guarded = guardRoute("/policies", state);
  const html = renderShell({ currentPath: "/policies", state });

  assert.equal(guarded.path, "/login");
  assert.equal(guarded.redirected, true);
  assert.match(html, /data-auth-required/);
});

test("load app context returns unauthenticated state on auth failure", async () => {
  const client = {
    getCurrentUser: async () => {
      throw new ApiClientError("Authentication is required.", { status: 401, payload: {} });
    }
  };

  const state = await loadAppContext({ apiClient: client, storage: createMemoryStorage() });

  assert.equal(state.authStatus, "unauthenticated");
  assert.equal(state.currentUser, null);
});

test("selected environment updates app state, storage, and tenant headers", () => {
  const storage = createMemoryStorage();
  const state = createAuthenticatedState({
    currentUser,
    organizations,
    environments,
    storage
  });
  const updated = updateSelectedEnvironment(state, "env_staging", storage);

  assert.equal(updated.selectedEnvironment.id, "env_staging");
  assert.equal(storage.getItem(STORAGE_ENVIRONMENT_KEY), "env_staging");
  assert.deepEqual(tenantHeaders(updated), {
    "X-Organization-ID": "org_default",
    "X-Environment-ID": "env_staging"
  });
});

function jsonResponse(payload, { status = 200, ok = true } = {}) {
  return {
    ok,
    status,
    headers: new Headers({ "content-type": "application/json" }),
    json: async () => payload,
    text: async () => JSON.stringify(payload)
  };
}
