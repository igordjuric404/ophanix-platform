from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.marketplace.samples import sample_plugin_manifests


class MarketplaceCatalogPhase1Tests(unittest.TestCase):
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

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
        }

    def test_imports_valid_manifest(self) -> None:
        manifest = sample_plugin_manifests()[0]

        response = self.client.post(
            "/api/v1/marketplace/plugins/import",
            headers=self._headers(),
            json={"manifest": manifest},
        )

        self.assertEqual(response.status_code, 201, response.text)
        plugin = response.json()
        self.assertEqual(plugin["name"], "support-triage-assistant")
        self.assertEqual(plugin["publisher"], "Ophanix Labs")
        self.assertEqual(plugin["plugin_type"], "agent")
        self.assertEqual(plugin["versions"][0]["version"], "1.0.0")
        self.assertEqual(plugin["versions"][0]["signature_status"], "signed")
        self.assertEqual(plugin["versions"][0]["required_capabilities"], ["tickets:read", "tickets:route"])
        self.assertEqual(plugin["versions"][0]["permissions"], ["agent.invoke", "audit.write"])

    def test_invalid_manifest_rejected(self) -> None:
        response = self.client.post(
            "/api/v1/marketplace/plugins/import",
            headers=self._headers(),
            json={
                "manifest": {
                    "name": "bad plugin",
                    "version": "one",
                    "description": "Broken",
                    "author": "Example",
                    "plugin_type": "integration",
                    "package_ref": "local://broken",
                }
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Plugin name", response.json()["message"])

    def test_catalog_list_and_detail_return_imported_plugin(self) -> None:
        for manifest in sample_plugin_manifests():
            imported = self.client.post(
                "/api/v1/marketplace/plugins/import",
                headers=self._headers(),
                json={"manifest": manifest},
            )
            self.assertEqual(imported.status_code, 201, imported.text)

        listed = self.client.get("/api/v1/marketplace/plugins", headers=self._headers())
        self.assertEqual(listed.status_code, 200, listed.text)
        plugins = listed.json()
        self.assertEqual(len(plugins), 2)
        names = {plugin["name"] for plugin in plugins}
        self.assertEqual(names, {"support-triage-assistant", "unsigned-data-exporter"})

        plugin_id = next(plugin["id"] for plugin in plugins if plugin["name"] == "unsigned-data-exporter")
        detail = self.client.get(
            f"/api/v1/marketplace/plugins/{plugin_id}",
            headers=self._headers(),
        )
        self.assertEqual(detail.status_code, 200, detail.text)
        self.assertEqual(detail.json()["versions"][0]["signature_status"], "unsigned")


if __name__ == "__main__":
    unittest.main()
