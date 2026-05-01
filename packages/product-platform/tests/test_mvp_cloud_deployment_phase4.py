from __future__ import annotations

import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings


PACKAGE_DIR = Path(__file__).resolve().parents[1]
CLOUD_DIR = PACKAGE_DIR / "deploy" / "cloud"


class MVPCloudDeploymentPhase4Tests(unittest.TestCase):
    def test_migration_job_runs_migrate_once_per_deploy(self) -> None:
        manifest = (CLOUD_DIR / "migration-job.yml").read_text()

        self.assertIn("kind: Job", manifest)
        self.assertIn('ophanix.io/run-once-per-deploy: "true"', manifest)
        self.assertIn('"product_platform.cli", "db", "migrate"', manifest)
        self.assertIn("restartPolicy: Never", manifest)

    def test_backup_observability_and_alert_definitions_exist(self) -> None:
        backup = (CLOUD_DIR / "backup-restore.md").read_text()
        observability = (CLOUD_DIR / "observability.yml").read_text()
        alerts = (CLOUD_DIR / "alerts.yml").read_text()

        self.assertIn("point-in-time recovery", backup)
        self.assertIn("Restore drill", backup)
        self.assertIn("request_id", observability)
        self.assertIn("correlation_id", observability)
        self.assertIn("ProductPlatformApiUnhealthy", alerts)
        self.assertIn("ProductPlatformWorkerUnhealthy", alerts)

    def test_health_response_includes_request_and_correlation_ids_for_logs(self) -> None:
        client = TestClient(create_app(Settings(session_secret="test-secret")), raise_server_exceptions=False)

        response = client.get(
            "/health",
            headers={
                "X-Request-ID": "req-cloud",
                "X-Correlation-ID": "corr-cloud",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["X-Request-ID"], "req-cloud")
        self.assertEqual(response.headers["X-Correlation-ID"], "corr-cloud")


if __name__ == "__main__":
    unittest.main()
