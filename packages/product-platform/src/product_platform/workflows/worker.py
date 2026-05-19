"""Persistent worker executor for queued workflow runs."""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from product_platform.artifacts.models import ArtifactCreateRequest, ArtifactLinkCreateRequest
from product_platform.artifacts.repository import ArtifactRepository
from product_platform.artifacts.storage import LocalArtifactProvider
from product_platform.audit.events import workflow_run_event
from product_platform.audit.store import AuditEventRepository
from product_platform.db.connection import Database
from product_platform.worker.store import JobStateRepository, JobStatus
from product_platform.workflows.repository import WorkflowRepository
from product_platform.workflows.runner import (
    WorkflowRunLogLine,
    WorkflowRunResult,
    WorkflowRunnerError,
    WorkflowRunnerRegistry,
    build_default_workflow_runner_registry,
)


WORKFLOW_JOB_TYPE = "workflow.run"


@dataclass(frozen=True)
class WorkflowJobExecution:
    """Result of one queued workflow worker execution."""

    job_id: str
    workflow_run_id: str
    status: str


class WorkflowRunWorker:
    """Execute persisted queued workflow jobs."""

    def __init__(
        self,
        database: Database,
        *,
        runner_registry: WorkflowRunnerRegistry | None = None,
        artifact_storage_path: str | Path | None = None,
    ) -> None:
        self.database = database
        self.runner_registry = runner_registry or build_default_workflow_runner_registry()
        self.artifact_storage_path = Path(
            artifact_storage_path
            or os.environ.get("OPHANIX_ARTIFACT_STORAGE_PATH", "/tmp/ophanix-product-artifacts")
        )

    def run_once(self, job_id: str | None = None) -> WorkflowJobExecution | None:
        """Execute one queued workflow job, returning None when no job is available."""

        with self.database.transaction() as connection:
            jobs = JobStateRepository(connection)
            job = (
                jobs.claim_queued_job(job_id)
                if job_id
                else jobs.claim_next_queued_job(job_type=WORKFLOW_JOB_TYPE)
            )
            if job is None:
                return None
            payload = _loads_mapping(job["payload_json"])
            workflow_run_id = str(payload.get("workflow_run_id") or "")
            command_ref = str(payload.get("command_ref") or "")
            inputs = payload.get("inputs") if isinstance(payload.get("inputs"), dict) else {}
            organization_id = str(job["organization_id"])
            environment_id = str(job["environment_id"])
            repository = WorkflowRepository(connection, organization_id)
            workflow_run = repository.get_run(workflow_run_id, environment_id=environment_id)
            if workflow_run is None:
                failed = jobs.mark_failed(
                    job["id"],
                    expected_attempt=int(job["attempts"]),
                    error_message="Workflow run not found.",
                    logs=["workflow run not found"],
                )
                return WorkflowJobExecution(
                    job_id=failed["id"],
                    workflow_run_id=workflow_run_id,
                    status=failed["status"],
                )

            if workflow_run["status"] != JobStatus.QUEUED:
                failed = jobs.mark_failed(
                    job["id"],
                    expected_attempt=int(job["attempts"]),
                    error_message="Workflow run is not queued.",
                    logs=[f"workflow run status was {workflow_run['status']}"],
                )
                return WorkflowJobExecution(
                    job_id=failed["id"],
                    workflow_run_id=workflow_run_id,
                    status=failed["status"],
                )

            started = repository.start_run(workflow_run_id, environment_id=environment_id)
            _insert_workflow_audit_event(
                connection,
                organization_id=organization_id,
                environment_id=environment_id,
                workflow_run_id=workflow_run_id,
                workflow_type=str(started["workflow_type"]),
                status=started["status"],
            )

        try:
            result = self.runner_registry.run(command_ref, inputs)
        except WorkflowRunnerError as exc:
            result = WorkflowRunResult(
                status="failed",
                exit_code=1,
                summary={"error": str(exc)},
                logs=[
                    WorkflowRunLogLine(
                        stream="stderr",
                        line_number=1,
                        message=str(exc),
                    )
                ],
            )

        with self.database.transaction() as connection:
            jobs = JobStateRepository(connection)
            repository = WorkflowRepository(connection, organization_id)
            try:
                completed = repository.complete_run(
                    workflow_run_id,
                    environment_id=environment_id,
                    result=result,
                )
            except RuntimeError:
                current = repository.get_run(workflow_run_id, environment_id=environment_id)
                if current is not None and current["status"] == "canceled":
                    return WorkflowJobExecution(
                        job_id=job["id"],
                        workflow_run_id=workflow_run_id,
                        status="canceled",
                    )
                raise
            _store_workflow_output_artifact(
                connection=connection,
                organization_id=organization_id,
                environment_id=environment_id,
                workflow_run=completed,
                result=result,
                artifact_storage_path=self.artifact_storage_path,
            )
            job_logs = [log.message for log in result.logs]
            job_result = {
                "workflow_run_id": workflow_run_id,
                "workflow_status": completed["status"],
                "exit_code": result.exit_code,
                "summary": result.summary,
            }
            if completed["status"] == "succeeded":
                job = jobs.mark_succeeded(
                    job["id"],
                    expected_attempt=int(job["attempts"]),
                    logs=job_logs,
                    metrics={"workflow_log_count": len(result.logs)},
                    result=job_result,
                )
            else:
                job = jobs.mark_failed(
                    job["id"],
                    expected_attempt=int(job["attempts"]),
                    error_message=str(result.summary.get("error") or "Workflow run failed."),
                    logs=job_logs,
                )
            _insert_workflow_audit_event(
                connection,
                organization_id=organization_id,
                environment_id=environment_id,
                workflow_run_id=workflow_run_id,
                workflow_type=str(completed["workflow_type"]),
                status=completed["status"],
            )
            return WorkflowJobExecution(
                job_id=job["id"],
                workflow_run_id=workflow_run_id,
                status=completed["status"],
            )


def _store_workflow_output_artifact(
    *,
    connection: Any,
    organization_id: str,
    environment_id: str,
    workflow_run: Any,
    result: WorkflowRunResult,
    artifact_storage_path: Path,
) -> None:
    payload = {
        "workflow_run_id": workflow_run["id"],
        "workflow_definition_id": workflow_run["workflow_definition_id"],
        "workflow_type": workflow_run["workflow_type"],
        "status": workflow_run["status"],
        "exit_code": result.exit_code,
        "summary": result.summary,
        "logs": [
            {"stream": log.stream, "line_number": log.line_number, "message": log.message}
            for log in result.logs
        ],
    }
    content = json.dumps(payload, sort_keys=True, indent=2).encode("utf-8")
    repository = ArtifactRepository(
        connection,
        organization_id,
        environment_id,
        LocalArtifactProvider(artifact_storage_path),
    )
    artifact = repository.create(
        ArtifactCreateRequest(
            artifact_type="workflow.output",
            name=f"{workflow_run['id']}-output.json",
            content_type="application/json",
            content_base64=base64.b64encode(content).decode("ascii"),
        ),
        actor_id=str(workflow_run["started_by"] or "workflow-worker"),
    )
    repository.create_link(
        artifact["id"],
        ArtifactLinkCreateRequest(
            target_type="workflow_run",
            target_id=workflow_run["id"],
            link_type="output",
        ),
    )


def _insert_workflow_audit_event(
    connection: Any,
    *,
    organization_id: str,
    environment_id: str,
    workflow_run_id: str,
    workflow_type: str,
    status: str,
) -> None:
    AuditEventRepository(connection).insert(
        workflow_run_event(
            organization_id=organization_id,
            environment_id=environment_id,
            workflow_run_id=workflow_run_id,
            workflow_type=workflow_type,
            status=status,
        )
    )


def _loads_mapping(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    loaded = json.loads(raw)
    return loaded if isinstance(loaded, dict) else {}
