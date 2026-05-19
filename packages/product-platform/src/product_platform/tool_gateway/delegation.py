"""Delegated user authorization persistence for Tool Gateway calls."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, field_validator

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
                approval_state, expires_at, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                user_id, provider_account_id, provider, required_scopes_json,
                status, approval_state, authorization_url, reason_code,
                expires_at, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
