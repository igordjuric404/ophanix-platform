"""API request and response models for background jobs."""

from __future__ import annotations

import json
from product_platform.db.postgres import Row
from typing import Any

from pydantic import BaseModel, Field


class JobCreateRequest(BaseModel):
    """Create a background job in the selected environment."""

    job_type: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    max_attempts: int = Field(default=3, ge=1, le=25)
    run_immediately: bool = False


class JobRunResponse(BaseModel):
    """UI-ready representation of one job run attempt."""

    id: str
    job_id: str
    status: str
    logs: list[str]
    metrics: dict[str, Any]
    result: dict[str, Any]
    created_at: str


class JobResponse(BaseModel):
    """UI-ready representation of a persisted background job."""

    id: str
    organization_id: str
    environment_id: str
    job_type: str
    status: str
    payload: dict[str, Any]
    scheduled_at: str | None
    started_at: str | None
    finished_at: str | None
    attempts: int
    max_attempts: int
    error_message: str | None
    created_at: str
    updated_at: str
    runs: list[JobRunResponse] = Field(default_factory=list)


class JobScheduleCreateRequest(BaseModel):
    """Create a recurring job schedule in the selected environment."""

    job_type: str = Field(min_length=1)
    cron_expression: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    next_run_at: str | None = None


class JobSchedulePatchRequest(BaseModel):
    """Patch mutable schedule controls."""

    enabled: bool | None = None
    next_run_at: str | None = None


class JobScheduleResponse(BaseModel):
    """UI-ready representation of a job schedule."""

    id: str
    organization_id: str
    environment_id: str
    job_type: str
    cron_expression: str
    payload: dict[str, Any]
    enabled: bool
    last_run_at: str | None
    next_run_at: str | None
    created_at: str
    updated_at: str


def job_run_response(row: Row) -> JobRunResponse:
    """Serialize one job run row."""

    return JobRunResponse(
        id=row["id"],
        job_id=row["job_id"],
        status=row["status"],
        logs=json.loads(row["logs_json"]),
        metrics=json.loads(row["metrics_json"]),
        result=json.loads(row["result_json"]),
        created_at=row["created_at"],
    )


def job_response(row: Row, runs: list[Row]) -> JobResponse:
    """Serialize a job row and its run attempts."""

    return JobResponse(
        id=row["id"],
        organization_id=row["organization_id"],
        environment_id=row["environment_id"],
        job_type=row["job_type"],
        status=row["status"],
        payload=json.loads(row["payload_json"]),
        scheduled_at=row["scheduled_at"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        attempts=row["attempts"],
        max_attempts=row["max_attempts"],
        error_message=row["error_message"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        runs=[job_run_response(run) for run in runs],
    )


def job_schedule_response(row: Row) -> JobScheduleResponse:
    """Serialize a job schedule row."""

    return JobScheduleResponse(
        id=row["id"],
        organization_id=row["organization_id"],
        environment_id=row["environment_id"],
        job_type=row["job_type"],
        cron_expression=row["cron_expression"],
        payload=json.loads(row["payload_json"]),
        enabled=bool(row["enabled"]),
        last_run_at=row["last_run_at"],
        next_run_at=row["next_run_at"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
