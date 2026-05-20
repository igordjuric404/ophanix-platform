from __future__ import annotations

import unittest
from pathlib import Path
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "agent-marketplace" / "src"))

from agent_marketplace.manifest import PluginManifest, PluginType
from agent_marketplace.signing import PluginSigner

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.marketplace.samples import sample_plugin_manifests
from marketplace_security_helpers import ed25519_key_pair


class PluginMarketplaceSecurityPhase1Tests(unittest.TestCase):
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
                dev_login_allowed_emails=["plugin-security@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "plugin-security@example.com", "roles": ["Platform Admin"]},
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.token = login.json()["access_token"]

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
        }

    def test_plugin_signature_verification_rejects_forgery(self) -> None:
        manifest = {
            **sample_plugin_manifests()[0],
            "name": "forged-signature-plugin",
            "signature": "not-a-real-ed25519-signature",
            "signature_status": "signed",
        }
        imported = self.client.post(
            "/api/v1/marketplace/plugins/import",
            headers=self._headers(),
            json={"manifest": manifest},
        )
        self.assertEqual(imported.status_code, 201, imported.text)
        version_id = imported.json()["versions"][0]["id"]

        response = self.client.post(
            f"/api/v1/marketplace/plugins/{version_id}/check-policy",
            headers=self._headers(),
            json={"require_signature": True},
        )

        self.assertEqual(response.status_code, 201, response.text)
        payload = response.json()
        self.assertEqual(payload["result"], "deny")
        self.assertEqual(payload["findings"][0]["code"], "signature_required")
        self.assertIn(
            payload["findings"][0]["details"]["signature_status"],
            {"invalid", "untrusted"},
        )

    def test_sdk_ed25519_signature_is_accepted_with_active_trusted_key(self) -> None:
        private_key, public_key = ed25519_key_pair()
        signing_key = self.client.post(
            "/api/v1/marketplace/signing-keys",
            headers=self._headers(),
            json={
                "name": "SDK Marketplace Root",
                "public_key": public_key,
                "trusted_root_id": "root_sdk",
            },
        )
        self.assertEqual(signing_key.status_code, 201, signing_key.text)
        sdk_manifest = PluginManifest(
            name="sdk-signed-plugin",
            version="1.0.0",
            description="Signed by the SDK Ed25519 helper.",
            author="Ophanix Labs",
            plugin_type=PluginType.AGENT,
            capabilities=["tickets:read"],
            package_ref="local://plugins/sdk-signed-plugin/1.0.0",
        )
        signed = PluginSigner(private_key).sign(sdk_manifest)
        manifest = {
            **signed.model_dump(mode="json"),
            "permissions": ["agent.invoke"],
            "signature_algorithm": "ed25519",
        }
        imported = self.client.post(
            "/api/v1/marketplace/plugins/import",
            headers=self._headers(),
            json={"manifest": manifest},
        )
        self.assertEqual(imported.status_code, 201, imported.text)
        version_id = imported.json()["versions"][0]["id"]

        response = self.client.post(
            f"/api/v1/marketplace/plugins/{version_id}/check-policy",
            headers=self._headers(),
            json={"require_signature": True},
        )

        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["result"], "allow")


if __name__ == "__main__":
    unittest.main()
