from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.audit.store import AuditEventQuery, AuditEventRepository
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


class RuntimeSessionsPhase1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection, "agent_active", "Active Runtime Agent", "active", 820)
            self._insert_agent(connection, "agent_suspended", "Suspended Runtime Agent", "suspended", 700)
        self.app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-05-01T00:00:00Z",
                dev_login_allowed_emails=["platform@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "platform@example.com", "roles": ["Platform Admin"]},
        )
        self.assertEqual(login.status_code, 200)
        self.token = login.json()["access_token"]

    def _headers(self, correlation_id: str = "corr-runtime-session") -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
            "X-Correlation-ID": correlation_id,
        }

    def _insert_agent(self, connection, agent_id: str, name: str, status: str, score: int) -> None:
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
                "Runtime session test agent",
                "langgraph",
                "service",
                "user_admin",
                "user_admin",
                status,
                score,
                "trusted",
                now,
                now,
            ),
        )

    def _create_session(self) -> dict:
        created = self.client.post(
            "/api/v1/runtime/sessions",
            headers=self._headers(),
            json={
                "agent_id": "agent_active",
                "ring": 2,
                "metadata": {"purpose": "phase1"},
            },
        )
        self.assertEqual(created.status_code, 201)
        return created.json()

    def test_create_session_for_active_agent_and_read_it_back(self) -> None:
        payload = self._create_session()

        self.assertEqual(payload["agent_id"], "agent_active")
        self.assertEqual(payload["agent_name"], "Active Runtime Agent")
        self.assertEqual(payload["state"], "active")
        self.assertEqual(payload["ring"], 2)
        self.assertEqual(payload["metadata"]["purpose"], "phase1")

        listed = self.client.get("/api/v1/runtime/sessions?state=active", headers=self._headers())
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()[0]["id"], payload["id"])

        detail = self.client.get(f"/api/v1/runtime/sessions/{payload['id']}", headers=self._headers())
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["actions"], [])

    def test_create_session_rejects_suspended_agent(self) -> None:
        rejected = self.client.post(
            "/api/v1/runtime/sessions",
            headers=self._headers(),
            json={"agent_id": "agent_suspended", "ring": 2},
        )

        self.assertEqual(rejected.status_code, 400)
        self.assertIn("active agent", rejected.json()["message"])

    def test_session_start_emits_audit_event(self) -> None:
        payload = self._create_session()

        events = AuditEventRepository(self.database.connect()).query(
            AuditEventQuery(
                organization_id="org_default",
                environment_id="env_default",
                resource_type="runtime_session",
                resource_id=payload["id"],
            )
        )

        self.assertEqual(events[0].event_type, "runtime.session.started")
        self.assertEqual(events[0].agent_id, "agent_active")
        self.assertEqual(events[0].correlation_id, "corr-runtime-session")

    def test_session_end_archives_and_emits_audit_event(self) -> None:
        payload = self._create_session()

        ended = self.client.post(
            f"/api/v1/runtime/sessions/{payload['id']}/end",
            headers=self._headers("corr-runtime-end"),
            json={"reason": "demo complete"},
        )

        self.assertEqual(ended.status_code, 200)
        ended_payload = ended.json()
        self.assertEqual(ended_payload["state"], "archived")
        self.assertEqual(ended_payload["metadata"]["ended_reason"], "demo complete")
        self.assertIsNotNone(ended_payload["ended_at"])

        events = AuditEventRepository(self.database.connect()).query(
            AuditEventQuery(
                organization_id="org_default",
                environment_id="env_default",
                resource_type="runtime_session",
                resource_id=payload["id"],
            )
        )
        self.assertIn("runtime.session.ended", {event.event_type for event in events})


if __name__ == "__main__":
    unittest.main()
