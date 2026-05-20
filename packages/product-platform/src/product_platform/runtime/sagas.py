"""Saga definition persistence and validation."""

from __future__ import annotations

import hashlib
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
from product_platform.runtime.saga_actions import validate_saga_action_name


SAGA_TERMINAL_STATUSES = frozenset(
    {"completed", "compensated", "failed", "compensation_failed", "cancelled"}
)
SAGA_EXECUTABLE_STATUSES = frozenset({"draft"})
SAGA_RECOVERABLE_STATUSES = frozenset({"running"})
SAGA_ACTIVITY_MODES = frozenset({"execute", "compensation"})
SAGA_ACTIVITY_STATUSES = frozenset({"started", "succeeded", "failed"})


class SagaNotFoundError(ValueError):
    """Raised when a saga is not visible in tenant scope."""


class SagaStepValidationError(ValueError):
    """Raised when a saga step is invalid."""


class SagaStateTransitionError(ValueError):
    """Raised when a saga lifecycle transition loses a state guard."""


class SagaActivityResultError(ValueError):
    """Raised when a durable saga activity result is invalid."""


class SagaCheckpointError(ValueError):
    """Raised when a durable saga checkpoint is invalid."""


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
        try:
            validate_saga_action_name(body.action_name, field_name="action_name")
            validate_saga_action_name(body.compensation_action, field_name="compensation_action")
        except ValueError as exc:
            raise SagaStepValidationError(str(exc)) from exc
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
        expected_statuses: set[str] | frozenset[str] | None = None,
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
        expected = tuple(sorted(expected_statuses or ()))
        expected_clause = ""
        values: list[object] = [
            status,
            started_at,
            finished_at,
            now,
            saga_id,
            self.organization_id,
            self.environment_id,
        ]
        if expected:
            expected_clause = f" AND status IN ({', '.join('?' for _ in expected)})"
            values.extend(expected)
        cursor = self.connection.execute(
            f"""
            UPDATE sagas
            SET status = ?,
                started_at = ?,
                finished_at = ?,
                updated_at = ?
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
              {expected_clause}
            """,
            values,
        )
        if expected and cursor.rowcount == 0:
            current = self.get_saga(saga_id)
            if current is None:
                raise SagaNotFoundError("Saga not found.")
            expected_label = ", ".join(expected)
            raise SagaStateTransitionError(
                f"Saga cannot transition from {current['status']} to {status}; expected one of: {expected_label}."
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

    def start_activity_result(
        self,
        *,
        saga_id: str,
        step_id: str,
        mode: str,
        action_name: str,
    ) -> Row:
        """Record an activity attempt before executing a side effect."""

        mode = _validate_activity_mode(mode)
        existing = self.get_activity_result(step_id, mode)
        now = utc_now_iso()
        if existing is not None:
            if existing["status"] == "succeeded":
                return existing
            self.connection.execute(
                """
                UPDATE saga_activity_results
                SET status = ?,
                    action_name = ?,
                    attempt_count = attempt_count + 1,
                    error_message = NULL,
                    updated_at = ?
                WHERE id = ?
                """,
                ("started", action_name, now, existing["id"]),
            )
            row = self.get_activity_result(step_id, mode)
            if row is None:
                raise SagaActivityResultError("Started activity result could not be loaded.")
            return row
        self._require_saga_step(saga_id, step_id)
        activity_id = generate_id("sgact")
        self.connection.execute(
            """
            INSERT INTO saga_activity_results (
                id, saga_id, step_id, activity_key, action_name, mode, status,
                attempt_count, result_json, error_message, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                activity_id,
                saga_id,
                step_id,
                _activity_key(saga_id, step_id, mode),
                action_name,
                mode,
                "started",
                1,
                "{}",
                None,
                now,
                now,
            ),
        )
        row = self.get_activity_result(step_id, mode)
        if row is None:
            raise SagaActivityResultError("Created activity result could not be loaded.")
        return row

    def complete_activity_result(
        self,
        *,
        saga_id: str,
        step_id: str,
        mode: str,
        action_name: str,
        result: dict,
    ) -> Row:
        """Persist a completed activity result for future replay."""

        mode = _validate_activity_mode(mode)
        existing = self.get_activity_result(step_id, mode)
        now = utc_now_iso()
        payload = json.dumps(result or {}, sort_keys=True)
        if existing is None:
            self._require_saga_step(saga_id, step_id)
            activity_id = generate_id("sgact")
            self.connection.execute(
                """
                INSERT INTO saga_activity_results (
                    id, saga_id, step_id, activity_key, action_name, mode, status,
                    attempt_count, result_json, error_message, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    activity_id,
                    saga_id,
                    step_id,
                    _activity_key(saga_id, step_id, mode),
                    action_name,
                    mode,
                    "succeeded",
                    1,
                    payload,
                    None,
                    now,
                    now,
                ),
            )
        elif existing["status"] != "succeeded":
            self.connection.execute(
                """
                UPDATE saga_activity_results
                SET action_name = ?,
                    status = ?,
                    result_json = ?,
                    error_message = NULL,
                    updated_at = ?
                WHERE id = ?
                """,
                (action_name, "succeeded", payload, now, existing["id"]),
            )
        row = self.get_activity_result(step_id, mode)
        if row is None:
            raise SagaActivityResultError("Completed activity result could not be loaded.")
        return row

    def fail_activity_result(
        self,
        *,
        saga_id: str,
        step_id: str,
        mode: str,
        action_name: str,
        error_message: str,
    ) -> Row:
        """Persist a failed activity attempt."""

        mode = _validate_activity_mode(mode)
        existing = self.get_activity_result(step_id, mode)
        now = utc_now_iso()
        if existing is None:
            self._require_saga_step(saga_id, step_id)
            activity_id = generate_id("sgact")
            self.connection.execute(
                """
                INSERT INTO saga_activity_results (
                    id, saga_id, step_id, activity_key, action_name, mode, status,
                    attempt_count, result_json, error_message, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    activity_id,
                    saga_id,
                    step_id,
                    _activity_key(saga_id, step_id, mode),
                    action_name,
                    mode,
                    "failed",
                    1,
                    "{}",
                    error_message,
                    now,
                    now,
                ),
            )
        else:
            self.connection.execute(
                """
                UPDATE saga_activity_results
                SET action_name = ?,
                    status = ?,
                    error_message = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (action_name, "failed", error_message, now, existing["id"]),
            )
        row = self.get_activity_result(step_id, mode)
        if row is None:
            raise SagaActivityResultError("Failed activity result could not be loaded.")
        return row

    def get_activity_result(self, step_id: str, mode: str) -> Row | None:
        """Get the durable activity result for one step and mode."""

        mode = _validate_activity_mode(mode)
        return self.connection.execute(
            """
            SELECT ar.*
            FROM saga_activity_results ar
            JOIN sagas s ON s.id = ar.saga_id
            WHERE ar.step_id = ?
              AND ar.mode = ?
              AND s.organization_id = ?
              AND s.environment_id = ?
            """,
            (step_id, mode, self.organization_id, self.environment_id),
        ).fetchone()

    def list_activity_results(self, saga_id: str) -> list[Row]:
        """List durable activity results for one saga."""

        return self.connection.execute(
            """
            SELECT ar.*
            FROM saga_activity_results ar
            JOIN sagas s ON s.id = ar.saga_id
            WHERE ar.saga_id = ?
              AND s.organization_id = ?
              AND s.environment_id = ?
            ORDER BY ar.created_at ASC, ar.id ASC
            """,
            (saga_id, self.organization_id, self.environment_id),
        ).fetchall()

    def create_checkpoint(
        self,
        *,
        saga_id: str,
        step_id: str,
        mode: str,
        payload: dict,
        policy_snapshot: dict | None = None,
        tool_calls: list[dict] | None = None,
        error: dict | None = None,
        schema_version: str = "saga-checkpoint.v1",
    ) -> Row:
        """Create a durable, hash-verified checkpoint for one saga step."""

        mode = _validate_activity_mode(mode)
        context = self._require_saga_step_context(saga_id, step_id)
        saga = context["saga"]
        payload_json = json.dumps(payload or {}, sort_keys=True)
        policy_snapshot_json = json.dumps(policy_snapshot or {}, sort_keys=True)
        tool_calls_json = json.dumps(tool_calls or [], sort_keys=True)
        error_json = json.dumps(error or {}, sort_keys=True)
        payload_hash = _checkpoint_hash(
            schema_version=schema_version,
            payload_json=payload_json,
            policy_snapshot_json=policy_snapshot_json,
            tool_calls_json=tool_calls_json,
            error_json=error_json,
        )
        existing = self.get_checkpoint(step_id, mode)
        if existing is not None:
            if existing["payload_hash"] != payload_hash:
                raise SagaCheckpointError("Existing checkpoint hash differs from requested payload.")
            self._verify_checkpoint_row(existing)
            return existing

        checkpoint_id = generate_id("sgchk")
        now = utc_now_iso()
        self.connection.execute(
            """
            INSERT INTO saga_checkpoints (
                id, organization_id, environment_id, saga_id, step_id, runtime_session_id,
                checkpoint_key, mode, schema_version, status, payload_json,
                policy_snapshot_json, tool_calls_json, error_json, payload_hash,
                hash_algorithm, restored_at, invalidated_reason, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                checkpoint_id,
                self.organization_id,
                self.environment_id,
                saga_id,
                step_id,
                saga["runtime_session_id"],
                _checkpoint_key(saga_id, step_id, mode),
                mode,
                schema_version,
                "valid",
                payload_json,
                policy_snapshot_json,
                tool_calls_json,
                error_json,
                payload_hash,
                "sha256",
                None,
                None,
                now,
                now,
            ),
        )
        row = self.get_checkpoint(step_id, mode)
        if row is None:
            raise SagaCheckpointError("Created checkpoint could not be loaded.")
        return row

    def get_checkpoint(self, step_id: str, mode: str) -> Row | None:
        """Return the durable checkpoint for one step and mode."""

        mode = _validate_activity_mode(mode)
        return self.connection.execute(
            """
            SELECT sc.*
            FROM saga_checkpoints sc
            WHERE sc.step_id = ?
              AND sc.mode = ?
              AND sc.organization_id = ?
              AND sc.environment_id = ?
            """,
            (step_id, mode, self.organization_id, self.environment_id),
        ).fetchone()

    def restore_checkpoint(self, step_id: str, mode: str) -> Row:
        """Verify and mark a checkpoint as restored for replay."""

        checkpoint = self.get_checkpoint(step_id, mode)
        if checkpoint is None:
            raise SagaCheckpointError("Checkpoint not found.")
        self._verify_checkpoint_row(checkpoint)
        now = utc_now_iso()
        self.connection.execute(
            """
            UPDATE saga_checkpoints
            SET restored_at = ?,
                updated_at = ?
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            (
                now,
                now,
                checkpoint["id"],
                self.organization_id,
                self.environment_id,
            ),
        )
        row = self.get_checkpoint(step_id, mode)
        if row is None:
            raise SagaCheckpointError("Restored checkpoint could not be loaded.")
        return row

    def list_checkpoints(self, saga_id: str) -> list[Row]:
        """List durable checkpoints for one saga."""

        return self.connection.execute(
            """
            SELECT sc.*
            FROM saga_checkpoints sc
            WHERE sc.saga_id = ?
              AND sc.organization_id = ?
              AND sc.environment_id = ?
            ORDER BY sc.created_at ASC, sc.id ASC
            """,
            (saga_id, self.organization_id, self.environment_id),
        ).fetchall()

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

    def _require_saga_step(self, saga_id: str, step_id: str) -> None:
        row = self.connection.execute(
            """
            SELECT 1
            FROM saga_steps st
            JOIN sagas s ON s.id = st.saga_id
            WHERE st.id = ?
              AND st.saga_id = ?
              AND s.organization_id = ?
              AND s.environment_id = ?
            """,
            (step_id, saga_id, self.organization_id, self.environment_id),
        ).fetchone()
        if row is None:
            raise SagaActivityResultError("Saga step not found for activity result.")

    def _require_saga_step_context(self, saga_id: str, step_id: str) -> dict[str, Row]:
        saga = self.get_saga(saga_id)
        if saga is None:
            raise SagaNotFoundError("Saga not found.")
        step = self.get_step(step_id)
        if step is None or step["saga_id"] != saga_id:
            raise SagaCheckpointError("Saga step not found for checkpoint.")
        return {"saga": saga, "step": step}

    def _verify_checkpoint_row(self, checkpoint: Row) -> None:
        if checkpoint["status"] != "valid":
            reason = checkpoint["invalidated_reason"] or "Checkpoint is not valid."
            raise SagaCheckpointError(reason)
        expected = _checkpoint_hash(
            schema_version=checkpoint["schema_version"],
            payload_json=checkpoint["payload_json"],
            policy_snapshot_json=checkpoint["policy_snapshot_json"],
            tool_calls_json=checkpoint["tool_calls_json"],
            error_json=checkpoint["error_json"],
        )
        if checkpoint["payload_hash"] != expected:
            raise SagaCheckpointError("Checkpoint integrity verification failed.")


def _validate_activity_mode(mode: str) -> str:
    normalized = mode.strip().lower()
    if normalized not in SAGA_ACTIVITY_MODES:
        supported = ", ".join(sorted(SAGA_ACTIVITY_MODES))
        raise SagaActivityResultError(f"activity mode must be one of: {supported}.")
    return normalized


def _activity_key(saga_id: str, step_id: str, mode: str) -> str:
    return f"{saga_id}:{step_id}:{mode}"


def _checkpoint_key(saga_id: str, step_id: str, mode: str) -> str:
    return f"{saga_id}:{step_id}:{mode}:checkpoint"


def _checkpoint_hash(
    *,
    schema_version: str,
    payload_json: str,
    policy_snapshot_json: str,
    tool_calls_json: str,
    error_json: str,
) -> str:
    canonical = json.dumps(
        {
            "schema_version": schema_version,
            "payload": json.loads(payload_json),
            "policy_snapshot": json.loads(policy_snapshot_json),
            "tool_calls": json.loads(tool_calls_json),
            "error": json.loads(error_json),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


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
