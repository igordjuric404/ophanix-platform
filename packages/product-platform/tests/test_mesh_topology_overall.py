from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


class MeshTopologyOverallTests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection, "demo_source", "Demo Source", "trusted")
            self._insert_agent(connection, "demo_target", "Demo Target", "standard")
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
            "X-Correlation-ID": "corr-mesh-overall",
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
                "Mesh overall test agent",
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

    def test_demo_handoff_appears_in_feed_topology_and_blocked_handoff_context(self) -> None:
        message = self.client.post(
            "/api/v1/mesh/messages",
            headers=self._headers(),
            json={
                "source_agent_id": "demo_source",
                "target_agent_id": "demo_target",
                "protocol": "a2a",
                "action": "handoff.request",
                "decision": "deny",
                "latency_ms": 33,
                "correlation_id": "corr-demo-handoff",
                "payload_summary": {
                    "trust_reason": "low_trust",
                    "policy_reason": "requires_approval",
                },
            },
        )
        self.assertEqual(message.status_code, 201)
        handoff = self.client.post(
            "/api/v1/mesh/handoffs",
            headers=self._headers(),
            json={
                "source_agent_id": "demo_source",
                "target_agent_id": "demo_target",
                "task_type": "claim_review",
                "required_capabilities": ["claims:read"],
                "trust_result": "denied",
                "policy_result": "deny",
                "status": "blocked",
                "reason": "low_trust; requires_approval",
                "correlation_id": "corr-demo-handoff",
                "metadata": {
                    "trust_reason": "low_trust",
                    "policy_reason": "requires_approval",
                },
            },
        )
        self.assertEqual(handoff.status_code, 201)

        feed = self.client.get(
            "/api/v1/mesh/messages?correlation_id=corr-demo-handoff",
            headers=self._headers(),
        )
        topology = self.client.get("/api/v1/mesh/topology", headers=self._headers())
        handoffs = self.client.get(
            "/api/v1/mesh/handoffs?status=blocked",
            headers=self._headers(),
        )

        self.assertEqual(feed.status_code, 200)
        self.assertEqual(feed.json()[0]["id"], message.json()["id"])
        self.assertEqual(topology.status_code, 200)
        self.assertEqual(topology.json()["edges"][0]["source_agent_id"], "demo_source")
        self.assertEqual(topology.json()["edges"][0]["target_agent_id"], "demo_target")
        self.assertEqual(topology.json()["edges"][0]["denied_count"], 1)
        self.assertEqual(handoffs.status_code, 200)
        self.assertEqual(handoffs.json()[0]["id"], handoff.json()["id"])
        self.assertEqual(handoffs.json()[0]["trust_result"], "denied")
        self.assertEqual(handoffs.json()[0]["policy_result"], "deny")
        self.assertIn("low_trust", handoffs.json()[0]["reason"])


if __name__ == "__main__":
    unittest.main()
