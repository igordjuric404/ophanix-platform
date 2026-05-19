from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.api.tenancy import Environment, TenantStore
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.integrations.secrets import DemoLocalSecretProvider


class ProviderCredentialScopePhase4Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            connection.execute(
                """
                INSERT INTO environments
                    (id, organization_id, name, slug, type, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "env_second",
                    "org_default",
                    "Second",
                    "second",
                    "development",
                    "2026-05-01T00:00:00Z",
                    "2026-05-01T00:00:00Z",
                ),
            )
        self.secret_provider = DemoLocalSecretProvider()
        tenant_store = TenantStore(
            environments=[
                Environment(
                    id="env_default",
                    organization_id="org_default",
                    name="Development",
                    slug="development",
                    type="development",
                    created_at="2026-05-01T00:00:00Z",
                ),
                Environment(
                    id="env_second",
                    organization_id="org_default",
                    name="Second",
                    slug="second",
                    type="development",
                    created_at="2026-05-01T00:00:00Z",
                ),
            ]
        )
        self.app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-05-01T00:00:00Z",
                dev_login_allowed_emails=[
                    "provider-scope@example.com",
                    "provider-viewer@example.com",
                ],
                session_secret="test-secret",
            ),
            database=self.database,
            tenant_store=tenant_store,
        )
        self.app.state.secret_provider = self.secret_provider
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={
                "email": "provider-scope@example.com",
                "roles": ["Platform Admin"],
                "environment_ids": ["env_default", "env_second"],
            },
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.token = login.json()["access_token"]

    def _login(self, email: str, roles: list[str]) -> str:
        response = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": email, "roles": roles},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["access_token"]

    def _headers(self, *, environment_id: str = "env_default", token: str | None = None) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token or self.token}",
            "X-Environment-ID": environment_id,
        }

    def _create_credential(self, **overrides: object) -> dict[str, object]:
        payload: dict[str, object] = {
            "name": "Scoped provider credential",
            "provider_type": "model_provider",
            "secret_value": "sk-scoped-secret",
        }
        payload.update(overrides)
        response = self.client.post(
            "/api/v1/integrations/provider-credentials",
            headers=self._headers(environment_id=str(payload.pop("_environment_id", "env_default"))),
            json=payload,
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_provider_credential_environment_scope_enforced(self) -> None:
        credential = self._create_credential(name="Environment scoped model key")

        self.assertEqual(credential["environment_id"], "env_default")

        default_list = self.client.get(
            "/api/v1/integrations/provider-credentials",
            headers=self._headers(environment_id="env_default"),
        )
        self.assertEqual(default_list.status_code, 200, default_list.text)
        self.assertEqual([row["id"] for row in default_list.json()], [credential["id"]])

        second_list = self.client.get(
            "/api/v1/integrations/provider-credentials",
            headers=self._headers(environment_id="env_second"),
        )
        self.assertEqual(second_list.status_code, 200, second_list.text)
        self.assertEqual(second_list.json(), [])

        cross_environment_health = self.client.post(
            f"/api/v1/integrations/provider-credentials/{credential['id']}/test",
            headers=self._headers(environment_id="env_second"),
        )
        self.assertEqual(cross_environment_health.status_code, 404, cross_environment_health.text)

    def test_expired_and_revoked_credentials_cannot_be_selected(self) -> None:
        expired = self._create_credential(
            name="Expired model key",
            expires_at="2020-01-01T00:00:00Z",
        )

        expired_health = self.client.post(
            f"/api/v1/integrations/provider-credentials/{expired['id']}/test",
            headers=self._headers(),
        )
        self.assertEqual(expired_health.status_code, 409, expired_health.text)
        self.assertIn("expired", expired_health.text)

        revoked = self._create_credential(
            name="Revoked model key",
            status="revoked",
        )
        framework_instance = self.client.post(
            "/api/v1/integrations/framework-instances",
            headers=self._headers(),
            json={
                "integration_id": "openai_agents",
                "name": "Revoked credential connector",
                "config": {
                    "project": "support-demo",
                    "credential_id": revoked["id"],
                },
            },
        )
        self.assertEqual(framework_instance.status_code, 409, framework_instance.text)
        self.assertIn("revoked", framework_instance.text)

    def test_sensitive_provider_credential_metadata_is_redacted_for_broad_readers(self) -> None:
        credential = self._create_credential(
            name="User scoped provider key",
            subject_type="user",
            subject_id="user_sales",
            provider_account_id="acct_sales_external",
            credential_type="oauth",
            scopes=["crm:read", "crm:write"],
            allowed_tool_ids=["openai_agents"],
        )
        self.assertEqual(credential["subject_id"], "user_sales")
        self.assertEqual(credential["provider_account_id"], "acct_sales_external")

        viewer_token = self._login("provider-viewer@example.com", ["Viewer"])
        listed = self.client.get(
            "/api/v1/integrations/provider-credentials",
            headers=self._headers(token=viewer_token),
        )

        self.assertEqual(listed.status_code, 200, listed.text)
        payload = listed.json()
        self.assertEqual(len(payload), 1)
        row = payload[0]
        self.assertEqual(row["environment_id"], "env_default")
        self.assertEqual(row["subject_type"], "user")
        self.assertIsNone(row["subject_id"])
        self.assertTrue(row["subject_id_redacted"])
        self.assertIsNone(row["provider_account_id"])
        self.assertTrue(row["provider_account_id_redacted"])
        self.assertIsNone(row["secret_ref"])
        self.assertTrue(row["secret_ref_redacted"])
        self.assertEqual(row["scopes"], ["crm:read", "crm:write"])
        self.assertEqual(row["allowed_tool_ids"], ["openai_agents"])
        self.assertNotIn("user_sales", listed.text)
        self.assertNotIn("acct_sales_external", listed.text)


if __name__ == "__main__":
    unittest.main()
