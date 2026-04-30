"""Role-based access control primitives."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import HTTPException, Request


class Permission:
    """Permission constants for product resource groups."""

    SYSTEM_READ = "system:read"
    TENANT_READ = "tenant:read"
    TENANT_MANAGE = "tenant:manage"
    POLICY_READ = "policy:read"
    POLICY_WRITE = "policy:write"
    AUDIT_READ = "audit:read"
    AUDIT_WRITE = "audit:write"
    JOB_RUN = "job:run"
    JOB_CANCEL = "job:cancel"
    API_KEYS_MANAGE = "api-keys:manage"
    SECURITY_MANAGE = "security:manage"
    COMPLIANCE_READ = "compliance:read"


VIEWER_PERMISSIONS = {
    Permission.SYSTEM_READ,
    Permission.TENANT_READ,
    Permission.POLICY_READ,
    Permission.AUDIT_READ,
    Permission.COMPLIANCE_READ,
}

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "Viewer": VIEWER_PERMISSIONS,
    "Operator": VIEWER_PERMISSIONS | {Permission.JOB_RUN, Permission.JOB_CANCEL},
    "Policy Admin": VIEWER_PERMISSIONS | {Permission.POLICY_WRITE, Permission.AUDIT_WRITE},
    "Security Admin": VIEWER_PERMISSIONS | {Permission.SECURITY_MANAGE, Permission.API_KEYS_MANAGE},
    "Compliance Admin": VIEWER_PERMISSIONS | {Permission.AUDIT_WRITE},
    "Platform Admin": {
        Permission.SYSTEM_READ,
        Permission.TENANT_READ,
        Permission.TENANT_MANAGE,
        Permission.POLICY_READ,
        Permission.POLICY_WRITE,
        Permission.AUDIT_READ,
        Permission.AUDIT_WRITE,
        Permission.JOB_RUN,
        Permission.JOB_CANCEL,
        Permission.API_KEYS_MANAGE,
        Permission.SECURITY_MANAGE,
        Permission.COMPLIANCE_READ,
    },
}

VALID_ROLES = set(ROLE_PERMISSIONS)


def permissions_for_roles(roles: list[str]) -> set[str]:
    """Return the union of permissions granted by a set of roles."""

    permissions: set[str] = set()
    for role in roles:
        permissions.update(ROLE_PERMISSIONS.get(role, set()))
    return permissions


def has_permission(principal: Any, permission: str) -> bool:
    """Check whether a principal has a permission."""

    roles = list(getattr(principal, "roles", []))
    scopes = list(getattr(principal, "scopes", []))
    return permission in permissions_for_roles(roles) or permission in scopes


def require_permission(permission: str) -> Callable[[Request], Any]:
    """FastAPI dependency that enforces a permission."""

    def dependency(request: Request) -> Any:
        principal = getattr(request.state, "principal", None)
        if principal is None:
            raise HTTPException(status_code=401, detail="Authentication is required.")
        if not has_permission(principal, permission):
            denied_events = getattr(request.app.state, "denied_audit_events", None)
            if denied_events is None:
                denied_events = []
                request.app.state.denied_audit_events = denied_events
            denied_events.append(
                {
                    "event_type": "auth.permission_denied",
                    "permission": permission,
                    "path": request.url.path,
                    "method": request.method,
                    "user_id": getattr(principal, "id", None),
                    "roles": list(getattr(principal, "roles", [])),
                    "request_id": getattr(
                        getattr(request.state, "request_context", None),
                        "request_id",
                        request.headers.get("X-Request-ID"),
                    ),
                }
            )
            raise HTTPException(status_code=403, detail=f"Missing permission: {permission}")
        return principal

    return dependency
