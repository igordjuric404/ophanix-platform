import { describe, expect, it } from "vitest";

import { defaultRoute, routeRegistry } from "./routes";

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
});

