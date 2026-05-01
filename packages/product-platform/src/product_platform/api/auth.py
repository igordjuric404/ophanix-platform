"""Development authentication and current-user helpers."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any
from uuid import uuid5, NAMESPACE_URL

from fastapi import Request
from pydantic import BaseModel, EmailStr, Field

from product_platform.api.settings import Settings
from product_platform.api.rbac import VALID_ROLES

SESSION_COOKIE_NAME = "ophanix_session"


class DevLoginRequest(BaseModel):
    """Development-only login request."""

    email: EmailStr
    display_name: str | None = None
    roles: list[str] | None = None
    organization_id: str | None = None


class UserPrincipal(BaseModel):
    """Authenticated product user."""

    id: str
    email: EmailStr
    display_name: str
    roles: list[str] = Field(default_factory=list)
    scopes: list[str] = Field(default_factory=list)
    organization_id: str | None = None
    environment_id: str | None = None
    actor_type: str = "user"


class AuthResponse(BaseModel):
    """Login response with one bearer token and current user."""

    access_token: str
    token_type: str = "bearer"
    expires_at: int
    user: UserPrincipal


class AuthService:
    """Small HMAC-signed token service for local development auth."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def login(self, request: DevLoginRequest) -> AuthResponse:
        allowed = {email.lower() for email in self._settings.dev_login_allowed_emails}
        if "*" not in allowed and request.email.lower() not in allowed:
            raise PermissionError("Email is not allowed for development login.")

        roles = request.roles or ["Platform Admin"]
        invalid_roles = sorted(set(roles) - VALID_ROLES)
        if invalid_roles:
            raise ValueError(f"Unknown role(s): {', '.join(invalid_roles)}")

        user = UserPrincipal(
            id=str(uuid5(NAMESPACE_URL, f"ophanix:user:{request.email.lower()}")),
            email=request.email,
            display_name=request.display_name or request.email.split("@")[0],
            roles=roles,
            organization_id=request.organization_id or self._settings.default_organization_id,
        )
        expires_at = int(time.time()) + self._settings.session_ttl_seconds
        token = self._encode(
            {
                "sub": user.id,
                "email": user.email,
                "display_name": user.display_name,
                "roles": user.roles,
                "organization_id": user.organization_id,
                "environment_id": user.environment_id,
                "actor_type": user.actor_type,
                "expires_at": expires_at,
            }
        )
        return AuthResponse(access_token=token, expires_at=expires_at, user=user)

    def authenticate_request(self, request: Request) -> UserPrincipal | None:
        token = self._token_from_request(request)
        if token is None:
            return None
        return self.verify_token(token)

    def verify_token(self, token: str) -> UserPrincipal | None:
        try:
            payload = self._decode(token)
        except ValueError:
            return None
        if int(payload.get("expires_at", 0)) < int(time.time()):
            return None
        return UserPrincipal(
            id=str(payload["sub"]),
            email=payload["email"],
            display_name=str(payload["display_name"]),
            roles=list(payload.get("roles", [])),
            organization_id=payload.get("organization_id"),
            environment_id=payload.get("environment_id"),
            actor_type=str(payload.get("actor_type", "user")),
        )

    def _token_from_request(self, request: Request) -> str | None:
        authorization = request.headers.get("Authorization", "")
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() == "bearer" and token:
            return token
        cookie = request.cookies.get(SESSION_COOKIE_NAME)
        return cookie or None

    def _encode(self, payload: dict[str, Any]) -> str:
        payload_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        payload_part = base64.urlsafe_b64encode(payload_bytes).decode().rstrip("=")
        signature = self._sign(payload_part)
        return f"{payload_part}.{signature}"

    def _decode(self, token: str) -> dict[str, Any]:
        payload_part, separator, signature = token.partition(".")
        if not separator:
            raise ValueError("Malformed token.")
        expected_signature = self._sign(payload_part)
        if not hmac.compare_digest(signature, expected_signature):
            raise ValueError("Invalid token signature.")
        padded = payload_part + ("=" * (-len(payload_part) % 4))
        return json.loads(base64.urlsafe_b64decode(padded.encode()).decode())

    def _sign(self, payload_part: str) -> str:
        digest = hmac.new(
            self._settings.session_secret.encode(),
            payload_part.encode(),
            hashlib.sha256,
        ).digest()
        return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def get_current_user(request: Request) -> UserPrincipal:
    principal = getattr(request.state, "principal", None)
    if not isinstance(principal, UserPrincipal):
        raise RuntimeError("Current user dependency used without authentication middleware.")
    return principal
