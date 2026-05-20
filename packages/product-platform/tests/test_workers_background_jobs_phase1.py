from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


PACKAGE_DIR = Path(__file__).resolve().parents[1]

VALID_POLICY_BODY = """version: "1.0"
name: worker-phase1-valid
rules: []
defaults:
  action: allow
"""


class WorkersBackgroundJobsPhase1Tests(unittest.TestCase):
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
                dev_login_allowed_emails=["worker-phase1@example.com"],
                session_secret="test-secret",
                artifact_storage_path=self.artifact_root.name,
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "worker-phase1@example.com", "roles": ["Platform Admin"]},
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.token = login.json()["access_token"]

    def tearDown(self) -> None:
        self.database.close()

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
        }

    def _cli_env(self) -> dict[str, str]:
        env = dict(os.environ)
        env["PYTHONPATH"] = str(PACKAGE_DIR / "src")
        env["OPHANIX_DATABASE_URL"] = self.database.database_url
        env["OPHANIX_ARTIFACT_STORAGE_PATH"] = self.artifact_root.name
        env["OPHANIX_SESSION_SECRET"] = "test-secret"
        return env

    def test_cli_worker_consumes_persistent_workflow_job(self) -> None:
        created = self.client.post(
            "/api/v1/workflows/policy_lint/runs",
            headers=self._headers(),
            json={
                "run_immediately": False,
                "inputs": {"policy_body": VALID_POLICY_BODY, "policy_format": "yaml"},
            },
        )
        self.assertEqual(created.status_code, 201, created.text)
        run = created.json()
        self.assertEqual(run["status"], "queued")

        result = subprocess.run(
            [sys.executable, "-m", "product_platform.cli", "worker", "run-once"],
            cwd=PACKAGE_DIR,
            env=self._cli_env(),
            check=True,
            capture_output=True,
            text=True,
        )

        self.assertIn(f"Worker job {run['id']} succeeded", result.stdout)
        completed = self.client.get(f"/api/v1/workflow-runs/{run['id']}", headers=self._headers())
        job = self.client.get(f"/api/v1/jobs/{run['id']}", headers=self._headers())
        self.assertEqual(completed.status_code, 200, completed.text)
        self.assertEqual(job.status_code, 200, job.text)
        self.assertEqual(completed.json()["status"], "succeeded")
        self.assertEqual(job.json()["status"], "succeeded")
        self.assertGreater(len(completed.json()["logs"]), 0)

    def test_cli_worker_ready_checks_persistent_job_store(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "product_platform.cli", "worker", "ready"],
            cwd=PACKAGE_DIR,
            env=self._cli_env(),
            check=True,
            capture_output=True,
            text=True,
        )

        self.assertIn("Worker ready: job store reachable", result.stdout)

    def test_deployment_worker_health_uses_persistent_readiness(self) -> None:
        compose = (PACKAGE_DIR / "docker-compose.demo.yml").read_text()
        worker_dockerfile = (PACKAGE_DIR / "deploy/cloud/Dockerfile.worker").read_text()
        smoke_script = (PACKAGE_DIR / "deploy/cloud/smoke-images.sh").read_text()
        observability = (PACKAGE_DIR / "deploy/cloud/observability.yml").read_text()

        self.assertIn('"worker", "ready"', compose)
        for content in (worker_dockerfile, smoke_script, observability):
            self.assertIn("worker ready", content)
        self.assertNotIn("worker noop", worker_dockerfile)
        self.assertNotIn("worker noop", smoke_script)


if __name__ == "__main__":
    unittest.main()
