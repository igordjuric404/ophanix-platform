from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.worker.runtime import JobContext, JobRegistry, JobResult
from product_platform.worker.persistent import PersistentJobWorker
from product_platform.worker.store import JobStateRepository, JobStatus
from product_platform.workflows.runner import (
    WorkflowRunLogLine,
    WorkflowRunResult,
    WorkflowRunnerRegistry,
)
from product_platform.workflows.worker import WorkflowRunWorker


VALID_POLICY_BODY = """version: "1.0"
name: worker-phase3-valid
rules: []
defaults:
  action: allow
"""


class WorkersBackgroundJobsPhase3Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.artifact_root = tempfile.TemporaryDirectory()
        self.addCleanup(self.artifact_root.cleanup)
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
        self.app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-05-20T00:00:00Z",
                dev_login_allowed_emails=[
                    "worker-phase3@example.com",
                    "viewer-phase3@example.com",
                ],
                session_secret="test-secret",
                artifact_storage_path=self.artifact_root.name,
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.operator_headers = self._login("worker-phase3@example.com", ["Operator"])
        self.viewer_headers = self._login("viewer-phase3@example.com", ["Viewer"])

    def tearDown(self) -> None:
        self.database.close()

    def _login(self, email: str, roles: list[str]) -> dict[str, str]:
        response = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": email, "roles": roles},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return {
            "Authorization": f"Bearer {response.json()['access_token']}",
            "X-Environment-ID": "env_default",
        }

    def test_persistent_worker_retries_then_enters_dead_letter_queue(self) -> None:
        registry = JobRegistry()

        def fail_job(context: JobContext) -> JobResult:
            context.log("attempt failed")
            return JobResult(status=JobStatus.FAILED, result={"error": "transient outage"})

        registry.register("demo.fail", fail_job)
        with self.database.transaction() as connection:
            repository = JobStateRepository(connection)
            repository.create_job(
                organization_id="org_default",
                environment_id="env_default",
                job_type="demo.fail",
                payload={},
                max_attempts=2,
                job_id="job_phase3_retry",
            )

        worker = PersistentJobWorker(
            self.database,
            registry=registry,
            worker_id="worker-phase3",
            lease_seconds=30,
        )
        first = worker.run_once()
        with self.database.transaction() as connection:
            repository = JobStateRepository(connection)
            after_first = repository.get_job("job_phase3_retry")
            blocked_claim = repository.claim_next_queued_job(job_type="demo.fail")
            connection.execute(
                """
                UPDATE background_jobs
                SET scheduled_at = ?, next_retry_at = ?
                WHERE id = ?
                """,
                (_past_iso(), _past_iso(), "job_phase3_retry"),
            )

        second = worker.run_once()
        with self.database.transaction() as connection:
            repository = JobStateRepository(connection)
            final = repository.get_job("job_phase3_retry")
            runs = repository.runs_for_job("job_phase3_retry")

        self.assertIsNotNone(first)
        self.assertEqual(first.status, JobStatus.QUEUED)
        self.assertEqual(after_first["status"], JobStatus.QUEUED)
        self.assertEqual(after_first["attempts"], 1)
        self.assertGreaterEqual(after_first["retry_backoff_seconds"], 60)
        self.assertIsNotNone(after_first["next_retry_at"])
        self.assertIsNone(blocked_claim)
        self.assertIsNotNone(second)
        self.assertEqual(second.status, JobStatus.DEAD_LETTERED)
        self.assertEqual(final["status"], JobStatus.DEAD_LETTERED)
        self.assertEqual(final["attempts"], 2)
        self.assertIsNotNone(final["dead_lettered_at"])
        self.assertEqual(final["dead_letter_reason"], "transient outage")
        self.assertEqual([run["status"] for run in runs], [JobStatus.FAILED, JobStatus.DEAD_LETTERED])

    def test_workflow_worker_requeues_failed_run_until_dead_lettered(self) -> None:
        created = self.client.post(
            "/api/v1/workflows/policy_lint/runs",
            headers=self.operator_headers,
            json={
                "run_immediately": False,
                "inputs": {"policy_body": VALID_POLICY_BODY, "policy_format": "yaml"},
            },
        )
        self.assertEqual(created.status_code, 201, created.text)
        run_id = created.json()["id"]
        with self.database.transaction() as connection:
            connection.execute(
                "UPDATE background_jobs SET max_attempts = ? WHERE id = ?",
                (2, run_id),
            )

        registry = WorkflowRunnerRegistry()
        registry.register("python:policy.lint", _always_failing_workflow)
        worker = WorkflowRunWorker(
            self.database,
            runner_registry=registry,
            artifact_storage_path=self.artifact_root.name,
            queue_name="workflows",
            worker_id="workflow-worker-phase3",
            lease_seconds=30,
        )

        first = worker.run_once()
        after_first_job = self.client.get(f"/api/v1/jobs/{run_id}", headers=self.operator_headers)
        after_first_run = self.client.get(
            f"/api/v1/workflow-runs/{run_id}",
            headers=self.operator_headers,
        )
        with self.database.transaction() as connection:
            connection.execute(
                """
                UPDATE background_jobs
                SET scheduled_at = ?, next_retry_at = ?
                WHERE id = ?
                """,
                (_past_iso(), _past_iso(), run_id),
            )
        second = worker.run_once()
        final_job = self.client.get(f"/api/v1/jobs/{run_id}", headers=self.operator_headers)
        final_run = self.client.get(f"/api/v1/workflow-runs/{run_id}", headers=self.operator_headers)

        self.assertIsNotNone(first)
        self.assertEqual(first.status, JobStatus.QUEUED)
        self.assertEqual(after_first_job.status_code, 200, after_first_job.text)
        self.assertEqual(after_first_job.json()["status"], JobStatus.QUEUED)
        self.assertEqual(after_first_job.json()["attempts"], 1)
        self.assertIsNotNone(after_first_job.json()["next_retry_at"])
        self.assertEqual(after_first_run.status_code, 200, after_first_run.text)
        self.assertEqual(after_first_run.json()["status"], "queued")
        self.assertIsNotNone(second)
        self.assertEqual(second.status, "failed")
        self.assertEqual(final_job.status_code, 200, final_job.text)
        self.assertEqual(final_job.json()["status"], JobStatus.DEAD_LETTERED)
        self.assertEqual(final_job.json()["dead_letter_reason"], "temporary workflow failure")
        self.assertEqual(final_run.status_code, 200, final_run.text)
        self.assertEqual(final_run.json()["status"], "failed")

    def test_dead_lettered_jobs_are_queryable_and_replayable_by_operator(self) -> None:
        with self.database.transaction() as connection:
            repository = JobStateRepository(connection)
            job = repository.create_job(
                organization_id="org_default",
                environment_id="env_default",
                job_type="demo.noop",
                payload={"source": "api"},
                max_attempts=1,
                job_id="job_phase3_dlq_api",
            )
            running = repository.mark_running(job["id"])
            repository.record_failed_attempt(
                job["id"],
                expected_attempt=int(running["attempts"]),
                error_message="terminal failure",
                logs=["failed"],
            )

        listed = self.client.get(
            "/api/v1/jobs",
            params={"status": JobStatus.DEAD_LETTERED},
            headers=self.operator_headers,
        )
        denied = self.client.post(
            "/api/v1/jobs/job_phase3_dlq_api/replay",
            headers=self.viewer_headers,
        )
        replayed = self.client.post(
            "/api/v1/jobs/job_phase3_dlq_api/replay",
            headers=self.operator_headers,
        )

        self.assertEqual(listed.status_code, 200, listed.text)
        self.assertEqual([job["id"] for job in listed.json()], ["job_phase3_dlq_api"])
        self.assertEqual(listed.json()[0]["dead_letter_reason"], "terminal failure")
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(replayed.status_code, 200, replayed.text)
        self.assertEqual(replayed.json()["status"], JobStatus.QUEUED)
        self.assertEqual(replayed.json()["attempts"], 0)
        self.assertIsNone(replayed.json()["dead_lettered_at"])

    def test_operator_can_cancel_failed_job(self) -> None:
        with self.database.transaction() as connection:
            repository = JobStateRepository(connection)
            job = repository.create_job(
                organization_id="org_default",
                environment_id="env_default",
                job_type="demo.noop",
                payload={},
                job_id="job_phase3_failed_cancel",
            )
            running = repository.mark_running(job["id"])
            repository.mark_failed(
                job["id"],
                expected_attempt=int(running["attempts"]),
                error_message="manual review",
                logs=["failed"],
            )

        canceled = self.client.post(
            "/api/v1/jobs/job_phase3_failed_cancel/cancel",
            headers=self.operator_headers,
        )

        self.assertEqual(canceled.status_code, 200, canceled.text)
        self.assertEqual(canceled.json()["status"], JobStatus.CANCELED)


def _always_failing_workflow(inputs: dict[str, Any]) -> WorkflowRunResult:
    return WorkflowRunResult(
        status="failed",
        exit_code=1,
        summary={"error": "temporary workflow failure", "input_keys": sorted(inputs)},
        logs=[
            WorkflowRunLogLine(
                stream="stderr",
                line_number=1,
                message="temporary workflow failure",
            )
        ],
    )


def _past_iso() -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()


if __name__ == "__main__":
    unittest.main()
