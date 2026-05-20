from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.marketplace.samples import sample_plugin_manifests
from marketplace_security_helpers import ed25519_key_pair, signed_manifest


class MarketplaceInstallationPhase3Tests(unittest.TestCase):
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
            json={"name": "Install Test Root", "public_key": self.public_key},
        )
        self.assertEqual(signing_key.status_code, 201, signing_key.text)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
        }

    def _import_manifest(self, manifest: dict) -> dict:
        response = self.client.post(
            "/api/v1/marketplace/plugins/import",
            headers=self._headers(),
            json={"manifest": manifest},
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def _check_allow(self, version_id: str) -> None:
        response = self.client.post(
            f"/api/v1/marketplace/plugins/{version_id}/check-policy",
            headers=self._headers(),
            json={
                "require_signature": True,
                "require_artifact_evidence": True,
                "allowed_plugin_types": ["agent"],
                "allowed_capabilities": ["tickets:read", "tickets:route"],
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["result"], "allow")

    def test_install_allowed_plugin(self) -> None:
        plugin = self._import_manifest(signed_manifest(sample_plugin_manifests()[0], self.private_key))
        version_id = plugin["versions"][0]["id"]
        self._check_allow(version_id)

        installed = self.client.post(
            "/api/v1/marketplace/installations",
            headers=self._headers(),
            json={"plugin_version_id": version_id, "environment_id": "env_default"},
        )

        self.assertEqual(installed.status_code, 201, installed.text)
        payload = installed.json()
        self.assertEqual(payload["plugin_name"], "support-triage-assistant")
        self.assertEqual(payload["status"], "installed")
        self.assertEqual(payload["environment_id"], "env_default")

        listed = self.client.get("/api/v1/marketplace/installations", headers=self._headers())
        self.assertEqual(listed.status_code, 200, listed.text)
        self.assertEqual(listed.json()[0]["id"], payload["id"])

    def test_duplicate_active_install_is_rejected(self) -> None:
        plugin = self._import_manifest(signed_manifest(sample_plugin_manifests()[0], self.private_key))
        version_id = plugin["versions"][0]["id"]
        self._check_allow(version_id)
        first = self.client.post(
            "/api/v1/marketplace/installations",
            headers=self._headers(),
            json={"plugin_version_id": version_id, "environment_id": "env_default"},
        )
        self.assertEqual(first.status_code, 201, first.text)

        duplicate = self.client.post(
            "/api/v1/marketplace/installations",
            headers=self._headers(),
            json={"plugin_version_id": version_id, "environment_id": "env_default"},
        )

        self.assertEqual(duplicate.status_code, 409, duplicate.text)
        self.assertIn("already installed", duplicate.json()["message"])
        listed = self.client.get("/api/v1/marketplace/installations", headers=self._headers())
        self.assertEqual(len(listed.json()), 1)

    def test_install_denied_plugin_fails(self) -> None:
        plugin = self._import_manifest(sample_plugin_manifests()[1])
        version_id = plugin["versions"][0]["id"]
        denied = self.client.post(
            f"/api/v1/marketplace/plugins/{version_id}/check-policy",
            headers=self._headers(),
            json={"require_signature": True},
        )
        self.assertEqual(denied.status_code, 201, denied.text)
        self.assertEqual(denied.json()["result"], "deny")

        installed = self.client.post(
            "/api/v1/marketplace/installations",
            headers=self._headers(),
            json={"plugin_version_id": version_id, "environment_id": "env_default"},
        )

        self.assertEqual(installed.status_code, 409)
        self.assertIn("denies installation", installed.json()["message"])

    def test_uninstall_updates_status(self) -> None:
        plugin = self._import_manifest(signed_manifest(sample_plugin_manifests()[0], self.private_key))
        version_id = plugin["versions"][0]["id"]
        self._check_allow(version_id)
        installed = self.client.post(
            "/api/v1/marketplace/installations",
            headers=self._headers(),
            json={"plugin_version_id": version_id, "environment_id": "env_default"},
        ).json()

        response = self.client.post(
            f"/api/v1/marketplace/installations/{installed['id']}/uninstall",
            headers=self._headers(),
        )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["status"], "uninstalled")
        self.assertIsNotNone(payload["uninstalled_at"])

    def test_install_emits_audit_event(self) -> None:
        plugin = self._import_manifest(signed_manifest(sample_plugin_manifests()[0], self.private_key))
        version_id = plugin["versions"][0]["id"]
        self._check_allow(version_id)
        installed = self.client.post(
            "/api/v1/marketplace/installations",
            headers={**self._headers(), "X-Correlation-ID": "corr_marketplace_install"},
            json={"plugin_version_id": version_id, "environment_id": "env_default"},
        )
        self.assertEqual(installed.status_code, 201, installed.text)

        with self.database.transaction() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM audit_events
                WHERE event_type = ?
                  AND resource_id = ?
                  AND correlation_id = ?
                """,
                (
                    "marketplace.plugin.installed",
                    installed.json()["id"],
                    "corr_marketplace_install",
                ),
            ).fetchone()

        self.assertIsNotNone(row)


if __name__ == "__main__":
    unittest.main()
