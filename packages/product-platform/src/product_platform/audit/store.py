"""Persistent audit event repository."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from product_platform.db.postgres import Connection, Row

from product_platform.audit.events import AuditEventEnvelope
from product_platform.audit.hash_chain import (
    CHECKPOINT_SIGNATURE_ALGORITHM,
    HASH_ALGORITHM,
    AuditVerificationResult,
    calculate_event_hash,
    sign_checkpoint_proof,
)
from product_platform.db.ids import generate_id
from product_platform.db.time import utc_now_iso


@dataclass(frozen=True)
class AuditEventQuery:
    """Filter set for audit event queries."""

    organization_id: str
    environment_id: str | None = None
    event_type: str | None = None
    source_component: str | None = None
    actor_type: str | None = None
    actor_id: str | None = None
    agent_id: str | None = None
    decision: str | None = None
    severity: str | None = None
    policy_id: str | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    correlation_id: str | None = None
    created_from: str | None = None
    created_to: str | None = None
    limit: int = 50
    offset: int = 0


class AuditEventRepository:
    """Insert and query canonical audit events."""

    def __init__(self, connection: Connection) -> None:
        self.connection = connection

    def insert(self, event: AuditEventEnvelope) -> AuditEventEnvelope:
        previous_hash = self._latest_hash(event.organization_id, event.environment_id)
        self.connection.execute(
            """
            INSERT INTO audit_events (
                id, organization_id, environment_id, event_type, source_component,
                actor_type, actor_id, agent_id, resource_type, resource_id, decision,
                severity, correlation_id, trace_id, policy_id, policy_version_id,
                trust_delta, payload_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.id,
                event.organization_id,
                event.environment_id,
                event.event_type,
                event.source_component,
                event.actor_type,
                event.actor_id,
                event.agent_id,
                event.resource_type,
                event.resource_id,
                event.decision,
                event.severity,
                event.correlation_id,
                event.trace_id,
                event.policy_id,
                event.policy_version_id,
                event.trust_delta,
                json.dumps(event.payload_json, sort_keys=True),
                event.created_at,
            ),
        )
        current_hash = calculate_event_hash(event, previous_hash)
        self.connection.execute(
            """
            INSERT INTO audit_event_hashes
                (event_id, previous_hash, current_hash, algorithm, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (event.id, previous_hash, current_hash, HASH_ALGORITHM, utc_now_iso()),
        )
        return event

    def get(
        self,
        event_id: str,
        organization_id: str,
        *,
        environment_id: str | None = None,
    ) -> AuditEventEnvelope | None:
        clauses = ["id = ?", "organization_id = ?"]
        values: list[object] = [event_id, organization_id]
        if environment_id is not None:
            clauses.append("environment_id = ?")
            values.append(environment_id)
        row = self.connection.execute(
            f"SELECT * FROM audit_events WHERE {' AND '.join(clauses)}",
            values,
        ).fetchone()
        return _row_to_event(row) if row else None

    def query(self, query: AuditEventQuery) -> list[AuditEventEnvelope]:
        clauses = ["organization_id = ?"]
        values: list[object] = [query.organization_id]
        for column, value in [
            ("environment_id", query.environment_id),
            ("event_type", query.event_type),
            ("source_component", query.source_component),
            ("actor_type", query.actor_type),
            ("actor_id", query.actor_id),
            ("agent_id", query.agent_id),
            ("decision", query.decision),
            ("severity", query.severity),
            ("policy_id", query.policy_id),
            ("resource_type", query.resource_type),
            ("resource_id", query.resource_id),
            ("correlation_id", query.correlation_id),
        ]:
            if value is not None:
                clauses.append(f"{column} = ?")
                values.append(value)
        if query.created_from is not None:
            clauses.append("created_at >= ?")
            values.append(query.created_from)
        if query.created_to is not None:
            clauses.append("created_at <= ?")
            values.append(query.created_to)
        values.extend([query.limit, query.offset])
        rows = self.connection.execute(
            f"""
            SELECT * FROM audit_events
            WHERE {' AND '.join(clauses)}
            ORDER BY created_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            values,
        ).fetchall()
        return [_row_to_event(row) for row in rows]

    def stream_events(
        self,
        *,
        organization_id: str,
        environment_id: str | None = None,
        event_type: str | None = None,
        last_event_id: str | None = None,
        limit: int = 100,
    ) -> list[AuditEventEnvelope]:
        clauses = ["organization_id = ?"]
        values: list[object] = [organization_id]
        if environment_id is not None:
            clauses.append("environment_id = ?")
            values.append(environment_id)
        if event_type is not None:
            clauses.append("event_type = ?")
            values.append(event_type)
        if last_event_id is not None:
            cursor_clauses = ["id = ?", "organization_id = ?"]
            cursor_values: list[object] = [last_event_id, organization_id]
            if environment_id is not None:
                cursor_clauses.append("environment_id = ?")
                cursor_values.append(environment_id)
            last_row = self.connection.execute(
                f"SELECT created_at, id FROM audit_events WHERE {' AND '.join(cursor_clauses)}",
                cursor_values,
            ).fetchone()
            if last_row is not None:
                clauses.append("(created_at > ? OR (created_at = ? AND id > ?))")
                values.extend([last_row["created_at"], last_row["created_at"], last_row["id"]])
        values.append(limit)
        rows = self.connection.execute(
            f"""
            SELECT * FROM audit_events
            WHERE {' AND '.join(clauses)}
            ORDER BY created_at ASC, id ASC
            LIMIT ?
            """,
            values,
        ).fetchall()
        return [_row_to_event(row) for row in rows]

    def verify_event(
        self,
        event_id: str,
        organization_id: str,
        *,
        environment_id: str | None = None,
    ) -> AuditVerificationResult:
        event = self.get(event_id, organization_id, environment_id=environment_id)
        if event is None:
            return AuditVerificationResult(
                valid=False,
                checked_count=0,
                failed_event_id=event_id,
                reason="event_not_found",
            )
        hash_row = self.connection.execute(
            "SELECT * FROM audit_event_hashes WHERE event_id = ?",
            (event_id,),
        ).fetchone()
        if hash_row is None:
            return AuditVerificationResult(
                valid=False,
                checked_count=1,
                failed_event_id=event_id,
                reason="hash_missing",
            )
        expected = calculate_event_hash(event, hash_row["previous_hash"])
        if expected != hash_row["current_hash"]:
            return AuditVerificationResult(
                valid=False,
                checked_count=1,
                failed_event_id=event_id,
                reason="hash_mismatch",
            )
        return AuditVerificationResult(valid=True, checked_count=1)

    def verify_range(
        self,
        organization_id: str,
        *,
        environment_id: str | None = None,
    ) -> AuditVerificationResult:
        clauses = ["e.organization_id = ?"]
        values: list[object] = [organization_id]
        if environment_id is not None:
            clauses.append("e.environment_id = ?")
            values.append(environment_id)
        rows = self.connection.execute(
            f"""
            SELECT e.*, h.previous_hash, h.current_hash
            FROM audit_events e
            LEFT JOIN audit_event_hashes h ON h.event_id = e.id
            WHERE {' AND '.join(clauses)}
            ORDER BY e.environment_id ASC, e.created_at ASC, e.id ASC
            """,
            values,
        ).fetchall()
        previous_hash_by_environment: dict[str | None, str | None] = {}
        current_hash_by_event_id: dict[str, str] = {}
        ordinal_by_event_id: dict[str, int] = {}
        first_hash_by_environment: dict[str | None, str] = {}
        ordinal_by_environment: dict[str | None, int] = {}
        checked_count = 0
        for row in rows:
            checked_count += 1
            event = _row_to_event(row)
            ordinal = ordinal_by_environment.get(event.environment_id, 0) + 1
            ordinal_by_environment[event.environment_id] = ordinal
            previous_hash = previous_hash_by_environment.get(event.environment_id)
            if row["current_hash"] is None:
                return AuditVerificationResult(
                    valid=False,
                    checked_count=checked_count,
                    failed_event_id=event.id,
                    reason="hash_missing",
                )
            if row["previous_hash"] != previous_hash:
                return AuditVerificationResult(
                    valid=False,
                    checked_count=checked_count,
                    failed_event_id=event.id,
                    reason="previous_hash_mismatch",
                )
            expected = calculate_event_hash(event, previous_hash)
            if expected != row["current_hash"]:
                return AuditVerificationResult(
                    valid=False,
                    checked_count=checked_count,
                    failed_event_id=event.id,
                    reason="hash_mismatch",
                )
            previous_hash = row["current_hash"]
            previous_hash_by_environment[event.environment_id] = previous_hash
            current_hash_by_event_id[event.id] = previous_hash
            ordinal_by_event_id[event.id] = ordinal
            first_hash_by_environment.setdefault(event.environment_id, previous_hash)
        for checkpoint in self._latest_checkpoints(organization_id, environment_id):
            checkpoint_count = int(checkpoint["event_count"])
            if checkpoint_count == 0:
                continue
            checkpoint_event_id = checkpoint["end_event_id"]
            checkpoint_environment_id = checkpoint["environment_id"]
            if checkpoint_event_id not in current_hash_by_event_id:
                return AuditVerificationResult(
                    valid=False,
                    checked_count=checked_count,
                    failed_event_id=checkpoint_event_id,
                    reason="checkpoint_event_missing",
                    checkpoint_id=checkpoint["id"],
                )
            if ordinal_by_event_id[checkpoint_event_id] != checkpoint_count:
                return AuditVerificationResult(
                    valid=False,
                    checked_count=checked_count,
                    failed_event_id=checkpoint_event_id,
                    reason="checkpoint_count_mismatch",
                    checkpoint_id=checkpoint["id"],
                )
            if current_hash_by_event_id[checkpoint_event_id] != checkpoint["last_hash"]:
                return AuditVerificationResult(
                    valid=False,
                    checked_count=checked_count,
                    failed_event_id=checkpoint_event_id,
                    reason="checkpoint_hash_mismatch",
                    checkpoint_id=checkpoint["id"],
                )
            if (
                checkpoint["first_hash"] is not None
                and first_hash_by_environment.get(checkpoint_environment_id) != checkpoint["first_hash"]
            ):
                return AuditVerificationResult(
                    valid=False,
                    checked_count=checked_count,
                    failed_event_id=checkpoint["start_event_id"],
                    reason="checkpoint_first_hash_mismatch",
                    checkpoint_id=checkpoint["id"],
                )
        return AuditVerificationResult(valid=True, checked_count=checked_count)

    def create_checkpoint(
        self,
        organization_id: str,
        *,
        environment_id: str | None = None,
        created_by: str = "system",
        scope: dict[str, Any] | None = None,
        signing_key: str | None = None,
    ) -> Row:
        """Persist a signed checkpoint for the current audit hash chain."""

        verification = self.verify_range(organization_id, environment_id=environment_id)
        if not verification.valid:
            raise ValueError(f"Cannot checkpoint invalid audit hash chain: {verification.reason}.")

        rows = self._hash_rows_for_scope(organization_id, environment_id=environment_id)
        checkpoint_id = generate_id("audchk")
        now = utc_now_iso()
        event_count = len(rows)
        first_row = rows[0] if rows else None
        last_row = rows[-1] if rows else None
        proof: dict[str, Any] = {
            "algorithm": HASH_ALGORITHM,
            "checkpoint_id": checkpoint_id,
            "created_at": now,
            "event_count": event_count,
            "environment_id": environment_id,
            "first_hash": first_row["current_hash"] if first_row is not None else None,
            "last_hash": last_row["current_hash"] if last_row is not None else None,
            "organization_id": organization_id,
            "signature_algorithm": CHECKPOINT_SIGNATURE_ALGORITHM,
            "scope": scope or {},
            "start_event_id": first_row["id"] if first_row is not None else None,
            "end_event_id": last_row["id"] if last_row is not None else None,
        }
        signature = sign_checkpoint_proof(proof, signing_key=signing_key)
        self.connection.execute(
            """
            INSERT INTO audit_hash_checkpoints (
                id, organization_id, environment_id, start_event_id, end_event_id,
                event_count, first_hash, last_hash, algorithm, scope_json, proof_json,
                signature, created_by, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                checkpoint_id,
                organization_id,
                environment_id,
                proof["start_event_id"],
                proof["end_event_id"],
                event_count,
                proof["first_hash"],
                proof["last_hash"],
                HASH_ALGORITHM,
                json.dumps(scope or {}, sort_keys=True),
                json.dumps(proof, sort_keys=True),
                signature,
                created_by,
                now,
            ),
        )
        row = self.connection.execute(
            "SELECT * FROM audit_hash_checkpoints WHERE id = ?",
            (checkpoint_id,),
        ).fetchone()
        if row is None:
            raise ValueError("Created audit hash checkpoint could not be loaded.")
        return row

    def latest_checkpoint(
        self,
        organization_id: str,
        *,
        environment_id: str | None = None,
    ) -> Row | None:
        """Return the latest signed checkpoint for an audit hash-chain scope."""

        return self._latest_checkpoint(organization_id, environment_id)

    def hash_metadata_for_events(self, event_ids: list[str]) -> dict[str, dict[str, Any]]:
        """Return hash-chain metadata for a set of event ids."""

        if not event_ids:
            return {}
        placeholders = ", ".join("?" for _ in event_ids)
        rows = self.connection.execute(
            f"""
            SELECT event_id, previous_hash, current_hash, algorithm, created_at
            FROM audit_event_hashes
            WHERE event_id IN ({placeholders})
            """,
            event_ids,
        ).fetchall()
        return {
            row["event_id"]: {
                "event_id": row["event_id"],
                "previous_hash": row["previous_hash"],
                "current_hash": row["current_hash"],
                "algorithm": row["algorithm"],
                "created_at": row["created_at"],
            }
            for row in rows
        }

    def export_chain_proof(
        self,
        *,
        organization_id: str,
        environment_id: str,
        event_ids: list[str],
        checkpoint: Row | None = None,
    ) -> dict[str, Any]:
        """Build exportable chain proof metadata for selected audit events."""

        selected_hashes = self.hash_metadata_for_events(event_ids)
        selected_events = [
            selected_hashes[event_id] for event_id in event_ids if event_id in selected_hashes
        ]
        checkpoint_row = checkpoint or self.latest_checkpoint(
            organization_id,
            environment_id=environment_id,
        )
        checkpoint_payload: dict[str, Any] | None = None
        if checkpoint_row is not None:
            checkpoint_payload = {
                "id": checkpoint_row["id"],
                "organization_id": checkpoint_row["organization_id"],
                "environment_id": checkpoint_row["environment_id"],
                "start_event_id": checkpoint_row["start_event_id"],
                "end_event_id": checkpoint_row["end_event_id"],
                "event_count": checkpoint_row["event_count"],
                "first_hash": checkpoint_row["first_hash"],
                "last_hash": checkpoint_row["last_hash"],
                "algorithm": checkpoint_row["algorithm"],
                "scope": json.loads(checkpoint_row["scope_json"] or "{}"),
                "proof": json.loads(checkpoint_row["proof_json"] or "{}"),
                "signature": checkpoint_row["signature"],
                "created_by": checkpoint_row["created_by"],
                "created_at": checkpoint_row["created_at"],
            }
        return {
            "algorithm": HASH_ALGORITHM,
            "organization_id": organization_id,
            "environment_id": environment_id,
            "selected_event_count": len(event_ids),
            "selected_events": selected_events,
            "range_verification": self.verify_range(
                organization_id,
                environment_id=environment_id,
            ).model_dump(mode="json"),
            "checkpoint": checkpoint_payload,
        }

    def _latest_hash(self, organization_id: str, environment_id: str | None) -> str | None:
        clauses = ["e.organization_id = ?"]
        values: list[object] = [organization_id]
        if environment_id is None:
            clauses.append("e.environment_id IS NULL")
        else:
            clauses.append("e.environment_id = ?")
            values.append(environment_id)
        row = self.connection.execute(
            f"""
            SELECT h.current_hash
            FROM audit_event_hashes h
            JOIN audit_events e ON e.id = h.event_id
            WHERE {' AND '.join(clauses)}
            ORDER BY e.created_at DESC, e.id DESC
            LIMIT 1
            """,
            values,
        ).fetchone()
        return row["current_hash"] if row else None

    def _hash_rows_for_scope(
        self,
        organization_id: str,
        *,
        environment_id: str | None,
    ) -> list[Row]:
        clauses = ["e.organization_id = ?"]
        values: list[object] = [organization_id]
        if environment_id is None:
            clauses.append("e.environment_id IS NULL")
        else:
            clauses.append("e.environment_id = ?")
            values.append(environment_id)
        return self.connection.execute(
            f"""
            SELECT e.id, e.environment_id, e.created_at, h.previous_hash, h.current_hash, h.algorithm
            FROM audit_events e
            JOIN audit_event_hashes h ON h.event_id = e.id
            WHERE {' AND '.join(clauses)}
            ORDER BY e.created_at ASC, e.id ASC
            """,
            values,
        ).fetchall()

    def _latest_checkpoint(
        self,
        organization_id: str,
        environment_id: str | None,
    ) -> Row | None:
        clauses = ["organization_id = ?"]
        values: list[object] = [organization_id]
        if environment_id is None:
            clauses.append("environment_id IS NULL")
        else:
            clauses.append("environment_id = ?")
            values.append(environment_id)
        return self.connection.execute(
            f"""
            SELECT *
            FROM audit_hash_checkpoints
            WHERE {' AND '.join(clauses)}
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            values,
        ).fetchone()

    def _latest_checkpoints(
        self,
        organization_id: str,
        environment_id: str | None,
    ) -> list[Row]:
        if environment_id is not None:
            row = self._latest_checkpoint(organization_id, environment_id)
            return [row] if row is not None else []
        return self.connection.execute(
            """
            SELECT DISTINCT ON (environment_id) *
            FROM audit_hash_checkpoints
            WHERE organization_id = ?
            ORDER BY environment_id ASC, created_at DESC, id DESC
            """,
            (organization_id,),
        ).fetchall()


def _row_to_event(row: Row) -> AuditEventEnvelope:
    return AuditEventEnvelope(
        id=row["id"],
        organization_id=row["organization_id"],
        environment_id=row["environment_id"],
        event_type=row["event_type"],
        source_component=row["source_component"],
        actor_type=row["actor_type"],
        actor_id=row["actor_id"],
        agent_id=row["agent_id"],
        resource_type=row["resource_type"],
        resource_id=row["resource_id"],
        decision=row["decision"],
        severity=row["severity"],
        correlation_id=row["correlation_id"],
        trace_id=row["trace_id"],
        policy_id=row["policy_id"],
        policy_version_id=row["policy_version_id"],
        trust_delta=row["trust_delta"],
        payload_json=json.loads(row["payload_json"]),
        created_at=row["created_at"],
    )
