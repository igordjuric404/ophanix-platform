from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.integrations.health import run_provider_health_test
from product_platform.integrations.secrets import DemoLocalSecretProvider


class ProviderHealthPhase2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
        self.secret_provider = DemoLocalSecretProvider()
        self.app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-05-01T00:00:00Z",
                dev_login_allowed_emails=["provider-health@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.app.state.secret_provider = self.secret_provider
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "provider-health@example.com", "roles": ["Platform Admin"]},
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.token = login.json()["access_token"]

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
        }

    def test_model_provider_health_success(self) -> None:
        result = run_provider_health_test("model_provider", "sk-demo")

        self.assertEqual(result.status, "healthy")
        self.assertIn("Model provider", result.message)

    def test_invalid_secret_returns_failed_health(self) -> None:
        result = run_provider_health_test("model_provider", "invalid-secret")

        self.assertEqual(result.status, "failed")
        self.assertIn("invalid", result.message)

    def test_credential_test_stores_health_check(self) -> None:
        credential = self.client.post(
            "/api/v1/integrations/provider-credentials",
            headers=self._headers(),
            json={
                "name": "OpenAI demo key",
                "provider_type": "model_provider",
                "secret_value": "sk-demo-secret",
            },
        )
        self.assertEqual(credential.status_code, 201, credential.text)

        response = self.client.post(
            f"/api/v1/integrations/provider-credentials/{credential.json()['id']}/test",
            headers=self._headers(),
        )

        self.assertEqual(response.status_code, 201, response.text)
        health = response.json()
        self.assertEqual(health["target_type"], "provider_credential")
        self.assertEqual(health["target_id"], credential.json()["id"])
        self.assertEqual(health["status"], "healthy")
        with self.database.transaction() as connection:
            stored = connection.execute(
                "SELECT * FROM integration_health_checks WHERE id = ?",
                (health["id"],),
            ).fetchone()
        self.assertIsNotNone(stored)


if __name__ == "__main__":
    unittest.main()
