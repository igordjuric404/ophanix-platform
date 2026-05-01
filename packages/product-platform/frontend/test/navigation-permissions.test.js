import assert from "node:assert/strict";
import test from "node:test";

import { renderShell } from "../src/render.js";
import { createInitialAppState, guardRoute } from "../src/state.js";
import { canAccessRoute, hasPermission, Permission } from "../src/permissions.js";

function stateForRoles(roles) {
  return createInitialAppState({
    currentUser: {
      id: `user_${roles.join("_")}`,
      display_name: roles.join(", "),
      email: "user@example.com",
      roles,
      organization_id: "org_default"
    }
  });
}

test("Viewer sees read-only sections and restricted sections are disabled", () => {
  const state = stateForRoles(["Viewer"]);
  const html = renderShell({ currentPath: "/overview", state });

  assert.equal(canAccessRoute("/overview", state.currentUser), true);
  assert.equal(canAccessRoute("/policies", state.currentUser), true);
  assert.equal(canAccessRoute("/settings", state.currentUser), false);
  assert.match(html, /href="\/overview"/);
  assert.match(html, /href="\/policies"/);
  assert.match(html, /data-route-disabled="\/settings"/);
  assert.match(html, /data-route-disabled="\/workflows"/);
});

test("Policy Admin can see and open policy pages", () => {
  const state = stateForRoles(["Policy Admin"]);
  const html = renderShell({ currentPath: "/policies", state });

  assert.equal(hasPermission(state.currentUser, Permission.POLICY_READ), true);
  assert.equal(hasPermission(state.currentUser, Permission.POLICY_WRITE), true);
  assert.match(html, /data-route-page="\/policies"/);
  assert.match(html, /<h1>Policies<\/h1>/);
  assert.doesNotMatch(html, /data-access-denied/);
});

test("unauthorized direct route renders access denied", () => {
  const state = stateForRoles(["Viewer"]);
  const guarded = guardRoute("/settings", state);
  const html = renderShell({ currentPath: "/settings", state });

  assert.equal(guarded.reason, "forbidden");
  assert.equal(guarded.path, "/settings");
  assert.match(html, /data-access-denied/);
  assert.match(html, /Access Denied/);
});

test("Operator can access workflow and runtime routes", () => {
  const state = stateForRoles(["Operator"]);

  assert.equal(canAccessRoute("/workflows", state.currentUser), true);
  assert.equal(canAccessRoute("/runtime", state.currentUser), true);
  assert.match(renderShell({ currentPath: "/workflows", state }), /data-route-page="\/workflows"/);
});
