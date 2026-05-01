"""Credential metadata persistence for registered agents."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from sqlite3 import Connection, Row
from typing import Any

from agentmesh.identity.credentials import CredentialManager

from product_platform.audit.events import AuditEventEnvelope
from product_platform.agents.models import (
    AgentCredentialResponse,
    CredentialScopeRequest,
    CredentialScopeResponse,
)
from product_platform.agents.repository import AgentNotFoundError
from product_platform.db.ids import generate_id
from product_platform.db.time import utc_now_iso


def hash_credential_token(token: str) -> str:
    """Return the stable SHA-256 token hash stored by the product database."""

    return hashlib.sha256(token.encode()).hexdigest()


def credential_expires_within_threshold(
    expires_at: str,
    *,
    now: datetime | str | None = None,
    threshold_hours: int,
) -> bool:
    """Return whether a credential expires between now and the threshold cutoff."""

    current_time = _coerce_utc_datetime(now)
    expiry_time = _coerce_utc_datetime(expires_at)
    return current_time <= expiry_time <= current_time + timedelta(hours=threshold_hours)


@dataclass(frozen=True)
class IssuedAgentCredential:
    """One-time issued credential material returned by the AgentMesh adapter."""

    agentmesh_credential_id: str
    token: str
    token_hash: str
    bearer_token: str
    issued_at: str
    expires_at: str
    ttl_seconds: int
    status: str


@dataclass(frozen=True)
class CredentialExpiryMonitorResult:
    """Result from one expiry monitor pass."""

    processed_count: int
    credential_ids: list[str]


class AgentCredentialIssuer:
    """Adapter around AgentMesh credential issuance."""

    def __init__(
        self,
        *,
        default_ttl_seconds: int = CredentialManager.DEFAULT_TTL,
        manager: CredentialManager | None = None,
    ) -> None:
        self.manager = manager or CredentialManager(default_ttl=default_ttl_seconds)

    def issue(
        self,
        *,
        agent_did: str,
        scopes: list[CredentialScopeRequest],
        ttl_seconds: int | None = None,
        issued_for: str | None = None,
    ) -> IssuedAgentCredential:
        """Issue a short-lived AgentMesh credential for the requested scopes."""

        credential = self.manager.issue(
            agent_did=agent_did,
            capabilities=[scope.scope for scope in scopes],
            resources=[scope.resource_id for scope in scopes if scope.resource_id],
            ttl_seconds=ttl_seconds,
            issued_for=issued_for,
        )
        return IssuedAgentCredential(
            agentmesh_credential_id=credential.credential_id,
            token=credential.token,
            token_hash=credential.token_hash,
            bearer_token=credential.to_bearer_token(),
            issued_at=_datetime_to_utc_iso(credential.issued_at),
            expires_at=_datetime_to_utc_iso(credential.expires_at),
            ttl_seconds=credential.ttl_seconds,
            status=credential.status,
        )


class CredentialExpiryMonitor:
    """Marks active credentials that are approaching expiry."""

    def __init__(
        self,
        repository: "AgentCredentialRepository",
        audit_repository: Any | None = None,
    ) -> None:
        self.repository = repository
        self.audit_repository = audit_repository

    def run(
        self,
        *,
        threshold_hours: int,
        actor_id: str,
        now: datetime | str | None = None,
        auto_rotate: bool = False,
    ) -> CredentialExpiryMonitorResult:
        """Mark active credentials expiring within the threshold as `expiring_soon`."""

        detected_at = _coerce_utc_datetime(now)
        processed_ids: list[str] = []
        for row in self.repository.list_expiring(
            threshold_hours=threshold_hours,
            now=detected_at,
        ):
            if row["status"] != "active":
                continue
            updated = self.repository.mark_expiring_soon(
                row["id"],
                threshold_hours=threshold_hours,
                detected_at=detected_at,
                auto_rotate=auto_rotate,
            )
            processed_ids.append(updated["id"])
            if self.audit_repository is not None:
                self.audit_repository.insert(
                    AuditEventEnvelope(
                        organization_id=self.repository.organization_id,
                        environment_id=self.repository.environment_id,
                        event_type="agent.credential.expiring_soon",
                        source_component="agent-registry",
                        actor_type="system",
                        actor_id=actor_id,
                        agent_id=updated["agent_id"],
                        resource_type="agent_credential",
                        resource_id=updated["id"],
                        payload_json={
                            "credential_id": updated["id"],
                            "expires_at": updated["expires_at"],
                            "threshold_hours": threshold_hours,
                            "auto_rotation_policy": {
                                "enabled": auto_rotate,
                                "mode": "placeholder",
                            },
                        },
                    )
                )
        return CredentialExpiryMonitorResult(
            processed_count=len(processed_ids),
            credential_ids=processed_ids,
        )


class AgentCredentialRepository:
    """Tenant-scoped credential metadata repository."""

    def __init__(self, connection: Connection, organization_id: str, environment_id: str) -> None:
        self.connection = connection
        self.organization_id = organization_id
        self.environment_id = environment_id

    def create_metadata(
        self,
        *,
        agent_id: str,
        credential_type: str,
        raw_token: str,
        issuer: str,
        expires_at: str,
        scopes: list[CredentialScopeRequest],
        metadata_json: dict[str, Any] | None = None,
        status: str = "active",
        issued_at: str | None = None,
    ) -> Row:
        """Persist credential metadata and scopes without storing the raw token."""

        if not self.agent_exists(agent_id):
            raise AgentNotFoundError("Agent not found.")
        metadata = metadata_json or {}
        self._ensure_secret_absent(raw_token, metadata)
        now = utc_now_iso()
        credential_id = generate_id("cred")
        self.connection.execute(
            """
            INSERT INTO agent_credentials (
                id, agent_id, credential_type, token_hash, issuer, status,
                issued_at, expires_at, revoked_at, last_used_at, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                credential_id,
                agent_id,
                credential_type,
                hash_credential_token(raw_token),
                issuer,
                status,
                issued_at or now,
                expires_at,
                now if status == "revoked" else None,
                None,
                json.dumps(metadata, sort_keys=True),
            ),
        )
        seen_scopes: set[tuple[str, str, str | None]] = set()
        for scope in scopes:
            key = (scope.scope, scope.resource_type, scope.resource_id)
            if key in seen_scopes:
                continue
            seen_scopes.add(key)
            self.connection.execute(
                """
                INSERT INTO credential_scopes (
                    id, credential_id, scope, resource_type, resource_id
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    generate_id("scope"),
                    credential_id,
                    scope.scope,
                    scope.resource_type,
                    scope.resource_id,
                ),
            )
        if status == "active":
            self.connection.execute(
                """
                UPDATE agents
                SET credential_status = ?, credential_expires_at = ?, updated_at = ?
                WHERE id = ? AND organization_id = ? AND environment_id = ? AND deleted_at IS NULL
                """,
                (
                    "active",
                    expires_at,
                    now,
                    agent_id,
                    self.organization_id,
                    self.environment_id,
                ),
            )
        row = self.get(credential_id)
        if row is None:
            raise ValueError("Created credential metadata could not be loaded.")
        return row

    def revoke(
        self,
        credential_id: str,
        *,
        reason: str,
        actor_id: str,
        publication_type: str,
    ) -> Row:
        """Revoke an active credential and record revocation metadata."""

        row = self.get(credential_id)
        if row is None:
            raise CredentialNotFoundError("Credential not found.")
        if row["status"] != "active":
            raise ValueError("Only active credentials can be revoked.")
        now = utc_now_iso()
        metadata = json.loads(row["metadata_json"])
        metadata["revocation"] = {
            "reason": reason,
            "requested_by": actor_id,
            "published_at": now,
            "publication_type": publication_type,
        }
        self.connection.execute(
            """
            UPDATE agent_credentials
            SET status = ?, revoked_at = ?, metadata_json = ?
            WHERE id = ?
            """,
            (
                "revoked",
                now,
                json.dumps(metadata, sort_keys=True),
                credential_id,
            ),
        )
        self._refresh_agent_credential_status(row["agent_id"])
        updated = self.get(credential_id)
        if updated is None:
            raise CredentialNotFoundError("Credential not found.")
        return updated

    def record_rotation(
        self,
        *,
        agent_id: str,
        previous_credential_id: str,
        new_credential_id: str,
        reason: str,
        requested_by: str,
    ) -> Row:
        """Record a completed credential rotation."""

        now = utc_now_iso()
        rotation_id = generate_id("rot")
        self.connection.execute(
            """
            INSERT INTO credential_rotations (
                id, agent_id, previous_credential_id, new_credential_id,
                reason, status, requested_by, completed_at, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rotation_id,
                agent_id,
                previous_credential_id,
                new_credential_id,
                reason,
                "completed",
                requested_by,
                now,
                now,
            ),
        )
        return self.connection.execute(
            "SELECT * FROM credential_rotations WHERE id = ?",
            (rotation_id,),
        ).fetchone()

    def record_lifecycle_evidence(
        self,
        *,
        agent_id: str,
        actor_id: str,
        reason: str,
        metadata_json: dict[str, Any],
    ) -> Row:
        """Record credential lifecycle evidence in the agent timeline."""

        agent = self.connection.execute(
            """
            SELECT *
            FROM agents
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
              AND deleted_at IS NULL
            """,
            (agent_id, self.organization_id, self.environment_id),
        ).fetchone()
        if agent is None:
            raise AgentNotFoundError("Agent not found.")
        now = utc_now_iso()
        event_id = generate_id("life")
        self.connection.execute(
            """
            INSERT INTO agent_lifecycle_events (
                id, agent_id, previous_state, next_state, actor_id, reason,
                metadata_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                agent_id,
                agent["status"],
                agent["status"],
                actor_id,
                reason,
                json.dumps(metadata_json, sort_keys=True),
                now,
            ),
        )
        return self.connection.execute(
            "SELECT * FROM agent_lifecycle_events WHERE id = ?",
            (event_id,),
        ).fetchone()

    def get(self, credential_id: str) -> Row | None:
        """Return one credential metadata row by tenant scope."""

        return self.connection.execute(
            """
            SELECT c.*
            FROM agent_credentials c
            JOIN agents a ON a.id = c.agent_id
            WHERE c.id = ?
              AND a.organization_id = ?
              AND a.environment_id = ?
              AND a.deleted_at IS NULL
            """,
            (credential_id, self.organization_id, self.environment_id),
        ).fetchone()

    def list_for_agent(self, agent_id: str, *, status: str | None = None) -> list[Row]:
        """List credential metadata for an accessible agent."""

        if not self.agent_exists(agent_id):
            raise AgentNotFoundError("Agent not found.")
        clauses = ["c.agent_id = ?"]
        values: list[object] = [agent_id]
        if status:
            clauses.append("c.status = ?")
            values.append(status)
        values.extend([self.organization_id, self.environment_id])
        return self.connection.execute(
            f"""
            SELECT c.*
            FROM agent_credentials c
            JOIN agents a ON a.id = c.agent_id
            WHERE {' AND '.join(clauses)}
              AND a.organization_id = ?
              AND a.environment_id = ?
              AND a.deleted_at IS NULL
            ORDER BY c.expires_at ASC, c.id ASC
            """,
            values,
        ).fetchall()

    def list_expiring(
        self,
        *,
        threshold_hours: int,
        now: datetime | str | None = None,
    ) -> list[Row]:
        """List non-revoked credentials expiring within a threshold."""

        rows = self.connection.execute(
            """
            SELECT c.*
            FROM agent_credentials c
            JOIN agents a ON a.id = c.agent_id
            WHERE a.organization_id = ?
              AND a.environment_id = ?
              AND a.deleted_at IS NULL
              AND c.status IN ('active', 'expiring_soon')
            ORDER BY c.expires_at ASC, c.id ASC
            """,
            (self.organization_id, self.environment_id),
        ).fetchall()
        return [
            row
            for row in rows
            if credential_expires_within_threshold(
                row["expires_at"],
                now=now,
                threshold_hours=threshold_hours,
            )
        ]

    def mark_expiring_soon(
        self,
        credential_id: str,
        *,
        threshold_hours: int,
        detected_at: datetime | str,
        auto_rotate: bool = False,
    ) -> Row:
        """Mark an active credential as expiring soon and store monitor metadata."""

        row = self.get(credential_id)
        if row is None:
            raise CredentialNotFoundError("Credential not found.")
        if row["status"] not in {"active", "expiring_soon"}:
            raise ValueError("Only active credentials can be marked expiring soon.")
        detected = _coerce_utc_datetime(detected_at).isoformat()
        metadata = json.loads(row["metadata_json"])
        metadata["expiry_monitor"] = {
            "detected_at": detected,
            "threshold_hours": threshold_hours,
            "auto_rotation_policy": {
                "enabled": auto_rotate,
                "mode": "placeholder",
            },
        }
        self.connection.execute(
            """
            UPDATE agent_credentials
            SET status = ?, metadata_json = ?
            WHERE id = ?
            """,
            (
                "expiring_soon",
                json.dumps(metadata, sort_keys=True),
                credential_id,
            ),
        )
        self._refresh_agent_credential_status(row["agent_id"])
        updated = self.get(credential_id)
        if updated is None:
            raise CredentialNotFoundError("Credential not found.")
        return updated

    def verify_token(
        self,
        credential_id: str,
        *,
        raw_token: str,
        now: datetime | str | None = None,
    ) -> dict[str, Any]:
        """Verify a raw token against stored credential metadata."""

        row = self.get(credential_id)
        if row is None:
            raise CredentialNotFoundError("Credential not found.")
        verified_at = _coerce_utc_datetime(now).isoformat()
        status = row["status"]
        if status not in {"active", "expiring_soon"}:
            return {
                "credential_id": credential_id,
                "agent_id": row["agent_id"],
                "valid": False,
                "status": status,
                "reason": f"Credential is {status}.",
                "verified_at": verified_at,
            }
        if _coerce_utc_datetime(row["expires_at"]) < _coerce_utc_datetime(now):
            self.connection.execute(
                """
                UPDATE agent_credentials
                SET status = ?
                WHERE id = ?
                """,
                ("expired", credential_id),
            )
            self._refresh_agent_credential_status(row["agent_id"])
            return {
                "credential_id": credential_id,
                "agent_id": row["agent_id"],
                "valid": False,
                "status": "expired",
                "reason": "Credential is expired.",
                "verified_at": verified_at,
            }
        if hash_credential_token(raw_token) != row["token_hash"]:
            return {
                "credential_id": credential_id,
                "agent_id": row["agent_id"],
                "valid": False,
                "status": status,
                "reason": "Token does not match credential.",
                "verified_at": verified_at,
            }
        self.connection.execute(
            """
            UPDATE agent_credentials
            SET last_used_at = ?
            WHERE id = ?
            """,
            (verified_at, credential_id),
        )
        return {
            "credential_id": credential_id,
            "agent_id": row["agent_id"],
            "valid": True,
            "status": status,
            "reason": "Credential token is valid.",
            "verified_at": verified_at,
        }

    def identity_did(self, agent_id: str) -> str:
        """Return the active DID for an accessible agent."""

        if not self.agent_exists(agent_id):
            raise AgentNotFoundError("Agent not found.")
        row = self.connection.execute(
            """
            SELECT i.did
            FROM agent_identities i
            JOIN agents a ON a.id = i.agent_id
            WHERE i.agent_id = ?
              AND i.identity_status = 'active'
              AND a.organization_id = ?
              AND a.environment_id = ?
              AND a.deleted_at IS NULL
            """,
            (agent_id, self.organization_id, self.environment_id),
        ).fetchone()
        if row is None:
            raise ValueError("Agent identity is required before issuing credentials.")
        return str(row["did"])

    def validate_scopes(self, agent_id: str, scopes: list[CredentialScopeRequest]) -> None:
        """Validate requested credential scopes against approved capabilities."""

        if not self.agent_exists(agent_id):
            raise AgentNotFoundError("Agent not found.")
        approved = {
            row["capability_name"]
            for row in self.connection.execute(
                """
                SELECT capability_name
                FROM agent_capabilities
                WHERE agent_id = ?
                  AND status = 'approved'
                """,
                (agent_id,),
            ).fetchall()
        }
        invalid = sorted({scope.scope for scope in scopes if scope.scope not in approved})
        if invalid:
            raise ValueError(
                "Credential scope is not approved for agent: " + ", ".join(invalid)
            )

    def list_scopes(self, credential_id: str) -> list[Row]:
        """List scopes for an accessible credential."""

        return self.connection.execute(
            """
            SELECT s.*
            FROM credential_scopes s
            JOIN agent_credentials c ON c.id = s.credential_id
            JOIN agents a ON a.id = c.agent_id
            WHERE s.credential_id = ?
              AND a.organization_id = ?
              AND a.environment_id = ?
              AND a.deleted_at IS NULL
            ORDER BY s.scope ASC, s.resource_type ASC, s.resource_id ASC
            """,
            (credential_id, self.organization_id, self.environment_id),
        ).fetchall()

    def scope_requests(self, credential_id: str) -> list[CredentialScopeRequest]:
        """Return persisted scopes as request models for re-issuance."""

        return [
            CredentialScopeRequest(
                scope=row["scope"],
                resource_type=row["resource_type"],
                resource_id=row["resource_id"],
            )
            for row in self.list_scopes(credential_id)
        ]

    def agent_exists(self, agent_id: str) -> bool:
        """Return whether an agent exists in this tenant environment."""

        row = self.connection.execute(
            """
            SELECT 1
            FROM agents
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
              AND deleted_at IS NULL
            """,
            (agent_id, self.organization_id, self.environment_id),
        ).fetchone()
        return row is not None

    def _ensure_secret_absent(self, raw_token: str, metadata: dict[str, Any]) -> None:
        encoded = json.dumps(metadata, sort_keys=True)
        if raw_token and raw_token in encoded:
            raise ValueError("Credential metadata must not include raw token material.")

    def _refresh_agent_credential_status(self, agent_id: str) -> None:
        expiring = self.connection.execute(
            """
            SELECT expires_at
            FROM agent_credentials
            WHERE agent_id = ? AND status = 'expiring_soon'
            ORDER BY expires_at ASC, id ASC
            LIMIT 1
            """,
            (agent_id,),
        ).fetchone()
        if expiring is not None:
            status = "expiring_soon"
            expires_at = expiring["expires_at"]
        else:
            active = self.connection.execute(
                """
                SELECT expires_at
                FROM agent_credentials
                WHERE agent_id = ? AND status = 'active'
                ORDER BY expires_at ASC, id ASC
                LIMIT 1
                """,
                (agent_id,),
            ).fetchone()
            if active is not None:
                status = "active"
                expires_at = active["expires_at"]
            else:
                revoked_count = self.connection.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM agent_credentials
                    WHERE agent_id = ? AND status = 'revoked'
                    """,
                    (agent_id,),
                ).fetchone()["count"]
                status = "revoked" if revoked_count else None
                expires_at = None
        self.connection.execute(
            """
            UPDATE agents
            SET credential_status = ?, credential_expires_at = ?, updated_at = ?
            WHERE id = ? AND organization_id = ? AND environment_id = ? AND deleted_at IS NULL
            """,
            (
                status,
                expires_at,
                utc_now_iso(),
                agent_id,
                self.organization_id,
                self.environment_id,
            ),
        )


class CredentialNotFoundError(ValueError):
    """Raised when credential metadata is not visible in tenant scope."""


def credential_scope_response(row: Row) -> CredentialScopeResponse:
    """Serialize a credential scope row."""

    return CredentialScopeResponse(
        id=row["id"],
        credential_id=row["credential_id"],
        scope=row["scope"],
        resource_type=row["resource_type"],
        resource_id=row["resource_id"],
    )


def agent_credential_response(
    repository: AgentCredentialRepository,
    row: Row,
) -> AgentCredentialResponse:
    """Serialize credential metadata without token hashes."""

    return AgentCredentialResponse(
        id=row["id"],
        agent_id=row["agent_id"],
        credential_type=row["credential_type"],
        issuer=row["issuer"],
        status=row["status"],
        issued_at=row["issued_at"],
        expires_at=row["expires_at"],
        revoked_at=row["revoked_at"],
        last_used_at=row["last_used_at"],
        metadata_json=json.loads(row["metadata_json"]),
        scopes=[
            credential_scope_response(scope)
            for scope in repository.list_scopes(row["id"])
        ],
    )


def _datetime_to_utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc).isoformat()
    return value.astimezone(timezone.utc).isoformat()


def _coerce_utc_datetime(value: datetime | str | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00").replace(" ", "+"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
