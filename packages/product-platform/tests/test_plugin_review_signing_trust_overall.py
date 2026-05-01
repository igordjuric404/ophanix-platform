from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.marketplace.samples import sample_plugin_manifests
from product_platform.marketplace.signing import sign_plugin_manifest_for_demo


class PluginReviewSigningTrustOverallTests(unittest.TestCase):
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
                dev_login_allowed_emails=["overall@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "overall@example.com", "roles": ["Platform Admin"]},
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.token = login.json()["access_token"]

    def _headers(self, correlation_id: str | None = None) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
        }
        if correlation_id:
            headers["X-Correlation-ID"] = correlation_id
        return headers

    def test_overall_review_signature_quality_trust_flow(self) -> None:
        signing_key = self.client.post(
            "/api/v1/marketplace/signing-keys",
            headers=self._headers("corr_overall_key"),
            json={"name": "Overall Marketplace Key", "public_key": "demo-public"},
        )
        self.assertEqual(signing_key.status_code, 201, signing_key.text)

        manifest = {
            **sample_plugin_manifests()[0],
            "name": "overall-trust-assistant",
            "review_required": True,
            "documentation": {
                "readme": "README",
                "examples": ["route-ticket"],
                "api_docs": "API reference",
                "changelog": "Initial release",
            },
            "tests": {"count": 25, "integration": True, "edge_cases": True},
            "operations": {
                "health_check": "/health",
                "rollback": "restore previous package",
                "owner": "ecosystem-ops",
            },
        }
        manifest["signature"] = sign_plugin_manifest_for_demo(manifest, "demo-public")

        imported = self.client.post(
            "/api/v1/marketplace/plugins/import",
            headers=self._headers(),
            json={"manifest": manifest},
        )
        self.assertEqual(imported.status_code, 201, imported.text)
        plugin = imported.json()
        version_id = plugin["versions"][0]["id"]

        review = self.client.post(
            f"/api/v1/marketplace/plugins/{version_id}/submit-review",
            headers=self._headers(),
            json={"findings": [{"code": "manual_review", "message": "Approval required"}]},
        )
        self.assertEqual(review.status_code, 201, review.text)
        self.assertEqual(review.json()["status"], "pending")

        denied_before_review = self.client.post(
            f"/api/v1/marketplace/plugins/{version_id}/check-policy",
            headers=self._headers(),
            json={"require_signature": True, "require_review_approval": True},
        )
        self.assertEqual(denied_before_review.status_code, 201, denied_before_review.text)
        self.assertEqual(denied_before_review.json()["result"], "deny")
        self.assertEqual(denied_before_review.json()["findings"][0]["code"], "review_not_approved")

        assessment = self.client.post(
            f"/api/v1/marketplace/plugins/{version_id}/assess-quality",
            headers=self._headers(),
        )
        self.assertEqual(assessment.status_code, 201, assessment.text)
        self.assertGreaterEqual(assessment.json()["score"], 90)

        approved = self.client.post(
            f"/api/v1/marketplace/reviews/{review.json()['id']}/approve",
            headers=self._headers(),
            json={"decision_reason": "Signature, docs, and operations checks passed."},
        )
        self.assertEqual(approved.status_code, 200, approved.text)
        self.assertEqual(approved.json()["status"], "approved")

        allowed_after_review = self.client.post(
            f"/api/v1/marketplace/plugins/{version_id}/check-policy",
            headers=self._headers(),
            json={
                "require_signature": True,
                "require_review_approval": True,
                "allowed_plugin_types": ["agent"],
            },
        )
        self.assertEqual(allowed_after_review.status_code, 201, allowed_after_review.text)
        self.assertEqual(allowed_after_review.json()["result"], "allow")

        trust = self.client.post(
            f"/api/v1/marketplace/plugins/{version_id}/recompute-trust",
            headers=self._headers(),
            json={
                "daily_active_users": 1000,
                "total_invocations": 5000,
                "error_count": 2,
                "adoption_trend": 0.2,
                "source_event_id": "overall_usage_event",
            },
        )
        self.assertEqual(trust.status_code, 201, trust.text)
        self.assertEqual(trust.json()["trust_tier"], "trusted")

        installed = self.client.post(
            "/api/v1/marketplace/installations",
            headers=self._headers("corr_overall_plugin_install"),
            json={"plugin_version_id": version_id, "environment_id": "env_default"},
        )
        self.assertEqual(installed.status_code, 201, installed.text)
        self.assertEqual(installed.json()["status"], "installed")

        detail = self.client.get(
            f"/api/v1/marketplace/plugins/{plugin['id']}",
            headers=self._headers(),
        )
        self.assertEqual(detail.status_code, 200, detail.text)
        version = detail.json()["versions"][0]
        self.assertEqual(version["trust_tier"], "trusted")
        self.assertEqual(version["quality_score"], assessment.json()["score"])


if __name__ == "__main__":
    unittest.main()
