from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.marketplace.samples import sample_plugin_manifests
from marketplace_security_helpers import ed25519_key_pair, signed_manifest


class PluginReviewWorkflowPhase1Tests(unittest.TestCase):
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
                dev_login_allowed_emails=["reviewer@example.com", "viewer@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.admin_token = self._login("reviewer@example.com", ["Platform Admin"])
        self.viewer_token = self._login("viewer@example.com", ["Viewer"])
        self.private_key, self.public_key = ed25519_key_pair()
        signing_key = self.client.post(
            "/api/v1/marketplace/signing-keys",
            headers=self._headers(),
            json={"name": "Review Test Root", "public_key": self.public_key},
        )
        self.assertEqual(signing_key.status_code, 201, signing_key.text)

    def _login(self, email: str, roles: list[str]) -> str:
        response = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": email, "roles": roles},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["access_token"]

    def _headers(self, token: str | None = None) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token or self.admin_token}",
            "X-Environment-ID": "env_default",
        }

    def _import_review_required_plugin(self) -> dict:
        manifest = signed_manifest(
            sample_plugin_manifests()[0],
            self.private_key,
            name="review-required-assistant",
            review_required=True,
        )
        response = self.client.post(
            "/api/v1/marketplace/plugins/import",
            headers=self._headers(),
            json={"manifest": manifest},
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_submit_review(self) -> None:
        plugin = self._import_review_required_plugin()
        version_id = plugin["versions"][0]["id"]

        response = self.client.post(
            f"/api/v1/marketplace/plugins/{version_id}/submit-review",
            headers=self._headers(),
            json={"findings": [{"code": "manual_review", "message": "Needs reviewer approval"}]},
        )

        self.assertEqual(response.status_code, 201, response.text)
        review = response.json()
        self.assertEqual(review["plugin_version_id"], version_id)
        self.assertEqual(review["status"], "pending")
        self.assertEqual(review["findings"][0]["code"], "manual_review")

        listed = self.client.get("/api/v1/marketplace/reviews", headers=self._headers())
        self.assertEqual(listed.status_code, 200, listed.text)
        self.assertEqual(listed.json()[0]["id"], review["id"])

    def test_approve_requires_reviewer_role(self) -> None:
        plugin = self._import_review_required_plugin()
        review = self.client.post(
            f"/api/v1/marketplace/plugins/{plugin['versions'][0]['id']}/submit-review",
            headers=self._headers(),
            json={},
        ).json()

        response = self.client.post(
            f"/api/v1/marketplace/reviews/{review['id']}/approve",
            headers=self._headers(self.viewer_token),
            json={"decision_reason": "Looks good"},
        )

        self.assertEqual(response.status_code, 403)

    def test_reject_requires_reason(self) -> None:
        plugin = self._import_review_required_plugin()
        review = self.client.post(
            f"/api/v1/marketplace/plugins/{plugin['versions'][0]['id']}/submit-review",
            headers=self._headers(),
            json={},
        ).json()

        response = self.client.post(
            f"/api/v1/marketplace/reviews/{review['id']}/reject",
            headers=self._headers(),
            json={},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("requires a reason", response.json()["message"])

    def test_unapproved_plugin_cannot_be_installed_when_review_required(self) -> None:
        plugin = self._import_review_required_plugin()
        version_id = plugin["versions"][0]["id"]
        review = self.client.post(
            f"/api/v1/marketplace/plugins/{version_id}/submit-review",
            headers=self._headers(),
            json={},
        ).json()
        allowed = self.client.post(
            f"/api/v1/marketplace/plugins/{version_id}/check-policy",
            headers=self._headers(),
            json={
                "require_signature": True,
                "require_artifact_evidence": True,
                "allowed_plugin_types": ["agent"],
            },
        )
        self.assertEqual(allowed.status_code, 201, allowed.text)
        self.assertEqual(allowed.json()["result"], "allow")

        blocked = self.client.post(
            "/api/v1/marketplace/installations",
            headers=self._headers(),
            json={"plugin_version_id": version_id, "environment_id": "env_default"},
        )
        self.assertEqual(blocked.status_code, 409)
        self.assertIn("review approval", blocked.json()["message"])

        approved = self.client.post(
            f"/api/v1/marketplace/reviews/{review['id']}/approve",
            headers=self._headers(),
            json={"decision_reason": "Review passed"},
        )
        self.assertEqual(approved.status_code, 200, approved.text)
        approved_policy = self.client.post(
            f"/api/v1/marketplace/plugins/{version_id}/check-policy",
            headers=self._headers(),
            json={
                "require_signature": True,
                "require_artifact_evidence": True,
                "require_review_approval": True,
                "allowed_plugin_types": ["agent"],
            },
        )
        self.assertEqual(approved_policy.status_code, 201, approved_policy.text)
        self.assertEqual(approved_policy.json()["result"], "allow")
        installed = self.client.post(
            "/api/v1/marketplace/installations",
            headers=self._headers(),
            json={"plugin_version_id": version_id, "environment_id": "env_default"},
        )
        self.assertEqual(installed.status_code, 201, installed.text)


if __name__ == "__main__":
    unittest.main()
