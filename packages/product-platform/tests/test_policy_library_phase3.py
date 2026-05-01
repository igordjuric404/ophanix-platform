from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.audit.store import AuditEventQuery, AuditEventRepository
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


POLICY_BODY = """version: "1.0"
name: activation-policy
rules:
  - name: block_shell
    condition:
      field: tool_name
      operator: eq
      value: run_shell
    action: deny
"""


class PolicyLibraryPhase3ActivationTests(unittest.TestCase):
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
        self.user = login.json()["user"]

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Request-ID": "req-policy-activation",
            "X-Correlation-ID": "corr-policy-activation",
        }

    def _create_policy_with_versions(self) -> tuple[dict, dict, dict]:
        policy = self.client.post(
            "/api/v1/policies",
            headers=self._headers(),
            json={"name": "Activation Guard", "scope": "agent"},
        )
        self.assertEqual(policy.status_code, 201)
        first = self.client.post(
            f"/api/v1/policies/{policy.json()['id']}/versions",
            headers=self._headers(),
            json={"body_text": POLICY_BODY, "body_format": "yaml"},
        )
        second = self.client.post(
            f"/api/v1/policies/{policy.json()['id']}/versions",
            headers=self._headers(),
            json={
                "body_text": POLICY_BODY.replace("run_shell", "delete_file"),
                "body_format": "yaml",
            },
        )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        return policy.json(), first.json(), second.json()

    def test_integration_activating_version_deactivates_prior_active_version(self) -> None:
        policy, first, second = self._create_policy_with_versions()

        activated_first = self.client.post(
            f"/api/v1/policies/{policy['id']}/versions/{first['id']}/activate",
            headers=self._headers(),
        )
        activated_second = self.client.post(
            f"/api/v1/policies/{policy['id']}/versions/{second['id']}/activate",
            headers=self._headers(),
        )
        versions = self.client.get(
            f"/api/v1/policies/{policy['id']}/versions",
            headers=self._headers(),
        ).json()

        self.assertEqual(activated_first.status_code, 200)
        self.assertEqual(activated_second.status_code, 200)
        by_id = {version["id"]: version for version in versions}
        self.assertEqual(by_id[first["id"]]["status"], "inactive")
        self.assertEqual(by_id[second["id"]]["status"], "active")

    def test_api_rollback_activates_previous_version(self) -> None:
        policy, first, second = self._create_policy_with_versions()
        self.client.post(
            f"/api/v1/policies/{policy['id']}/versions/{second['id']}/activate",
            headers=self._headers(),
        )

        rollback = self.client.post(
            f"/api/v1/policies/{policy['id']}/versions/{first['id']}/rollback",
            headers=self._headers(),
        )
        versions = self.client.get(
            f"/api/v1/policies/{policy['id']}/versions",
            headers=self._headers(),
        ).json()

        self.assertEqual(rollback.status_code, 200)
        self.assertEqual(rollback.json()["status"], "active")
        by_id = {version["id"]: version for version in versions}
        self.assertEqual(by_id[first["id"]]["status"], "active")
        self.assertEqual(by_id[second["id"]]["status"], "inactive")

    def test_api_archived_version_cannot_be_activated(self) -> None:
        policy, first, _ = self._create_policy_with_versions()
        archive = self.client.post(
            f"/api/v1/policies/{policy['id']}/versions/{first['id']}/archive",
            headers=self._headers(),
        )

        activate = self.client.post(
            f"/api/v1/policies/{policy['id']}/versions/{first['id']}/activate",
            headers=self._headers(),
        )

        self.assertEqual(archive.status_code, 200)
        self.assertEqual(archive.json()["status"], "archived")
        self.assertEqual(activate.status_code, 400)
        self.assertIn("Archived policy versions", activate.json()["message"])

    def test_integration_activation_emits_audit_event(self) -> None:
        policy, first, _ = self._create_policy_with_versions()

        response = self.client.post(
            f"/api/v1/policies/{policy['id']}/versions/{first['id']}/activate",
            headers=self._headers(),
        )
        self.assertEqual(response.status_code, 200)
        events = AuditEventRepository(self.database.connect()).query(
            AuditEventQuery(
                organization_id="org_default",
                event_type="policy.version.activated",
                policy_id=policy["id"],
            )
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].resource_type, "policy_version")
        self.assertEqual(events[0].resource_id, first["id"])
        self.assertEqual(events[0].policy_version_id, first["id"])
        self.assertEqual(events[0].actor_id, self.user["id"])
        self.assertEqual(events[0].correlation_id, "corr-policy-activation")


if __name__ == "__main__":
    unittest.main()
