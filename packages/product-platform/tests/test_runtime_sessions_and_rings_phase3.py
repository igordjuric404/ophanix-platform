from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.audit.store import AuditEventQuery, AuditEventRepository
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


class RuntimeSessionsPhase3Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection, "agent_high", "High Trust Runtime Agent", "active", 820)
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

    def _headers(self, correlation_id: str = "corr-runtime-rules") -> dict[str, str]:
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
                "Runtime ring rule test agent",
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
            json={"agent_id": "agent_high", "ring": 2},
        )
        self.assertEqual(created.status_code, 201)
        return created.json()

    def test_create_ring_rule_and_emit_audit_event(self) -> None:
        created = self.client.post(
            "/api/v1/runtime/ring-rules",
            headers=self._headers(),
            json={
                "action_pattern": "reports.read_*",
                "required_ring": 1,
                "min_trust_score": 700,
                "enabled": True,
            },
        )

        self.assertEqual(created.status_code, 201)
        payload = created.json()
        self.assertEqual(payload["action_pattern"], "reports.read_*")
        self.assertEqual(payload["required_ring"], 1)

        listed = self.client.get("/api/v1/runtime/ring-rules?enabled=true", headers=self._headers())
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()[0]["id"], payload["id"])

        events = AuditEventRepository(self.database.connect()).query(
            AuditEventQuery(
                organization_id="org_default",
                environment_id="env_default",
                resource_type="runtime_ring_rule",
                resource_id=payload["id"],
            )
        )
        self.assertEqual(events[0].event_type, "runtime.ring_rule.created")

    def test_custom_rule_overrides_default_classification(self) -> None:
        created_rule = self.client.post(
            "/api/v1/runtime/ring-rules",
            headers=self._headers(),
            json={
                "action_pattern": "reports.read_*",
                "required_ring": 1,
                "min_trust_score": 0,
                "enabled": True,
            },
        )
        self.assertEqual(created_rule.status_code, 201)
        session = self._create_session()

        action = self.client.post(
            f"/api/v1/runtime/sessions/{session['id']}/actions",
            headers=self._headers("corr-runtime-rule-override"),
            json={
                "action_name": "reports.read_balance",
                "resource_type": "report",
                "reversibility": "none",
                "is_read_only": True,
            },
        )

        self.assertEqual(action.status_code, 201)
        payload = action.json()
        self.assertEqual(payload["required_ring"], 1)
        self.assertEqual(payload["decision"], "denied")
        self.assertIn("required ring 1", payload["reason"])

    def test_invalid_ring_rule_values_are_rejected(self) -> None:
        invalid = self.client.post(
            "/api/v1/runtime/ring-rules",
            headers=self._headers(),
            json={
                "action_pattern": "admin.*",
                "required_ring": 4,
                "min_trust_score": 0,
                "enabled": True,
            },
        )

        self.assertEqual(invalid.status_code, 422)


if __name__ == "__main__":
    unittest.main()
