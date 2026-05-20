"""Persistent database-backed worker execution."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from product_platform.audit.events import workflow_run_event
from product_platform.audit.store import AuditEventRepository
from product_platform.db.connection import Database
from product_platform.worker.runtime import JobContext, JobRegistry, JobResult
from product_platform.worker.store import JobStateRepository, JobStatus
from product_platform.workflows.worker import WorkflowJobExecution, WorkflowRunWorker


@dataclass(frozen=True)
class PersistentJobExecution:
    """Result of one persistent worker execution."""

    job_id: str
    job_type: str
    status: str
    error_message: str | None = None


def build_default_persistent_job_registry() -> JobRegistry:
    """Build handlers for generic persistent jobs handled outside workflow runs."""

    registry = JobRegistry()
    registry.register("demo.noop", _handle_demo_noop)
    return registry


class PersistentJobWorker:
    """Consume persistent background jobs with registered handlers."""

    def __init__(
        self,
        database: Database,
        *,
        registry: JobRegistry | None = None,
        queue_name: str | None = None,
        worker_id: str | None = None,
        lease_seconds: int = 300,
    ) -> None:
        self.database = database
        self.registry = registry or build_default_persistent_job_registry()
        self.queue_name = queue_name
        self.worker_id = worker_id
        self.lease_seconds = lease_seconds

    def run_once(self) -> PersistentJobExecution | None:
        """Claim and execute one registered persistent job."""

        with self.database.transaction() as connection:
            jobs = JobStateRepository(connection)
            job = self._claim_registered_job(jobs)
            if job is None:
                return None
            _insert_job_audit_event(connection, job=job, status=job["status"])

        payload = _loads_mapping(job["payload_json"])
        context = JobContext(
            job_id=job["id"],
            job_type=job["job_type"],
            payload=payload,
        )
        try:
            handler = self.registry.resolve(job["job_type"])
            result = handler(context)
        except Exception as exc:
            result = JobResult(status=JobStatus.FAILED, result={"error": str(exc)})
            error_message = str(exc)
        else:
            error_message = None

        with self.database.transaction() as connection:
            jobs = JobStateRepository(connection)
            if result.status == JobStatus.SUCCEEDED:
                completed = jobs.mark_succeeded(
                    job["id"],
                    expected_attempt=int(job["attempts"]),
                    logs=context.logs,
                    metrics=result.metrics | context.metrics,
                    result=result.result,
                )
            else:
                completed = jobs.record_failed_attempt(
                    job["id"],
                    expected_attempt=int(job["attempts"]),
                    error_message=error_message
                    or str(result.result.get("error") or "Persistent job failed."),
                    logs=context.logs,
                )
            _insert_job_audit_event(connection, job=completed, status=completed["status"])
            return PersistentJobExecution(
                job_id=completed["id"],
                job_type=completed["job_type"],
                status=completed["status"],
                error_message=completed["error_message"],
            )

    def _claim_registered_job(self, jobs: JobStateRepository) -> Any | None:
        for job_type in self.registry.job_types:
            job = jobs.claim_next_queued_job(
                job_type=job_type,
                queue_name=self.queue_name,
                worker_id=self.worker_id,
                lease_seconds=self.lease_seconds,
            )
            if job is not None:
                return job
        return None


class ProductPlatformWorker:
    """Production worker that consumes workflow and generic persistent jobs."""

    def __init__(
        self,
        database: Database,
        *,
        queue_name: str | None = None,
        worker_id: str | None = None,
        lease_seconds: int = 300,
        workflow_worker: WorkflowRunWorker | None = None,
        generic_worker: PersistentJobWorker | None = None,
    ) -> None:
        self.workflow_worker = workflow_worker or WorkflowRunWorker(
            database,
            queue_name=queue_name,
            worker_id=worker_id,
            lease_seconds=lease_seconds,
        )
        self.generic_worker = generic_worker or PersistentJobWorker(
            database,
            queue_name=queue_name,
            worker_id=worker_id,
            lease_seconds=lease_seconds,
        )

    def run_once(self) -> WorkflowJobExecution | PersistentJobExecution | None:
        workflow_execution = self.workflow_worker.run_once()
        if workflow_execution is not None:
            return workflow_execution
        return self.generic_worker.run_once()


def check_worker_store_ready(database: Database) -> None:
    """Raise when the worker cannot reach the persistent job store."""

    with database.transaction() as connection:
        connection.execute("SELECT 1 FROM background_jobs LIMIT 1").fetchone()


def _handle_demo_noop(context: JobContext) -> JobResult:
    context.log(f"processed {context.job_id}")
    return JobResult(status=JobStatus.SUCCEEDED, result={"ok": True, "job_type": context.job_type})


def _insert_job_audit_event(connection: Any, *, job: Any, status: str) -> None:
    AuditEventRepository(connection).insert(
        workflow_run_event(
            organization_id=job["organization_id"],
            environment_id=job["environment_id"],
            workflow_run_id=job["id"],
            workflow_type=job["job_type"],
            status=status,
        )
    )


def _loads_mapping(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    loaded = json.loads(raw)
    return loaded if isinstance(loaded, dict) else {}
