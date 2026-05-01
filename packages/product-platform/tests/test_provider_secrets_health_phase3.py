from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.integrations.health import should_emit_repeated_failure_event
from product_platform.integrations.models import FrameworkInstanceCreateRequest
from product_platform.integrations.repository import IntegrationRegistryRepository


class ScheduledHealthPhase3Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
        self.app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-05-01T00:00:00Z",
                dev_login_allowed_emails=["scheduled-health@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "scheduled-health@example.com", "roles": ["Platform Admin"]},
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.token = login.json()["access_token"]

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
        }

    def test_scheduled_health_job_records_result(self) -> None:
        with self.database.transaction() as connection:
            repository = IntegrationRegistryRepository(connection, "org_default", "env_default")
            instance = repository.create_instance(
                FrameworkInstanceCreateRequest(
                    integration_id="openai_agents",
                    name="Scheduled OpenAI connector",
                    config={"project": "demo-project"},
                ),
                created_by="user_admin",
            )
            rows = repository.run_scheduled_health_checks()

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["target_type"], "framework_instance")
        self.assertEqual(rows[0]["target_id"], instance["id"])
        self.assertEqual(rows[0]["status"], "healthy")

    def test_repeated_failure_triggers_event(self) -> None:
        self.assertTrue(should_emit_repeated_failure_event(["failed", "failed", "healthy"]))
        self.assertFalse(should_emit_repeated_failure_event(["failed", "healthy", "failed"]))

    def test_latest_health_check_returns_newest_result(self) -> None:
        first = self.client.post(
            "/api/v1/integrations/health-checks",
            headers=self._headers(),
            json={
                "target_type": "provider_credential",
                "target_id": "provcred_demo",
                "status": "failed",
                "latency_ms": 10,
                "message": "Old failure",
                "details": {},
            },
        )
        self.assertEqual(first.status_code, 201, first.text)
        second = self.client.post(
            "/api/v1/integrations/health-checks",
            headers=self._headers(),
            json={
                "target_type": "provider_credential",
                "target_id": "provcred_demo",
                "status": "healthy",
                "latency_ms": 5,
                "message": "Recovered",
                "details": {},
            },
        )
        self.assertEqual(second.status_code, 201, second.text)

        latest = self.client.get("/api/v1/integrations/health-checks/latest", headers=self._headers())

        self.assertEqual(latest.status_code, 200, latest.text)
        self.assertEqual(latest.json()[0]["status"], "healthy")
        self.assertEqual(latest.json()[0]["message"], "Recovered")


if __name__ == "__main__":
    unittest.main()
