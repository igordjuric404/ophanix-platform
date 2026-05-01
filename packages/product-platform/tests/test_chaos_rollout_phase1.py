from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


class ChaosExperimentDefinitionsPhase1Tests(unittest.TestCase):
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
                dev_login_allowed_emails=["chaos@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "chaos@example.com", "roles": ["Platform Admin"]},
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.token = login.json()["access_token"]

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
        }

    def _experiment_payload(self) -> dict:
        return {
            "name": "Demo latency experiment",
            "fault_type": "latency",
            "target_type": "agent",
            "target_id": "agent_demo",
            "blast_radius": {"max_agents": 1, "environment": "demo"},
            "guardrails": {"max_error_rate": 0.05, "max_duration_seconds": 60},
        }

    def test_create_demo_chaos_experiment(self) -> None:
        response = self.client.post(
            "/api/v1/observability/chaos/experiments",
            headers=self._headers(),
            json=self._experiment_payload(),
        )

        self.assertEqual(response.status_code, 201, response.text)
        experiment = response.json()
        self.assertEqual(experiment["fault_type"], "latency")
        self.assertEqual(experiment["status"], "ready")
        self.assertEqual(experiment["blast_radius"]["max_agents"], 1)

        listed = self.client.get("/api/v1/observability/chaos/experiments", headers=self._headers())
        self.assertEqual(listed.status_code, 200, listed.text)
        self.assertEqual(listed.json()[0]["id"], experiment["id"])

    def test_missing_guardrail_rejected(self) -> None:
        payload = self._experiment_payload()
        payload["guardrails"] = {}

        response = self.client.post(
            "/api/v1/observability/chaos/experiments",
            headers=self._headers(),
            json=payload,
        )

        self.assertEqual(response.status_code, 422)

    def test_production_target_rejected_by_default(self) -> None:
        payload = self._experiment_payload()
        payload["target_id"] = "production"
        payload["blast_radius"] = {"max_agents": 1, "environment": "production"}

        response = self.client.post(
            "/api/v1/observability/chaos/experiments",
            headers=self._headers(),
            json=payload,
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Production chaos targets", response.json()["message"])


if __name__ == "__main__":
    unittest.main()
