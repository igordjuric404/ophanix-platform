"""Gateway bearer-token verification for external agent calls."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from product_platform.db.postgres import Connection, Row

from pydantic import BaseModel, Field

from product_platform.agents.credentials import credential_token_hash_candidates, hash_credential_token
from product_platform.agents.lifecycle import (
    agent_non_operational_message,
    agent_non_operational_reason_code,
    is_agent_operational,
)
from product_platform.db.time import utc_now_iso

MAX_GATEWAY_TOKEN_LENGTH = 4096
BEARER_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9._~+/=-]+$")


class GatewayAuthenticationError(ValueError):
    """Raised when gateway token verification fails."""

    def __init__(
        self,
        reason_code: str,
        message: str,
        *,
        organization_id: str | None = None,
        environment_id: str | None = None,
        agent_id: str | None = None,
        credential_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.reason_code = reason_code
        self.organization_id = organization_id
        self.environment_id = environment_id
        self.agent_id = agent_id
        self.credential_id = credential_id


class GatewayCredentialScope(BaseModel):
    """Structured scope grant attached to one gateway credential."""

    scope: str
    resource_type: str
    resource_id: str | None = None


class GatewayPrincipal(BaseModel):
    """Authenticated external agent principal for Tool Gateway routes."""

    organization_id: str
    environment_id: str
    agent_id: str
    credential_id: str
    scopes: list[str] = Field(default_factory=list)
    scope_grants: list[GatewayCredentialScope] = Field(default_factory=list)
    request_id: str

    def allows_tool_scope(self, required_scope: str, *, tool_id: str, tool_name: str) -> bool:
        """Return whether this credential grants a scope for the specific tool resource."""

        normalized_scope = required_scope.strip()
        if not normalized_scope:
            return False
        tool_resource_ids = {tool_id.strip(), tool_name.strip().lower()}
        for grant in self.scope_grants:
            if grant.scope != normalized_scope or grant.resource_type != "tool":
                continue
            if grant.resource_id is None:
                return True
            resource_id = grant.resource_id.strip()
            if resource_id == tool_id or resource_id.lower() in tool_resource_ids:
                return True
        return False


def parse_bearer_authorization(authorization: str | None) -> str:
    """Parse `Authorization: Bearer <token>` without exposing token material."""

    if authorization is None or not authorization.strip():
        raise GatewayAuthenticationError(
            "missing_authorization",
            "Authorization bearer token is required.",
        )
    scheme, separator, token = authorization.partition(" ")
    if scheme.strip().lower() != "bearer":
        raise GatewayAuthenticationError(
            "invalid_authorization_scheme",
            "Authorization scheme must be Bearer.",
        )
    if not separator or not token.strip():
        raise GatewayAuthenticationError(
            "empty_bearer_token",
            "Bearer token must not be empty.",
        )
    stripped = token.strip()
    if stripped != token or any(character.isspace() for character in stripped):
        raise GatewayAuthenticationError(
            "invalid_bearer_token",
            "Bearer token contains unsupported whitespace.",
        )
    if not BEARER_TOKEN_PATTERN.fullmatch(stripped):
        raise GatewayAuthenticationError(
            "invalid_bearer_token",
            "Bearer token contains unsupported characters.",
        )
    if len(stripped) > MAX_GATEWAY_TOKEN_LENGTH:
        raise GatewayAuthenticationError(
            "token_too_large",
            "Bearer token is too large.",
        )
    return stripped


def hash_gateway_token(token: str) -> str:
    """Hash a presented gateway token for lookup."""

    return hash_credential_token(token)


class GatewayTokenVerifier:
    """Verify presented gateway bearer tokens against agent credential metadata."""

    def __init__(self, connection: Connection) -> None:
        self.connection = connection

    def verify_authorization_header(
        self,
        authorization: str | None,
        *,
        request_id: str,
        now: datetime | str | None = None,
    ) -> GatewayPrincipal:
        """Verify an Authorization header and return a gateway principal."""

        token = parse_bearer_authorization(authorization)
        return self.verify_token(token, request_id=request_id, now=now)

    def verify_token(
        self,
        raw_token: str,
        *,
        request_id: str,
        now: datetime | str | None = None,
    ) -> GatewayPrincipal:
        """Verify a raw token without logging or storing it."""

        row = self._get_credential_by_token_hashes(credential_token_hash_candidates(raw_token))
        if row is None:
            raise GatewayAuthenticationError(
                "credential_not_found",
                "Gateway credential was not found.",
            )
        if row["credential_status"] != "active":
            raise self._credential_error(row, "credential_inactive", "Gateway credential is not active.")
        current_time = _coerce_utc_datetime(now)
        expires_at = _coerce_utc_datetime(row["expires_at"])
        if expires_at <= current_time:
            self.connection.execute(
                "UPDATE agent_credentials SET status = ? WHERE id = ?",
                ("expired", row["credential_id"]),
            )
            raise self._credential_error(row, "credential_expired", "Gateway credential is expired.")
        if not is_agent_operational(row["agent_status"]):
            raise self._credential_error(
                row,
                agent_non_operational_reason_code(row["agent_status"]),
                agent_non_operational_message(row["agent_status"]),
            )
        if row["identity_status"] is not None and row["identity_status"] != "active":
            raise self._credential_error(
                row,
                "agent_identity_inactive",
                f"Agent identity is {row['identity_status']}.",
            )

        verified_at = utc_now_iso()
        self.connection.execute(
            """
            UPDATE agent_credentials
            SET last_used_at = ?
            WHERE id = ?
            """,
            (verified_at, row["credential_id"]),
        )
        return GatewayPrincipal(
            organization_id=row["organization_id"],
            environment_id=row["environment_id"],
            agent_id=row["agent_id"],
            credential_id=row["credential_id"],
            scopes=self._credential_scopes(row["credential_id"]),
            scope_grants=self._credential_scope_grants(row["credential_id"]),
            request_id=request_id,
        )

    def _get_credential_by_token_hashes(self, token_hashes: list[str]) -> Row | None:
        placeholders = ", ".join("?" for _ in token_hashes)
        return self.connection.execute(
            f"""
            SELECT
                c.id AS credential_id,
                c.agent_id,
                c.status AS credential_status,
                c.expires_at,
                a.organization_id,
                a.environment_id,
                a.status AS agent_status,
                i.identity_status
            FROM agent_credentials c
            JOIN agents a ON a.id = c.agent_id
            LEFT JOIN agent_identities i ON i.agent_id = a.id
            WHERE c.token_hash IN ({placeholders})
              AND a.deleted_at IS NULL
            """,
            tuple(token_hashes),
        ).fetchone()

    def _credential_scopes(self, credential_id: str) -> list[str]:
        rows = self.connection.execute(
            """
            SELECT DISTINCT scope
            FROM credential_scopes
            WHERE credential_id = ?
            ORDER BY scope ASC
            """,
            (credential_id,),
        ).fetchall()
        return [row["scope"] for row in rows]

    def _credential_scope_grants(self, credential_id: str) -> list[GatewayCredentialScope]:
        rows = self.connection.execute(
            """
            SELECT scope, resource_type, resource_id
            FROM credential_scopes
            WHERE credential_id = ?
            ORDER BY scope ASC, resource_type ASC, resource_id ASC, id ASC
            """,
            (credential_id,),
        ).fetchall()
        return [
            GatewayCredentialScope(
                scope=row["scope"],
                resource_type=row["resource_type"],
                resource_id=row["resource_id"],
            )
            for row in rows
        ]

    def _credential_error(self, row: Row, reason_code: str, message: str) -> GatewayAuthenticationError:
        return GatewayAuthenticationError(
            reason_code,
            message,
            organization_id=row["organization_id"],
            environment_id=row["environment_id"],
            agent_id=row["agent_id"],
            credential_id=row["credential_id"],
        )


def _coerce_utc_datetime(value: datetime | str | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)
