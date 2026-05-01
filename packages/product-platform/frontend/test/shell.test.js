import assert from "node:assert/strict";
import test from "node:test";

import { DEFAULT_ROUTE, PRODUCT_ROUTES, findRoute, normalizePath, routeGroups } from "../src/navigation.js";
import { renderShell, renderRouteSummary } from "../src/render.js";

const expectedRoutePaths = [
  "/overview",
  "/agents",
  "/policies",
  "/trust",
  "/mcp",
  "/mesh",
  "/runtime",
  "/discovery",
  "/marketplace",
  "/compliance",
  "/observability",
  "/integrations",
  "/workflows",
  "/demo-lab",
  "/settings"
];

test("component render includes the shell layout regions", () => {
  const html = renderShell({ currentPath: DEFAULT_ROUTE });

  assert.match(html, /data-app-shell/);
  assert.match(html, /aria-label="Product navigation"/);
  assert.match(html, /class="top-bar"/);
  assert.match(html, /class="content-region"/);
  assert.match(html, /Search agents, policies, tools, events/);
});

test("route registry contains every top-level product route in order", () => {
  assert.deepEqual(
    PRODUCT_ROUTES.map((route) => route.path),
    expectedRoutePaths
  );
  assert.equal(routeGroups()[0].area, "Command");
  assert.equal(renderRouteSummary().split("\n").length, PRODUCT_ROUTES.length);
});

test("root path normalizes to the overview route", () => {
  assert.equal(normalizePath("/"), "/overview");
  assert.equal(normalizePath("/overview/"), "/overview");
  assert.equal(findRoute("/overview")?.label, "Overview");
});

test("every top-level route renders its placeholder page and active nav item", () => {
  for (const route of PRODUCT_ROUTES) {
    const html = renderShell({ currentPath: route.path });

    assert.match(html, new RegExp(`data-route-page="${route.path}"`));
    assert.match(html, new RegExp(`<h1>${route.label}</h1>`));
    assert.match(html, new RegExp(`href="${route.path}"[\\s\\S]*aria-current="page"`));
  }
});

test("unknown routes render a not-found placeholder inside the shell", () => {
  const html = renderShell({ currentPath: "/missing" });

  assert.match(html, /data-route-page="not-found"/);
  assert.match(html, /Page Not Found/);
});
