"""Workflow catalog repository."""

from __future__ import annotations

import json
from product_platform.db.postgres import Connection, Row
from typing import Any

from product_platform.db.ids import generate_id
from product_platform.db.time import utc_now_iso
from product_platform.workflows.models import WorkflowDefinitionResponse
from product_platform.workflows.models import WorkflowRunResponse, validate_workflow_inputs
from product_platform.workflows.runner import WorkflowRunResult


class WorkflowRepository:
    """Read registered workflow definitions."""

    def __init__(self, connection: Connection, organization_id: str) -> None:
        self.connection = connection
        self.organization_id = organization_id

    def list_definitions(
        self,
        *,
        enabled: bool | None = None,
        workflow_type: str | None = None,
    ) -> list[Row]:
        """List workflow definitions in stable catalog order."""

        clauses = ["organization_id = ?"]
        values: list[object] = [self.organization_id]
        if enabled is not None:
            clauses.append("enabled = ?")
            values.append(1 if enabled else 0)
        if workflow_type:
            clauses.append("workflow_type = ?")
            values.append(workflow_type)
        return self.connection.execute(
            f"""
            SELECT *
            FROM workflow_definitions
            WHERE {' AND '.join(clauses)}
            ORDER BY workflow_type ASC, name ASC
            """,
            values,
        ).fetchall()

    def get_definition(self, workflow_definition_id: str) -> Row | None:
        return self.connection.execute(
            """
            SELECT *
            FROM workflow_definitions
            WHERE id = ?
              AND organization_id = ?
              AND enabled = 1
            """,
            (workflow_definition_id, self.organization_id),
        ).fetchone()

    def create_run(
        self,
        definition: Row,
        *,
        environment_id: str,
        inputs: dict[str, Any],
        started_by: str,
    ) -> Row:
        validate_workflow_inputs(json.loads(definition["input_schema_json"]), inputs)
        run_id = generate_id("wrun")
        now = utc_now_iso()
        self.connection.execute(
            """
            INSERT INTO workflow_runs (
                id, organization_id, environment_id, workflow_type, status,
                payload_json, created_at, updated_at, deleted_at,
                workflow_definition_id, inputs_json, started_by, started_at,
                finished_at, exit_code, summary_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                self.organization_id,
                environment_id,
                definition["workflow_type"],
                "queued",
                json.dumps(inputs, sort_keys=True),
                now,
                now,
                None,
                definition["id"],
                json.dumps(inputs, sort_keys=True),
                started_by,
                None,
                None,
                None,
                json.dumps({}, sort_keys=True),
            ),
        )
        row = self.get_run(run_id, environment_id=environment_id)
        if row is None:
            raise ValueError("Created workflow run could not be loaded.")
        return row

    def start_run(self, run_id: str, *, environment_id: str) -> Row:
        now = utc_now_iso()
        cursor = self.connection.execute(
            """
            UPDATE workflow_runs
            SET status = ?, started_at = COALESCE(started_at, ?), updated_at = ?
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
              AND status = ?
            """,
            ("running", now, now, run_id, self.organization_id, environment_id, "queued"),
        )
        if cursor.rowcount == 0:
            row = self.get_run(run_id, environment_id=environment_id)
            if row is None:
                raise ValueError("Workflow run not found.")
            raise RuntimeError("Workflow run is not queued.")
        row = self.get_run(run_id, environment_id=environment_id)
        if row is None:
            raise ValueError("Workflow run not found.")
        return row

    def complete_run(
        self,
        run_id: str,
        *,
        environment_id: str,
        result: WorkflowRunResult,
    ) -> Row:
        now = utc_now_iso()
        status = "succeeded" if result.status == "succeeded" else "failed"
        cursor = self.connection.execute(
            """
            UPDATE workflow_runs
            SET status = ?,
                finished_at = ?,
                exit_code = ?,
                summary_json = ?,
                updated_at = ?
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
              AND status = ?
            """,
            (
                status,
                now,
                result.exit_code,
                json.dumps(result.summary, sort_keys=True),
                now,
                run_id,
                self.organization_id,
                environment_id,
                "running",
            ),
        )
        if cursor.rowcount == 0:
            row = self.get_run(run_id, environment_id=environment_id)
            if row is None:
                raise ValueError("Workflow run not found.")
            raise RuntimeError("Workflow run is not running.")
        self.replace_logs(run_id, result.logs)
        row = self.get_run(run_id, environment_id=environment_id)
        if row is None:
            raise ValueError("Workflow run not found.")
        return row

    def requeue_run(
        self,
        run_id: str,
        *,
        environment_id: str,
        summary: dict[str, Any] | None = None,
    ) -> Row:
        """Move a failed workflow run back to queued for a scheduled worker retry."""

        now = utc_now_iso()
        cursor = self.connection.execute(
            """
            UPDATE workflow_runs
            SET status = ?,
                started_at = NULL,
                finished_at = NULL,
                exit_code = NULL,
                summary_json = ?,
                updated_at = ?
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
              AND status = ?
            """,
            (
                "queued",
                json.dumps(summary or {}, sort_keys=True),
                now,
                run_id,
                self.organization_id,
                environment_id,
                "failed",
            ),
        )
        if cursor.rowcount == 0:
            row = self.get_run(run_id, environment_id=environment_id)
            if row is None:
                raise ValueError("Workflow run not found.")
            raise RuntimeError("Workflow run is not failed.")
        row = self.get_run(run_id, environment_id=environment_id)
        if row is None:
            raise ValueError("Workflow run not found.")
        return row

    def cancel_run(self, run_id: str, *, environment_id: str) -> Row:
        row = self.get_run(run_id, environment_id=environment_id)
        if row is None:
            raise ValueError("Workflow run not found.")
        if row["status"] not in {"queued", "running"}:
            raise RuntimeError("Completed workflow runs cannot be canceled.")
        now = utc_now_iso()
        cursor = self.connection.execute(
            """
            UPDATE workflow_runs
            SET status = ?, finished_at = ?, updated_at = ?
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
              AND status IN (?, ?)
            """,
            ("canceled", now, now, run_id, self.organization_id, environment_id, "queued", "running"),
        )
        if cursor.rowcount == 0:
            raise RuntimeError("Completed workflow runs cannot be canceled.")
        canceled = self.get_run(run_id, environment_id=environment_id)
        if canceled is None:
            raise ValueError("Workflow run not found.")
        return canceled

    def replace_logs(self, run_id: str, logs: list[Any]) -> None:
        self.connection.execute("DELETE FROM workflow_logs WHERE workflow_run_id = ?", (run_id,))
        now = utc_now_iso()
        for index, log in enumerate(logs, start=1):
            self.connection.execute(
                """
                INSERT INTO workflow_logs (
                    id, workflow_run_id, stream, line_number, message, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    generate_id("wlog"),
                    run_id,
                    getattr(log, "stream", "stdout"),
                    getattr(log, "line_number", index),
                    getattr(log, "message", str(log)),
                    now,
                ),
            )

    def list_runs(
        self,
        *,
        environment_id: str,
        status: str | None = None,
        workflow_definition_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Row]:
        clauses = ["r.organization_id = ?", "r.environment_id = ?", "r.deleted_at IS NULL"]
        values: list[object] = [self.organization_id, environment_id]
        if status:
            clauses.append("r.status = ?")
            values.append(status)
        if workflow_definition_id:
            clauses.append("r.workflow_definition_id = ?")
            values.append(workflow_definition_id)
        values.extend([limit, offset])
        return self.connection.execute(
            f"""
            SELECT r.*, d.command_ref
            FROM workflow_runs r
            LEFT JOIN workflow_definitions d ON d.id = r.workflow_definition_id
            WHERE {' AND '.join(clauses)}
            ORDER BY r.created_at DESC, r.id DESC
            LIMIT ? OFFSET ?
            """,
            values,
        ).fetchall()

    def get_run(self, run_id: str, *, environment_id: str) -> Row | None:
        return self.connection.execute(
            """
            SELECT r.*, d.command_ref
            FROM workflow_runs r
            LEFT JOIN workflow_definitions d ON d.id = r.workflow_definition_id
            WHERE r.id = ?
              AND r.organization_id = ?
              AND r.environment_id = ?
              AND r.deleted_at IS NULL
            """,
            (run_id, self.organization_id, environment_id),
        ).fetchone()

    def logs_for_run(self, run_id: str) -> list[Row]:
        return self.connection.execute(
            """
            SELECT *
            FROM workflow_logs
            WHERE workflow_run_id = ?
            ORDER BY line_number ASC, id ASC
            """,
            (run_id,),
        ).fetchall()


def workflow_definition_response(row: Row) -> WorkflowDefinitionResponse:
    """Serialize one workflow definition row."""

    return WorkflowDefinitionResponse(
        id=row["id"],
        organization_id=row["organization_id"],
        name=row["name"],
        workflow_type=row["workflow_type"],
        command_ref=row["command_ref"],
        input_schema=json.loads(row["input_schema_json"]),
        enabled=bool(row["enabled"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def workflow_run_response(repository: WorkflowRepository, row: Row) -> WorkflowRunResponse:
    """Serialize one workflow run with logs."""

    return WorkflowRunResponse(
        id=row["id"],
        organization_id=row["organization_id"],
        environment_id=row["environment_id"],
        workflow_definition_id=row["workflow_definition_id"],
        workflow_type=row["workflow_type"],
        command_ref=row["command_ref"] if "command_ref" in row.keys() else None,
        status=row["status"],
        inputs=json.loads(row["inputs_json"] or row["payload_json"] or "{}"),
        started_by=row["started_by"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        exit_code=row["exit_code"],
        summary=json.loads(row["summary_json"] or "{}"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        logs=[
            {
                "id": log["id"],
                "workflow_run_id": log["workflow_run_id"],
                "stream": log["stream"],
                "line_number": log["line_number"],
                "message": log["message"],
                "created_at": log["created_at"],
            }
            for log in repository.logs_for_run(row["id"])
        ],
    )
