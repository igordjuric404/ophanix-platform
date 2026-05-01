from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.audit.store import AuditEventQuery, AuditEventRepository
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


class RuntimeSessionsOverallTests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection, "agent_high", "High Trust Runtime Agent", "active", 960)
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

    def _headers(self, correlation_id: str = "corr-runtime-overall") -> dict[str, str]:
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
                "Runtime overall validation agent",
                "langgraph",
                "service",
                "user_admin",
                "user_admin",
                status,
                score,
                "verified_partner",
                now,
                now,
            ),
        )

    def test_runtime_session_safe_privileged_actions_and_audit(self) -> None:
        created = self.client.post(
            "/api/v1/runtime/sessions",
            headers=self._headers("corr-runtime-start"),
            json={"agent_id": "agent_high", "ring": 2, "metadata": {"scenario": "overall"}},
        )
        self.assertEqual(created.status_code, 201)
        session = created.json()
        self.assertEqual(session["state"], "active")

        safe = self.client.post(
            f"/api/v1/runtime/sessions/{session['id']}/actions",
            headers=self._headers("corr-runtime-safe"),
            json={
                "action_name": "reports.read_balance",
                "resource_type": "report",
                "reversibility": "none",
                "is_read_only": True,
            },
        )
        self.assertEqual(safe.status_code, 201)
        safe_payload = safe.json()
        self.assertEqual(safe_payload["decision"], "allowed")
        self.assertEqual(safe_payload["required_ring"], 3)

        privileged = self.client.post(
            f"/api/v1/runtime/sessions/{session['id']}/actions",
            headers=self._headers("corr-runtime-ring0"),
            json={
                "action_name": "runtime.configure_kernel",
                "resource_type": "runtime-action",
                "reversibility": "none",
                "is_admin": True,
                "has_consensus": True,
            },
        )
        self.assertEqual(privileged.status_code, 201)
        privileged_payload = privileged.json()
        self.assertEqual(privileged_payload["decision"], "denied")
        self.assertEqual(privileged_payload["required_ring"], 0)
        self.assertIn("Public Preview", privileged_payload["reason"])

        decisions = self.client.get(
            f"/api/v1/runtime/ring-decisions?session_id={session['id']}",
            headers=self._headers(),
        )
        self.assertEqual(decisions.status_code, 200)
        decisions_by_action = {item["runtime_action_id"]: item for item in decisions.json()}
        self.assertEqual(decisions_by_action[safe_payload["id"]]["result"], "allowed")
        self.assertEqual(decisions_by_action[privileged_payload["id"]]["result"], "denied")

        detail = self.client.get(f"/api/v1/runtime/sessions/{session['id']}", headers=self._headers())
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(len(detail.json()["actions"]), 2)

        audit = AuditEventRepository(self.database.connect())
        session_events = audit.query(
            AuditEventQuery(
                organization_id="org_default",
                environment_id="env_default",
                resource_type="runtime_session",
                resource_id=session["id"],
            )
        )
        safe_events = audit.query(
            AuditEventQuery(
                organization_id="org_default",
                environment_id="env_default",
                resource_type="runtime_action",
                resource_id=safe_payload["id"],
            )
        )
        privileged_events = audit.query(
            AuditEventQuery(
                organization_id="org_default",
                environment_id="env_default",
                resource_type="runtime_action",
                resource_id=privileged_payload["id"],
            )
        )
        self.assertIn("runtime.session.started", {event.event_type for event in session_events})
        self.assertEqual(safe_events[0].decision, "allowed")
        self.assertEqual(privileged_events[0].decision, "denied")


if __name__ == "__main__":
    unittest.main()
