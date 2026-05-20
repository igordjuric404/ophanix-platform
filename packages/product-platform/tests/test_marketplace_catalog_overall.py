from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.marketplace.samples import sample_plugin_manifests
from marketplace_security_helpers import ed25519_key_pair, signed_manifest


class MarketplaceCatalogOverallTests(unittest.TestCase):
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
                dev_login_allowed_emails=["marketplace@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "marketplace@example.com", "roles": ["Platform Admin"]},
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.token = login.json()["access_token"]
        self.private_key, self.public_key = ed25519_key_pair()
        signing_key = self.client.post(
            "/api/v1/marketplace/signing-keys",
            headers=self._headers(),
            json={"name": "Overall Marketplace Root", "public_key": self.public_key},
        )
        self.assertEqual(signing_key.status_code, 201, signing_key.text)

    def _headers(self, correlation_id: str | None = None) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
        }
        if correlation_id:
            headers["X-Correlation-ID"] = correlation_id
        return headers

    def test_overall_marketplace_install_flow(self) -> None:
        imported_plugins = []
        manifests = [
            signed_manifest(sample_plugin_manifests()[0], self.private_key),
            sample_plugin_manifests()[1],
        ]
        for manifest in manifests:
            response = self.client.post(
                "/api/v1/marketplace/plugins/import",
                headers=self._headers(),
                json={"manifest": manifest},
            )
            self.assertEqual(response.status_code, 201, response.text)
            imported_plugins.append(response.json())

        catalog = self.client.get("/api/v1/marketplace/plugins", headers=self._headers())
        self.assertEqual(catalog.status_code, 200, catalog.text)
        self.assertEqual(len(catalog.json()), 2)

        signed = next(plugin for plugin in imported_plugins if plugin["name"] == "support-triage-assistant")
        signed_version_id = signed["versions"][0]["id"]
        allowed = self.client.post(
            f"/api/v1/marketplace/plugins/{signed_version_id}/check-policy",
            headers=self._headers(),
            json={
                "require_signature": True,
                "require_artifact_evidence": True,
                "allowed_plugin_types": ["agent"],
            },
        )
        self.assertEqual(allowed.status_code, 201, allowed.text)
        self.assertEqual(allowed.json()["result"], "allow")
        installed = self.client.post(
            "/api/v1/marketplace/installations",
            headers=self._headers("corr_overall_marketplace"),
            json={"plugin_version_id": signed_version_id, "environment_id": "env_default"},
        )
        self.assertEqual(installed.status_code, 201, installed.text)
        self.assertEqual(installed.json()["status"], "installed")

        unsigned = next(plugin for plugin in imported_plugins if plugin["name"] == "unsigned-data-exporter")
        unsigned_version_id = unsigned["versions"][0]["id"]
        denied = self.client.post(
            f"/api/v1/marketplace/plugins/{unsigned_version_id}/check-policy",
            headers=self._headers(),
            json={"require_signature": True},
        )
        self.assertEqual(denied.status_code, 201, denied.text)
        self.assertEqual(denied.json()["result"], "deny")
        blocked = self.client.post(
            "/api/v1/marketplace/installations",
            headers=self._headers(),
            json={"plugin_version_id": unsigned_version_id, "environment_id": "env_default"},
        )
        self.assertEqual(blocked.status_code, 409)

        installations = self.client.get("/api/v1/marketplace/installations", headers=self._headers())
        self.assertEqual(installations.status_code, 200, installations.text)
        self.assertEqual(len(installations.json()), 1)
        self.assertEqual(installations.json()[0]["plugin_name"], "support-triage-assistant")

        with self.database.transaction() as connection:
            audit_event = connection.execute(
                """
                SELECT *
                FROM audit_events
                WHERE event_type = ?
                  AND correlation_id = ?
                """,
                ("marketplace.plugin.installed", "corr_overall_marketplace"),
            ).fetchone()
        self.assertIsNotNone(audit_event)


if __name__ == "__main__":
    unittest.main()
