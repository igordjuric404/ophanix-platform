"""Development authentication and current-user helpers."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any
from uuid import uuid5, NAMESPACE_URL

import jwt
from fastapi import Request
from pydantic import BaseModel, EmailStr, Field
from jwt import PyJWKClient, PyJWKSet
from jwt.exceptions import PyJWTError

from product_platform.api.settings import Settings
from product_platform.api.rbac import VALID_ROLES

SESSION_COOKIE_NAME = "ophanix_session"


class DevLoginRequest(BaseModel):
    """Development-only login request."""

    email: EmailStr
    display_name: str | None = None
    roles: list[str] | None = None
    organization_id: str | None = None
    environment_ids: list[str] | None = None


class UserPrincipal(BaseModel):
    """Authenticated product user."""

    id: str
    email: EmailStr
    display_name: str
    roles: list[str] = Field(default_factory=list)
    scopes: list[str] = Field(default_factory=list)
    organization_id: str | None = None
    environment_id: str | None = None
    environment_ids: list[str] = Field(default_factory=list)
    idp_subject: str | None = None
    idp_issuer: str | None = None
    token_id: str | None = None
    actor_type: str = "user"


class AuthResponse(BaseModel):
    """Login response with one bearer token and current user."""

    access_token: str
    token_type: str = "bearer"
    expires_at: int
    user: UserPrincipal


class OIDCValidationError(ValueError):
    """Raised when an enterprise IdP token cannot be trusted."""


def _is_local_environment(environment: str) -> bool:
    return environment.strip().lower() in {"development", "dev", "local", "local-demo", "test"}


def _unique_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        candidates = [value]
    elif isinstance(value, list | tuple | set):
        candidates = list(value)
    else:
        candidates = [value]
    normalized: list[str] = []
    for candidate in candidates:
        item = str(candidate).strip()
        if item and item not in normalized:
            normalized.append(item)
    return normalized


def _load_group_role_map(raw: str) -> dict[str, list[str]]:
    try:
        parsed = json.loads(raw or "{}")
    except json.JSONDecodeError as exc:
        raise OIDCValidationError("IdP group-role mapping is not valid JSON.") from exc
    if not isinstance(parsed, dict):
        raise OIDCValidationError("IdP group-role mapping must be a JSON object.")
    mapping: dict[str, list[str]] = {}
    for group, roles in parsed.items():
        group_name = str(group).strip()
        role_names = [role for role in _unique_string_list(roles) if role in VALID_ROLES]
        if group_name and role_names:
            mapping[group_name] = role_names
    return mapping


class OIDCTokenValidator:
    """Validate enterprise OIDC/JWKS bearer tokens and map claims to a principal."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._issuer = settings.idp_issuer_url
        self._audience = settings.idp_audience
        self._algorithms = list(settings.idp_algorithms or ["RS256"])
        self._static_jwks_json = settings.idp_jwks_json
        self._jwks_client = (
            PyJWKClient(settings.idp_jwks_url)
            if settings.idp_jwks_url and not settings.idp_jwks_json
            else None
        )
        self._group_role_map = _load_group_role_map(settings.idp_group_role_map_json)

    @property
    def enabled(self) -> bool:
        return bool(
            self._issuer
            and self._audience
            and self._algorithms
            and (self._static_jwks_json or self._jwks_client is not None)
        )

    def verify(self, token: str) -> UserPrincipal:
        if not self.enabled:
            raise OIDCValidationError("OIDC validation is not configured.")
        try:
            signing_key = self._signing_key(token)
            claims = jwt.decode(
                token,
                signing_key,
                algorithms=self._algorithms,
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["exp", "iss", "sub", "aud"]},
            )
        except (KeyError, PyJWTError, ValueError) as exc:
            raise OIDCValidationError("OIDC token validation failed.") from exc
        return self._principal_from_claims(claims)

    def _signing_key(self, token: str) -> Any:
        if self._static_jwks_json:
            header = jwt.get_unverified_header(token)
            kid = str(header.get("kid") or "")
            if not kid:
                raise OIDCValidationError("OIDC token is missing a key id.")
            jwk = PyJWKSet.from_json(self._static_jwks_json)[kid]
            return jwk.key
        if self._jwks_client is None:
            raise OIDCValidationError("OIDC JWKS client is not configured.")
        return self._jwks_client.get_signing_key_from_jwt(token).key

    def _principal_from_claims(self, claims: dict[str, Any]) -> UserPrincipal:
        issuer = str(claims["iss"])
        subject = str(claims["sub"])
        email = (
            claims.get("email")
            or claims.get("upn")
            or claims.get("preferred_username")
            or claims.get("unique_name")
        )
        if not email:
            raise OIDCValidationError("OIDC token is missing an email-compatible claim.")
        roles = self._roles_from_claims(claims)
        organization_id = (
            claims.get(self._settings.idp_organization_id_claim)
            or claims.get("organization_id")
            or self._settings.default_organization_id
        )
        environment_ids = _unique_string_list(claims.get(self._settings.idp_environment_ids_claim))
        return UserPrincipal(
            id=str(uuid5(NAMESPACE_URL, f"ophanix:oidc:{issuer}:{subject}")),
            email=str(email),
            display_name=str(claims.get("name") or claims.get("display_name") or str(email).split("@")[0]),
            roles=roles,
            organization_id=str(organization_id) if organization_id else None,
            environment_id=environment_ids[0] if environment_ids else None,
            environment_ids=environment_ids,
            idp_subject=subject,
            idp_issuer=issuer,
            token_id=str(claims.get("jti")) if claims.get("jti") else None,
            actor_type="user",
        )

    def _roles_from_claims(self, claims: dict[str, Any]) -> list[str]:
        roles: list[str] = []
        for role in _unique_string_list(claims.get(self._settings.idp_roles_claim)):
            if role in VALID_ROLES and role not in roles:
                roles.append(role)
        for group in _unique_string_list(claims.get(self._settings.idp_groups_claim)):
            for role in self._group_role_map.get(group, []):
                if role not in roles:
                    roles.append(role)
        return roles


class AuthService:
    """Small HMAC-signed token service for local development auth."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._local_token_auth_enabled = (
            settings.enable_dev_login
            if settings.enable_dev_login is not None
            else _is_local_environment(settings.environment)
        )
        self._oidc_validator = OIDCTokenValidator(settings)

    def login(self, request: DevLoginRequest) -> AuthResponse:
        allowed = {email.lower() for email in self._settings.dev_login_allowed_emails}
        if "*" not in allowed and request.email.lower() not in allowed:
            raise PermissionError("Email is not allowed for development login.")

        roles = request.roles or ["Platform Admin"]
        invalid_roles = sorted(set(roles) - VALID_ROLES)
        if invalid_roles:
            raise ValueError(f"Unknown role(s): {', '.join(invalid_roles)}")

        if request.environment_ids is None:
            environment_ids = (
                [self._settings.default_environment_id]
                if self._settings.default_environment_id
                else []
            )
        else:
            environment_ids = _unique_string_list(request.environment_ids)

        user = UserPrincipal(
            id=str(uuid5(NAMESPACE_URL, f"ophanix:user:{request.email.lower()}")),
            email=request.email,
            display_name=request.display_name or request.email.split("@")[0],
            roles=roles,
            organization_id=request.organization_id or self._settings.default_organization_id,
            environment_id=environment_ids[0] if environment_ids else None,
            environment_ids=environment_ids,
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
                "environment_ids": user.environment_ids,
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
        if token.count(".") == 2 and self._oidc_validator.enabled:
            try:
                return self._oidc_validator.verify(token)
            except OIDCValidationError:
                return None
        if not self._local_token_auth_enabled:
            return None
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
            environment_ids=list(payload.get("environment_ids", [])),
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
