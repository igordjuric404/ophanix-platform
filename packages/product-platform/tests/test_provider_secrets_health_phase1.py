from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.integrations.secrets import DemoLocalSecretProvider


class ProviderCredentialPhase1Tests(unittest.TestCase):
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
                dev_login_allowed_emails=["provider-secrets@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.app.state.secret_provider = self.secret_provider
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "provider-secrets@example.com", "roles": ["Platform Admin"]},
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.token = login.json()["access_token"]

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
        }

    def test_create_credential_masks_value(self) -> None:
        response = self.client.post(
            "/api/v1/integrations/provider-credentials",
            headers=self._headers(),
            json={
                "name": "OpenAI demo key",
                "provider_type": "model_provider",
                "secret_value": "sk-demo-secret",
            },
        )

        self.assertEqual(response.status_code, 201, response.text)
        credential = response.json()
        self.assertEqual(credential["provider_type"], "model_provider")
        self.assertEqual(credential["masked_secret"], "••••••••")
        self.assertNotIn("sk-demo-secret", response.text)

        listed = self.client.get("/api/v1/integrations/provider-credentials", headers=self._headers())
        self.assertEqual(listed.status_code, 200, listed.text)
        self.assertEqual(listed.json()[0]["id"], credential["id"])
        self.assertNotIn("sk-demo-secret", listed.text)

    def test_raw_secret_is_not_stored(self) -> None:
        response = self.client.post(
            "/api/v1/integrations/provider-credentials",
            headers=self._headers(),
            json={
                "name": "Anthropic demo key",
                "provider_type": "model_provider",
                "secret_value": "sk-raw-value-not-in-db",
            },
        )
        self.assertEqual(response.status_code, 201, response.text)

        with self.database.transaction() as connection:
            rows = connection.execute("SELECT * FROM provider_credentials").fetchall()
            serialized = "\n".join(str(dict(row)) for row in rows)
        self.assertNotIn("sk-raw-value-not-in-db", serialized)
        self.assertIn("secref_", serialized)

    def test_demo_secret_provider_retrieves_by_ref(self) -> None:
        secret_ref = self.secret_provider.store("demo-secret-value")

        self.assertEqual(self.secret_provider.retrieve(secret_ref), "demo-secret-value")


if __name__ == "__main__":
    unittest.main()
