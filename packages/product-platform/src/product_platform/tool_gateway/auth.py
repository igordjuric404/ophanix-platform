"""Gateway bearer-token verification for external agent calls."""

from __future__ import annotations

from datetime import datetime, timezone
from sqlite3 import Connection, Row

from pydantic import BaseModel, Field

from product_platform.agents.credentials import hash_credential_token
from product_platform.db.time import utc_now_iso

MAX_GATEWAY_TOKEN_LENGTH = 4096


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


class GatewayPrincipal(BaseModel):
    """Authenticated external agent principal for Tool Gateway routes."""

    organization_id: str
    environment_id: str
    agent_id: str
    credential_id: str
    scopes: list[str] = Field(default_factory=list)
    request_id: str


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

        token_hash = hash_gateway_token(raw_token)
        row = self._get_credential_by_token_hash(token_hash)
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
        if row["agent_status"] != "active":
            raise self._credential_error(row, "agent_inactive", "Agent is not active.")

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
            request_id=request_id,
        )

    def _get_credential_by_token_hash(self, token_hash: str) -> Row | None:
        return self.connection.execute(
            """
            SELECT
                c.id AS credential_id,
                c.agent_id,
                c.status AS credential_status,
                c.expires_at,
                a.organization_id,
                a.environment_id,
                a.status AS agent_status
            FROM agent_credentials c
            JOIN agents a ON a.id = c.agent_id
            WHERE c.token_hash = ?
              AND a.deleted_at IS NULL
            """,
            (token_hash,),
        ).fetchone()

    def _credential_scopes(self, credential_id: str) -> list[str]:
        rows = self.connection.execute(
            """
            SELECT scope
            FROM credential_scopes
            WHERE credential_id = ?
            ORDER BY scope ASC, id ASC
            """,
            (credential_id,),
        ).fetchall()
        return [row["scope"] for row in rows]

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
