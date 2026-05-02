import { describe, expect, it } from "vitest";

import type { UserPrincipal } from "../api/types";
import { canAccessRoute } from "./rbac";

function userWithRole(role: string): UserPrincipal {
  return {
    id: `user_${role}`,
    email: "user@example.com",
    display_name: role,
    roles: [role]
  };
}

describe("route RBAC", () => {
  it("keeps viewer access read-only and blocks operational routes", () => {
    const viewer = userWithRole("Viewer");

    expect(canAccessRoute("/overview", viewer)).toBe(true);
    expect(canAccessRoute("/policies", viewer)).toBe(true);
    expect(canAccessRoute("/runtime", viewer)).toBe(false);
  });

  it("allows policy admins to reach policy governance but not settings", () => {
    const policyAdmin = userWithRole("Policy Admin");

    expect(canAccessRoute("/policies", policyAdmin)).toBe(true);
    expect(canAccessRoute("/settings", policyAdmin)).toBe(false);
  });
});

