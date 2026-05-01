from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.observability.slo import evaluate_slo_measurement


class ObservabilitySloPhase1Tests(unittest.TestCase):
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
                dev_login_allowed_emails=["slo@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "slo@example.com", "roles": ["Platform Admin"]},
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.token = login.json()["access_token"]

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
        }

    def _create_slo(self) -> dict:
        response = self.client.post(
            "/api/v1/observability/slo",
            headers=self._headers(),
            json={
                "name": "Demo agent task success",
                "target_type": "agent",
                "target_id": "agent_demo",
                "sli": "task_success_rate",
                "target_value": 0.99,
                "window": "30d",
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_burn_rate_calculation(self) -> None:
        result = evaluate_slo_measurement(target_value=0.99, value=0.995)

        self.assertEqual(result.burn_rate, 0.5)
        self.assertEqual(result.error_budget_remaining, 0.5)
        self.assertEqual(result.status, "healthy")

    def test_create_slo(self) -> None:
        slo = self._create_slo()

        self.assertEqual(slo["name"], "Demo agent task success")
        self.assertEqual(slo["target_type"], "agent")
        self.assertEqual(slo["target_value"], 0.99)
        self.assertEqual(slo["status"], "unknown")

        listed = self.client.get("/api/v1/observability/slo", headers=self._headers())
        self.assertEqual(listed.status_code, 200, listed.text)
        self.assertEqual(listed.json()[0]["id"], slo["id"])

    def test_measurement_updates_status(self) -> None:
        slo = self._create_slo()
        measurement = self.client.post(
            f"/api/v1/observability/slo/{slo['id']}/measurements",
            headers=self._headers(),
            json={
                "value": 0.95,
                "good_events": 95,
                "total_events": 100,
                "metadata": {"source": "agent_runtime"},
                "measured_at": "2026-05-01T00:10:00+00:00",
            },
        )

        self.assertEqual(measurement.status_code, 201, measurement.text)
        payload = measurement.json()
        self.assertEqual(payload["slo_id"], slo["id"])
        self.assertEqual(payload["burn_rate"], 5.0)
        self.assertEqual(payload["status"], "exhausted")

        listed = self.client.get("/api/v1/observability/slo", headers=self._headers())
        self.assertEqual(listed.status_code, 200, listed.text)
        updated = listed.json()[0]
        self.assertEqual(updated["status"], "exhausted")
        self.assertEqual(updated["measurements"][0]["id"], payload["id"])
        self.assertEqual(updated["measurements"][0]["metadata"]["source"], "agent_runtime")


if __name__ == "__main__":
    unittest.main()
