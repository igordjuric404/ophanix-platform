from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.integrations.secrets import DemoLocalSecretProvider


class ProviderSecretsHealthOverallTests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            connection.execute(
                """
                INSERT INTO agents (
                    id, organization_id, environment_id, name, description, framework,
                    runtime_type, owner_user_id, sponsor_user_id, status,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "agent_demo_support",
                    "org_default",
                    "env_default",
                    "Demo Support Agent",
                    "Handles support triage.",
                    "openai_agents",
                    "service",
                    "user_admin",
                    "user_admin",
                    "active",
                    "2026-05-01T00:00:00Z",
                    "2026-05-01T00:00:00Z",
                ),
            )
        self.secret_provider = DemoLocalSecretProvider()
        self.app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-05-01T00:00:00Z",
                dev_login_allowed_emails=["provider-overall@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.app.state.secret_provider = self.secret_provider
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "provider-overall@example.com", "roles": ["Platform Admin"]},
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.token = login.json()["access_token"]

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
        }

    def test_add_key_health_check_link_connector_and_show_latest_health(self) -> None:
        credential = self.client.post(
            "/api/v1/integrations/provider-credentials",
            headers=self._headers(),
            json={
                "name": "OpenAI support key",
                "provider_type": "model_provider",
                "secret_value": "sk-support-demo",
            },
        )
        self.assertEqual(credential.status_code, 201, credential.text)
        credential_body = credential.json()
        self.assertEqual(credential_body["masked_secret"], "••••••••")
        self.assertNotIn("sk-support-demo", credential.text)

        health = self.client.post(
            f"/api/v1/integrations/provider-credentials/{credential_body['id']}/test",
            headers=self._headers(),
        )
        self.assertEqual(health.status_code, 201, health.text)
        self.assertEqual(health.json()["status"], "healthy")
        self.assertEqual(health.json()["target_id"], credential_body["id"])

        instance = self.client.post(
            "/api/v1/integrations/framework-instances",
            headers=self._headers(),
            json={
                "integration_id": "openai_agents",
                "name": "OpenAI Agents support connector",
                "config": {
                    "project": "support-demo",
                    "credential_id": credential_body["id"],
                },
            },
        )
        self.assertEqual(instance.status_code, 201, instance.text)
        self.assertEqual(instance.json()["config"]["credential_id"], credential_body["id"])

        link = self.client.post(
            f"/api/v1/integrations/framework-instances/{instance.json()['id']}/link-agent",
            headers=self._headers(),
            json={
                "agent_id": "agent_demo_support",
                "framework_agent_ref": "assistant:support-demo",
                "sdk_version": "0.3.0",
            },
        )
        self.assertEqual(link.status_code, 201, link.text)
        self.assertEqual(link.json()["agent_name"], "Demo Support Agent")

        latest = self.client.get("/api/v1/integrations/health-checks/latest", headers=self._headers())
        self.assertEqual(latest.status_code, 200, latest.text)
        provider_health = [
            row
            for row in latest.json()
            if row["target_type"] == "provider_credential" and row["target_id"] == credential_body["id"]
        ]
        self.assertEqual(len(provider_health), 1)
        self.assertEqual(provider_health[0]["status"], "healthy")


if __name__ == "__main__":
    unittest.main()
