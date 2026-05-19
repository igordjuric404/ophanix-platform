import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import type { UserPrincipal } from "../api/types";
import { canAccessRoute, permissions, rolePermissions } from "./rbac";

function userWithRole(role: string): UserPrincipal {
  return {
    id: `user_${role}`,
    email: "user@example.com",
    display_name: role,
    roles: [role]
  };
}

describe("route RBAC", () => {
  it("keeps frontend permission constants in contract with backend RBAC", () => {
    const backendRbac = readFileSync(
      "../src/product_platform/api/rbac.py",
      "utf8"
    );
    const backendPermissions = Array.from(
      backendRbac.matchAll(/^\s+[A-Z_]+\s+=\s+"([^"]+)"/gm),
      (match) => match[1]
    ).sort();

    expect(Object.values(permissions).sort()).toEqual(backendPermissions);
  });

  it("matches backend role templates for compliance and observability permissions", () => {
    expect(rolePermissions["Viewer"]).toContain(permissions.OBSERVABILITY_READ);
    expect(rolePermissions["Operator"]).not.toContain(permissions.OBSERVABILITY_WRITE);
    expect(rolePermissions["Compliance Admin"]).toContain(permissions.COMPLIANCE_WRITE);
    expect(rolePermissions["Compliance Admin"]).not.toContain(permissions.AUDIT_WRITE);
  });

  it("keeps viewer access read-only and blocks operational routes", () => {
    const viewer = userWithRole("Viewer");

    expect(canAccessRoute("/overview", viewer)).toBe(true);
    expect(canAccessRoute("/policies", viewer)).toBe(true);
    expect(canAccessRoute("/observability", viewer)).toBe(true);
    expect(canAccessRoute("/runtime", viewer)).toBe(false);
  });

  it("allows policy admins to reach policy governance but not settings", () => {
    const policyAdmin = userWithRole("Policy Admin");

    expect(canAccessRoute("/policies", policyAdmin)).toBe(true);
    expect(canAccessRoute("/settings", policyAdmin)).toBe(false);
  });

  it("allows security admins to reach settings for API key operations", () => {
    const securityAdmin = userWithRole("Security Admin");

    expect(canAccessRoute("/settings", securityAdmin)).toBe(true);
  });
});
