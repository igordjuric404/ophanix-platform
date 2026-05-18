"""Persistent job state repository."""

from __future__ import annotations

import json
from product_platform.db.postgres import Connection, Row
from typing import Any

from product_platform.db.ids import generate_id
from product_platform.db.time import utc_now_iso


class JobStatus:
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


class JobStateRepository:
    """Stores job state transitions and run metadata."""

    def __init__(self, connection: Connection) -> None:
        self.connection = connection

    def create_job(
        self,
        *,
        organization_id: str,
        environment_id: str,
        job_type: str,
        payload: dict[str, Any],
        scheduled_at: str | None = None,
        max_attempts: int = 3,
        job_id: str | None = None,
    ) -> Row:
        now = utc_now_iso()
        resolved_id = job_id or generate_id("job")
        self.connection.execute(
            """
            INSERT INTO background_jobs (
                id, organization_id, environment_id, job_type, status, payload_json,
                scheduled_at, attempts, max_attempts, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                resolved_id,
                organization_id,
                environment_id,
                job_type,
                JobStatus.QUEUED,
                json.dumps(payload, sort_keys=True),
                scheduled_at,
                0,
                max_attempts,
                now,
                now,
            ),
        )
        return self.get_job(resolved_id)

    def get_job(self, job_id: str) -> Row:
        row = self.connection.execute(
            "SELECT * FROM background_jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"Job not found: {job_id}")
        return row

    def get_job_for_org(self, job_id: str, organization_id: str) -> Row | None:
        return self.connection.execute(
            """
            SELECT * FROM background_jobs
            WHERE id = ? AND organization_id = ?
            """,
            (job_id, organization_id),
        ).fetchone()

    def list_jobs(
        self,
        organization_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Row]:
        return self.connection.execute(
            """
            SELECT * FROM background_jobs
            WHERE organization_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            (organization_id, limit, offset),
        ).fetchall()

    def next_queued_job(self, *, job_type: str | None = None) -> Row | None:
        clauses = ["status = ?"]
        values: list[object] = [JobStatus.QUEUED]
        if job_type is not None:
            clauses.append("job_type = ?")
            values.append(job_type)
        return self.connection.execute(
            f"""
            SELECT *
            FROM background_jobs
            WHERE {' AND '.join(clauses)}
            ORDER BY created_at ASC, id ASC
            LIMIT 1
            """,
            values,
        ).fetchone()

    def claim_next_queued_job(self, *, job_type: str | None = None) -> Row | None:
        """Atomically claim the next queued job for one worker."""

        now = utc_now_iso()
        clauses = ["status = ?"]
        values: list[object] = [JobStatus.QUEUED]
        if job_type is not None:
            clauses.append("job_type = ?")
            values.append(job_type)
        return self.connection.execute(
            f"""
            UPDATE background_jobs
            SET status = ?, started_at = ?, attempts = attempts + 1, updated_at = ?
            WHERE id = (
                SELECT id
                FROM background_jobs
                WHERE {' AND '.join(clauses)}
                ORDER BY created_at ASC, id ASC
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            RETURNING *
            """,
            (JobStatus.RUNNING, now, now, *values),
        ).fetchone()

    def claim_queued_job(self, job_id: str) -> Row | None:
        """Atomically claim a specific queued job."""

        now = utc_now_iso()
        return self.connection.execute(
            """
            UPDATE background_jobs
            SET status = ?, started_at = ?, attempts = attempts + 1, updated_at = ?
            WHERE id = ? AND status = ?
            RETURNING *
            """,
            (JobStatus.RUNNING, now, now, job_id, JobStatus.QUEUED),
        ).fetchone()

    def mark_running(self, job_id: str) -> Row:
        row = self.claim_queued_job(job_id)
        if row is None:
            raise RuntimeError("Queued job could not be claimed.")
        return row

    def mark_succeeded(
        self,
        job_id: str,
        *,
        logs: list[str],
        metrics: dict[str, Any],
        result: dict[str, Any],
    ) -> Row:
        now = utc_now_iso()
        self.connection.execute(
            """
            UPDATE background_jobs
            SET status = ?, finished_at = ?, error_message = NULL, updated_at = ?
            WHERE id = ?
            """,
            (JobStatus.SUCCEEDED, now, now, job_id),
        )
        self._create_run(job_id, JobStatus.SUCCEEDED, logs=logs, metrics=metrics, result=result)
        return self.get_job(job_id)

    def mark_failed(self, job_id: str, *, error_message: str, logs: list[str]) -> Row:
        now = utc_now_iso()
        self.connection.execute(
            """
            UPDATE background_jobs
            SET status = ?, finished_at = ?, error_message = ?, updated_at = ?
            WHERE id = ?
            """,
            (JobStatus.FAILED, now, error_message, now, job_id),
        )
        self._create_run(
            job_id,
            JobStatus.FAILED,
            logs=logs,
            metrics={},
            result={"error": error_message},
        )
        return self.get_job(job_id)

    def requeue_for_retry(self, job_id: str) -> Row:
        now = utc_now_iso()
        self.connection.execute(
            """
            UPDATE background_jobs
            SET status = ?, started_at = NULL, finished_at = NULL, error_message = NULL, updated_at = ?
            WHERE id = ? AND attempts < max_attempts
            """,
            (JobStatus.QUEUED, now, job_id),
        )
        return self.get_job(job_id)

    def cancel(self, job_id: str) -> Row:
        now = utc_now_iso()
        self.connection.execute(
            """
            UPDATE background_jobs
            SET status = ?, finished_at = ?, updated_at = ?
            WHERE id = ? AND status = ?
            """,
            (JobStatus.CANCELED, now, now, job_id, JobStatus.QUEUED),
        )
        return self.get_job(job_id)

    def runs_for_job(self, job_id: str) -> list[Row]:
        return self.connection.execute(
            "SELECT * FROM job_runs WHERE job_id = ? ORDER BY created_at, id",
            (job_id,),
        ).fetchall()

    def _create_run(
        self,
        job_id: str,
        status: str,
        *,
        logs: list[str],
        metrics: dict[str, Any],
        result: dict[str, Any],
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO job_runs (id, job_id, status, logs_json, metrics_json, result_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                generate_id("run"),
                job_id,
                status,
                json.dumps(logs),
                json.dumps(metrics, sort_keys=True),
                json.dumps(result, sort_keys=True),
                utc_now_iso(),
            ),
        )
