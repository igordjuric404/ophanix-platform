import { describe, expect, it } from "vitest";

import { defaultRoute, routeGroups, routeRegistry } from "./routes";

describe("route registry", () => {
  it("preserves the current top-level route taxonomy", () => {
    expect(defaultRoute).toBe("/overview");
    expect(routeRegistry.map((route) => route.path)).toEqual([
      "/overview",
      "/agents",
      "/policies",
      "/trust",
      "/mcp",
      "/mesh",
      "/runtime",
      "/tool-gateway/decisions",
      "/discovery",
      "/marketplace",
      "/compliance",
      "/observability",
      "/integrations",
      "/workflows",
      "/demo-lab",
      "/settings"
    ]);
  });

  it("keeps route paths unique and display metadata complete", () => {
    expect(new Set(routeRegistry.map((route) => route.path)).size).toBe(routeRegistry.length);

    for (const route of routeRegistry) {
      expect(route.label).toBeTruthy();
      expect(route.area).toBeTruthy();
      expect(route.description).toBeTruthy();
    }
  });

  it("groups routes without dropping entries", () => {
    const expectedAreas = Array.from(new Set(routeRegistry.map((route) => route.area)));
    const groups = routeGroups();
    const groupedPaths = groups.flatMap((group) => group.routes.map((route) => route.path));

    expect(groups.map((group) => group.area)).toEqual(expectedAreas);
    expect(groupedPaths).toHaveLength(routeRegistry.length);
    expect(new Set(groupedPaths)).toEqual(new Set(routeRegistry.map((route) => route.path)));
  });
});
