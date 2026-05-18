"""Job schedule calculation and enqueueing."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from product_platform.db.ids import generate_id
from product_platform.db.postgres import Connection, Row
from product_platform.db.time import utc_now_iso
from product_platform.worker.store import JobStateRepository


SUPPORTED_CRON_SUFFIX = "* * * *"


def calculate_next_run(expression: str, from_time: datetime) -> datetime:
    """Calculate the next run for supported interval/cron expressions."""

    expression = validate_schedule_expression(expression)
    if expression.startswith("interval:"):
        return from_time + _parse_interval(expression.removeprefix("interval:"))
    minutes = _parse_supported_cron_minutes(expression)
    if minutes is not None:
        candidate = from_time.replace(second=0, microsecond=0) + timedelta(minutes=1)
        while candidate.minute % minutes != 0:
            candidate += timedelta(minutes=1)
        return candidate
    if expression == "@hourly":
        return from_time.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    raise ValueError(f"Unsupported schedule expression: {expression}")


class JobScheduleRepository:
    """Stores schedules and enqueues due jobs."""

    def __init__(self, connection: Connection) -> None:
        self.connection = connection

    def create_schedule(
        self,
        *,
        organization_id: str,
        environment_id: str,
        job_type: str,
        expression: str,
        payload: dict[str, Any],
        enabled: bool = True,
        next_run_at: str | None = None,
        schedule_id: str | None = None,
    ) -> Row:
        expression = validate_schedule_expression(expression)
        now = utc_now_iso()
        resolved_id = schedule_id or generate_id("sched")
        self.connection.execute(
            """
            INSERT INTO job_schedules (
                id, organization_id, environment_id, job_type, cron_expression,
                payload_json, enabled, next_run_at, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                resolved_id,
                organization_id,
                environment_id,
                job_type,
                expression,
                json.dumps(payload, sort_keys=True),
                1 if enabled else 0,
                next_run_at,
                now,
                now,
            ),
        )
        return self.get_schedule(resolved_id)

    def get_schedule(self, schedule_id: str) -> Row:
        row = self.connection.execute(
            "SELECT * FROM job_schedules WHERE id = ?",
            (schedule_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"Schedule not found: {schedule_id}")
        return row

    def get_schedule_for_org(
        self,
        schedule_id: str,
        organization_id: str,
        *,
        environment_id: str | None = None,
    ) -> Row | None:
        clauses = ["id = ?", "organization_id = ?"]
        values: list[object] = [schedule_id, organization_id]
        if environment_id is not None:
            clauses.append("environment_id = ?")
            values.append(environment_id)
        return self.connection.execute(
            f"""
            SELECT * FROM job_schedules
            WHERE {' AND '.join(clauses)}
            """,
            values,
        ).fetchone()

    def list_schedules(
        self,
        organization_id: str,
        *,
        environment_id: str | None = None,
    ) -> list[Row]:
        clauses = ["organization_id = ?"]
        values: list[object] = [organization_id]
        if environment_id is not None:
            clauses.append("environment_id = ?")
            values.append(environment_id)
        return self.connection.execute(
            f"""
            SELECT * FROM job_schedules
            WHERE {' AND '.join(clauses)}
            ORDER BY created_at DESC, id DESC
            """,
            values,
        ).fetchall()

    def set_enabled(self, schedule_id: str, enabled: bool) -> Row:
        self.connection.execute(
            "UPDATE job_schedules SET enabled = ?, updated_at = ? WHERE id = ?",
            (1 if enabled else 0, utc_now_iso(), schedule_id),
        )
        return self.get_schedule(schedule_id)

    def update_schedule(
        self,
        schedule_id: str,
        organization_id: str,
        *,
        environment_id: str | None = None,
        enabled: bool | None = None,
        next_run_at: str | None = None,
    ) -> Row | None:
        existing = self.get_schedule_for_org(
            schedule_id,
            organization_id,
            environment_id=environment_id,
        )
        if existing is None:
            return None
        clauses = ["id = ?", "organization_id = ?"]
        values: list[object] = [
            None if enabled is None else 1 if enabled else 0,
            next_run_at,
            utc_now_iso(),
            schedule_id,
            organization_id,
        ]
        if environment_id is not None:
            clauses.append("environment_id = ?")
            values.append(environment_id)
        self.connection.execute(
            f"""
            UPDATE job_schedules
            SET enabled = COALESCE(?, enabled),
                next_run_at = COALESCE(?, next_run_at),
                updated_at = ?
            WHERE {' AND '.join(clauses)}
            """,
            values,
        )
        return self.get_schedule(schedule_id)

    def enqueue_due(self, now: datetime) -> list[Row]:
        now_iso = now.isoformat()
        due = self.connection.execute(
            """
            SELECT * FROM job_schedules
            WHERE enabled = 1 AND next_run_at IS NOT NULL AND next_run_at <= ?
            ORDER BY next_run_at, id
            FOR UPDATE SKIP LOCKED
            """,
            (now_iso,),
        ).fetchall()
        jobs: list[Row] = []
        job_repository = JobStateRepository(self.connection)
        for schedule in due:
            payload = json.loads(schedule["payload_json"])
            scheduled_at = schedule["next_run_at"]
            if self._scheduled_job_exists(schedule, scheduled_at):
                self._advance_schedule(schedule, now)
                continue
            job = job_repository.create_job(
                organization_id=schedule["organization_id"],
                environment_id=schedule["environment_id"],
                job_type=schedule["job_type"],
                payload=payload,
                scheduled_at=scheduled_at,
            )
            jobs.append(job)
            self._advance_schedule(schedule, now)
        return jobs

    def _scheduled_job_exists(self, schedule: Row, scheduled_at: str) -> bool:
        row = self.connection.execute(
            """
            SELECT 1 FROM background_jobs
            WHERE organization_id = ?
              AND environment_id = ?
              AND job_type = ?
              AND payload_json = ?
              AND scheduled_at = ?
            """,
            (
                schedule["organization_id"],
                schedule["environment_id"],
                schedule["job_type"],
                schedule["payload_json"],
                scheduled_at,
            ),
        ).fetchone()
        return row is not None

    def _advance_schedule(self, schedule: Row, now: datetime) -> None:
        next_run = calculate_next_run(schedule["cron_expression"], now).isoformat()
        self.connection.execute(
            """
            UPDATE job_schedules
            SET last_run_at = ?, next_run_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (schedule["next_run_at"], next_run, utc_now_iso(), schedule["id"]),
        )


def validate_schedule_expression(expression: str) -> str:
    """Return a normalized supported schedule expression or raise ValueError."""

    normalized = expression.strip()
    if not normalized:
        raise ValueError("Schedule expression must not be blank.")
    if normalized == "@hourly":
        return normalized
    if normalized.startswith("interval:"):
        _parse_interval(normalized.removeprefix("interval:"))
        return normalized
    if _parse_supported_cron_minutes(normalized) is not None:
        return normalized
    raise ValueError(f"Unsupported schedule expression: {expression}")


def _parse_supported_cron_minutes(expression: str) -> int | None:
    parts = expression.split()
    if len(parts) != 5 or " ".join(parts[1:]) != SUPPORTED_CRON_SUFFIX:
        return None
    minute = parts[0]
    if not minute.startswith("*/"):
        return None
    try:
        minutes = int(minute.removeprefix("*/"))
    except ValueError as exc:
        raise ValueError(f"Unsupported schedule expression: {expression}") from exc
    if minutes < 1 or minutes > 60:
        raise ValueError("Cron minute interval must be between 1 and 60.")
    return minutes


def _parse_interval(interval: str) -> timedelta:
    if len(interval) < 2:
        raise ValueError("Interval schedule must include a positive amount and unit.")
    unit = interval[-1]
    try:
        amount = int(interval[:-1])
    except ValueError as exc:
        raise ValueError("Interval amount must be an integer.") from exc
    if amount <= 0:
        raise ValueError("Interval amount must be greater than zero.")
    if unit == "s":
        return timedelta(seconds=amount)
    if unit == "m":
        return timedelta(minutes=amount)
    if unit == "h":
        return timedelta(hours=amount)
    if unit == "d":
        return timedelta(days=amount)
    raise ValueError(f"Unsupported interval unit: {unit}")
