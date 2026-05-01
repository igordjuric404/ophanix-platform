from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


class SagaBuilderPhase1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection, "agent_claims", "Claims Agent")
            self._insert_capability(connection, "agent_claims", "claims.lookup")
            self._insert_capability(connection, "agent_claims", "claims.refund")
        self.app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-05-01T00:00:00Z",
                dev_login_allowed_emails=["operator@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "operator@example.com", "roles": ["Operator"]},
        )
        self.assertEqual(login.status_code, 200)
        self.token = login.json()["access_token"]

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
        }

    def _insert_agent(self, connection, agent_id: str, name: str) -> None:
        now = "2026-05-01T00:00:00+00:00"
        connection.execute(
            """
            INSERT INTO agents (
                id, organization_id, environment_id, name, description, framework,
                runtime_type, owner_user_id, sponsor_user_id, status, trust_score,
                trust_tier, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                agent_id,
                "org_default",
                "env_default",
                name,
                "Saga test agent",
                "langgraph",
                "service",
                "user_admin",
                "user_admin",
                "active",
                850,
                "trusted",
                now,
                now,
            ),
        )

    def _insert_capability(self, connection, agent_id: str, capability: str) -> None:
        now = "2026-05-01T00:00:00+00:00"
        connection.execute(
            """
            INSERT INTO agent_capabilities (
                id, agent_id, capability_name, resource_type, status,
                requested_by, approved_by, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"cap_{agent_id}_{capability.replace('.', '_')}",
                agent_id,
                capability,
                "runtime-action",
                "approved",
                "user_admin",
                "user_admin",
                now,
            ),
        )

    def _create_saga(self) -> dict:
        created = self.client.post(
            "/api/v1/runtime/sagas",
            headers=self._headers(),
            json={"name": "Refund Saga", "correlation_id": "corr-saga"},
        )
        self.assertEqual(created.status_code, 201)
        return created.json()

    def test_create_saga_starts_as_draft(self) -> None:
        saga = self._create_saga()

        self.assertEqual(saga["name"], "Refund Saga")
        self.assertEqual(saga["status"], "draft")
        self.assertEqual(saga["correlation_id"], "corr-saga")

        listed = self.client.get("/api/v1/runtime/sagas?status=draft", headers=self._headers())
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()[0]["id"], saga["id"])

    def test_add_ordered_steps(self) -> None:
        saga = self._create_saga()

        first = self.client.post(
            f"/api/v1/runtime/sagas/{saga['id']}/steps",
            headers=self._headers(),
            json={
                "step_order": 1,
                "name": "Lookup order",
                "action_name": "claims.lookup_order",
                "target_agent_id": "agent_claims",
                "required_capability": "claims.lookup",
                "timeout_seconds": 60,
                "retry_count": 1,
            },
        )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(first.json()["step_order"], 1)

        second = self.client.post(
            f"/api/v1/runtime/sagas/{saga['id']}/steps",
            headers=self._headers(),
            json={
                "step_order": 2,
                "name": "Issue refund",
                "action_name": "claims.issue_refund",
                "target_agent_id": "agent_claims",
                "required_capability": "claims.refund",
                "compensation_action": "claims.reverse_refund",
            },
        )
        self.assertEqual(second.status_code, 201)

        detail = self.client.get(f"/api/v1/runtime/sagas/{saga['id']}", headers=self._headers())
        self.assertEqual(detail.status_code, 200)
        self.assertEqual([step["step_order"] for step in detail.json()["steps"]], [1, 2])
        self.assertIn("saga.step.added", {event["event_type"] for event in detail.json()["events"]})

    def test_invalid_capability_is_rejected(self) -> None:
        saga = self._create_saga()

        rejected = self.client.post(
            f"/api/v1/runtime/sagas/{saga['id']}/steps",
            headers=self._headers(),
            json={
                "step_order": 1,
                "name": "Unknown action",
                "action_name": "claims.unknown",
                "target_agent_id": "agent_claims",
                "required_capability": "claims.unknown",
            },
        )

        self.assertEqual(rejected.status_code, 400)
        self.assertIn("approved capability", rejected.json()["message"])


if __name__ == "__main__":
    unittest.main()
