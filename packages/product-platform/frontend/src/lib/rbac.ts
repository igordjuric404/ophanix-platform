import type { UserPrincipal } from "../api/types";

export const permissions = {
  SYSTEM_READ: "system:read",
  TENANT_READ: "tenant:read",
  TENANT_MANAGE: "tenant:manage",
  POLICY_READ: "policy:read",
  POLICY_WRITE: "policy:write",
  AGENT_READ: "agent:read",
  AGENT_WRITE: "agent:write",
  AUDIT_READ: "audit:read",
  AUDIT_WRITE: "audit:write",
  JOB_RUN: "job:run",
  JOB_CANCEL: "job:cancel",
  API_KEYS_MANAGE: "api-keys:manage",
  SECURITY_MANAGE: "security:manage",
  COMPLIANCE_READ: "compliance:read"
} as const;

const viewerPermissions: Set<string> = new Set([
  permissions.SYSTEM_READ,
  permissions.TENANT_READ,
  permissions.POLICY_READ,
  permissions.AGENT_READ,
  permissions.AUDIT_READ,
  permissions.COMPLIANCE_READ
]);

export const rolePermissions: Record<string, Set<string>> = {
  Viewer: viewerPermissions,
  Operator: new Set([
    ...viewerPermissions,
    permissions.AGENT_WRITE,
    permissions.JOB_RUN,
    permissions.JOB_CANCEL
  ]),
  "Policy Admin": new Set([...viewerPermissions, permissions.POLICY_WRITE, permissions.AUDIT_WRITE]),
  "Security Admin": new Set([
    ...viewerPermissions,
    permissions.SECURITY_MANAGE,
    permissions.API_KEYS_MANAGE
  ]),
  "Compliance Admin": new Set([...viewerPermissions, permissions.AUDIT_WRITE]),
  "Platform Admin": new Set(Object.values(permissions))
};

export function userHasPermission(user: UserPrincipal | null | undefined, permission: string) {
  if (!user) {
    return false;
  }
  const explicitScopes = new Set(user.scopes ?? []);
  if (explicitScopes.has(permission)) {
    return true;
  }
  return user.roles.some((role) =>
    rolePermissions[role as keyof typeof rolePermissions]?.has(permission)
  );
}
