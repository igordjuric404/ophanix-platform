"""Persistent audit event repository."""

from __future__ import annotations

import json
from dataclasses import dataclass
from sqlite3 import Connection, Row

from product_platform.audit.events import AuditEventEnvelope
from product_platform.audit.hash_chain import (
    HASH_ALGORITHM,
    AuditVerificationResult,
    calculate_event_hash,
)
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
        previous_hash = self._latest_hash(event.organization_id)
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

    def get(self, event_id: str, organization_id: str) -> AuditEventEnvelope | None:
        row = self.connection.execute(
            "SELECT * FROM audit_events WHERE id = ? AND organization_id = ?",
            (event_id, organization_id),
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
        event_type: str | None = None,
        last_event_id: str | None = None,
        limit: int = 100,
    ) -> list[AuditEventEnvelope]:
        clauses = ["organization_id = ?"]
        values: list[object] = [organization_id]
        if event_type is not None:
            clauses.append("event_type = ?")
            values.append(event_type)
        if last_event_id is not None:
            last_row = self.connection.execute(
                "SELECT created_at, id FROM audit_events WHERE id = ? AND organization_id = ?",
                (last_event_id, organization_id),
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

    def verify_event(self, event_id: str, organization_id: str) -> AuditVerificationResult:
        event = self.get(event_id, organization_id)
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

    def verify_range(self, organization_id: str) -> AuditVerificationResult:
        rows = self.connection.execute(
            """
            SELECT e.*, h.previous_hash, h.current_hash
            FROM audit_events e
            LEFT JOIN audit_event_hashes h ON h.event_id = e.id
            WHERE e.organization_id = ?
            ORDER BY e.created_at ASC, e.id ASC
            """,
            (organization_id,),
        ).fetchall()
        previous_hash: str | None = None
        checked_count = 0
        for row in rows:
            checked_count += 1
            event = _row_to_event(row)
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
        return AuditVerificationResult(valid=True, checked_count=checked_count)

    def _latest_hash(self, organization_id: str) -> str | None:
        row = self.connection.execute(
            """
            SELECT h.current_hash
            FROM audit_event_hashes h
            JOIN audit_events e ON e.id = h.event_id
            WHERE e.organization_id = ?
            ORDER BY e.created_at DESC, e.id DESC
            LIMIT 1
            """,
            (organization_id,),
        ).fetchone()
        return row["current_hash"] if row else None


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
