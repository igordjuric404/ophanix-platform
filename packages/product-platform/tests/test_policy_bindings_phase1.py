from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.audit.store import AuditEventQuery, AuditEventRepository
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


POLICY_BODY = """version: "1.0"
name: binding-policy
rules:
  - name: block_shell
    condition:
      field: tool_name
      operator: eq
      value: run_shell
    action: deny
"""


class PolicyBindingsPhase1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection, "agent_default", "org_default", "env_default", "Claims Agent")
            connection.execute(
                """
                INSERT INTO organizations (id, name, slug, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    "org_other",
                    "Other Org",
                    "other-org",
                    "2026-05-01T00:00:00+00:00",
                    "2026-05-01T00:00:00+00:00",
                ),
            )
            connection.execute(
                """
                INSERT INTO environments (id, organization_id, name, slug, type, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "env_other",
                    "org_other",
                    "Other",
                    "other",
                    "development",
                    "2026-05-01T00:00:00+00:00",
                    "2026-05-01T00:00:00+00:00",
                ),
            )
            self._insert_agent(connection, "agent_other", "org_other", "env_other", "Other Agent")
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
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
            "X-Correlation-ID": "corr-policy-binding",
        }

    def _insert_agent(self, connection, agent_id: str, org_id: str, env_id: str, name: str) -> None:
        now = "2026-05-01T00:00:00+00:00"
        connection.execute(
            """
            INSERT INTO agents (
                id, organization_id, environment_id, name, description, framework,
                runtime_type, owner_user_id, sponsor_user_id, status, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                agent_id,
                org_id,
                env_id,
                name,
                "",
                "langgraph",
                "service",
                "owner",
                "sponsor",
                "active",
                now,
                now,
            ),
        )

    def _create_policy_version(self) -> tuple[dict, dict]:
        policy = self.client.post(
            "/api/v1/policies",
            headers=self._headers(),
            json={"name": "Binding Guard", "scope": "agent"},
        )
        self.assertEqual(policy.status_code, 201)
        version = self.client.post(
            f"/api/v1/policies/{policy.json()['id']}/versions",
            headers=self._headers(),
            json={"body_text": POLICY_BODY, "body_format": "yaml"},
        )
        self.assertEqual(version.status_code, 201)
        return policy.json(), version.json()

    def test_api_create_agent_binding(self) -> None:
        policy, version = self._create_policy_version()

        response = self.client.post(
            "/api/v1/policy-bindings",
            headers=self._headers(),
            json={
                "policy_id": policy["id"],
                "policy_version_id": version["id"],
                "target_type": "agent",
                "target_id": "agent_default",
                "mode": "shadow",
                "rollout_percentage": 25,
                "priority": 10,
            },
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertTrue(payload["id"].startswith("pbind_"))
        self.assertEqual(payload["target_type"], "agent")
        self.assertEqual(payload["target_id"], "agent_default")
        self.assertEqual(payload["policy_version_id"], version["id"])
        self.assertEqual(payload["mode"], "shadow")
        self.assertEqual(payload["rollout_percentage"], 25)

    def test_api_invalid_target_is_rejected(self) -> None:
        policy, version = self._create_policy_version()

        response = self.client.post(
            "/api/v1/policy-bindings",
            headers=self._headers(),
            json={
                "policy_id": policy["id"],
                "policy_version_id": version["id"],
                "target_type": "agent",
                "target_id": "agent_missing",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Agent target not found", response.json()["message"])

    def test_api_binding_cannot_target_another_organization(self) -> None:
        policy, version = self._create_policy_version()

        response = self.client.post(
            "/api/v1/policy-bindings",
            headers=self._headers(),
            json={
                "policy_id": policy["id"],
                "policy_version_id": version["id"],
                "target_type": "agent",
                "target_id": "agent_other",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Agent target not found", response.json()["message"])

    def test_integration_audit_event_emitted(self) -> None:
        policy, version = self._create_policy_version()

        response = self.client.post(
            "/api/v1/policy-bindings",
            headers=self._headers(),
            json={
                "policy_id": policy["id"],
                "policy_version_id": version["id"],
                "target_type": "agent",
                "target_id": "agent_default",
            },
        )
        self.assertEqual(response.status_code, 201)
        events = AuditEventRepository(self.database.connect()).query(
            AuditEventQuery(
                organization_id="org_default",
                event_type="policy.binding.created",
                policy_id=policy["id"],
            )
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].resource_type, "policy_binding")
        self.assertEqual(events[0].resource_id, response.json()["id"])
        self.assertEqual(events[0].payload_json["target_id"], "agent_default")
        self.assertEqual(events[0].correlation_id, "corr-policy-binding")

    def test_api_list_patch_delete_and_exception_endpoints(self) -> None:
        policy, version = self._create_policy_version()
        created = self.client.post(
            "/api/v1/policy-bindings",
            headers=self._headers(),
            json={
                "policy_id": policy["id"],
                "policy_version_id": version["id"],
                "target_type": "agent",
                "target_id": "agent_default",
            },
        )
        self.assertEqual(created.status_code, 201)
        binding_id = created.json()["id"]

        listed = self.client.get("/api/v1/policy-bindings", headers=self._headers())
        patched = self.client.patch(
            f"/api/v1/policy-bindings/{binding_id}",
            headers=self._headers(),
            json={"mode": "audit-only", "rollout_percentage": 50},
        )
        exception = self.client.post(
            f"/api/v1/policy-bindings/{binding_id}/exceptions",
            headers=self._headers(),
            json={"reason": "temporary maintenance", "expires_at": "2026-05-02T00:00:00+00:00"},
        )
        exceptions = self.client.get(
            f"/api/v1/policy-exceptions?binding_id={binding_id}",
            headers=self._headers(),
        )
        deleted = self.client.delete(
            f"/api/v1/policy-bindings/{binding_id}",
            headers=self._headers(),
        )

        self.assertEqual(listed.status_code, 200)
        self.assertEqual([binding["id"] for binding in listed.json()], [binding_id])
        self.assertEqual(patched.status_code, 200)
        self.assertEqual(patched.json()["mode"], "audit-only")
        self.assertEqual(patched.json()["rollout_percentage"], 50)
        self.assertEqual(exception.status_code, 201)
        self.assertEqual(exception.json()["reason"], "temporary maintenance")
        self.assertEqual(exceptions.status_code, 200)
        self.assertEqual(len(exceptions.json()), 1)
        self.assertEqual(deleted.status_code, 204)


if __name__ == "__main__":
    unittest.main()
