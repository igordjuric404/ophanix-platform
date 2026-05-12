"""Saga definition persistence and validation."""

from __future__ import annotations

import json
from product_platform.db.postgres import Connection, Row

from product_platform.db.ids import generate_id
from product_platform.db.time import utc_now_iso
from product_platform.runtime.models import (
    SagaCreateRequest,
    SagaEventResponse,
    SagaResponse,
    SagaStepCreateRequest,
    SagaStepResponse,
)


class SagaNotFoundError(ValueError):
    """Raised when a saga is not visible in tenant scope."""


class SagaStepValidationError(ValueError):
    """Raised when a saga step is invalid."""


class SagaRepository:
    """Tenant-scoped saga definition repository."""

    def __init__(self, connection: Connection, organization_id: str, environment_id: str) -> None:
        self.connection = connection
        self.organization_id = organization_id
        self.environment_id = environment_id

    def create_saga(self, body: SagaCreateRequest, *, created_by: str) -> Row:
        """Create a draft saga."""

        if body.runtime_session_id:
            self._require_runtime_session(body.runtime_session_id)
        saga_id = generate_id("saga")
        now = utc_now_iso()
        self.connection.execute(
            """
            INSERT INTO sagas (
                id, organization_id, environment_id, runtime_session_id, name,
                status, created_by, started_at, finished_at, correlation_id,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                saga_id,
                self.organization_id,
                self.environment_id,
                body.runtime_session_id,
                body.name,
                "draft",
                created_by,
                None,
                None,
                body.correlation_id,
                now,
                now,
            ),
        )
        self.create_event(
            saga_id,
            event_type="saga.created",
            message="Saga draft created.",
            payload={"name": body.name},
        )
        row = self.get_saga(saga_id)
        if row is None:
            raise SagaNotFoundError("Created saga could not be loaded.")
        return row

    def get_saga(self, saga_id: str) -> Row | None:
        """Get one saga by tenant scope."""

        return self.connection.execute(
            """
            SELECT *
            FROM sagas
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            (saga_id, self.organization_id, self.environment_id),
        ).fetchone()

    def list_sagas(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Row]:
        """List sagas."""

        clauses = ["organization_id = ?", "environment_id = ?"]
        values: list[object] = [self.organization_id, self.environment_id]
        if status:
            clauses.append("status = ?")
            values.append(status)
        values.extend([limit, offset])
        return self.connection.execute(
            f"""
            SELECT *
            FROM sagas
            WHERE {' AND '.join(clauses)}
            ORDER BY created_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            values,
        ).fetchall()

    def add_step(self, saga_id: str, body: SagaStepCreateRequest) -> Row:
        """Add an ordered step to a draft saga."""

        saga = self.get_saga(saga_id)
        if saga is None:
            raise SagaNotFoundError("Saga not found.")
        if saga["status"] != "draft":
            raise SagaStepValidationError("Saga steps can only be changed while draft.")
        expected_order = self.next_step_order(saga_id)
        if body.step_order != expected_order:
            raise SagaStepValidationError(f"Next saga step_order must be {expected_order}.")
        self._require_active_agent(body.target_agent_id)
        if body.required_capability:
            self._require_agent_capability(body.target_agent_id, body.required_capability)
        step_id = generate_id("sgstep")
        now = utc_now_iso()
        self.connection.execute(
            """
            INSERT INTO saga_steps (
                id, saga_id, step_order, name, action_name, target_agent_id,
                required_capability, timeout_seconds, retry_count,
                compensation_action, status, result_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                step_id,
                saga_id,
                body.step_order,
                body.name,
                body.action_name,
                body.target_agent_id,
                body.required_capability,
                body.timeout_seconds,
                body.retry_count,
                body.compensation_action,
                "pending",
                "{}",
                now,
                now,
            ),
        )
        self.connection.execute("UPDATE sagas SET updated_at = ? WHERE id = ?", (now, saga_id))
        self.create_event(
            saga_id,
            step_id=step_id,
            event_type="saga.step.added",
            message=f"Step {body.step_order} added.",
            payload={"action_name": body.action_name},
        )
        row = self.get_step(step_id)
        if row is None:
            raise SagaStepValidationError("Created saga step could not be loaded.")
        return row

    def next_step_order(self, saga_id: str) -> int:
        """Return the next contiguous step order for a saga."""

        row = self.connection.execute(
            "SELECT COALESCE(MAX(step_order), 0) + 1 AS next_order FROM saga_steps WHERE saga_id = ?",
            (saga_id,),
        ).fetchone()
        return int(row["next_order"])

    def get_step(self, step_id: str) -> Row | None:
        """Get one saga step with target agent context."""

        return self.connection.execute(
            """
            SELECT
                s.*,
                a.name AS target_agent_name
            FROM saga_steps s
            JOIN sagas saga ON saga.id = s.saga_id
            JOIN agents a ON a.id = s.target_agent_id
            WHERE s.id = ?
              AND saga.organization_id = ?
              AND saga.environment_id = ?
            """,
            (step_id, self.organization_id, self.environment_id),
        ).fetchone()

    def list_steps(self, saga_id: str) -> list[Row]:
        """List saga steps in execution order."""

        return self.connection.execute(
            """
            SELECT
                s.*,
                a.name AS target_agent_name
            FROM saga_steps s
            JOIN sagas saga ON saga.id = s.saga_id
            JOIN agents a ON a.id = s.target_agent_id
            WHERE s.saga_id = ?
              AND saga.organization_id = ?
              AND saga.environment_id = ?
            ORDER BY s.step_order ASC
            """,
            (saga_id, self.organization_id, self.environment_id),
        ).fetchall()

    def update_saga_status(
        self,
        saga_id: str,
        status: str,
        *,
        mark_started: bool = False,
        mark_finished: bool = False,
    ) -> Row:
        """Update saga lifecycle status and timestamps."""

        saga = self.get_saga(saga_id)
        if saga is None:
            raise SagaNotFoundError("Saga not found.")
        now = utc_now_iso()
        started_at = saga["started_at"]
        finished_at = saga["finished_at"]
        if mark_started and started_at is None:
            started_at = now
        if mark_finished:
            finished_at = now
        self.connection.execute(
            """
            UPDATE sagas
            SET status = ?,
                started_at = ?,
                finished_at = ?,
                updated_at = ?
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            (
                status,
                started_at,
                finished_at,
                now,
                saga_id,
                self.organization_id,
                self.environment_id,
            ),
        )
        row = self.get_saga(saga_id)
        if row is None:
            raise SagaNotFoundError("Updated saga could not be loaded.")
        return row

    def link_runtime_session(self, saga_id: str, runtime_session_id: str) -> Row:
        """Attach a runtime session to a saga."""

        if self.get_saga(saga_id) is None:
            raise SagaNotFoundError("Saga not found.")
        self._require_runtime_session(runtime_session_id)
        self.connection.execute(
            """
            UPDATE sagas
            SET runtime_session_id = ?,
                updated_at = ?
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            (
                runtime_session_id,
                utc_now_iso(),
                saga_id,
                self.organization_id,
                self.environment_id,
            ),
        )
        self.create_event(
            saga_id,
            event_type="saga.runtime_session.linked",
            message="Runtime session linked to saga.",
            payload={"runtime_session_id": runtime_session_id},
        )
        row = self.get_saga(saga_id)
        if row is None:
            raise SagaNotFoundError("Linked saga could not be loaded.")
        return row

    def update_step_status(
        self,
        step_id: str,
        status: str,
        *,
        result: dict | None = None,
    ) -> Row:
        """Persist one saga step status/result transition."""

        if self.get_step(step_id) is None:
            raise SagaStepValidationError("Saga step not found.")
        self.connection.execute(
            """
            UPDATE saga_steps
            SET status = ?,
                result_json = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (status, json.dumps(result or {}, sort_keys=True), utc_now_iso(), step_id),
        )
        row = self.get_step(step_id)
        if row is None:
            raise SagaStepValidationError("Updated saga step could not be loaded.")
        return row

    def create_event(
        self,
        saga_id: str,
        *,
        event_type: str,
        message: str,
        payload: dict | None = None,
        step_id: str | None = None,
    ) -> Row:
        """Persist a saga event."""

        event_id = generate_id("sgevt")
        self.connection.execute(
            """
            INSERT INTO saga_events (
                id, saga_id, step_id, event_type, message, payload_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                saga_id,
                step_id,
                event_type,
                message,
                json.dumps(payload or {}, sort_keys=True),
                utc_now_iso(),
            ),
        )
        return self.connection.execute("SELECT * FROM saga_events WHERE id = ?", (event_id,)).fetchone()

    def list_events(self, saga_id: str) -> list[Row]:
        """List saga events in chronological order."""

        return self.connection.execute(
            """
            SELECT e.*
            FROM saga_events e
            JOIN sagas s ON s.id = e.saga_id
            WHERE e.saga_id = ?
              AND s.organization_id = ?
              AND s.environment_id = ?
            ORDER BY e.created_at ASC, e.id ASC
            """,
            (saga_id, self.organization_id, self.environment_id),
        ).fetchall()

    def _require_runtime_session(self, session_id: str) -> None:
        row = self.connection.execute(
            """
            SELECT 1
            FROM runtime_sessions
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            (session_id, self.organization_id, self.environment_id),
        ).fetchone()
        if row is None:
            raise SagaStepValidationError("Runtime session not found.")

    def _require_active_agent(self, agent_id: str) -> None:
        row = self.connection.execute(
            """
            SELECT 1
            FROM agents
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
              AND status = 'active'
              AND deleted_at IS NULL
            """,
            (agent_id, self.organization_id, self.environment_id),
        ).fetchone()
        if row is None:
            raise SagaStepValidationError("Saga step target agent must be active.")

    def _require_agent_capability(self, agent_id: str, capability: str) -> None:
        row = self.connection.execute(
            """
            SELECT 1
            FROM agent_capabilities
            WHERE agent_id = ?
              AND capability_name = ?
              AND status = 'approved'
            """,
            (agent_id, capability),
        ).fetchone()
        if row is None:
            raise SagaStepValidationError(f"Agent does not have approved capability: {capability}.")


def saga_step_response(row: Row) -> SagaStepResponse:
    """Serialize a saga step row."""

    return SagaStepResponse(
        id=row["id"],
        saga_id=row["saga_id"],
        step_order=row["step_order"],
        name=row["name"],
        action_name=row["action_name"],
        target_agent_id=row["target_agent_id"],
        target_agent_name=row["target_agent_name"],
        required_capability=row["required_capability"],
        timeout_seconds=row["timeout_seconds"],
        retry_count=row["retry_count"],
        compensation_action=row["compensation_action"],
        status=row["status"],
        result=json.loads(row["result_json"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def saga_event_response(row: Row) -> SagaEventResponse:
    """Serialize a saga event row."""

    return SagaEventResponse(
        id=row["id"],
        saga_id=row["saga_id"],
        step_id=row["step_id"],
        event_type=row["event_type"],
        message=row["message"],
        payload=json.loads(row["payload_json"]),
        created_at=row["created_at"],
    )


def saga_response(
    row: Row,
    *,
    steps: list[SagaStepResponse] | None = None,
    events: list[SagaEventResponse] | None = None,
) -> SagaResponse:
    """Serialize a saga row."""

    return SagaResponse(
        id=row["id"],
        organization_id=row["organization_id"],
        environment_id=row["environment_id"],
        runtime_session_id=row["runtime_session_id"],
        name=row["name"],
        status=row["status"],
        created_by=row["created_by"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        correlation_id=row["correlation_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        steps=steps or [],
        events=events or [],
    )
