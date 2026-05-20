from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.marketplace.samples import sample_plugin_manifests
from product_platform.marketplace.signing import verify_plugin_signature_with_key
from marketplace_security_helpers import ed25519_key_pair, signed_manifest


class PluginSigningKeysPhase2Tests(unittest.TestCase):
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
                dev_login_allowed_emails=["signer@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "signer@example.com", "roles": ["Platform Admin"]},
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.token = login.json()["access_token"]
        self.private_key, self.public_key = ed25519_key_pair()

    def _headers(self, correlation_id: str | None = None) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
        }
        if correlation_id:
            headers["X-Correlation-ID"] = correlation_id
        return headers

    def test_add_signing_key(self) -> None:
        response = self.client.post(
            "/api/v1/marketplace/signing-keys",
            headers=self._headers("corr_key_add"),
            json={"name": "Demo Marketplace Key", "public_key": self.public_key},
        )

        self.assertEqual(response.status_code, 201, response.text)
        signing_key = response.json()
        self.assertEqual(signing_key["name"], "Demo Marketplace Key")
        self.assertEqual(signing_key["status"], "active")
        self.assertEqual(signing_key["key_type"], "ed25519")
        self.assertEqual(len(signing_key["public_key_fingerprint"]), 64)

        listed = self.client.get("/api/v1/marketplace/signing-keys", headers=self._headers())
        self.assertEqual(listed.status_code, 200, listed.text)
        self.assertEqual(listed.json()[0]["id"], signing_key["id"])

        with self.database.transaction() as connection:
            audit = connection.execute(
                """
                SELECT *
                FROM audit_events
                WHERE event_type = ?
                  AND resource_id = ?
                  AND correlation_id = ?
                """,
                ("marketplace.signing_key.created", signing_key["id"], "corr_key_add"),
            ).fetchone()
        self.assertIsNotNone(audit)

    def test_plugin_signature_verifies_with_active_key(self) -> None:
        manifest = signed_manifest(
            sample_plugin_manifests()[0],
            self.private_key,
            name="signed-active-key",
        )

        self.assertTrue(
            verify_plugin_signature_with_key(
                manifest,
                public_key=self.public_key,
                key_status="active",
            )
        )

    def test_revoked_key_does_not_verify(self) -> None:
        manifest = signed_manifest(
            sample_plugin_manifests()[0],
            self.private_key,
            name="signed-revoked-key",
        )

        self.assertFalse(
            verify_plugin_signature_with_key(
                manifest,
                public_key=self.public_key,
                key_status="revoked",
            )
        )

    def test_revoked_key_invalidates_policy_signature_check(self) -> None:
        manifest = signed_manifest(
            sample_plugin_manifests()[0],
            self.private_key,
            name="signed-policy-key",
        )
        imported = self.client.post(
            "/api/v1/marketplace/plugins/import",
            headers=self._headers(),
            json={"manifest": manifest},
        )
        self.assertEqual(imported.status_code, 201, imported.text)
        version_id = imported.json()["versions"][0]["id"]
        signing_key = self.client.post(
            "/api/v1/marketplace/signing-keys",
            headers=self._headers(),
            json={"name": "Policy Key", "public_key": self.public_key},
        ).json()

        allowed = self.client.post(
            f"/api/v1/marketplace/plugins/{version_id}/check-policy",
            headers=self._headers(),
            json={"require_signature": True},
        )
        self.assertEqual(allowed.status_code, 201, allowed.text)
        self.assertEqual(allowed.json()["result"], "allow")

        revoked = self.client.post(
            f"/api/v1/marketplace/signing-keys/{signing_key['id']}/revoke",
            headers=self._headers("corr_key_revoke"),
        )
        self.assertEqual(revoked.status_code, 200, revoked.text)
        self.assertEqual(revoked.json()["status"], "revoked")
        denied = self.client.post(
            f"/api/v1/marketplace/plugins/{version_id}/check-policy",
            headers=self._headers(),
            json={"require_signature": True},
        )
        self.assertEqual(denied.status_code, 201, denied.text)
        self.assertEqual(denied.json()["result"], "deny")
        self.assertEqual(denied.json()["findings"][0]["details"]["signature_status"], "invalid")


if __name__ == "__main__":
    unittest.main()
