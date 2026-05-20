from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.marketplace.samples import sample_plugin_manifests
from marketplace_security_helpers import ed25519_key_pair, signed_manifest


class PluginMarketplaceSecurityPhase3Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
        self.app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-05-20T00:00:00Z",
                dev_login_allowed_emails=["plugin-policy@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "plugin-policy@example.com", "roles": ["Platform Admin"]},
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.token = login.json()["access_token"]
        self.private_key, self.public_key = ed25519_key_pair()
        signing_key = self.client.post(
            "/api/v1/marketplace/signing-keys",
            headers=self._headers(),
            json={"name": "Policy Test Root", "public_key": self.public_key},
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

    def test_marketplace_install_fails_closed_without_policy(self) -> None:
        manifest = signed_manifest(
            sample_plugin_manifests()[0],
            self.private_key,
            name="missing-explicit-policy-plugin",
        )
        imported = self.client.post(
            "/api/v1/marketplace/plugins/import",
            headers=self._headers(),
            json={"manifest": manifest},
        )
        self.assertEqual(imported.status_code, 201, imported.text)
        version_id = imported.json()["versions"][0]["id"]

        installed = self.client.post(
            "/api/v1/marketplace/installations",
            headers=self._headers("corr-missing-install-policy"),
            json={"plugin_version_id": version_id, "environment_id": "env_default"},
        )

        self.assertEqual(installed.status_code, 409)
        self.assertIn("policy result", installed.json()["message"])

        with self.database.transaction() as connection:
            audit = connection.execute(
                """
                SELECT *
                FROM audit_events
                WHERE event_type = ?
                  AND resource_id = ?
                  AND correlation_id = ?
                  AND decision = ?
                """,
                (
                    "marketplace.plugin.install_blocked",
                    version_id,
                    "corr-missing-install-policy",
                    "deny",
                ),
            ).fetchone()
        self.assertIsNotNone(audit)

    def test_marketplace_install_stores_policy_and_artifact_evidence(self) -> None:
        manifest = signed_manifest(
            sample_plugin_manifests()[0],
            self.private_key,
            name="policy-evidence-plugin",
        )
        imported = self.client.post(
            "/api/v1/marketplace/plugins/import",
            headers=self._headers(),
            json={"manifest": manifest},
        )
        self.assertEqual(imported.status_code, 201, imported.text)
        version = imported.json()["versions"][0]
        version_id = version["id"]
        artifact_evidence_id = version["artifact_evidence"]["id"]
        policy = self.client.post(
            f"/api/v1/marketplace/plugins/{version_id}/check-policy",
            headers=self._headers(),
            json={
                "require_signature": True,
                "require_artifact_evidence": True,
                "allowed_plugin_types": ["agent"],
            },
        )
        self.assertEqual(policy.status_code, 201, policy.text)
        self.assertEqual(policy.json()["result"], "allow")

        installed = self.client.post(
            "/api/v1/marketplace/installations",
            headers=self._headers(),
            json={"plugin_version_id": version_id, "environment_id": "env_default"},
        )

        self.assertEqual(installed.status_code, 201, installed.text)
        payload = installed.json()
        self.assertEqual(payload["policy_result_id"], policy.json()["id"])
        self.assertEqual(payload["artifact_evidence_id"], artifact_evidence_id)

    def test_stale_policy_result_cannot_be_reused_for_install(self) -> None:
        manifest = signed_manifest(
            sample_plugin_manifests()[0],
            self.private_key,
            name="stale-policy-plugin",
        )
        imported = self.client.post(
            "/api/v1/marketplace/plugins/import",
            headers=self._headers(),
            json={"manifest": manifest},
        )
        self.assertEqual(imported.status_code, 201, imported.text)
        version_id = imported.json()["versions"][0]["id"]
        policy = self.client.post(
            f"/api/v1/marketplace/plugins/{version_id}/check-policy",
            headers=self._headers(),
            json={
                "require_signature": True,
                "require_artifact_evidence": True,
                "allowed_plugin_types": ["agent"],
            },
        )
        self.assertEqual(policy.status_code, 201, policy.text)
        self.assertEqual(policy.json()["result"], "allow")
        with self.database.transaction() as connection:
            connection.execute(
                "UPDATE plugin_versions SET updated_at = ? WHERE id = ?",
                ("2099-01-01T00:00:00Z", version_id),
            )

        installed = self.client.post(
            "/api/v1/marketplace/installations",
            headers=self._headers(),
            json={"plugin_version_id": version_id, "environment_id": "env_default"},
        )

        self.assertEqual(installed.status_code, 409)
        self.assertIn("stale", installed.json()["message"])


if __name__ == "__main__":
    unittest.main()
