"""Credential metadata persistence for registered agents."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from product_platform.db.postgres import Connection, Row
from typing import Any

from agentmesh.identity.credentials import CredentialManager

from product_platform.audit.events import AuditEventEnvelope
from product_platform.agents.lifecycle import agent_non_operational_message, is_agent_operational
from product_platform.agents.models import (
    AgentCredentialResponse,
    CredentialScopeRequest,
    CredentialScopeResponse,
)
from product_platform.agents.repository import AgentNotFoundError
from product_platform.db.ids import generate_id
from product_platform.db.time import utc_now_iso

SENSITIVE_METADATA_KEY_TOKENS = {
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "password",
    "private_key",
    "secret",
    "token",
}
SENSITIVE_METADATA_TEXT_RE = re.compile(
    r"(?i)\b(bearer\s+[A-Za-z0-9._~+/=-]{8,}|"
    r"(?:api[-_\s]?key|authorization|password|secret|token)\s*[:=]\s*['\"]?[^,'\"\s]{8,})"
)
LIFECYCLE_CREDENTIAL_REVOKE_STATUSES = frozenset(
    {"restricted", "quarantined", "suspended", "revoked", "decommissioning", "decommissioned"}
)
LIFECYCLE_IDENTITY_DISABLED_STATUSES = frozenset(
    {
        "restricted",
        "quarantined",
        "suspended",
        "revoked",
        "decommissioning",
        "decommissioned",
        "archived",
    }
)
LIFECYCLE_IDENTITY_REACTIVATABLE_STATUSES = frozenset({"restricted", "quarantined", "suspended", "orphaned"})


def hash_credential_token(token: str) -> str:
    """Return the stable token hash stored by the product database."""

    pepper = os.environ.get("OPHANIX_GATEWAY_TOKEN_HASH_PEPPER")
    if pepper:
        key_id = os.environ.get("OPHANIX_GATEWAY_TOKEN_HASH_PEPPER_ID")
        return _hmac_credential_token_hash(token, pepper, key_id=key_id)
    return legacy_credential_token_hash(token)


def legacy_credential_token_hash(token: str) -> str:
    """Return the legacy unpeppered SHA-256 token hash."""

    return hashlib.sha256(token.encode()).hexdigest()


def credential_token_hash_candidates(token: str) -> list[str]:
    """Return accepted hashes for lookup during pepper migration."""

    candidates = [hash_credential_token(token)]
    pepper = os.environ.get("OPHANIX_GATEWAY_TOKEN_HASH_PEPPER")
    for key_id, previous_pepper in _previous_token_hash_peppers():
        candidates.append(_hmac_credential_token_hash(token, previous_pepper, key_id=key_id))
    legacy = legacy_credential_token_hash(token)
    if (not pepper or _bool_env("OPHANIX_GATEWAY_TOKEN_HASH_ACCEPT_LEGACY", False)) and (
        legacy not in candidates
    ):
        candidates.append(legacy)
    return candidates


def _hmac_credential_token_hash(token: str, pepper: str, *, key_id: str | None) -> str:
    digest = hmac.new(
        pepper.encode("utf-8"),
        token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    normalized_key_id = (key_id or "").strip()
    if normalized_key_id:
        return f"hmac-sha256:{normalized_key_id}:{digest}"
    return f"hmac-sha256:{digest}"


def _previous_token_hash_peppers() -> list[tuple[str | None, str]]:
    raw = os.environ.get("OPHANIX_GATEWAY_TOKEN_HASH_PREVIOUS_PEPPERS", "")
    previous: list[tuple[str | None, str]] = []
    for item in raw.split(","):
        entry = item.strip()
        if not entry:
            continue
        if ":" in entry:
            key_id, pepper = entry.split(":", 1)
            previous.append((key_id.strip() or None, pepper))
        else:
            previous.append((None, entry))
    return previous


def _bool_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


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


@dataclass(frozen=True)
class AgentLifecycleCredentialCascadeResult:
    """Credential and identity changes caused by an agent lifecycle transition."""

    credential_ids: list[str]
    identity_status: str | None


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

    def cascade_agent_lifecycle_status(
        self,
        *,
        agent_id: str,
        next_status: str,
        actor_id: str,
        reason: str,
    ) -> AgentLifecycleCredentialCascadeResult:
        """Invalidate credentials and identity state after restrictive lifecycle transitions."""

        if not self.agent_exists(agent_id):
            raise AgentNotFoundError("Agent not found.")
        revoked_credential_ids: list[str] = []
        now = utc_now_iso()
        if next_status in LIFECYCLE_CREDENTIAL_REVOKE_STATUSES:
            rows = self.connection.execute(
                """
                SELECT *
                FROM agent_credentials
                WHERE agent_id = ?
                  AND status IN ('active', 'expiring_soon')
                ORDER BY issued_at ASC, id ASC
                """,
                (agent_id,),
            ).fetchall()
            for row in rows:
                metadata = json.loads(row["metadata_json"])
                metadata["revocation"] = {
                    "reason": reason,
                    "requested_by": actor_id,
                    "published_at": now,
                    "publication_type": "lifecycle_transition",
                    "trigger": "agent_lifecycle",
                    "lifecycle_state": next_status,
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
                        row["id"],
                    ),
                )
                revoked_credential_ids.append(str(row["id"]))
            if revoked_credential_ids:
                self._refresh_agent_credential_status(agent_id)

        identity_status = self._cascade_identity_status(agent_id, next_status)
        return AgentLifecycleCredentialCascadeResult(
            credential_ids=revoked_credential_ids,
            identity_status=identity_status,
        )

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
        if row["token_hash"] not in credential_token_hash_candidates(raw_token):
            return {
                "credential_id": credential_id,
                "agent_id": row["agent_id"],
                "valid": False,
                "status": status,
                "reason": "Token does not match credential.",
                "verified_at": verified_at,
            }
        agent_context = self._agent_auth_context(row["agent_id"])
        if agent_context is None:
            raise AgentNotFoundError("Agent not found.")
        if not is_agent_operational(agent_context["status"]):
            return {
                "credential_id": credential_id,
                "agent_id": row["agent_id"],
                "valid": False,
                "status": status,
                "reason": agent_non_operational_message(agent_context["status"]),
                "verified_at": verified_at,
            }
        identity_status = agent_context["identity_status"]
        if identity_status is not None and identity_status != "active":
            return {
                "credential_id": credential_id,
                "agent_id": row["agent_id"],
                "valid": False,
                "status": status,
                "reason": f"Agent identity is {identity_status}.",
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
            SELECT i.did, i.identity_status, a.status AS agent_status
            FROM agent_identities i
            JOIN agents a ON a.id = i.agent_id
            WHERE i.agent_id = ?
              AND a.organization_id = ?
              AND a.environment_id = ?
              AND a.deleted_at IS NULL
            """,
            (agent_id, self.organization_id, self.environment_id),
        ).fetchone()
        if row is None:
            raise ValueError("Agent identity is required before issuing credentials.")
        if not is_agent_operational(row["agent_status"]):
            raise ValueError(agent_non_operational_message(row["agent_status"]))
        if row["identity_status"] != "active":
            raise ValueError(f"Agent identity is {row['identity_status']}.")
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
        invalid_tool_resources: list[str] = []
        for scope in scopes:
            if scope.resource_type != "tool":
                continue
            if not scope.resource_id:
                invalid_tool_resources.append("<missing>")
                continue
            row = self.connection.execute(
                """
                SELECT id
                FROM tool_definitions
                WHERE organization_id = ?
                  AND environment_id = ?
                  AND status = 'active'
                  AND (id = ? OR name = ?)
                """,
                (
                    self.organization_id,
                    self.environment_id,
                    scope.resource_id,
                    scope.resource_id,
                ),
            ).fetchone()
            if row is None:
                invalid_tool_resources.append(scope.resource_id)
        if invalid_tool_resources:
            raise ValueError(
                "Credential tool resource is not an active tool: "
                + ", ".join(sorted(set(invalid_tool_resources)))
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

    def _cascade_identity_status(self, agent_id: str, next_status: str) -> str | None:
        target_status: str | None = None
        if next_status in LIFECYCLE_IDENTITY_DISABLED_STATUSES:
            target_status = next_status
        elif next_status == "active":
            row = self.connection.execute(
                """
                SELECT identity_status
                FROM agent_identities
                WHERE agent_id = ?
                """,
                (agent_id,),
            ).fetchone()
            if row is not None and row["identity_status"] in LIFECYCLE_IDENTITY_REACTIVATABLE_STATUSES:
                target_status = "active"
        if target_status is None:
            row = self.connection.execute(
                """
                SELECT identity_status
                FROM agent_identities
                WHERE agent_id = ?
                """,
                (agent_id,),
            ).fetchone()
            return str(row["identity_status"]) if row is not None else None
        self.connection.execute(
            """
            UPDATE agent_identities
            SET identity_status = ?
            WHERE agent_id = ?
            """,
            (target_status, agent_id),
        )
        return target_status

    def _agent_auth_context(self, agent_id: str) -> Row | None:
        return self.connection.execute(
            """
            SELECT a.status, i.identity_status
            FROM agents a
            LEFT JOIN agent_identities i ON i.agent_id = a.id
            WHERE a.id = ?
              AND a.organization_id = ?
              AND a.environment_id = ?
              AND a.deleted_at IS NULL
            """,
            (agent_id, self.organization_id, self.environment_id),
        ).fetchone()

    def _ensure_secret_absent(self, raw_token: str, metadata: dict[str, Any]) -> None:
        encoded = json.dumps(metadata, sort_keys=True)
        if raw_token and (
            raw_token in encoded
            or f"Bearer {raw_token}" in encoded
            or f"bearer {raw_token}" in encoded
        ):
            raise ValueError("Credential metadata must not include raw token material.")
        self._ensure_metadata_has_no_secret_markers(metadata)

    def _ensure_metadata_has_no_secret_markers(self, value: Any, *, path: str = "metadata") -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                normalized_key = _normalize_metadata_key(str(key))
                if _is_sensitive_metadata_key(normalized_key):
                    raise ValueError(
                        f"Credential metadata field must not contain secret material: {path}.{key}."
                    )
                self._ensure_metadata_has_no_secret_markers(child, path=f"{path}.{key}")
            return
        if isinstance(value, list):
            for index, child in enumerate(value):
                self._ensure_metadata_has_no_secret_markers(child, path=f"{path}[{index}]")
            return
        if isinstance(value, str) and SENSITIVE_METADATA_TEXT_RE.search(value):
            raise ValueError(f"Credential metadata must not include secret material: {path}.")

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


def _is_sensitive_metadata_key(normalized_key: str) -> bool:
    if normalized_key in SENSITIVE_METADATA_KEY_TOKENS:
        return True
    return normalized_key.endswith(
        (
            "_api_key",
            "_apikey",
            "_authorization",
            "_bearer",
            "_password",
            "_private_key",
            "_secret",
            "_token",
        )
    )


def _normalize_metadata_key(key: str) -> str:
    with_word_boundaries = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", key.strip())
    return re.sub(r"[^a-z0-9]+", "_", with_word_boundaries.lower()).strip("_")


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
