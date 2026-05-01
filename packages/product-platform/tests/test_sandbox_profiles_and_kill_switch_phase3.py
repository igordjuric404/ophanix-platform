from __future__ import annotations

import json
import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


class KillSwitchPhase3Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection, "agent_kill", "Kill Switch Agent")
            self._insert_runtime_session(connection, "rtssn_kill", "agent_kill")
        self.app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-05-01T00:00:00Z",
                dev_login_allowed_emails=["security@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "security@example.com", "roles": ["Security Admin"]},
        )
        self.assertEqual(login.status_code, 200)
        self.token = login.json()["access_token"]

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
            "X-Correlation-ID": "corr-kill",
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
                "Kill switch test agent",
                "langgraph",
                "service",
                "user_admin",
                "user_admin",
                "active",
                720,
                "trusted",
                now,
                now,
            ),
        )

    def _insert_runtime_session(self, connection, session_id: str, agent_id: str) -> None:
        connection.execute(
            """
            INSERT INTO runtime_sessions (
                id, organization_id, environment_id, agent_id, state, ring,
                sponsor_user_id, started_at, ended_at, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                "org_default",
                "env_default",
                agent_id,
                "active",
                2,
                "user_admin",
                "2026-05-01T00:00:00+00:00",
                None,
                json.dumps({"purpose": "kill-switch-test"}),
            ),
        )

    def test_kill_switch_requires_reason(self) -> None:
        rejected = self.client.post(
            "/api/v1/runtime/kill-switch",
            headers=self._headers(),
            json={
                "target_type": "session",
                "target_id": "rtssn_kill",
                "scope": "target",
                "confirmation": "KILL session:rtssn_kill",
            },
        )

        self.assertEqual(rejected.status_code, 422)

    def test_unsupported_target_rejected(self) -> None:
        rejected = self.client.post(
            "/api/v1/runtime/kill-switch",
            headers=self._headers(),
            json={
                "target_type": "database",
                "target_id": "primary",
                "scope": "target",
                "reason": "Unsupported target test",
                "confirmation": "KILL database:primary",
            },
        )

        self.assertEqual(rejected.status_code, 400)
        self.assertIn("Unsupported kill-switch target_type", rejected.json()["message"])

    def test_kill_event_persisted_and_audited(self) -> None:
        triggered = self.client.post(
            "/api/v1/runtime/kill-switch",
            headers=self._headers(),
            json={
                "target_type": "session",
                "target_id": "rtssn_kill",
                "scope": "target",
                "reason": "Emergency stop test",
                "confirmation": "KILL session:rtssn_kill",
            },
        )

        self.assertEqual(triggered.status_code, 201, triggered.text)
        event = triggered.json()
        self.assertEqual(event["status"], "triggered")
        self.assertEqual(event["target_type"], "session")

        listed = self.client.get("/api/v1/runtime/kill-switch/events", headers=self._headers())
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()[0]["id"], event["id"])

        with self.database.connect() as connection:
            kill_rows = connection.execute("SELECT * FROM kill_switch_events").fetchall()
            session = connection.execute(
                "SELECT * FROM runtime_sessions WHERE id = 'rtssn_kill'"
            ).fetchone()
            audit_rows = connection.execute(
                """
                SELECT *
                FROM audit_events
                WHERE event_type = 'runtime.kill_switch'
                """
            ).fetchall()
        self.assertEqual(len(kill_rows), 1)
        self.assertEqual(session["state"], "archived")
        self.assertEqual(json.loads(session["metadata_json"])["kill_switch_reason"], "Emergency stop test")
        self.assertEqual(len(audit_rows), 1)
        self.assertEqual(audit_rows[0]["severity"], "critical")
        audit_payload = json.loads(audit_rows[0]["payload_json"])
        self.assertEqual(audit_payload["action"], "kill_switch")
        self.assertEqual(audit_payload["status"], "kill_switch_triggered")


if __name__ == "__main__":
    unittest.main()
