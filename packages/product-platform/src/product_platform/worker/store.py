"""Persistent job state repository."""

from __future__ import annotations

import json
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

from product_platform.db.ids import generate_id
from product_platform.db.postgres import Connection, Row
from product_platform.db.time import utc_now_iso


class JobStatus:
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DEAD_LETTERED = "dead_lettered"
    CANCELED = "canceled"

    ALL = {QUEUED, RUNNING, SUCCEEDED, FAILED, DEAD_LETTERED, CANCELED}


class JobStateConflictError(RuntimeError):
    """Raised when a job transition no longer matches the expected state."""


class JobIdempotencyConflictError(RuntimeError):
    """Raised when an idempotency key is reused for different job content."""


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
        queue_name: str = "default",
        priority: int = 0,
        concurrency_key: str | None = None,
        idempotency_key: str | None = None,
        operation_type: str | None = None,
        operation_id: str | None = None,
        max_attempts: int = 3,
        job_id: str | None = None,
        trace_id: str | None = None,
        span_id: str | None = None,
        parent_span_id: str | None = None,
        traceparent: str | None = None,
        tracestate: str | None = None,
        baggage: str | None = None,
    ) -> Row:
        now = utc_now_iso()
        resolved_id = job_id or generate_id("job")
        normalized_queue_name = _normalize_queue_name(queue_name)
        normalized_idempotency_key = _normalize_optional_identity(idempotency_key)
        normalized_operation_type = _normalize_optional_identity(operation_type)
        normalized_operation_id = _normalize_optional_identity(operation_id)
        if (normalized_operation_type is None) != (normalized_operation_id is None):
            raise ValueError("operation_type and operation_id must be provided together.")
        payload_json = json.dumps(payload, sort_keys=True)
        payload_hash = _job_idempotency_payload_hash(
            job_type=job_type,
            payload_json=payload_json,
            queue_name=normalized_queue_name,
            operation_type=normalized_operation_type,
            operation_id=normalized_operation_id,
        )
        existing = self._find_idempotent_job(
            organization_id=organization_id,
            environment_id=environment_id,
            job_type=job_type,
            idempotency_key=normalized_idempotency_key,
            operation_type=normalized_operation_type,
            operation_id=normalized_operation_id,
        )
        if existing is not None:
            _assert_same_idempotent_payload(existing, payload_hash)
            return existing
        row = self.connection.execute(
            """
            INSERT INTO background_jobs (
                id, organization_id, environment_id, job_type, queue_name, priority,
                status, payload_json, scheduled_at, concurrency_key,
                idempotency_key, operation_type, operation_id, idempotency_payload_hash,
                attempts, max_attempts,
                trace_id, span_id, parent_span_id, traceparent, tracestate, baggage,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT DO NOTHING
            RETURNING *
            """,
            (
                resolved_id,
                organization_id,
                environment_id,
                job_type,
                normalized_queue_name,
                priority,
                JobStatus.QUEUED,
                payload_json,
                scheduled_at,
                concurrency_key,
                normalized_idempotency_key,
                normalized_operation_type,
                normalized_operation_id,
                payload_hash,
                0,
                max_attempts,
                trace_id,
                span_id,
                parent_span_id,
                traceparent,
                tracestate,
                baggage,
                now,
                now,
            ),
        ).fetchone()
        if row is not None:
            return row
        existing = self._find_idempotent_job(
            organization_id=organization_id,
            environment_id=environment_id,
            job_type=job_type,
            idempotency_key=normalized_idempotency_key,
            operation_type=normalized_operation_type,
            operation_id=normalized_operation_id,
        )
        if existing is not None:
            _assert_same_idempotent_payload(existing, payload_hash)
            return existing
        raise JobStateConflictError("Job could not be created because a unique key already exists.")

    def get_job(self, job_id: str) -> Row:
        row = self.connection.execute(
            "SELECT * FROM background_jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"Job not found: {job_id}")
        return row

    def get_job_for_org(
        self,
        job_id: str,
        organization_id: str,
        *,
        environment_id: str | None = None,
    ) -> Row | None:
        clauses = ["id = ?", "organization_id = ?"]
        values: list[object] = [job_id, organization_id]
        if environment_id is not None:
            clauses.append("environment_id = ?")
            values.append(environment_id)
        return self.connection.execute(
            f"""
            SELECT * FROM background_jobs
            WHERE {' AND '.join(clauses)}
            """,
            values,
        ).fetchone()

    def _find_idempotent_job(
        self,
        *,
        organization_id: str,
        environment_id: str,
        job_type: str,
        idempotency_key: str | None,
        operation_type: str | None,
        operation_id: str | None,
    ) -> Row | None:
        clauses: list[str] = []
        values: list[object] = [organization_id, environment_id, job_type]
        if idempotency_key is not None:
            clauses.append("idempotency_key = ?")
            values.append(idempotency_key)
        if operation_type is not None and operation_id is not None:
            clauses.append("(operation_type = ? AND operation_id = ?)")
            values.extend([operation_type, operation_id])
        if not clauses:
            return None
        return self.connection.execute(
            f"""
            SELECT *
            FROM background_jobs
            WHERE organization_id = ?
              AND environment_id = ?
              AND job_type = ?
              AND ({' OR '.join(clauses)})
            ORDER BY created_at ASC, id ASC
            LIMIT 1
            """,
            values,
        ).fetchone()

    def list_jobs(
        self,
        organization_id: str,
        *,
        environment_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Row]:
        clauses = ["organization_id = ?"]
        values: list[object] = [organization_id]
        if environment_id is not None:
            clauses.append("environment_id = ?")
            values.append(environment_id)
        if status is not None:
            clauses.append("status = ?")
            values.append(status)
        values.extend([limit, offset])
        return self.connection.execute(
            f"""
            SELECT * FROM background_jobs
            WHERE {' AND '.join(clauses)}
            ORDER BY created_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            values,
        ).fetchall()

    def next_queued_job(
        self,
        *,
        job_type: str | None = None,
        queue_name: str | None = None,
    ) -> Row | None:
        now = utc_now_iso()
        clauses = ["status = ?", "(scheduled_at IS NULL OR scheduled_at <= ?)"]
        values: list[object] = [JobStatus.QUEUED, now]
        if job_type is not None:
            clauses.append("job_type = ?")
            values.append(job_type)
        if queue_name is not None:
            clauses.append("queue_name = ?")
            values.append(_normalize_queue_name(queue_name))
        return self.connection.execute(
            f"""
            SELECT *
            FROM background_jobs
            WHERE {' AND '.join(clauses)}
            ORDER BY priority DESC, COALESCE(scheduled_at, created_at) ASC, created_at ASC, id ASC
            LIMIT 1
            """,
            values,
        ).fetchone()

    def claim_next_queued_job(
        self,
        *,
        job_type: str | None = None,
        queue_name: str | None = None,
        worker_id: str | None = None,
        lease_seconds: int = 300,
    ) -> Row | None:
        """Atomically claim the next due queued or stale leased job for one worker."""

        now = utc_now_iso()
        lease_until = _lease_until_iso(lease_seconds)
        clauses = [
            "attempts < max_attempts",
            "((status = ? AND (scheduled_at IS NULL OR scheduled_at <= ?)) "
            "OR (status = ? AND lease_until IS NOT NULL AND lease_until <= ?))",
        ]
        values: list[object] = [JobStatus.QUEUED, now, JobStatus.RUNNING, now]
        if job_type is not None:
            clauses.append("job_type = ?")
            values.append(job_type)
        if queue_name is not None:
            clauses.append("queue_name = ?")
            values.append(_normalize_queue_name(queue_name))
        return self.connection.execute(
            f"""
            UPDATE background_jobs
            SET status = ?,
                started_at = ?,
                attempts = attempts + 1,
                claimed_by = ?,
                lease_until = ?,
                heartbeat_at = ?,
                updated_at = ?
            WHERE id = (
                SELECT id
                FROM background_jobs
                WHERE {' AND '.join(clauses)}
                ORDER BY priority DESC, COALESCE(scheduled_at, created_at) ASC, created_at ASC, id ASC
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            RETURNING *
            """,
            (JobStatus.RUNNING, now, worker_id, lease_until, now, now, *values),
        ).fetchone()

    def claim_queued_job(
        self,
        job_id: str,
        *,
        worker_id: str | None = None,
        lease_seconds: int = 300,
    ) -> Row | None:
        """Atomically claim a specific queued job."""

        now = utc_now_iso()
        lease_until = _lease_until_iso(lease_seconds)
        return self.connection.execute(
            """
            UPDATE background_jobs
            SET status = ?,
                started_at = ?,
                attempts = attempts + 1,
                claimed_by = ?,
                lease_until = ?,
                heartbeat_at = ?,
                updated_at = ?
            WHERE id = ?
              AND attempts < max_attempts
              AND (
                (status = ? AND (scheduled_at IS NULL OR scheduled_at <= ?))
                OR (status = ? AND lease_until IS NOT NULL AND lease_until <= ?)
              )
            RETURNING *
            """,
            (
                JobStatus.RUNNING,
                now,
                worker_id,
                lease_until,
                now,
                now,
                job_id,
                JobStatus.QUEUED,
                now,
                JobStatus.RUNNING,
                now,
            ),
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
        expected_attempt: int,
        logs: list[str],
        metrics: dict[str, Any],
        result: dict[str, Any],
    ) -> Row:
        now = utc_now_iso()
        row = self.connection.execute(
            """
            UPDATE background_jobs
            SET status = ?,
                finished_at = ?,
                error_message = NULL,
                claimed_by = NULL,
                lease_until = NULL,
                heartbeat_at = NULL,
                updated_at = ?
            WHERE id = ? AND status = ? AND attempts = ?
            RETURNING *
            """,
            (JobStatus.SUCCEEDED, now, now, job_id, JobStatus.RUNNING, expected_attempt),
        ).fetchone()
        if row is None:
            raise JobStateConflictError("Job is no longer running for the expected attempt.")
        self._create_run(job_id, JobStatus.SUCCEEDED, logs=logs, metrics=metrics, result=result)
        return row

    def mark_failed(
        self,
        job_id: str,
        *,
        expected_attempt: int,
        error_message: str,
        logs: list[str],
    ) -> Row:
        now = utc_now_iso()
        row = self.connection.execute(
            """
            UPDATE background_jobs
            SET status = ?,
                finished_at = ?,
                error_message = ?,
                claimed_by = NULL,
                lease_until = NULL,
                heartbeat_at = NULL,
                updated_at = ?
            WHERE id = ? AND status = ? AND attempts = ?
            RETURNING *
            """,
            (JobStatus.FAILED, now, error_message, now, job_id, JobStatus.RUNNING, expected_attempt),
        ).fetchone()
        if row is None:
            raise JobStateConflictError("Job is no longer running for the expected attempt.")
        self._create_run(
            job_id,
            JobStatus.FAILED,
            logs=logs,
            metrics={},
            result={"error": error_message},
        )
        return row

    def requeue_for_retry(self, job_id: str, *, expected_attempt: int) -> Row:
        now = utc_now_iso()
        row = self.connection.execute(
            """
            UPDATE background_jobs
            SET status = ?,
                started_at = NULL,
                finished_at = NULL,
                error_message = NULL,
                claimed_by = NULL,
                lease_until = NULL,
                heartbeat_at = NULL,
                updated_at = ?
            WHERE id = ? AND status = ? AND attempts = ? AND attempts < max_attempts
            RETURNING *
            """,
            (JobStatus.QUEUED, now, job_id, JobStatus.FAILED, expected_attempt),
        ).fetchone()
        if row is None:
            raise JobStateConflictError("Job is not failed for the expected retry attempt.")
        return row

    def record_failed_attempt(
        self,
        job_id: str,
        *,
        expected_attempt: int,
        error_message: str,
        logs: list[str],
    ) -> Row:
        """Record a worker failure and either schedule retry or dead-letter the job."""

        current = self.get_job(job_id)
        if current["status"] != JobStatus.RUNNING or int(current["attempts"]) != expected_attempt:
            raise JobStateConflictError("Job is no longer running for the expected attempt.")
        now = utc_now_iso()
        max_attempts = int(current["max_attempts"])
        if expected_attempt < max_attempts:
            backoff_seconds = _retry_backoff_seconds(job_id, expected_attempt)
            retry_at = _iso_after_seconds(backoff_seconds)
            row = self.connection.execute(
                """
                UPDATE background_jobs
                SET status = ?,
                    started_at = NULL,
                    finished_at = NULL,
                    scheduled_at = ?,
                    error_message = ?,
                    retry_backoff_seconds = ?,
                    next_retry_at = ?,
                    dead_lettered_at = NULL,
                    dead_letter_reason = NULL,
                    claimed_by = NULL,
                    lease_until = NULL,
                    heartbeat_at = NULL,
                    updated_at = ?
                WHERE id = ? AND status = ? AND attempts = ?
                RETURNING *
                """,
                (
                    JobStatus.QUEUED,
                    retry_at,
                    error_message,
                    backoff_seconds,
                    retry_at,
                    now,
                    job_id,
                    JobStatus.RUNNING,
                    expected_attempt,
                ),
            ).fetchone()
            if row is None:
                raise JobStateConflictError("Job is no longer running for the expected attempt.")
            self._create_run(
                job_id,
                JobStatus.FAILED,
                logs=logs,
                metrics={
                    "attempt": expected_attempt,
                    "max_attempts": max_attempts,
                    "retry_backoff_seconds": backoff_seconds,
                },
                result={
                    "error": error_message,
                    "retry_scheduled_at": retry_at,
                    "dead_lettered": False,
                },
            )
            return row

        row = self.connection.execute(
            """
            UPDATE background_jobs
            SET status = ?,
                finished_at = ?,
                scheduled_at = NULL,
                error_message = ?,
                retry_backoff_seconds = 0,
                next_retry_at = NULL,
                dead_lettered_at = ?,
                dead_letter_reason = ?,
                claimed_by = NULL,
                lease_until = NULL,
                heartbeat_at = NULL,
                updated_at = ?
            WHERE id = ? AND status = ? AND attempts = ?
            RETURNING *
            """,
            (
                JobStatus.DEAD_LETTERED,
                now,
                error_message,
                now,
                error_message,
                now,
                job_id,
                JobStatus.RUNNING,
                expected_attempt,
            ),
        ).fetchone()
        if row is None:
            raise JobStateConflictError("Job is no longer running for the expected attempt.")
        self._create_run(
            job_id,
            JobStatus.DEAD_LETTERED,
            logs=logs,
            metrics={"attempt": expected_attempt, "max_attempts": max_attempts},
            result={"error": error_message, "dead_lettered": True},
        )
        return row

    def replay(
        self,
        job_id: str,
        *,
        organization_id: str | None = None,
        environment_id: str | None = None,
    ) -> Row:
        """Replay a failed or dead-lettered job from the beginning of its retry budget."""

        now = utc_now_iso()
        clauses = ["id = ?", "status IN (?, ?)"]
        values: list[object] = [job_id, JobStatus.FAILED, JobStatus.DEAD_LETTERED]
        if organization_id is not None:
            clauses.append("organization_id = ?")
            values.append(organization_id)
        if environment_id is not None:
            clauses.append("environment_id = ?")
            values.append(environment_id)
        row = self.connection.execute(
            f"""
            UPDATE background_jobs
            SET status = ?,
                scheduled_at = NULL,
                started_at = NULL,
                finished_at = NULL,
                attempts = 0,
                error_message = NULL,
                retry_backoff_seconds = 0,
                next_retry_at = NULL,
                dead_lettered_at = NULL,
                dead_letter_reason = NULL,
                claimed_by = NULL,
                lease_until = NULL,
                heartbeat_at = NULL,
                updated_at = ?
            WHERE {' AND '.join(clauses)}
            RETURNING *
            """,
            (JobStatus.QUEUED, now, *values),
        ).fetchone()
        if row is None:
            raise JobStateConflictError("Job is not failed or dead-lettered for replay.")
        return row

    def cancel(
        self,
        job_id: str,
        *,
        organization_id: str | None = None,
        environment_id: str | None = None,
    ) -> Row:
        now = utc_now_iso()
        clauses = ["id = ?", "status IN (?, ?, ?)"]
        values: list[object] = [
            job_id,
            JobStatus.QUEUED,
            JobStatus.FAILED,
            JobStatus.DEAD_LETTERED,
        ]
        if organization_id is not None:
            clauses.append("organization_id = ?")
            values.append(organization_id)
        if environment_id is not None:
            clauses.append("environment_id = ?")
            values.append(environment_id)
        row = self.connection.execute(
            f"""
            UPDATE background_jobs
            SET status = ?,
                finished_at = ?,
                claimed_by = NULL,
                lease_until = NULL,
                heartbeat_at = NULL,
                next_retry_at = NULL,
                retry_backoff_seconds = 0,
                updated_at = ?
            WHERE {' AND '.join(clauses)}
            RETURNING *
            """,
            (JobStatus.CANCELED, now, now, *values),
        ).fetchone()
        if row is None:
            raise JobStateConflictError("Queued, failed, or dead-lettered job could not be canceled.")
        return row

    def heartbeat(
        self,
        job_id: str,
        *,
        worker_id: str | None,
        expected_attempt: int,
        lease_seconds: int = 300,
    ) -> Row:
        now = utc_now_iso()
        clauses = ["id = ?", "status = ?", "attempts = ?"]
        values: list[object] = [
            _lease_until_iso(lease_seconds),
            now,
            now,
            job_id,
            JobStatus.RUNNING,
            expected_attempt,
        ]
        if worker_id is not None:
            clauses.append("claimed_by = ?")
            values.append(worker_id)
        row = self.connection.execute(
            f"""
            UPDATE background_jobs
            SET lease_until = ?, heartbeat_at = ?, updated_at = ?
            WHERE {' AND '.join(clauses)}
            RETURNING *
            """,
            values,
        ).fetchone()
        if row is None:
            raise JobStateConflictError("Running job heartbeat was rejected.")
        return row

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


def _normalize_queue_name(queue_name: str) -> str:
    normalized = queue_name.strip()
    if not normalized:
        raise ValueError("queue_name must not be blank.")
    return normalized


def _normalize_optional_identity(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _job_idempotency_payload_hash(
    *,
    job_type: str,
    payload_json: str,
    queue_name: str,
    operation_type: str | None,
    operation_id: str | None,
) -> str:
    content = json.dumps(
        {
            "job_type": job_type,
            "payload_json": payload_json,
            "queue_name": queue_name,
            "operation_type": operation_type,
            "operation_id": operation_id,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _assert_same_idempotent_payload(existing: Row, payload_hash: str) -> None:
    existing_hash = existing.get("idempotency_payload_hash")
    if existing_hash is not None and existing_hash != payload_hash:
        raise JobIdempotencyConflictError(
            "Idempotency key or operation identity was reused with different job content."
        )


def _lease_until_iso(lease_seconds: int) -> str:
    if lease_seconds <= 0:
        raise ValueError("lease_seconds must be greater than zero.")
    return (datetime.now(timezone.utc) + timedelta(seconds=lease_seconds)).isoformat()


def _iso_after_seconds(seconds: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


def _retry_backoff_seconds(job_id: str, attempt: int) -> int:
    base_seconds = 60
    max_seconds = 3600
    exponential = min(max_seconds, base_seconds * (2 ** max(0, attempt - 1)))
    jitter_bound = min(30, max(1, exponential // 4))
    deterministic_jitter = sum(ord(char) for char in f"{job_id}:{attempt}") % (jitter_bound + 1)
    return min(max_seconds, exponential + deterministic_jitter)
