from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


VALID_POLICY = """version: "1.0"
name: editor-policy
rules:
  - name: block_shell
    condition:
      field: tool_name
      operator: eq
      value: run_shell
    action: deny
"""

INVALID_POLICY = VALID_POLICY.replace("operator: eq", "operator: around")


class PolicyEditorPhase2ApiTests(unittest.TestCase):
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
                dev_login_allowed_emails=["admin@example.com", "viewer@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def _login(self, email: str, roles: list[str]) -> str:
        response = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": email, "roles": roles},
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["access_token"]

    def _headers(self, token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}", "X-Request-ID": "req-policy-editor"}

    def _create_policy(self, token: str) -> dict:
        response = self.client.post(
            "/api/v1/policies",
            headers=self._headers(token),
            json={"name": "Editor Guard", "scope": "agent"},
        )
        self.assertEqual(response.status_code, 201)
        return response.json()

    def test_api_lints_unsaved_body(self) -> None:
        token = self._login("admin@example.com", ["Policy Admin"])

        response = self.client.post(
            "/api/v1/policies/lint",
            headers=self._headers(token),
            json={"body_text": INVALID_POLICY, "body_format": "yaml"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["passed"])
        self.assertEqual(payload["error_count"], 1)
        self.assertEqual(payload["issues"][0]["code"], "schema.unknown_operator")

    def test_api_save_draft_creates_version(self) -> None:
        token = self._login("admin@example.com", ["Policy Admin"])
        policy = self._create_policy(token)

        response = self.client.post(
            f"/api/v1/policies/{policy['id']}/versions/draft",
            headers=self._headers(token),
            json={"body_text": VALID_POLICY, "body_format": "yaml", "status": "active"},
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["status"], "draft")
        self.assertEqual(payload["version_number"], 1)

    def test_api_viewer_cannot_save_draft(self) -> None:
        admin = self._login("admin@example.com", ["Policy Admin"])
        viewer = self._login("viewer@example.com", ["Viewer"])
        policy = self._create_policy(admin)

        response = self.client.post(
            f"/api/v1/policies/{policy['id']}/versions/draft",
            headers=self._headers(viewer),
            json={"body_text": VALID_POLICY, "body_format": "yaml"},
        )

        self.assertEqual(response.status_code, 403)

    def test_integration_lint_results_are_persisted(self) -> None:
        token = self._login("admin@example.com", ["Policy Admin"])
        policy = self._create_policy(token)

        draft = self.client.post(
            f"/api/v1/policies/{policy['id']}/versions/draft",
            headers=self._headers(token),
            json={"body_text": INVALID_POLICY, "body_format": "yaml"},
        )
        self.assertEqual(draft.status_code, 201)
        results = self.client.get(
            f"/api/v1/policies/{policy['id']}/versions/{draft.json()['id']}/lint-results",
            headers=self._headers(token),
        )

        self.assertEqual(results.status_code, 200)
        self.assertEqual(len(results.json()), 1)
        self.assertEqual(results.json()[0]["code"], "schema.unknown_operator")

        relint = self.client.post(
            f"/api/v1/policies/{policy['id']}/versions/{draft.json()['id']}/lint",
            headers=self._headers(token),
        )
        self.assertEqual(relint.status_code, 200)
        self.assertEqual(relint.json()["issues"][0]["code"], "schema.unknown_operator")


if __name__ == "__main__":
    unittest.main()
