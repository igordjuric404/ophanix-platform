from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


IMPORTED_POLICY = """version: "1.0"
name: overall-policy
description: Overall policy library validation
rules:
  - name: block_shell
    condition:
      field: tool_name
      operator: eq
      value: run_shell
    action: deny
"""


class PolicyLibraryOverallValidationTests(unittest.TestCase):
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
            json={"email": "admin@example.com", "roles": ["Platform Admin"]},
        )
        self.assertEqual(login.status_code, 200)
        self.token = login.json()["access_token"]

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
            "X-Correlation-ID": "corr-policy-overall",
        }

    def test_overall_import_version_activate_rollback_and_audit_explorer_flow(self) -> None:
        imported = self.client.post(
            "/api/v1/policies/import",
            headers=self._headers(),
            json={"body_text": IMPORTED_POLICY, "body_format": "yaml", "scope": "agent"},
        )
        self.assertEqual(imported.status_code, 201)
        policy = imported.json()["policy"]
        first_version = imported.json()["version"]

        second = self.client.post(
            f"/api/v1/policies/{policy['id']}/versions",
            headers=self._headers(),
            json={
                "body_text": IMPORTED_POLICY.replace("run_shell", "delete_file"),
                "body_format": "yaml",
            },
        )
        self.assertEqual(second.status_code, 201)
        activated = self.client.post(
            f"/api/v1/policies/{policy['id']}/versions/{second.json()['id']}/activate",
            headers=self._headers(),
        )
        rollback = self.client.post(
            f"/api/v1/policies/{policy['id']}/versions/{first_version['id']}/rollback",
            headers=self._headers(),
        )
        detail = self.client.get(f"/api/v1/policies/{policy['id']}", headers=self._headers())
        audit_events = self.client.get(
            f"/api/v1/audit/events?policy_id={policy['id']}",
            headers=self._headers(),
        )

        self.assertEqual(activated.status_code, 200)
        self.assertEqual(rollback.status_code, 200)
        self.assertEqual(detail.status_code, 200)
        versions = {version["id"]: version for version in detail.json()["versions"]}
        self.assertEqual(versions[first_version["id"]]["status"], "active")
        self.assertEqual(versions[second.json()["id"]]["status"], "inactive")
        self.assertEqual(audit_events.status_code, 200)
        event_types = [event["event_type"] for event in audit_events.json()]
        self.assertIn("policy.version.activated", event_types)
        self.assertIn("policy.version.rolled_back", event_types)


if __name__ == "__main__":
    unittest.main()
