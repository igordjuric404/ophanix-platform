from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.discovery.models import DiscoveryTargetCreateRequest
from product_platform.discovery.repository import DiscoveryRepository
from product_platform.discovery.runner import DiscoveryScanRunner
from product_platform.worker.scheduler import JobScheduleRepository


class DiscoveryScanRunnerPhase4Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
        self.app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-04-30T00:00:00Z",
                dev_login_allowed_emails=["admin@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "admin@example.com", "roles": ["Platform Admin"]},
        )
        self.assertEqual(login.status_code, 200)
        self.token = login.json()["access_token"]

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
        }

    def _create_config_target_api(self, path: str) -> str:
        response = self.client.post(
            "/api/v1/discovery/targets",
            headers=self._headers(),
            json={
                "scanner_type": "config",
                "target_type": "filesystem",
                "target_value": path,
                "config_json": {"paths": [path]},
            },
        )
        self.assertEqual(response.status_code, 201)
        return response.json()["id"]

    def test_api_target_schedule_creates_job_schedule_and_shows_next_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            target_id = self._create_config_target_api(tmpdir)
            next_run_at = datetime(2026, 4, 30, 12, 0, tzinfo=timezone.utc).isoformat()

            response = self.client.patch(
                f"/api/v1/discovery/targets/{target_id}/schedule",
                headers=self._headers(),
                json={"mode": "hourly", "enabled": True, "next_run_at": next_run_at},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["schedule_mode"], "hourly")
        self.assertEqual(payload["next_run_at"], next_run_at)
        self.assertTrue(payload["schedule_id"].startswith("sched_"))

        targets = self.client.get("/api/v1/discovery/targets", headers=self._headers())
        self.assertEqual(targets.status_code, 200)
        self.assertEqual(targets.json()[0]["next_run_at"], next_run_at)

    def test_integration_schedule_enqueues_discovery_job(self) -> None:
        now = datetime(2026, 4, 30, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmpdir:
            target_id = self._create_config_target_api(tmpdir)
            response = self.client.patch(
                f"/api/v1/discovery/targets/{target_id}/schedule",
                headers=self._headers(),
                json={"mode": "hourly", "enabled": True, "next_run_at": now.isoformat()},
            )
            self.assertEqual(response.status_code, 200)

            with self.database.transaction() as connection:
                jobs = JobScheduleRepository(connection).enqueue_due(now)
                rows = connection.execute("SELECT * FROM background_jobs").fetchall()

        self.assertEqual(len(jobs), 1)
        self.assertEqual(rows[0]["job_type"], "discovery.scan")
        self.assertEqual(json.loads(rows[0]["payload_json"])["target_id"], target_id)

    def test_integration_discovery_job_can_run_immediately(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "agentmesh.yaml").write_text("name: job-agent\n", encoding="utf-8")
            target_id = self._create_config_target_api(tmpdir)

            response = self.client.post(
                "/api/v1/jobs",
                headers=self._headers(),
                json={
                    "job_type": "discovery.scan",
                    "payload": {"target_id": target_id},
                    "run_immediately": True,
                },
            )

        self.assertEqual(response.status_code, 201)
        job = response.json()
        self.assertEqual(job["status"], "succeeded")
        self.assertEqual(job["runs"][0]["result"]["discovery_status"], "succeeded")
        self.assertEqual(job["runs"][0]["result"]["raw_finding_count"], 1)

    def test_unit_overlapping_run_is_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.database.transaction() as connection:
                repository = DiscoveryRepository(connection, "org_default", "env_default")
                target = repository.create_target(
                    DiscoveryTargetCreateRequest(
                        scanner_type="config",
                        target_type="filesystem",
                        target_value=tmpdir,
                        config_json={"paths": [tmpdir]},
                    )
                )
                repository.create_run(target)
                skipped = asyncio.run(DiscoveryScanRunner(repository).run_target(target["id"]))
                running_count = connection.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM discovery_runs
                    WHERE target_id = ? AND status = 'running'
                    """,
                    (target["id"],),
                ).fetchone()["count"]
                skipped_count = connection.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM discovery_runs
                    WHERE target_id = ? AND status = 'skipped'
                    """,
                    (target["id"],),
                ).fetchone()["count"]

        self.assertEqual(skipped["status"], "skipped")
        self.assertEqual(json.loads(skipped["summary_json"])["overlap"], True)
        self.assertEqual(running_count, 1)
        self.assertEqual(skipped_count, 1)


if __name__ == "__main__":
    unittest.main()
