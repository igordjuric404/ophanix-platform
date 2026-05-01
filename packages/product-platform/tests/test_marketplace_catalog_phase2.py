from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.marketplace.models import PluginPolicyCheckRequest
from product_platform.marketplace.policy import PluginPolicyInput, evaluate_plugin_policy
from product_platform.marketplace.repository import MarketplaceCatalogRepository
from product_platform.marketplace.samples import sample_plugin_manifests


class MarketplacePolicyPhase2Tests(unittest.TestCase):
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

    def _import_manifest(self, manifest: dict) -> dict:
        response = self.client.post(
            "/api/v1/marketplace/plugins/import",
            headers=self._headers(),
            json={"manifest": manifest},
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_unsigned_plugin_denied_when_signature_required(self) -> None:
        evaluation = evaluate_plugin_policy(
            PluginPolicyInput(
                plugin_type="integration",
                signature_status="unsigned",
                required_capabilities=["data:export"],
                manifest={"organization": "global"},
            ),
            PluginPolicyCheckRequest(require_signature=True),
        )

        self.assertEqual(evaluation.result, "deny")
        self.assertEqual(evaluation.findings[0]["code"], "signature_required")

    def test_allowed_plugin_passes(self) -> None:
        evaluation = evaluate_plugin_policy(
            PluginPolicyInput(
                plugin_type="agent",
                signature_status="signed",
                required_capabilities=["tickets:read"],
                manifest={"organization": "Ophanix Demo", "review_required": True, "review_status": "approved"},
            ),
            PluginPolicyCheckRequest(
                require_signature=True,
                allowed_plugin_types=["agent"],
                allowed_capabilities=["tickets:read", "tickets:route"],
                allowed_organizations=["Ophanix Demo"],
                require_review_approval=True,
            ),
        )

        self.assertEqual(evaluation.result, "allow")
        self.assertEqual(evaluation.findings, [])

    def test_check_policy_persists_result_and_install_gate(self) -> None:
        plugin = self._import_manifest(sample_plugin_manifests()[1])
        version_id = plugin["versions"][0]["id"]

        response = self.client.post(
            f"/api/v1/marketplace/plugins/{version_id}/check-policy",
            headers=self._headers(),
            json={
                "require_signature": True,
                "allowed_plugin_types": ["integration"],
                "allowed_capabilities": ["data:read"],
            },
        )

        self.assertEqual(response.status_code, 201, response.text)
        result = response.json()
        self.assertEqual(result["plugin_version_id"], version_id)
        self.assertEqual(result["result"], "deny")
        codes = {finding["code"] for finding in result["findings"]}
        self.assertEqual(codes, {"signature_required", "capability_not_allowed"})

        with self.database.transaction() as connection:
            repository = MarketplaceCatalogRepository(connection, "org_default")
            latest = repository.latest_policy_result_for_version(version_id)
            self.assertIsNotNone(latest)
            self.assertEqual(latest["result"], "deny")
            self.assertFalse(repository.version_install_allowed(version_id))


if __name__ == "__main__":
    unittest.main()
