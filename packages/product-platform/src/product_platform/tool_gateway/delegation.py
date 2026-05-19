"""Delegated user authorization persistence for Tool Gateway calls."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator

from product_platform.db.ids import generate_id
from product_platform.db.postgres import Connection, Row
from product_platform.db.time import utc_now_iso

SUPPORTED_DELEGATION_STATUSES = {"active", "disabled", "revoked", "expired"}
SUPPORTED_AUTHORIZATION_SESSION_STATUSES = {
    "pending_authorization",
    "pending_approval",
    "authorized",
    "expired",
    "revoked",
}
SUPPORTED_APPROVAL_STATES = {
    "not_required",
    "pending_authorization",
    "pending_approval",
    "approved",
    "denied",
}
SUPPORTED_OAUTH_APP_STATUSES = {"active", "disabled", "revoked"}
OAUTH_TOKEN_REF_PATTERN = re.compile(r"^(?:secref_[A-Za-z0-9]+|env:[A-Z_][A-Z0-9_]*|vault:[A-Za-z0-9_./:@-]+)$")


class OAuthProviderAppCreateRequest(BaseModel):
    """Register OAuth client metadata without storing raw client secrets."""

    model_config = ConfigDict(extra="forbid")

    provider: str = Field(min_length=1)
    client_id: str = Field(min_length=1)
    authorization_url: str = Field(min_length=1)
    token_url: str = Field(min_length=1)
    redirect_url: str = Field(min_length=1)
    scopes: list[str] = Field(default_factory=list)
    client_secret_ref: str | None = None
    status: str = "active"

    @field_validator("provider", "client_id")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank.")
        return stripped

    @field_validator("authorization_url", "token_url", "redirect_url")
    @classmethod
    def _validate_url(cls, value: str) -> str:
        stripped = value.strip()
        parsed = urlparse(stripped)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("OAuth URLs must be absolute https:// URLs.")
        return stripped

    @field_validator("scopes")
    @classmethod
    def _normalize_scopes(cls, value: list[str]) -> list[str]:
        return _normalize_scope_list(value)

    @field_validator("client_secret_ref")
    @classmethod
    def _validate_optional_secret_ref(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_token_ref(value, "client_secret_ref")

    @field_validator("status")
    @classmethod
    def _validate_status(cls, value: str) -> str:
        status = value.strip().lower()
        if status not in SUPPORTED_OAUTH_APP_STATUSES:
            supported = ", ".join(sorted(SUPPORTED_OAUTH_APP_STATUSES))
            raise ValueError(f"status must be one of: {supported}.")
        return status


class OAuthProviderAppResponse(BaseModel):
    """OAuth client metadata safe for product API responses."""

    id: str
    organization_id: str
    environment_id: str
    provider: str
    client_id: str
    authorization_url: str
    token_url: str
    redirect_url: str
    scopes: list[str] = Field(default_factory=list)
    client_secret_ref_redacted: bool = True
    status: str
    created_by: str
    created_at: str
    updated_at: str


class OAuthAuthorizationSessionStartRequest(BaseModel):
    """Start an OAuth authorization session for a delegated tool call."""

    model_config = ConfigDict(extra="forbid")

    oauth_app_id: str | None = None
    agent_id: str = Field(min_length=1)
    credential_id: str = Field(min_length=1)
    tool_id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    required_scopes: list[str] = Field(min_length=1)
    user_id: str | None = None
    provider_account_id: str | None = None
    expires_at: str | None = None

    @field_validator("oauth_app_id", "user_id", "provider_account_id", "expires_at")
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("agent_id", "credential_id", "tool_id", "provider")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank.")
        return stripped

    @field_validator("required_scopes")
    @classmethod
    def _normalize_required_scopes(cls, value: list[str]) -> list[str]:
        scopes = _normalize_scope_list(value)
        if not scopes:
            raise ValueError("required_scopes must include at least one scope.")
        return scopes


class OAuthAuthorizationSessionCompleteRequest(BaseModel):
    """Complete an OAuth session using token references created by a vault provider."""

    model_config = ConfigDict(extra="forbid")

    user_id: str = Field(min_length=1)
    provider_account_id: str = Field(min_length=1)
    scopes: list[str] = Field(min_length=1)
    access_token: str | None = Field(default=None, repr=False)
    refresh_token: str | None = Field(default=None, repr=False)
    access_token_ref: str = Field(min_length=1)
    refresh_token_ref: str | None = None
    expires_at: str = Field(min_length=1)
    approval_state: str = "approved"

    @field_validator("user_id", "provider_account_id", "expires_at")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank.")
        return stripped

    @field_validator("scopes")
    @classmethod
    def _normalize_scopes(cls, value: list[str]) -> list[str]:
        scopes = _normalize_scope_list(value)
        if not scopes:
            raise ValueError("scopes must include at least one scope.")
        return scopes

    @field_validator("access_token_ref", "refresh_token_ref")
    @classmethod
    def _validate_token_ref(cls, value: str | None, info: Any) -> str | None:
        if value is None:
            return None
        return _validate_token_ref(value, str(info.field_name))

    @field_validator("approval_state")
    @classmethod
    def _validate_approval_state(cls, value: str) -> str:
        approval_state = value.strip().lower()
        if approval_state not in SUPPORTED_APPROVAL_STATES:
            supported = ", ".join(sorted(SUPPORTED_APPROVAL_STATES))
            raise ValueError(f"approval_state must be one of: {supported}.")
        return approval_state


class OAuthDelegatedAuthorizationRefreshRequest(BaseModel):
    """Refresh a delegated authorization with a new access-token reference."""

    model_config = ConfigDict(extra="forbid")

    access_token_ref: str = Field(min_length=1)
    access_token: str | None = Field(default=None, repr=False)
    refresh_token: str | None = Field(default=None, repr=False)
    refresh_token_ref: str | None = None
    expires_at: str = Field(min_length=1)

    @field_validator("access_token_ref", "refresh_token_ref")
    @classmethod
    def _validate_token_ref(cls, value: str | None, info: Any) -> str | None:
        if value is None:
            return None
        return _validate_token_ref(value, str(info.field_name))

    @field_validator("expires_at")
    @classmethod
    def _strip_expires_at(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank.")
        return stripped


class OAuthDelegatedAuthorizationRevokeRequest(BaseModel):
    """Revoke a delegated OAuth authorization."""

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1)

    @field_validator("reason")
    @classmethod
    def _strip_reason(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank.")
        return stripped


class DelegatedAuthorizationResponse(BaseModel):
    """Delegated authorization metadata with token refs redacted."""

    id: str
    organization_id: str
    environment_id: str
    agent_id: str
    tool_id: str
    user_id: str
    provider_account_id: str
    provider: str
    scopes: list[str] = Field(default_factory=list)
    status: str
    approval_state: str
    expires_at: str
    access_token_ref_redacted: bool = True
    refresh_token_ref_redacted: bool = True
    token_expires_at: str | None = None
    last_refreshed_at: str | None = None
    revoked_at: str | None = None
    revoked_reason: str | None = None
    created_at: str
    updated_at: str


class ToolDelegationRequirementCreate(BaseModel):
    """Create a tool-level requirement for per-user delegated authorization."""

    tool_id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    required_scopes: list[str] = Field(min_length=1)
    approval_required: bool = True
    status: str = "active"

    @field_validator("tool_id", "provider")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank.")
        return stripped

    @field_validator("required_scopes")
    @classmethod
    def _normalize_scopes(cls, value: list[str]) -> list[str]:
        scopes = _normalize_scope_list(value)
        if not scopes:
            raise ValueError("required_scopes must include at least one scope.")
        return scopes

    @field_validator("status")
    @classmethod
    def _validate_status(cls, value: str) -> str:
        status = value.strip().lower()
        if status not in SUPPORTED_DELEGATION_STATUSES:
            supported = ", ".join(sorted(SUPPORTED_DELEGATION_STATUSES))
            raise ValueError(f"status must be one of: {supported}.")
        return status


class DelegatedAuthorizationCreate(BaseModel):
    """Persist user/provider authorization evidence for one agent-tool pair."""

    agent_id: str = Field(min_length=1)
    tool_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    provider_account_id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    scopes: list[str] = Field(min_length=1)
    status: str = "active"
    approval_state: str = "approved"
    expires_at: str = Field(min_length=1)
    access_token_ref: str | None = None
    refresh_token_ref: str | None = None

    @field_validator("agent_id", "tool_id", "user_id", "provider_account_id", "provider", "expires_at")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank.")
        return stripped

    @field_validator("scopes")
    @classmethod
    def _normalize_scopes(cls, value: list[str]) -> list[str]:
        scopes = _normalize_scope_list(value)
        if not scopes:
            raise ValueError("scopes must include at least one scope.")
        return scopes

    @field_validator("status")
    @classmethod
    def _validate_status(cls, value: str) -> str:
        status = value.strip().lower()
        if status not in SUPPORTED_DELEGATION_STATUSES:
            supported = ", ".join(sorted(SUPPORTED_DELEGATION_STATUSES))
            raise ValueError(f"status must be one of: {supported}.")
        return status

    @field_validator("approval_state")
    @classmethod
    def _validate_approval_state(cls, value: str) -> str:
        approval_state = value.strip().lower()
        if approval_state not in SUPPORTED_APPROVAL_STATES:
            supported = ", ".join(sorted(SUPPORTED_APPROVAL_STATES))
            raise ValueError(f"approval_state must be one of: {supported}.")
        return approval_state

    @field_validator("access_token_ref", "refresh_token_ref")
    @classmethod
    def _validate_token_ref(cls, value: str | None, info: Any) -> str | None:
        if value is None:
            return None
        return _validate_token_ref(value, str(info.field_name))


class AuthorizationChallengeResponse(BaseModel):
    """Agent-facing authorization challenge returned by the gateway."""

    authorization_session_id: str
    authorization_url: str
    provider: str
    required_scopes: list[str]
    approval_state: str
    status: str
    expires_at: str | None = None


class AuthorizationStatusResponse(AuthorizationChallengeResponse):
    """Status returned when SDKs poll an authorization session."""


class ToolDelegationRepository:
    """Tenant-scoped store for tool delegation requirements and grants."""

    def __init__(self, connection: Connection, organization_id: str, environment_id: str) -> None:
        self.connection = connection
        self.organization_id = organization_id
        self.environment_id = environment_id

    def create_oauth_provider_app(
        self,
        body: OAuthProviderAppCreateRequest,
        *,
        created_by: str,
    ) -> Row:
        """Register OAuth provider application metadata in tenant scope."""

        app_id = generate_id("oauthapp")
        now = utc_now_iso()
        self.connection.execute(
            """
            INSERT INTO tool_oauth_provider_apps (
                id, organization_id, environment_id, provider, client_id,
                authorization_url, token_url, redirect_url, scopes_json,
                client_secret_ref, status, created_by, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                app_id,
                self.organization_id,
                self.environment_id,
                body.provider,
                body.client_id,
                body.authorization_url,
                body.token_url,
                body.redirect_url,
                _scope_json(body.scopes),
                body.client_secret_ref,
                body.status,
                created_by,
                now,
                now,
            ),
        )
        row = self.get_oauth_provider_app(app_id)
        if row is None:
            raise ValueError("Created OAuth provider app could not be loaded.")
        return row

    def get_oauth_provider_app(self, oauth_app_id: str) -> Row | None:
        """Fetch one OAuth provider app by id."""

        return self.connection.execute(
            """
            SELECT *
            FROM tool_oauth_provider_apps
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            (oauth_app_id, self.organization_id, self.environment_id),
        ).fetchone()

    def list_oauth_provider_apps(self, *, provider: str | None = None) -> list[Row]:
        """List OAuth provider app metadata."""

        clauses = ["organization_id = ?", "environment_id = ?"]
        values: list[object] = [self.organization_id, self.environment_id]
        if provider:
            clauses.append("provider = ?")
            values.append(provider)
        return self.connection.execute(
            f"""
            SELECT *
            FROM tool_oauth_provider_apps
            WHERE {' AND '.join(clauses)}
            ORDER BY updated_at DESC, id DESC
            """,
            values,
        ).fetchall()

    def create_requirement(self, body: ToolDelegationRequirementCreate) -> Row:
        """Create or replace the active delegated-authorization requirement for a tool."""

        requirement_id = generate_id("tooldelegreq")
        now = utc_now_iso()
        self.connection.execute(
            """
            INSERT INTO tool_delegation_requirements (
                id, organization_id, environment_id, tool_id, provider,
                required_scopes_json, approval_required, status, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                requirement_id,
                self.organization_id,
                self.environment_id,
                body.tool_id,
                body.provider,
                _scope_json(body.required_scopes),
                1 if body.approval_required else 0,
                body.status,
                now,
                now,
            ),
        )
        row = self.get_requirement(requirement_id)
        if row is None:
            raise ValueError("Created tool delegation requirement could not be loaded.")
        return row

    def get_requirement(self, requirement_id: str) -> Row | None:
        """Fetch one delegation requirement by id in tenant scope."""

        return self.connection.execute(
            """
            SELECT *
            FROM tool_delegation_requirements
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            (requirement_id, self.organization_id, self.environment_id),
        ).fetchone()

    def get_active_requirement(self, tool_id: str) -> Row | None:
        """Fetch the active delegated authorization requirement for a tool, if any."""

        return self.connection.execute(
            """
            SELECT *
            FROM tool_delegation_requirements
            WHERE organization_id = ?
              AND environment_id = ?
              AND tool_id = ?
              AND status = 'active'
            ORDER BY updated_at DESC, id DESC
            LIMIT 1
            """,
            (self.organization_id, self.environment_id, tool_id),
        ).fetchone()

    def create_authorization(self, body: DelegatedAuthorizationCreate) -> Row:
        """Persist a delegated user/provider authorization grant."""

        authorization_id = generate_id("tooldelega")
        now = utc_now_iso()
        self.connection.execute(
            """
            INSERT INTO tool_delegated_authorizations (
                id, organization_id, environment_id, agent_id, tool_id,
                user_id, provider_account_id, provider, scopes_json, status,
                approval_state, expires_at, access_token_ref, refresh_token_ref,
                token_expires_at, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                authorization_id,
                self.organization_id,
                self.environment_id,
                body.agent_id,
                body.tool_id,
                body.user_id,
                body.provider_account_id,
                body.provider,
                _scope_json(body.scopes),
                body.status,
                body.approval_state,
                body.expires_at,
                body.access_token_ref,
                body.refresh_token_ref,
                body.expires_at,
                now,
                now,
            ),
        )
        row = self.get_authorization(authorization_id)
        if row is None:
            raise ValueError("Created delegated authorization could not be loaded.")
        return row

    def get_authorization(self, authorization_id: str) -> Row | None:
        """Fetch one delegated authorization by id in tenant scope."""

        return self.connection.execute(
            """
            SELECT *
            FROM tool_delegated_authorizations
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            (authorization_id, self.organization_id, self.environment_id),
        ).fetchone()

    def find_authorization(
        self,
        *,
        agent_id: str,
        tool_id: str,
        user_id: str,
        provider_account_id: str,
        provider: str,
    ) -> Row | None:
        """Find the newest delegated authorization matching this user/provider binding."""

        return self.connection.execute(
            """
            SELECT *
            FROM tool_delegated_authorizations
            WHERE organization_id = ?
              AND environment_id = ?
              AND agent_id = ?
              AND tool_id = ?
              AND user_id = ?
              AND provider_account_id = ?
              AND provider = ?
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (
                self.organization_id,
                self.environment_id,
                agent_id,
                tool_id,
                user_id,
                provider_account_id,
                provider,
            ),
        ).fetchone()

    def create_authorization_session(
        self,
        *,
        agent_id: str,
        credential_id: str,
        tool_id: str,
        provider: str,
        required_scopes: list[str],
        reason_code: str,
        approval_state: str,
        user_id: str | None = None,
        provider_account_id: str | None = None,
        oauth_app_id: str | None = None,
        status: str = "pending_authorization",
        expires_at: str | None = None,
    ) -> Row:
        """Create an authorization session for agent SDK polling and user consent."""

        session_id = generate_id("oauthsess")
        authorization_url = f"https://auth.ophanix.local/gateway/authorizations/{session_id}"
        now = utc_now_iso()
        self.connection.execute(
            """
            INSERT INTO tool_oauth_authorization_sessions (
                id, organization_id, environment_id, agent_id, credential_id, tool_id,
                user_id, provider_account_id, provider, required_scopes_json, oauth_app_id,
                status, approval_state, authorization_url, reason_code,
                expires_at, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                self.organization_id,
                self.environment_id,
                agent_id,
                credential_id,
                tool_id,
                user_id,
                provider_account_id,
                provider,
                _scope_json(required_scopes),
                oauth_app_id,
                status,
                approval_state,
                authorization_url,
                reason_code,
                expires_at,
                now,
                now,
            ),
        )
        row = self.get_authorization_session(session_id)
        if row is None:
            raise ValueError("Created authorization session could not be loaded.")
        return row

    def start_authorization_session(self, body: OAuthAuthorizationSessionStartRequest) -> Row:
        """Create a product-started OAuth authorization session."""

        if body.oauth_app_id is not None and self.get_oauth_provider_app(body.oauth_app_id) is None:
            raise ValueError("OAuth provider app not found.")
        return self.create_authorization_session(
            agent_id=body.agent_id,
            credential_id=body.credential_id,
            tool_id=body.tool_id,
            provider=body.provider,
            required_scopes=body.required_scopes,
            reason_code="authorization_required",
            approval_state="pending_authorization",
            user_id=body.user_id,
            provider_account_id=body.provider_account_id,
            oauth_app_id=body.oauth_app_id,
            status="pending_authorization",
            expires_at=body.expires_at,
        )

    def complete_authorization_session(
        self,
        authorization_session_id: str,
        body: OAuthAuthorizationSessionCompleteRequest,
    ) -> Row:
        """Complete an OAuth session and persist token references only."""

        session = self.get_authorization_session(authorization_session_id)
        if session is None:
            raise ValueError("Authorization session not found.")
        if session["status"] in {"revoked", "authorized"}:
            raise ValueError("Authorization session is not pending.")
        authorization = self.create_authorization(
            DelegatedAuthorizationCreate(
                agent_id=str(session["agent_id"]),
                tool_id=str(session["tool_id"]),
                user_id=body.user_id,
                provider_account_id=body.provider_account_id,
                provider=str(session["provider"]),
                scopes=body.scopes,
                status="active",
                approval_state=body.approval_state,
                expires_at=body.expires_at,
                access_token_ref=body.access_token_ref,
                refresh_token_ref=body.refresh_token_ref,
            )
        )
        now = utc_now_iso()
        self.connection.execute(
            """
            UPDATE tool_oauth_authorization_sessions
            SET status = 'authorized',
                approval_state = ?,
                user_id = ?,
                provider_account_id = ?,
                delegated_authorization_id = ?,
                completed_at = ?,
                updated_at = ?
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            (
                body.approval_state,
                body.user_id,
                body.provider_account_id,
                authorization["id"],
                now,
                now,
                authorization_session_id,
                self.organization_id,
                self.environment_id,
            ),
        )
        return authorization

    def refresh_authorization(
        self,
        authorization_id: str,
        body: OAuthDelegatedAuthorizationRefreshRequest,
    ) -> Row:
        """Persist a refreshed access-token reference and new expiry."""

        row = self.get_authorization(authorization_id)
        if row is None:
            raise ValueError("Delegated authorization not found.")
        if row["status"] == "revoked":
            raise ValueError("Revoked delegated authorization cannot be refreshed.")
        refresh_token_ref = body.refresh_token_ref or row["refresh_token_ref"]
        if not refresh_token_ref:
            raise ValueError("refresh_token_ref is required to refresh delegated authorization.")
        now = utc_now_iso()
        self.connection.execute(
            """
            UPDATE tool_delegated_authorizations
            SET access_token_ref = ?,
                refresh_token_ref = ?,
                token_expires_at = ?,
                expires_at = ?,
                status = 'active',
                last_refreshed_at = ?,
                updated_at = ?
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            (
                body.access_token_ref,
                refresh_token_ref,
                body.expires_at,
                body.expires_at,
                now,
                now,
                authorization_id,
                self.organization_id,
                self.environment_id,
            ),
        )
        refreshed = self.get_authorization(authorization_id)
        if refreshed is None:
            raise ValueError("Refreshed delegated authorization could not be loaded.")
        return refreshed

    def revoke_authorization(
        self,
        authorization_id: str,
        body: OAuthDelegatedAuthorizationRevokeRequest,
    ) -> Row:
        """Revoke a delegated authorization."""

        row = self.get_authorization(authorization_id)
        if row is None:
            raise ValueError("Delegated authorization not found.")
        now = utc_now_iso()
        self.connection.execute(
            """
            UPDATE tool_delegated_authorizations
            SET status = 'revoked',
                revoked_at = ?,
                revoked_reason = ?,
                updated_at = ?
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            (
                now,
                body.reason,
                now,
                authorization_id,
                self.organization_id,
                self.environment_id,
            ),
        )
        revoked = self.get_authorization(authorization_id)
        if revoked is None:
            raise ValueError("Revoked delegated authorization could not be loaded.")
        return revoked

    def get_authorization_session(
        self,
        authorization_session_id: str,
        *,
        agent_id: str | None = None,
        credential_id: str | None = None,
    ) -> Row | None:
        """Fetch an authorization session, optionally bound to an agent credential."""

        clauses = [
            "id = ?",
            "organization_id = ?",
            "environment_id = ?",
        ]
        values: list[object] = [
            authorization_session_id,
            self.organization_id,
            self.environment_id,
        ]
        if agent_id is not None:
            clauses.append("agent_id = ?")
            values.append(agent_id)
        if credential_id is not None:
            clauses.append("credential_id = ?")
            values.append(credential_id)
        return self.connection.execute(
            f"""
            SELECT *
            FROM tool_oauth_authorization_sessions
            WHERE {' AND '.join(clauses)}
            """,
            values,
        ).fetchone()


def requirement_scopes(row: Row) -> list[str]:
    """Return normalized required scopes from a requirement row."""

    return _loads_scope_json(row["required_scopes_json"])


def authorization_scopes(row: Row) -> list[str]:
    """Return normalized scopes from an authorization row."""

    return _loads_scope_json(row["scopes_json"])


def authorization_session_response(row: Row) -> AuthorizationStatusResponse:
    """Serialize an authorization session row for API/SDK callers."""

    return AuthorizationStatusResponse(
        authorization_session_id=row["id"],
        authorization_url=row["authorization_url"],
        provider=row["provider"],
        required_scopes=_loads_scope_json(row["required_scopes_json"]),
        approval_state=row["approval_state"],
        status=row["status"],
        expires_at=row["expires_at"],
    )


def oauth_provider_app_response(row: Row) -> OAuthProviderAppResponse:
    """Serialize OAuth provider app metadata without secret references."""

    return OAuthProviderAppResponse(
        id=row["id"],
        organization_id=row["organization_id"],
        environment_id=row["environment_id"],
        provider=row["provider"],
        client_id=row["client_id"],
        authorization_url=row["authorization_url"],
        token_url=row["token_url"],
        redirect_url=row["redirect_url"],
        scopes=_loads_scope_json(row["scopes_json"]),
        client_secret_ref_redacted=row["client_secret_ref"] is not None,
        status=row["status"],
        created_by=row["created_by"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def delegated_authorization_response(row: Row) -> DelegatedAuthorizationResponse:
    """Serialize delegated authorization metadata without token references."""

    return DelegatedAuthorizationResponse(
        id=row["id"],
        organization_id=row["organization_id"],
        environment_id=row["environment_id"],
        agent_id=row["agent_id"],
        tool_id=row["tool_id"],
        user_id=row["user_id"],
        provider_account_id=row["provider_account_id"],
        provider=row["provider"],
        scopes=authorization_scopes(row),
        status=row["status"],
        approval_state=row["approval_state"],
        expires_at=row["expires_at"],
        access_token_ref_redacted=row["access_token_ref"] is not None,
        refresh_token_ref_redacted=row["refresh_token_ref"] is not None,
        token_expires_at=row["token_expires_at"],
        last_refreshed_at=row["last_refreshed_at"],
        revoked_at=row["revoked_at"],
        revoked_reason=row["revoked_reason"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def authorization_is_current(row: Row, *, now: str | datetime | None = None) -> bool:
    """Return whether a delegated authorization has not expired."""

    return _coerce_utc(row["expires_at"]) > _coerce_utc(now)


def authorization_has_required_scopes(row: Row, required_scopes: list[str]) -> bool:
    """Return whether an authorization covers every required provider scope."""

    granted = set(authorization_scopes(row))
    return set(required_scopes).issubset(granted)


def _scope_json(scopes: list[str]) -> str:
    return json.dumps(_normalize_scope_list(scopes), sort_keys=True, separators=(",", ":"))


def _loads_scope_json(value: Any) -> list[str]:
    if not isinstance(value, str) or not value:
        return []
    try:
        loaded = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(loaded, list):
        return []
    return _normalize_scope_list([str(item) for item in loaded])


def _normalize_scope_list(scopes: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for scope in scopes:
        if not isinstance(scope, str):
            continue
        stripped = scope.strip()
        if not stripped or stripped in seen:
            continue
        seen.add(stripped)
        normalized.append(stripped)
    return normalized


def _validate_token_ref(value: str, field_name: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field_name} must not be blank.")
    lowered = stripped.lower()
    if lowered.startswith(("bearer ", "ya29.", "sk-", "tok-", "access_token:")):
        raise ValueError(f"{field_name} must be a vault/env secret reference, not raw token material.")
    if not OAUTH_TOKEN_REF_PATTERN.fullmatch(stripped):
        raise ValueError(f"{field_name} must be a supported secret reference.")
    return stripped


def _coerce_utc(value: str | datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        parsed = value
    else:
        normalized = value.strip()
        if normalized.endswith("Z"):
            normalized = f"{normalized[:-1]}+00:00"
        parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
