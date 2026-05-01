from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.audit.store import AuditEventQuery, AuditEventRepository
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


class MeshTopologyPhase1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection, "mesh_source", "Mesh Source", "trusted")
            self._insert_agent(connection, "mesh_target", "Mesh Target", "trusted")
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
            "X-Correlation-ID": "corr-mesh",
        }

    def _insert_agent(self, connection, agent_id: str, name: str, trust_tier: str) -> None:
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
                "Mesh test agent",
                "langgraph",
                "service",
                "owner",
                "sponsor",
                "active",
                735,
                trust_tier,
                now,
                now,
            ),
        )

    def test_api_ingests_message(self) -> None:
        response = self.client.post(
            "/api/v1/mesh/messages",
            headers=self._headers(),
            json={
                "source_agent_id": "mesh_source",
                "target_agent_id": "mesh_target",
                "protocol": "a2a",
                "action": "handoff.request",
                "decision": "allow",
                "latency_ms": 42,
                "correlation_id": "corr-message",
                "payload_summary": {"task_type": "claims"},
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["source_agent_id"], "mesh_source")
        self.assertEqual(response.json()["target_agent_name"], "Mesh Target")
        self.assertEqual(response.json()["payload_summary"]["task_type"], "claims")

    def test_api_unknown_source_agent_is_rejected(self) -> None:
        response = self.client.post(
            "/api/v1/mesh/messages",
            headers=self._headers(),
            json={
                "source_agent_id": "missing_agent",
                "target_agent_id": "mesh_target",
                "protocol": "a2a",
                "action": "handoff.request",
                "decision": "allow",
            },
        )

        self.assertEqual(response.status_code, 404)

    def test_api_blocked_message_emits_audit_event(self) -> None:
        response = self.client.post(
            "/api/v1/mesh/messages",
            headers=self._headers(),
            json={
                "source_agent_id": "mesh_source",
                "target_agent_id": "mesh_target",
                "protocol": "mcp",
                "action": "tool.call",
                "decision": "deny",
                "latency_ms": 7,
                "payload_summary": {"reason": "policy"},
            },
        )
        self.assertEqual(response.status_code, 201)

        events = AuditEventRepository(self.database.connect()).query(
            AuditEventQuery(
                organization_id="org_default",
                environment_id="env_default",
                resource_type="mesh_message",
            )
        )

        self.assertEqual(events[0].event_type, "mesh.message.blocked")
        self.assertEqual(events[0].resource_id, response.json()["id"])
        self.assertEqual(events[0].decision, "deny")
        self.assertEqual(events[0].correlation_id, "corr-mesh")

    def test_api_ingests_handoff(self) -> None:
        response = self.client.post(
            "/api/v1/mesh/handoffs",
            headers=self._headers(),
            json={
                "source_agent_id": "mesh_source",
                "target_agent_id": "mesh_target",
                "task_type": "claim_review",
                "required_capabilities": ["claims:read"],
                "trust_result": "allowed",
                "policy_result": "allow",
                "status": "accepted",
                "reason": "trust_threshold_satisfied",
                "correlation_id": "corr-handoff",
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["task_type"], "claim_review")
        self.assertEqual(response.json()["required_capabilities"], ["claims:read"])


if __name__ == "__main__":
    unittest.main()
