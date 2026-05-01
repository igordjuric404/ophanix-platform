"""Demo environment reset scope and execution helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from sqlite3 import Connection, Row
from typing import Any

from product_platform.audit.events import AuditEventEnvelope
from product_platform.audit.hash_chain import HASH_ALGORITHM, calculate_event_hash
from product_platform.audit.store import AuditEventRepository
from product_platform.db.ids import generate_id
from product_platform.db.seed import seed_demo_data
from product_platform.db.time import utc_now_iso
from product_platform.demo.models import DemoResetRunResponse, DemoResetStatus

RESET_CLEAR_ORDER = (
    "demo_step_runs",
    "demo_runs",
    "demo_lab_audit_events",
)

RESET_PRESERVED_TABLES = (
    "organizations",
    "environments",
    "users",
    "organization_memberships",
    "api_keys",
    "auth_sessions",
    "provider_credentials",
    "integrations",
    "integration_instances",
    "policy_placeholders",
    "demo_scenarios",
    "demo_steps",
    "demo_reset_runs",
)

RESET_DEMO_MARKER_TABLES = (
    "demo_runs",
    "demo_step_runs",
)


@dataclass(frozen=True)
class DemoResetScope:
    """Tables and markers used by local demo reset."""

    clear_order: tuple[str, ...] = RESET_CLEAR_ORDER
    preserved_tables: tuple[str, ...] = RESET_PRESERVED_TABLES
    marker_tables: tuple[str, ...] = RESET_DEMO_MARKER_TABLES


def demo_reset_scope() -> DemoResetScope:
    """Return the local demo reset scope."""

    return DemoResetScope()


class DemoResetNotFoundError(ValueError):
    """Raised when a reset run is not visible in the current tenant/environment."""


class DemoResetRepository:
    """Organization and environment scoped reset-run repository."""

    def __init__(self, connection: Connection, organization_id: str, environment_id: str) -> None:
        self.connection = connection
        self.organization_id = organization_id
        self.environment_id = environment_id

    def create_run(self, *, requested_by: str) -> Row:
        """Create a running reset history row."""

        now = utc_now_iso()
        reset_id = generate_id("demo_reset")
        self.connection.execute(
            """
            INSERT INTO demo_reset_runs (
                id, organization_id, environment_id, status, requested_by,
                started_at, finished_at, summary_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                reset_id,
                self.organization_id,
                self.environment_id,
                DemoResetStatus.RUNNING,
                requested_by,
                now,
                None,
                _json({"status": DemoResetStatus.RUNNING}),
                now,
                now,
            ),
        )
        return self.get_run(reset_id)

    def get_run(self, reset_id: str) -> Row:
        """Get one reset run in the current tenant/environment."""

        row = self.connection.execute(
            """
            SELECT *
            FROM demo_reset_runs
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            (reset_id, self.organization_id, self.environment_id),
        ).fetchone()
        if row is None:
            raise DemoResetNotFoundError("Reset run not found.")
        return row

    def get_optional(self, reset_id: str) -> Row | None:
        """Get one reset run or `None` when it is not visible."""

        try:
            return self.get_run(reset_id)
        except DemoResetNotFoundError:
            return None

    def list_runs(self, *, limit: int = 20, offset: int = 0) -> list[Row]:
        """List reset history in newest-first order."""

        return self.connection.execute(
            """
            SELECT *
            FROM demo_reset_runs
            WHERE organization_id = ? AND environment_id = ?
            ORDER BY started_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            (self.organization_id, self.environment_id, limit, offset),
        ).fetchall()

    def mark_succeeded(self, reset_id: str, summary: dict[str, Any]) -> Row:
        """Mark a reset run as succeeded."""

        return self._finish(reset_id, DemoResetStatus.SUCCEEDED, summary)

    def mark_failed(self, reset_id: str, summary: dict[str, Any]) -> Row:
        """Mark a reset run as failed."""

        return self._finish(reset_id, DemoResetStatus.FAILED, summary)

    def _finish(self, reset_id: str, status: str, summary: dict[str, Any]) -> Row:
        now = utc_now_iso()
        self.connection.execute(
            """
            UPDATE demo_reset_runs
            SET status = ?, finished_at = ?, summary_json = ?, updated_at = ?
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            (
                status,
                now,
                _json(summary),
                now,
                reset_id,
                self.organization_id,
                self.environment_id,
            ),
        )
        return self.get_run(reset_id)


class DemoEnvironmentResetService:
    """Executes local demo reset synchronously for the selected environment."""

    def __init__(
        self,
        connection: Connection,
        organization_id: str,
        environment_id: str,
        *,
        audit_repository: AuditEventRepository | None = None,
    ) -> None:
        self.connection = connection
        self.organization_id = organization_id
        self.environment_id = environment_id
        self.repository = DemoResetRepository(connection, organization_id, environment_id)
        self.audit_repository = audit_repository or AuditEventRepository(connection)

    def reset(self, *, requested_by: str, correlation_id: str | None = None) -> Row:
        """Clear scenario-generated state, reload seeds, and emit a reset audit event."""

        reset_run = self.repository.create_run(requested_by=requested_by)
        try:
            cleared = self._clear_demo_state()
            seed_demo_data(self.connection)
            seeded = self._seeded_counts()
            preserved = self._preserved_counts()
            summary = {
                "status": DemoResetStatus.SUCCEEDED,
                "cleared": cleared,
                "seeded": seeded,
                "preserved": preserved,
                "scope": {
                    "clear_order": list(demo_reset_scope().clear_order),
                    "preserved_tables": list(demo_reset_scope().preserved_tables),
                },
            }
            completed = self.repository.mark_succeeded(reset_run["id"], summary)
            self.audit_repository.insert(
                demo_reset_audit_event(
                    organization_id=self.organization_id,
                    environment_id=self.environment_id,
                    actor_id=requested_by,
                    reset_id=completed["id"],
                    status=completed["status"],
                    summary=summary,
                    correlation_id=correlation_id,
                )
            )
            return completed
        except Exception as exc:
            summary = {
                "status": DemoResetStatus.FAILED,
                "error": str(exc),
            }
            failed = self.repository.mark_failed(reset_run["id"], summary)
            self.audit_repository.insert(
                demo_reset_audit_event(
                    organization_id=self.organization_id,
                    environment_id=self.environment_id,
                    actor_id=requested_by,
                    reset_id=failed["id"],
                    status=failed["status"],
                    summary=summary,
                    correlation_id=correlation_id,
                    event_type="demo.reset.failed",
                )
            )
            return failed

    def _clear_demo_state(self) -> dict[str, int]:
        step_runs_deleted = self.connection.execute(
            """
            DELETE FROM demo_step_runs
            WHERE demo_run_id IN (
                SELECT id
                FROM demo_runs
                WHERE organization_id = ? AND environment_id = ?
            )
            """,
            (self.organization_id, self.environment_id),
        ).rowcount
        runs_deleted = self.connection.execute(
            """
            DELETE FROM demo_runs
            WHERE organization_id = ? AND environment_id = ?
            """,
            (self.organization_id, self.environment_id),
        ).rowcount
        audit_hashes_deleted = self.connection.execute(
            """
            DELETE FROM audit_event_hashes
            WHERE event_id IN (
                SELECT id
                FROM audit_events
                WHERE organization_id = ?
                  AND environment_id = ?
                  AND source_component = 'demo-lab'
            )
            """,
            (self.organization_id, self.environment_id),
        ).rowcount
        audit_events_deleted = self.connection.execute(
            """
            DELETE FROM audit_events
            WHERE organization_id = ?
              AND environment_id = ?
              AND source_component = 'demo-lab'
            """,
            (self.organization_id, self.environment_id),
        ).rowcount
        _rebuild_audit_hash_chain(self.connection, self.organization_id)
        return {
            "demo_step_runs": int(step_runs_deleted),
            "demo_runs": int(runs_deleted),
            "demo_lab_audit_hashes": int(audit_hashes_deleted),
            "demo_lab_audit_events": int(audit_events_deleted),
        }

    def _seeded_counts(self) -> dict[str, int]:
        return {
            "policy_placeholders": _count(
                self.connection,
                "policy_placeholders",
                "organization_id = ? AND environment_id = ?",
                (self.organization_id, self.environment_id),
            ),
            "demo_scenarios": _count(
                self.connection,
                "demo_scenarios",
                "organization_id = ? AND environment_id = ?",
                (self.organization_id, self.environment_id),
            ),
            "demo_steps": int(
                self.connection.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM demo_steps ds
                    JOIN demo_scenarios sc ON sc.id = ds.scenario_id
                    WHERE sc.organization_id = ? AND sc.environment_id = ?
                    """,
                    (self.organization_id, self.environment_id),
                ).fetchone()["count"]
            ),
        }

    def _preserved_counts(self) -> dict[str, int]:
        return {
            "users": _count(self.connection, "users", "1 = 1", ()),
            "organizations": _count(self.connection, "organizations", "id = ?", (self.organization_id,)),
            "environments": _count(
                self.connection,
                "environments",
                "id = ? AND organization_id = ?",
                (self.environment_id, self.organization_id),
            ),
            "provider_credentials": _count(
                self.connection,
                "provider_credentials",
                "organization_id = ?",
                (self.organization_id,),
            ),
        }


def query_demo_markers(
    connection: Connection,
    *,
    organization_id: str,
    environment_id: str,
) -> dict[str, int]:
    """Return queryable counts of scenario-owned demo records."""

    run_count = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM demo_runs
        WHERE organization_id = ? AND environment_id = ?
        """,
        (organization_id, environment_id),
    ).fetchone()["count"]
    step_run_count = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM demo_step_runs dsr
        JOIN demo_runs dr ON dr.id = dsr.demo_run_id
        WHERE dr.organization_id = ? AND dr.environment_id = ?
        """,
        (organization_id, environment_id),
    ).fetchone()["count"]
    return {
        "demo_runs": int(run_count),
        "demo_step_runs": int(step_run_count),
    }


def demo_reset_run_response(row: Row) -> DemoResetRunResponse:
    """Serialize a reset run row."""

    return DemoResetRunResponse(
        id=row["id"],
        organization_id=row["organization_id"],
        environment_id=row["environment_id"],
        status=row["status"],
        requested_by=row["requested_by"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        summary=json.loads(row["summary_json"] or "{}"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def demo_reset_audit_event(
    *,
    organization_id: str,
    environment_id: str,
    actor_id: str,
    reset_id: str,
    status: str,
    summary: dict[str, Any],
    correlation_id: str | None = None,
    event_type: str = "demo.reset.completed",
) -> AuditEventEnvelope:
    """Build a canonical audit event for reset completion."""

    return AuditEventEnvelope(
        organization_id=organization_id,
        environment_id=environment_id,
        event_type=event_type,
        source_component="demo-lab",
        actor_type="user",
        actor_id=actor_id,
        resource_type="demo_reset",
        resource_id=reset_id,
        severity="error" if status == DemoResetStatus.FAILED else "info",
        correlation_id=correlation_id,
        payload_json={"status": status, "summary": summary},
    )


def _rebuild_audit_hash_chain(connection: Connection, organization_id: str) -> None:
    rows = connection.execute(
        """
        SELECT *
        FROM audit_events
        WHERE organization_id = ?
        ORDER BY created_at ASC, id ASC
        """,
        (organization_id,),
    ).fetchall()
    connection.execute(
        """
        DELETE FROM audit_event_hashes
        WHERE event_id IN (
            SELECT id FROM audit_events WHERE organization_id = ?
        )
        """,
        (organization_id,),
    )
    previous_hash: str | None = None
    now = utc_now_iso()
    for row in rows:
        event = AuditEventEnvelope(
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
            payload_json=json.loads(row["payload_json"] or "{}"),
            created_at=row["created_at"],
        )
        current_hash = calculate_event_hash(event, previous_hash)
        connection.execute(
            """
            INSERT INTO audit_event_hashes
                (event_id, previous_hash, current_hash, algorithm, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (event.id, previous_hash, current_hash, HASH_ALGORITHM, now),
        )
        previous_hash = current_hash


def _count(
    connection: Connection,
    table_name: str,
    where_sql: str,
    values: tuple[object, ...],
) -> int:
    row = connection.execute(
        f"SELECT COUNT(*) AS count FROM {table_name} WHERE {where_sql}",
        values,
    ).fetchone()
    return int(row["count"])


def _json(value: dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True)
