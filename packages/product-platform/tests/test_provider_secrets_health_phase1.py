from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.audit.store import AuditEventQuery, AuditEventRepository
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.integrations.secrets import (
    DemoLocalSecretProvider,
    EnvironmentSecretProvider,
    build_secret_provider,
)


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
                dev_login_allowed_emails=[
                    "provider-secrets@example.com",
                    "viewer@example.com",
                    "security@example.com",
                ],
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

    def _login(self, email: str, roles: list[str]) -> str:
        response = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": email, "roles": roles},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["access_token"]

    def _headers(self, token: str | None = None) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token or self.token}",
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

    def test_create_credential_accepts_precreated_secret_ref_for_read_only_provider(self) -> None:
        self.app.state.secret_provider = EnvironmentSecretProvider()
        with patch.dict(os.environ, {"OPHANIX_SECRET_PROVIDER_TOKEN": "sk-demo-secret"}, clear=False):
            credential = self.client.post(
                "/api/v1/integrations/provider-credentials",
                headers=self._headers(),
                json={
                    "name": "OpenAI env key",
                    "provider_type": "model_provider",
                    "secret_ref": "env:OPHANIX_SECRET_PROVIDER_TOKEN",
                },
            )
            self.assertEqual(credential.status_code, 201, credential.text)

            health = self.client.post(
                f"/api/v1/integrations/provider-credentials/{credential.json()['id']}/test",
                headers=self._headers(),
            )

        self.assertEqual(credential.json()["secret_ref"], "env:OPHANIX_SECRET_PROVIDER_TOKEN")
        self.assertNotIn("sk-demo-secret", credential.text)
        self.assertEqual(health.status_code, 201, health.text)
        self.assertEqual(health.json()["status"], "healthy")

    def test_compliance_reader_list_redacts_secret_ref_by_default(self) -> None:
        credential = self.client.post(
            "/api/v1/integrations/provider-credentials",
            headers=self._headers(),
            json={
                "name": "Redacted model key",
                "provider_type": "model_provider",
                "secret_value": "sk-redacted-secret",
            },
        )
        self.assertEqual(credential.status_code, 201, credential.text)
        secret_ref = credential.json()["secret_ref"]
        viewer_token = self._login("viewer@example.com", ["Viewer"])

        listed = self.client.get(
            "/api/v1/integrations/provider-credentials",
            headers=self._headers(viewer_token),
        )

        self.assertEqual(listed.status_code, 200, listed.text)
        payload = listed.json()
        self.assertEqual(len(payload), 1)
        self.assertIsNone(payload[0]["secret_ref"])
        self.assertTrue(payload[0]["secret_ref_redacted"])
        self.assertNotIn(secret_ref, listed.text)
        self.assertNotIn("sk-redacted-secret", listed.text)

    def test_secret_ref_visibility_requires_dedicated_permission(self) -> None:
        credential = self.client.post(
            "/api/v1/integrations/provider-credentials",
            headers=self._headers(),
            json={
                "name": "Privileged model key",
                "provider_type": "model_provider",
                "secret_value": "sk-privileged-secret",
            },
        )
        self.assertEqual(credential.status_code, 201, credential.text)
        secret_ref = credential.json()["secret_ref"]

        default_list = self.client.get(
            "/api/v1/integrations/provider-credentials",
            headers=self._headers(),
        )
        self.assertEqual(default_list.status_code, 200, default_list.text)
        self.assertIsNone(default_list.json()[0]["secret_ref"])
        self.assertTrue(default_list.json()[0]["secret_ref_redacted"])

        privileged_list = self.client.get(
            "/api/v1/integrations/provider-credentials?include_secret_ref=true",
            headers=self._headers(),
        )
        self.assertEqual(privileged_list.status_code, 200, privileged_list.text)
        self.assertEqual(privileged_list.json()[0]["secret_ref"], secret_ref)
        self.assertFalse(privileged_list.json()[0]["secret_ref_redacted"])

        viewer_token = self._login("viewer@example.com", ["Viewer"])
        denied = self.client.get(
            "/api/v1/integrations/provider-credentials?include_secret_ref=true",
            headers=self._headers(viewer_token),
        )
        self.assertEqual(denied.status_code, 403)

    def test_provider_secret_retrieve_emits_audit_event_without_secret_material(self) -> None:
        credential = self.client.post(
            "/api/v1/integrations/provider-credentials",
            headers=self._headers(),
            json={
                "name": "Audited model key",
                "provider_type": "model_provider",
                "secret_value": "sk-audit-secret",
            },
        )
        self.assertEqual(credential.status_code, 201, credential.text)
        credential_id = credential.json()["id"]
        secret_ref = credential.json()["secret_ref"]

        health = self.client.post(
            f"/api/v1/integrations/provider-credentials/{credential_id}/test",
            headers={**self._headers(), "X-Correlation-ID": "corr-secret-retrieve"},
        )

        self.assertEqual(health.status_code, 201, health.text)
        audit_events = AuditEventRepository(self.database.connect()).query(
            AuditEventQuery(
                organization_id="org_default",
                environment_id="env_default",
                event_type="integration.provider_secret.retrieve",
            )
        )
        self.assertEqual(len(audit_events), 1)
        event = audit_events[0]
        self.assertEqual(event.resource_type, "provider_credential")
        self.assertEqual(event.resource_id, credential_id)
        self.assertEqual(event.decision, "allow")
        self.assertEqual(event.correlation_id, "corr-secret-retrieve")
        self.assertEqual(event.payload_json["purpose"], "health_check")
        self.assertTrue(event.payload_json["secret_present"])
        serialized_payload = str(event.payload_json)
        self.assertNotIn(secret_ref, serialized_payload)
        self.assertNotIn("sk-audit-secret", serialized_payload)

    def test_create_credential_rejects_unprefixed_env_secret_ref(self) -> None:
        self.app.state.secret_provider = EnvironmentSecretProvider()

        response = self.client.post(
            "/api/v1/integrations/provider-credentials",
            headers=self._headers(),
            json={
                "name": "Unsafe env key",
                "provider_type": "model_provider",
                "secret_ref": "env:OPHANIX_SESSION_SECRET",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("configured environment secret prefix", response.text)

    def test_create_credential_with_read_only_provider_requires_secret_ref(self) -> None:
        self.app.state.secret_provider = EnvironmentSecretProvider()

        response = self.client.post(
            "/api/v1/integrations/provider-credentials",
            headers=self._headers(),
            json={
                "name": "OpenAI raw key",
                "provider_type": "model_provider",
                "secret_value": "sk-demo-secret",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("secret_ref", response.json()["message"])
        self.assertNotIn("sk-demo-secret", response.text)

    def test_demo_secret_provider_retrieves_by_ref(self) -> None:
        secret_ref = self.secret_provider.store("demo-secret-value")

        self.assertEqual(self.secret_provider.retrieve(secret_ref), "demo-secret-value")

    def test_environment_secret_provider_reads_prefixed_secret_refs(self) -> None:
        with patch.dict(os.environ, {"OPHANIX_SECRET_SECREF_PARTNER": "partner-secret"}, clear=False):
            provider = EnvironmentSecretProvider()

            self.assertEqual(provider.retrieve("secref_partner"), "partner-secret")

    def test_environment_secret_provider_reads_explicit_prefixed_env_refs(self) -> None:
        with patch.dict(os.environ, {"OPHANIX_SECRET_PARTNER_TOKEN": "partner-token"}, clear=False):
            provider = EnvironmentSecretProvider()

            self.assertEqual(provider.retrieve("env:OPHANIX_SECRET_PARTNER_TOKEN"), "partner-token")

    def test_environment_secret_provider_rejects_explicit_unprefixed_env_refs(self) -> None:
        provider = EnvironmentSecretProvider()

        with self.assertRaisesRegex(ValueError, "configured environment secret prefix"):
            provider.retrieve("env:PARTNER_TOKEN")

    def test_environment_secret_provider_is_read_only(self) -> None:
        provider = EnvironmentSecretProvider()

        with self.assertRaisesRegex(RuntimeError, "read-only"):
            provider.store("do-not-store")

    def test_non_local_secret_provider_requires_supported_ref(self) -> None:
        with self.assertRaisesRegex(ValueError, "OPHANIX_SECRET_MANAGER_REF"):
            build_secret_provider(None, environment="production")

        with self.assertRaisesRegex(ValueError, "demo secret provider"):
            build_secret_provider("demo", environment="production")

        provider = build_secret_provider("env:OPHANIX_TOOL_GATEWAY_SECRET_", environment="production")
        self.assertIsInstance(provider, EnvironmentSecretProvider)


if __name__ == "__main__":
    unittest.main()
