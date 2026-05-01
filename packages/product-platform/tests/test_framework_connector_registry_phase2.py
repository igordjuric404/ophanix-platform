from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


class ConnectorInstancesPhase2Tests(unittest.TestCase):
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
                dev_login_allowed_emails=["instances@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "instances@example.com", "roles": ["Platform Admin"]},
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.token = login.json()["access_token"]

    def _headers(self, correlation_id: str | None = None) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
        }
        if correlation_id:
            headers["X-Correlation-ID"] = correlation_id
        return headers

    def _create_instance(self) -> dict:
        response = self.client.post(
            "/api/v1/integrations/framework-instances",
            headers=self._headers(),
            json={
                "integration_id": "openai_agents",
                "name": "OpenAI Agents demo connector",
                "config": {"project": "demo-project", "telemetry_mode": "full"},
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_create_openai_agents_connector_instance(self) -> None:
        instance = self._create_instance()

        self.assertEqual(instance["integration_id"], "openai_agents")
        self.assertEqual(instance["integration_name"], "OpenAI Agents")
        self.assertEqual(instance["status"], "active")
        self.assertEqual(instance["config"]["project"], "demo-project")

        listed = self.client.get("/api/v1/integrations/framework-instances", headers=self._headers())
        self.assertEqual(listed.status_code, 200, listed.text)
        self.assertEqual(listed.json()[0]["id"], instance["id"])

    def test_secret_like_values_rejected_from_config(self) -> None:
        response = self.client.post(
            "/api/v1/integrations/framework-instances",
            headers=self._headers(),
            json={
                "integration_id": "openai_agents",
                "name": "Unsafe connector",
                "config": {"project": "demo-project", "api_key": "sk-secret"},
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("secret-like", response.json()["message"])

    def test_update_emits_audit_event(self) -> None:
        instance = self._create_instance()

        response = self.client.patch(
            f"/api/v1/integrations/framework-instances/{instance['id']}",
            headers=self._headers("corr_instance_update"),
            json={"name": "OpenAI Agents updated", "config": {"project": "demo-project"}},
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["name"], "OpenAI Agents updated")
        with self.database.transaction() as connection:
            audit = connection.execute(
                """
                SELECT *
                FROM audit_events
                WHERE event_type = ?
                  AND resource_id = ?
                  AND correlation_id = ?
                """,
                ("integration.instance.updated", instance["id"], "corr_instance_update"),
            ).fetchone()
        self.assertIsNotNone(audit)


if __name__ == "__main__":
    unittest.main()
