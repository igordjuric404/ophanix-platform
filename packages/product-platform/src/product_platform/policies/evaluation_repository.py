"""Persistence for policy simulator and live evaluation feed rows."""

from __future__ import annotations

import json
from dataclasses import dataclass
from product_platform.db.postgres import Connection, Row
from typing import Any

from product_platform.db.ids import generate_id
from product_platform.db.time import utc_now_iso
from product_platform.policies.models import (
    PolicyEvaluationResponse,
    PolicyEvaluationSummaryResponse,
    PolicyEvaluationTimeBucket,
)


class PolicyEvaluationNotFoundError(ValueError):
    """Raised when a policy evaluation row is not visible in scope."""


@dataclass(frozen=True)
class PolicyEvaluationQuery:
    """Filter set for policy evaluation feed queries."""

    organization_id: str
    environment_id: str
    decision: str | None = None
    mode: str | None = None
    agent_id: str | None = None
    action: str | None = None
    policy_id: str | None = None
    correlation_id: str | None = None
    limit: int = 50
    offset: int = 0


class PolicyEvaluationRepository:
    """Repository for environment-scoped policy evaluation records."""

    def __init__(self, connection: Connection) -> None:
        self.connection = connection

    def create(self, evaluation: PolicyEvaluationResponse) -> Row:
        """Persist an adapter response and return the created row."""

        evaluation_id = evaluation.id or generate_id("peval")
        created_at = evaluation.created_at or utc_now_iso()
        self.connection.execute(
            """
            INSERT INTO policy_evaluations (
                id, organization_id, environment_id, policy_id, policy_version_id,
                binding_id, binding_mode, agent_id, target_type, target_id, action,
                resource_type, resource_id, context_json, decision, policy_action,
                matched_rule, reason, latency_ms, mode, correlation_id, backend,
                error, audit_preview_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                evaluation_id,
                evaluation.organization_id,
                evaluation.environment_id,
                evaluation.policy_id,
                evaluation.policy_version_id,
                evaluation.binding_id,
                evaluation.binding_mode,
                evaluation.agent_id,
                evaluation.target_type,
                evaluation.target_id,
                evaluation.action,
                evaluation.resource_type,
                evaluation.resource_id,
                json.dumps(evaluation.context, sort_keys=True),
                evaluation.decision,
                evaluation.policy_action,
                evaluation.matched_rule,
                evaluation.reason,
                evaluation.latency_ms,
                evaluation.mode,
                evaluation.correlation_id,
                evaluation.backend,
                1 if evaluation.error else 0,
                json.dumps(evaluation.audit_preview, sort_keys=True),
                created_at,
            ),
        )
        row = self.get(
            evaluation_id,
            evaluation.organization_id,
            evaluation.environment_id,
        )
        if row is None:
            raise PolicyEvaluationNotFoundError("Created policy evaluation could not be loaded.")
        return row

    def get(
        self,
        evaluation_id: str,
        organization_id: str,
        environment_id: str,
    ) -> Row | None:
        """Get one evaluation row by tenant and environment scope."""

        return self.connection.execute(
            """
            SELECT *
            FROM policy_evaluations
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            (evaluation_id, organization_id, environment_id),
        ).fetchone()

    def list(self, query: PolicyEvaluationQuery) -> list[Row]:
        """List evaluation rows in scope with feed filters."""

        clauses, values = _query_clauses(query)
        values.extend([query.limit, query.offset])
        return self.connection.execute(
            f"""
            SELECT *
            FROM policy_evaluations
            WHERE {' AND '.join(clauses)}
            ORDER BY created_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            values,
        ).fetchall()

    def summary(self, query: PolicyEvaluationQuery) -> PolicyEvaluationSummaryResponse:
        """Aggregate feed rows by decision, mode, action, and daily buckets."""

        clauses, values = _query_clauses(query)
        where_sql = " AND ".join(clauses)
        total_row = self.connection.execute(
            f"SELECT COUNT(*) AS total_count FROM policy_evaluations WHERE {where_sql}",
            values,
        ).fetchone()
        decision_counts = self._count_by("decision", where_sql, values)
        mode_counts = self._count_by("mode", where_sql, values)
        action_counts = self._count_by("action", where_sql, values)
        bucket_rows = self.connection.execute(
            f"""
            SELECT substr(created_at, 1, 10) AS bucket, decision, COUNT(*) AS count
            FROM policy_evaluations
            WHERE {where_sql}
            GROUP BY bucket, decision
            ORDER BY bucket ASC
            """,
            values,
        ).fetchall()
        buckets: dict[str, PolicyEvaluationTimeBucket] = {}
        for row in bucket_rows:
            bucket = row["bucket"]
            current = buckets.setdefault(
                bucket,
                PolicyEvaluationTimeBucket(bucket=bucket, total_count=0, decision_counts={}),
            )
            count = int(row["count"])
            current.total_count += count
            current.decision_counts[row["decision"]] = count
        return PolicyEvaluationSummaryResponse(
            total_count=int(total_row["total_count"]) if total_row else 0,
            decision_counts=decision_counts,
            mode_counts=mode_counts,
            action_counts=action_counts,
            time_buckets=list(buckets.values()),
        )

    def stream(
        self,
        query: PolicyEvaluationQuery,
        *,
        last_event_id: str | None = None,
    ) -> list[Row]:
        """Return rows in ascending stream order, optionally after an evaluation id."""

        clauses, values = _query_clauses(query)
        if last_event_id is not None:
            last_row = self.get(last_event_id, query.organization_id, query.environment_id)
            if last_row is not None:
                clauses.append("(created_at > ? OR (created_at = ? AND id > ?))")
                values.extend([last_row["created_at"], last_row["created_at"], last_row["id"]])
        values.append(query.limit)
        return self.connection.execute(
            f"""
            SELECT *
            FROM policy_evaluations
            WHERE {' AND '.join(clauses)}
            ORDER BY created_at ASC, id ASC
            LIMIT ?
            """,
            values,
        ).fetchall()

    def _count_by(self, column: str, where_sql: str, values: list[object]) -> dict[str, int]:
        rows = self.connection.execute(
            f"""
            SELECT {column} AS key, COUNT(*) AS count
            FROM policy_evaluations
            WHERE {where_sql}
            GROUP BY {column}
            ORDER BY {column} ASC
            """,
            values,
        ).fetchall()
        return {row["key"]: int(row["count"]) for row in rows if row["key"] is not None}


def policy_evaluation_response(row: Row) -> PolicyEvaluationResponse:
    """Serialize a persisted evaluation row."""

    return PolicyEvaluationResponse(
        id=row["id"],
        organization_id=row["organization_id"],
        environment_id=row["environment_id"],
        policy_id=row["policy_id"],
        policy_version_id=row["policy_version_id"],
        binding_id=row["binding_id"],
        binding_mode=row["binding_mode"],
        agent_id=row["agent_id"],
        target_type=row["target_type"],
        target_id=row["target_id"],
        action=row["action"],
        resource_type=row["resource_type"],
        resource_id=row["resource_id"],
        context=_loads_mapping(row["context_json"]),
        decision=row["decision"],
        policy_action=row["policy_action"],
        matched_rule=row["matched_rule"],
        reason=row["reason"],
        latency_ms=float(row["latency_ms"]),
        mode=row["mode"],
        correlation_id=row["correlation_id"],
        backend=row["backend"],
        error=bool(row["error"]),
        audit_preview=_loads_mapping(row["audit_preview_json"]),
        created_at=row["created_at"],
    )


def _loads_mapping(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    loaded = json.loads(raw)
    return loaded if isinstance(loaded, dict) else {}


def _query_clauses(query: PolicyEvaluationQuery) -> tuple[list[str], list[object]]:
    clauses = ["organization_id = ?", "environment_id = ?"]
    values: list[object] = [query.organization_id, query.environment_id]
    for column, value in [
        ("decision", query.decision),
        ("mode", query.mode),
        ("agent_id", query.agent_id),
        ("action", query.action),
        ("policy_id", query.policy_id),
        ("correlation_id", query.correlation_id),
    ]:
        if value is not None:
            clauses.append(f"{column} = ?")
            values.append(value)
    return clauses, values
