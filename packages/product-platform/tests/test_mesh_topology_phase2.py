from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


class MeshTopologyPhase2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection, "mesh_source_a", "Mesh Source A", "trusted")
            self._insert_agent(connection, "mesh_source_b", "Mesh Source B", "standard")
            self._insert_agent(connection, "mesh_target_a", "Mesh Target A", "trusted")
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
        self._seed_messages()

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
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
                "Mesh feed test agent",
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

    def _post_message(self, **overrides) -> dict:
        payload = {
            "source_agent_id": "mesh_source_a",
            "target_agent_id": "mesh_target_a",
            "protocol": "a2a",
            "action": "handoff.request",
            "decision": "allow",
            "latency_ms": 10,
            "correlation_id": "corr-a2a",
            "payload_summary": {"task_type": "claims"},
        }
        payload.update(overrides)
        response = self.client.post("/api/v1/mesh/messages", headers=self._headers(), json=payload)
        self.assertEqual(response.status_code, 201)
        return response.json()

    def _seed_messages(self) -> None:
        self._post_message(protocol="a2a", correlation_id="corr-a2a")
        self._post_message(
            source_agent_id="mesh_source_b",
            protocol="mcp",
            action="tool.call",
            decision="deny",
            correlation_id="corr-mcp",
        )

    def test_api_filters_by_protocol(self) -> None:
        response = self.client.get(
            "/api/v1/mesh/messages?protocol=mcp",
            headers=self._headers(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]["protocol"], "mcp")
        self.assertEqual(response.json()[0]["source_agent_name"], "Mesh Source B")

    def test_api_filters_by_source_agent(self) -> None:
        response = self.client.get(
            "/api/v1/mesh/messages?source_agent_id=mesh_source_a",
            headers=self._headers(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]["source_agent_id"], "mesh_source_a")
        self.assertEqual(response.json()[0]["target_trust_tier"], "trusted")

    def test_api_correlation_id_lookup_returns_matching_message(self) -> None:
        response = self.client.get(
            "/api/v1/mesh/messages?correlation_id=corr-mcp",
            headers=self._headers(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]["decision"], "deny")


if __name__ == "__main__":
    unittest.main()
