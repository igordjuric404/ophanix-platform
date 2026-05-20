from __future__ import annotations

import unittest
from datetime import datetime, timezone
from typing import Any

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.worker.persistent import PersistentJobWorker
from product_platform.worker.scheduler import JobScheduleRepository
from product_platform.worker.store import (
    JobIdempotencyConflictError,
    JobStateRepository,
    JobStatus,
)


class WorkersBackgroundJobsPhase4Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
        self.app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-05-20T00:00:00Z",
                dev_login_allowed_emails=["worker-phase4@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.operator_headers = self._login("worker-phase4@example.com", ["Operator"])

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

    def test_duplicate_enqueue_api_returns_existing_job_and_rejects_conflict(self) -> None:
        body: dict[str, Any] = {
            "job_type": "demo.noop",
            "payload": {"source": "phase4"},
            "idempotency_key": "phase4-api-key",
            "operation_type": "manual",
            "operation_id": "phase4-operation",
        }
        first = self.client.post("/api/v1/jobs", json=body, headers=self.operator_headers)
        second = self.client.post("/api/v1/jobs", json=body, headers=self.operator_headers)
        conflict = self.client.post(
            "/api/v1/jobs",
            json={**body, "payload": {"source": "changed"}},
            headers=self.operator_headers,
        )

        self.assertEqual(first.status_code, 201, first.text)
        self.assertEqual(second.status_code, 201, second.text)
        self.assertEqual(first.json()["id"], second.json()["id"])
        self.assertEqual(second.json()["idempotency_key"], "phase4-api-key")
        self.assertEqual(second.json()["operation_type"], "manual")
        self.assertEqual(second.json()["operation_id"], "phase4-operation")
        self.assertEqual(conflict.status_code, 409, conflict.text)
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM background_jobs
                WHERE idempotency_key = ?
                """,
                ("phase4-api-key",),
            ).fetchone()
        self.assertEqual(row["count"], 1)

    def test_scheduler_uses_operation_identity_for_duplicate_safe_enqueue(self) -> None:
        due_at = "2026-05-20T10:00:00+00:00"
        now = datetime(2026, 5, 20, 10, 0, 1, tzinfo=timezone.utc)
        with self.database.transaction() as connection:
            schedules = JobScheduleRepository(connection)
            schedule = schedules.create_schedule(
                organization_id="org_default",
                environment_id="env_default",
                job_type="demo.noop",
                expression="interval:5m",
                payload={"scheduled": True},
                next_run_at=due_at,
                schedule_id="sched_phase4_dedupe",
            )
            first = schedules.enqueue_due(now)
            connection.execute(
                "UPDATE job_schedules SET next_run_at = ? WHERE id = ?",
                (due_at, schedule["id"]),
            )
            duplicate = schedules.enqueue_due(now)
            rows = connection.execute(
                """
                SELECT idempotency_key, operation_type, operation_id
                FROM background_jobs
                WHERE operation_type = ?
                """,
                ("schedule",),
            ).fetchall()

        self.assertEqual(len(first), 1)
        self.assertEqual(duplicate, [])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["idempotency_key"], f"schedule:{schedule['id']}:{due_at}")
        self.assertEqual(rows[0]["operation_type"], "schedule")
        self.assertEqual(rows[0]["operation_id"], f"{schedule['id']}:{due_at}")

    def test_idempotent_duplicate_job_claim_executes_side_effect_once(self) -> None:
        with self.database.transaction() as connection:
            repository = JobStateRepository(connection)
            first = repository.create_job(
                organization_id="org_default",
                environment_id="env_default",
                job_type="demo.noop",
                payload={"once": True},
                idempotency_key="phase4-worker-once",
                operation_type="manual",
                operation_id="phase4-worker-operation",
            )
            duplicate = repository.create_job(
                organization_id="org_default",
                environment_id="env_default",
                job_type="demo.noop",
                payload={"once": True},
                idempotency_key="phase4-worker-once",
                operation_type="manual",
                operation_id="phase4-worker-operation",
            )

        first_run = PersistentJobWorker(self.database, worker_id="phase4-worker").run_once()
        second_run = PersistentJobWorker(self.database, worker_id="phase4-worker").run_once()
        with self.database.transaction() as connection:
            repository = JobStateRepository(connection)
            current = repository.get_job(first["id"])
            runs = repository.runs_for_job(first["id"])
            with self.assertRaises(JobIdempotencyConflictError):
                repository.create_job(
                    organization_id="org_default",
                    environment_id="env_default",
                    job_type="demo.noop",
                    payload={"once": False},
                    idempotency_key="phase4-worker-once",
                    operation_type="manual",
                    operation_id="phase4-worker-operation",
                )

        self.assertEqual(first["id"], duplicate["id"])
        self.assertIsNotNone(first_run)
        self.assertEqual(first_run.status, JobStatus.SUCCEEDED)
        self.assertIsNone(second_run)
        self.assertEqual(current["status"], JobStatus.SUCCEEDED)
        self.assertEqual(len(runs), 1)


if __name__ == "__main__":
    unittest.main()
