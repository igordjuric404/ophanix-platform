from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.agents.lifecycle import AgentLifecycleAdapter, AgentLifecycleTransitionError
from product_platform.api.settings import Settings
from product_platform.audit.store import AuditEventQuery, AuditEventRepository
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


class LifecycleAdapterTests(unittest.TestCase):
    def test_valid_state_transition(self) -> None:
        AgentLifecycleAdapter().validate_transition("active", "suspended")

    def test_invalid_state_transition_fails(self) -> None:
        with self.assertRaises(AgentLifecycleTransitionError):
            AgentLifecycleAdapter().validate_transition("rejected", "active")


class LifecycleWorkflowApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection, "agent_active", "active", "2026-04-01T00:00:00+00:00")
            self._insert_agent(connection, "agent_pending", "pending_approval", None)
        self.app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-04-30T00:00:00Z",
                dev_login_allowed_emails=["admin@example.com", "viewer@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.admin_token = self._login("admin@example.com", ["Platform Admin"])
        self.viewer_token = self._login("viewer@example.com", ["Viewer"])

    def _insert_agent(self, connection, agent_id: str, status: str, heartbeat: str | None) -> None:
        now = "2026-04-30T00:00:00+00:00"
        connection.execute(
            """
            INSERT INTO agents (
                id, organization_id, environment_id, name, description, framework,
                runtime_type, owner_user_id, sponsor_user_id, status,
                last_heartbeat_at, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                agent_id,
                "org_default",
                "env_default",
                agent_id,
                "Lifecycle test agent",
                "langgraph",
                "service",
                "owner_1",
                "sponsor_1",
                status,
                heartbeat,
                now,
                now,
            ),
        )

    def _login(self, email: str, roles: list[str]) -> str:
        response = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": email, "roles": roles},
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["access_token"]

    def _headers(self, token: str | None = None) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token or self.admin_token}",
            "X-Environment-ID": "env_default",
        }

    def test_suspend_active_agent_persists_lifecycle_and_audit(self) -> None:
        response = self.client.post(
            "/api/v1/agents/agent_active/suspend",
            headers=self._headers(),
            json={"reason": "maintenance"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "suspended")
        event = self.database.connect().execute(
            "SELECT * FROM agent_lifecycle_events WHERE agent_id = ? AND next_state = ?",
            ("agent_active", "suspended"),
        ).fetchone()
        self.assertIsNotNone(event)
        audit = AuditEventRepository(self.database.connect()).query(
            AuditEventQuery(
                organization_id="org_default",
                event_type="agent.lifecycle",
                agent_id="agent_active",
            )
        )
        self.assertTrue(any(item.payload_json["lifecycle_state"] == "suspended" for item in audit))

    def test_cannot_activate_rejected_agent(self) -> None:
        rejected = self.client.post(
            "/api/v1/agents/agent_pending/reject",
            headers=self._headers(),
            json={"reason": "not needed"},
        )
        self.assertEqual(rejected.status_code, 200)

        response = self.client.post(
            "/api/v1/agents/agent_pending/activate",
            headers=self._headers(),
        )

        self.assertEqual(response.status_code, 400)

    def test_reason_is_required_for_suspend_and_decommission(self) -> None:
        suspend = self.client.post(
            "/api/v1/agents/agent_active/suspend",
            headers=self._headers(),
            json={},
        )
        decommission = self.client.post(
            "/api/v1/agents/agent_active/decommission",
            headers=self._headers(),
            json={},
        )

        self.assertEqual(suspend.status_code, 422)
        self.assertEqual(decommission.status_code, 422)

    def test_viewer_cannot_mutate_lifecycle(self) -> None:
        response = self.client.post(
            "/api/v1/agents/agent_active/suspend",
            headers=self._headers(self.viewer_token),
            json={"reason": "viewer"},
        )

        self.assertEqual(response.status_code, 403)

    def test_heartbeat_updates_last_heartbeat(self) -> None:
        response = self.client.post(
            "/api/v1/agents/agent_active/heartbeat",
            headers=self._headers(),
            json={"status": "healthy", "metadata_json": {"latency_ms": 22}},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.json()["last_heartbeat_at"])
        heartbeat = self.database.connect().execute(
            "SELECT * FROM agent_heartbeats WHERE agent_id = ?",
            ("agent_active",),
        ).fetchone()
        self.assertEqual(heartbeat["status"], "healthy")

    def test_orphan_detection_marks_stale_active_agent(self) -> None:
        response = self.client.post(
            "/api/v1/agents/orphan-detection/run",
            headers=self._headers(),
            json={"threshold_hours": 1},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("agent_active", response.json()["orphaned_agent_ids"])
        agent = self.database.connect().execute(
            "SELECT status FROM agents WHERE id = ?",
            ("agent_active",),
        ).fetchone()
        self.assertEqual(agent["status"], "orphaned")


if __name__ == "__main__":
    unittest.main()
