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
  COMPLIANCE_READ: "compliance:read",
  COMPLIANCE_WRITE: "compliance:write",
  OBSERVABILITY_READ: "observability:read",
  OBSERVABILITY_WRITE: "observability:write"
} as const;

const viewerPermissions: Set<string> = new Set([
  permissions.SYSTEM_READ,
  permissions.TENANT_READ,
  permissions.POLICY_READ,
  permissions.AGENT_READ,
  permissions.AUDIT_READ,
  permissions.COMPLIANCE_READ,
  permissions.OBSERVABILITY_READ
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
  "Compliance Admin": new Set([...viewerPermissions, permissions.COMPLIANCE_WRITE]),
  "Platform Admin": new Set(Object.values(permissions))
};

export const routePermissions: Record<string, string | readonly string[]> = {
  "/overview": permissions.SYSTEM_READ,
  "/agents": permissions.AGENT_READ,
  "/policies": permissions.POLICY_READ,
  "/trust": permissions.COMPLIANCE_READ,
  "/mcp": permissions.AUDIT_READ,
  "/mesh": permissions.SYSTEM_READ,
  "/runtime": permissions.JOB_RUN,
  "/tool-gateway/decisions": permissions.AUDIT_READ,
  "/discovery": permissions.JOB_RUN,
  "/marketplace": permissions.TENANT_READ,
  "/compliance": permissions.COMPLIANCE_READ,
  "/observability": permissions.OBSERVABILITY_READ,
  "/integrations": permissions.SECURITY_MANAGE,
  "/workflows": permissions.JOB_RUN,
  "/demo-lab": permissions.JOB_RUN,
  "/settings": [permissions.TENANT_MANAGE, permissions.API_KEYS_MANAGE]
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

export function userHasEnvironmentAccess(
  user: UserPrincipal | null | undefined,
  environmentId: string | null | undefined
) {
  if (!user || !environmentId) {
    return false;
  }
  const environmentIds = user.environment_ids ?? [];
  return environmentIds.includes(environmentId);
}

export function canAccessRoute(
  path: string,
  user: UserPrincipal | null | undefined,
  environmentId?: string | null
) {
  if (environmentId !== undefined && !userHasEnvironmentAccess(user, environmentId)) {
    return false;
  }
  const requiredPermission = routePermissions[path];
  if (!requiredPermission) {
    return true;
  }
  const acceptedPermissions = Array.isArray(requiredPermission)
    ? requiredPermission
    : [requiredPermission];
  return acceptedPermissions.some((permission) => userHasPermission(user, permission));
}
