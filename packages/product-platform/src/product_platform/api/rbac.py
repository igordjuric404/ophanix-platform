"""Role-based access control primitives."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)


class Permission:
    """Permission constants for product resource groups."""

    SYSTEM_READ = "system:read"
    TENANT_READ = "tenant:read"
    TENANT_MANAGE = "tenant:manage"
    POLICY_READ = "policy:read"
    POLICY_WRITE = "policy:write"
    AGENT_READ = "agent:read"
    AGENT_WRITE = "agent:write"
    AUDIT_READ = "audit:read"
    AUDIT_WRITE = "audit:write"
    JOB_RUN = "job:run"
    JOB_CANCEL = "job:cancel"
    API_KEYS_MANAGE = "api-keys:manage"
    SECURITY_MANAGE = "security:manage"
    SECRETS_READ = "secrets:read"
    COMPLIANCE_READ = "compliance:read"
    COMPLIANCE_WRITE = "compliance:write"
    OBSERVABILITY_READ = "observability:read"
    OBSERVABILITY_WRITE = "observability:write"


VIEWER_PERMISSIONS = {
    Permission.SYSTEM_READ,
    Permission.TENANT_READ,
    Permission.POLICY_READ,
    Permission.AGENT_READ,
    Permission.AUDIT_READ,
    Permission.COMPLIANCE_READ,
    Permission.OBSERVABILITY_READ,
}

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "Viewer": VIEWER_PERMISSIONS,
    "Operator": VIEWER_PERMISSIONS
    | {Permission.AGENT_WRITE, Permission.JOB_RUN, Permission.JOB_CANCEL},
    "Policy Admin": VIEWER_PERMISSIONS | {Permission.POLICY_WRITE, Permission.AUDIT_WRITE},
    "Security Admin": VIEWER_PERMISSIONS
    | {Permission.SECURITY_MANAGE, Permission.API_KEYS_MANAGE, Permission.SECRETS_READ},
    "Compliance Admin": VIEWER_PERMISSIONS | {Permission.COMPLIANCE_WRITE},
    "Platform Admin": {
        Permission.SYSTEM_READ,
        Permission.TENANT_READ,
        Permission.TENANT_MANAGE,
        Permission.POLICY_READ,
        Permission.POLICY_WRITE,
        Permission.AGENT_READ,
        Permission.AGENT_WRITE,
        Permission.AUDIT_READ,
        Permission.AUDIT_WRITE,
        Permission.JOB_RUN,
        Permission.JOB_CANCEL,
        Permission.API_KEYS_MANAGE,
        Permission.SECURITY_MANAGE,
        Permission.SECRETS_READ,
        Permission.COMPLIANCE_READ,
        Permission.COMPLIANCE_WRITE,
        Permission.OBSERVABILITY_READ,
        Permission.OBSERVABILITY_WRITE,
    },
}

VALID_ROLES = set(ROLE_PERMISSIONS)
VALID_PERMISSIONS = frozenset().union(*ROLE_PERMISSIONS.values())


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


def validate_delegated_api_key_scopes(principal: Any, scopes: list[str]) -> list[str]:
    """Return validated API-key scopes that the principal is allowed to delegate."""

    normalized: list[str] = []
    for scope in scopes:
        value = scope.strip()
        if not value:
            continue
        if value not in normalized:
            normalized.append(value)
    unknown_scopes = sorted(set(normalized) - VALID_PERMISSIONS)
    if unknown_scopes:
        raise ValueError(f"Unknown API key scope(s): {', '.join(unknown_scopes)}")
    denied_scopes = sorted(scope for scope in normalized if not has_permission(principal, scope))
    if denied_scopes:
        raise PermissionError(
            "Cannot delegate API key scope(s) not granted to the current principal: "
            + ", ".join(denied_scopes)
        )
    return normalized


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
            event = {
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
            denied_events.append(event)
            recorder = getattr(request.app.state, "permission_denied_audit_recorder", None)
            if callable(recorder):
                try:
                    recorder(request, principal, event)
                except Exception:
                    logger.exception("Failed to persist permission-denied audit event.")
            raise HTTPException(status_code=403, detail=f"Missing permission: {permission}")
        return principal

    return dependency
