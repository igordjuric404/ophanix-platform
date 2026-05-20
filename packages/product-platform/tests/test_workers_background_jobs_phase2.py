from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.worker.store import JobStateRepository, JobStatus


class WorkersBackgroundJobsPhase2Tests(unittest.TestCase):
    def test_queue_priority_schedule_guard_and_worker_identity_control_claims(self) -> None:
        database = create_migrated_test_database()
        try:
            now = datetime.now(timezone.utc)
            future = (now + timedelta(hours=1)).isoformat()
            with database.transaction() as connection:
                seed_demo_data(connection)
                repository = JobStateRepository(connection)
                default_job = repository.create_job(
                    organization_id="org_default",
                    environment_id="env_default",
                    job_type="demo.noop",
                    queue_name="default",
                    priority=100,
                    payload={"queue": "default"},
                    job_id="job_default_high",
                )
                low = repository.create_job(
                    organization_id="org_default",
                    environment_id="env_default",
                    job_type="demo.noop",
                    queue_name="critical",
                    priority=1,
                    payload={"order": "low"},
                    job_id="job_critical_low",
                )
                high = repository.create_job(
                    organization_id="org_default",
                    environment_id="env_default",
                    job_type="demo.noop",
                    queue_name="critical",
                    priority=50,
                    payload={"order": "high"},
                    job_id="job_critical_high",
                )
                future_job = repository.create_job(
                    organization_id="org_default",
                    environment_id="env_default",
                    job_type="demo.noop",
                    queue_name="critical",
                    priority=500,
                    scheduled_at=future,
                    payload={"order": "future"},
                    job_id="job_critical_future",
                )

                first = repository.claim_next_queued_job(
                    job_type="demo.noop",
                    queue_name="critical",
                    worker_id="worker-a",
                    lease_seconds=60,
                )
                second = repository.claim_next_queued_job(
                    job_type="demo.noop",
                    queue_name="critical",
                    worker_id="worker-a",
                    lease_seconds=60,
                )
                third = repository.claim_next_queued_job(
                    job_type="demo.noop",
                    queue_name="critical",
                    worker_id="worker-a",
                    lease_seconds=60,
                )
                default_claimed = repository.claim_next_queued_job(
                    job_type="demo.noop",
                    queue_name="default",
                    worker_id="worker-default",
                    lease_seconds=60,
                )

            self.assertEqual(first["id"], high["id"])
            self.assertEqual(first["claimed_by"], "worker-a")
            self.assertIsNotNone(first["lease_until"])
            self.assertIsNotNone(first["heartbeat_at"])
            self.assertEqual(first["attempts"], 1)
            self.assertEqual(second["id"], low["id"])
            self.assertIsNone(third)
            self.assertEqual(default_claimed["id"], default_job["id"])
            self.assertEqual(future_job["status"], JobStatus.QUEUED)
        finally:
            database.close()

    def test_stale_worker_lease_is_recovered_by_next_worker(self) -> None:
        database = create_migrated_test_database()
        try:
            stale_time = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
            with database.transaction() as connection:
                seed_demo_data(connection)
                repository = JobStateRepository(connection)
                job = repository.create_job(
                    organization_id="org_default",
                    environment_id="env_default",
                    job_type="demo.noop",
                    queue_name="critical",
                    payload={"lease": "recover"},
                    max_attempts=3,
                    job_id="job_stale_lease",
                )
                first = repository.claim_next_queued_job(
                    job_type="demo.noop",
                    queue_name="critical",
                    worker_id="worker-a",
                    lease_seconds=60,
                )
                connection.execute(
                    """
                    UPDATE background_jobs
                    SET lease_until = ?, heartbeat_at = ?
                    WHERE id = ?
                    """,
                    (stale_time, stale_time, job["id"]),
                )
                recovered = repository.claim_next_queued_job(
                    job_type="demo.noop",
                    queue_name="critical",
                    worker_id="worker-b",
                    lease_seconds=60,
                )

            self.assertEqual(first["id"], job["id"])
            self.assertEqual(recovered["id"], job["id"])
            self.assertEqual(recovered["claimed_by"], "worker-b")
            self.assertEqual(recovered["attempts"], 2)
            self.assertEqual(recovered["status"], JobStatus.RUNNING)
        finally:
            database.close()

    def test_worker_heartbeat_extends_running_lease(self) -> None:
        database = create_migrated_test_database()
        try:
            with database.transaction() as connection:
                seed_demo_data(connection)
                repository = JobStateRepository(connection)
                repository.create_job(
                    organization_id="org_default",
                    environment_id="env_default",
                    job_type="demo.noop",
                    queue_name="default",
                    payload={"heartbeat": True},
                    job_id="job_heartbeat",
                )
                running = repository.claim_next_queued_job(
                    job_type="demo.noop",
                    queue_name="default",
                    worker_id="worker-heartbeat",
                    lease_seconds=60,
                )
                heartbeat = repository.heartbeat(
                    running["id"],
                    worker_id="worker-heartbeat",
                    expected_attempt=running["attempts"],
                    lease_seconds=120,
                )

            self.assertEqual(heartbeat["id"], running["id"])
            self.assertEqual(heartbeat["claimed_by"], "worker-heartbeat")
            self.assertNotEqual(heartbeat["lease_until"], running["lease_until"])
            self.assertNotEqual(heartbeat["heartbeat_at"], running["heartbeat_at"])
        finally:
            database.close()

    def test_api_job_response_exposes_queue_priority_and_lease_metadata(self) -> None:
        database = create_migrated_test_database()
        try:
            with database.transaction() as connection:
                seed_demo_data(connection)
            app = create_app(
                Settings(
                    app_name="Ophanix Test Platform",
                    environment="test",
                    build_sha="test-sha",
                    build_time="2026-05-20T00:00:00Z",
                    dev_login_allowed_emails=["worker-phase2@example.com"],
                    session_secret="test-secret",
                ),
                database=database,
            )
            client = TestClient(app, raise_server_exceptions=False)
            headers = _login(client)

            created = client.post(
                "/api/v1/jobs",
                headers=headers,
                json={
                    "job_type": "demo.noop",
                    "payload": {"source": "phase2"},
                    "queue_name": "critical",
                    "priority": 42,
                    "concurrency_key": "tenant:phase2",
                },
            )

            self.assertEqual(created.status_code, 201, created.text)
            payload = created.json()
            self.assertEqual(payload["queue_name"], "critical")
            self.assertEqual(payload["priority"], 42)
            self.assertEqual(payload["concurrency_key"], "tenant:phase2")
            self.assertIsNone(payload["claimed_by"])
            self.assertIsNone(payload["lease_until"])
            self.assertIsNone(payload["heartbeat_at"])
        finally:
            database.close()


def _login(client: TestClient) -> dict[str, str]:
    login_body: dict[str, Any] = {
        "email": "worker-phase2@example.com",
        "roles": ["Platform Admin"],
    }
    login = client.post("/api/v1/auth/dev-login", json=login_body)
    if login.status_code != 200:
        raise AssertionError(login.text)
    return {
        "Authorization": f"Bearer {login.json()['access_token']}",
        "X-Environment-ID": "env_default",
    }


if __name__ == "__main__":
    unittest.main()
