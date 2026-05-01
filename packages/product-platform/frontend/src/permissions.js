export const Permission = {
  SYSTEM_READ: "system:read",
  TENANT_READ: "tenant:read",
  TENANT_MANAGE: "tenant:manage",
  POLICY_READ: "policy:read",
  POLICY_WRITE: "policy:write",
  AUDIT_READ: "audit:read",
  AUDIT_WRITE: "audit:write",
  JOB_RUN: "job:run",
  JOB_CANCEL: "job:cancel",
  API_KEYS_MANAGE: "api-keys:manage",
  SECURITY_MANAGE: "security:manage",
  COMPLIANCE_READ: "compliance:read"
};

const viewerPermissions = new Set([
  Permission.SYSTEM_READ,
  Permission.TENANT_READ,
  Permission.POLICY_READ,
  Permission.AUDIT_READ,
  Permission.COMPLIANCE_READ
]);

export const ROLE_PERMISSIONS = {
  Viewer: viewerPermissions,
  Operator: union(viewerPermissions, [Permission.JOB_RUN, Permission.JOB_CANCEL]),
  "Policy Admin": union(viewerPermissions, [Permission.POLICY_WRITE, Permission.AUDIT_WRITE]),
  "Security Admin": union(viewerPermissions, [
    Permission.SECURITY_MANAGE,
    Permission.API_KEYS_MANAGE
  ]),
  "Compliance Admin": union(viewerPermissions, [Permission.AUDIT_WRITE]),
  "Platform Admin": new Set(Object.values(Permission))
};

export const ROUTE_PERMISSIONS = {
  "/overview": Permission.SYSTEM_READ,
  "/agents": Permission.TENANT_READ,
  "/policies": Permission.POLICY_READ,
  "/trust": Permission.COMPLIANCE_READ,
  "/mcp": Permission.AUDIT_READ,
  "/mesh": Permission.SYSTEM_READ,
  "/runtime": Permission.JOB_RUN,
  "/discovery": Permission.JOB_RUN,
  "/marketplace": Permission.TENANT_READ,
  "/compliance": Permission.COMPLIANCE_READ,
  "/observability": Permission.AUDIT_READ,
  "/integrations": Permission.SECURITY_MANAGE,
  "/workflows": Permission.JOB_RUN,
  "/demo-lab": Permission.JOB_RUN,
  "/settings": Permission.TENANT_MANAGE
};

export function permissionsForRoles(roles = []) {
  const permissions = new Set();
  for (const role of roles) {
    for (const permission of ROLE_PERMISSIONS[role] ?? []) {
      permissions.add(permission);
    }
  }
  return permissions;
}

export function hasPermission(user, permission) {
  if (!permission) {
    return true;
  }
  const rolePermissions = permissionsForRoles(user?.roles ?? []);
  return rolePermissions.has(permission) || (user?.scopes ?? []).includes(permission);
}

export function canAccessRoute(path, user) {
  return hasPermission(user, ROUTE_PERMISSIONS[path]);
}

function union(base, additions) {
  return new Set([...base, ...additions]);
}
