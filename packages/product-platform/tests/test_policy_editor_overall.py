from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


VALID_POLICY = """version: "1.0"
name: editor-overall
rules:
  - name: block_shell
    condition:
      field: tool_name
      operator: eq
      value: run_shell
    action: deny
"""


class PolicyEditorOverallValidationTests(unittest.TestCase):
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
                dev_login_allowed_emails=["admin@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "admin@example.com", "roles": ["Policy Admin"]},
        )
        self.assertEqual(login.status_code, 200)
        self.token = login.json()["access_token"]

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}", "X-Request-ID": "req-policy-editor-overall"}

    def test_overall_open_imported_policy_lint_fix_save_and_verify_history(self) -> None:
        imported = self.client.post(
            "/api/v1/policies/import",
            headers=self._headers(),
            json={"body_text": VALID_POLICY, "body_format": "yaml", "scope": "agent"},
        )
        self.assertEqual(imported.status_code, 201)
        policy_id = imported.json()["policy"]["id"]
        invalid_body = VALID_POLICY.replace("operator: eq", "operator: around")

        invalid_lint = self.client.post(
            "/api/v1/policies/lint",
            headers=self._headers(),
            json={"body_text": invalid_body, "body_format": "yaml"},
        )
        fixed_version = self.client.post(
            f"/api/v1/policies/{policy_id}/versions/draft",
            headers=self._headers(),
            json={"body_text": VALID_POLICY.replace("run_shell", "delete_file"), "body_format": "yaml"},
        )
        detail = self.client.get(f"/api/v1/policies/{policy_id}", headers=self._headers())

        self.assertEqual(invalid_lint.status_code, 200)
        self.assertFalse(invalid_lint.json()["passed"])
        self.assertEqual(invalid_lint.json()["issues"][0]["code"], "schema.unknown_operator")
        self.assertEqual(fixed_version.status_code, 201)
        self.assertEqual(detail.status_code, 200)
        versions = detail.json()["versions"]
        self.assertEqual(len(versions), 2)
        self.assertTrue(
            any(
                version["id"] == fixed_version.json()["id"]
                and "delete_file" in version["body_text"]
                for version in versions
            )
        )


if __name__ == "__main__":
    unittest.main()
