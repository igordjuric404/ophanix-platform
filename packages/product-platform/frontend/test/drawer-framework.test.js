import assert from "node:assert/strict";
import test from "node:test";

import {
  DRAWER_KINDS,
  closeDrawer,
  drawerDeepLink,
  drawerFromDeepLink,
  focusTargetForDrawer,
  handleDrawerKeydown,
  openDrawer,
  renderDrawer
} from "../src/drawers.js";
import { renderShell } from "../src/render.js";
import { createInitialAppState, withDrawer } from "../src/state.js";

test("component opens and closes drawer inside the shell", () => {
  const drawer = openDrawer({
    kind: DRAWER_KINDS.AUDIT_EVENT,
    resourceId: "evt_123",
    title: "Audit Event",
    subtitle: "evt_123",
    status: "Verified",
    content: "<p>Evidence content</p>"
  });
  const html = renderShell({
    currentPath: "/overview",
    state: withDrawer(createInitialAppState(), drawer)
  });

  assert.match(html, /data-drawer-open/);
  assert.match(html, /role="dialog"/);
  assert.match(html, /Audit Event/);
  assert.equal(renderDrawer(closeDrawer()), "");
});

test("component renders loading, empty, and error states", () => {
  const loading = renderDrawer(openDrawer({ title: "Loading", state: "loading" }));
  const empty = renderDrawer(openDrawer({ title: "Empty", state: "empty" }));
  const error = renderDrawer(openDrawer({ title: "Error", state: "error", error: "Not found" }));

  assert.match(loading, /data-drawer-loading/);
  assert.match(empty, /data-drawer-empty/);
  assert.match(error, /data-drawer-error/);
  assert.match(error, /Not found/);
});

test("accessibility markup and focus target are present", () => {
  const drawer = openDrawer({ title: "Policy Decision", subtitle: "Decision detail" });
  const html = renderDrawer(drawer);

  assert.match(html, /aria-modal="true"/);
  assert.match(html, /aria-labelledby="detail-drawer-title"/);
  assert.match(html, /aria-describedby="detail-drawer-description"/);
  assert.match(html, /data-drawer-close/);
  assert.equal(focusTargetForDrawer(drawer), "[data-drawer-close]");
  assert.equal(focusTargetForDrawer(closeDrawer()), ".content-region");
});

test("keyboard escape closes an open drawer", () => {
  let prevented = false;
  const drawer = openDrawer({ title: "Runtime Action" });
  const next = handleDrawerKeydown(
    {
      key: "Escape",
      preventDefault: () => {
        prevented = true;
      }
    },
    drawer
  );

  assert.equal(prevented, true);
  assert.equal(next.open, false);
});

test("deep links serialize and restore a loading drawer", () => {
  const drawer = openDrawer({
    kind: DRAWER_KINDS.WORKFLOW_RUN,
    resourceId: "job_123",
    title: "Workflow Run",
    activeTab: "related"
  });
  const deepLink = drawerDeepLink(drawer);
  const restored = drawerFromDeepLink(deepLink);

  assert.equal(deepLink, "?drawer=workflow-run&id=job_123&tab=related");
  assert.equal(restored.open, true);
  assert.equal(restored.kind, DRAWER_KINDS.WORKFLOW_RUN);
  assert.equal(restored.resourceId, "job_123");
  assert.equal(restored.activeTab, "related");
  assert.equal(restored.state, "loading");
});
