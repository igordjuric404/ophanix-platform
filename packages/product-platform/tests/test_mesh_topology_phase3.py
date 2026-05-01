from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.mesh.topology import aggregate_mesh_topology


class MeshTopologyPhase3Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection, "mesh_topo_source", "Mesh Topo Source", "trusted")
            self._insert_agent(connection, "mesh_topo_target", "Mesh Topo Target", "standard")
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
                "Mesh topology test agent",
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

    def test_unit_aggregation_creates_expected_edge(self) -> None:
        topology = aggregate_mesh_topology(
            [
                {
                    "source_agent_id": "agent_a",
                    "target_agent_id": "agent_b",
                    "protocol": "a2a",
                    "decision": "allow",
                    "latency_ms": 40,
                    "source_agent_name": "Agent A",
                    "target_agent_name": "Agent B",
                    "source_agent_status": "active",
                    "target_agent_status": "active",
                    "source_trust_tier": "trusted",
                    "target_trust_tier": "standard",
                }
            ]
        )

        self.assertEqual(len(topology.nodes), 2)
        self.assertEqual(len(topology.edges), 1)
        self.assertEqual(topology.edges[0].source_agent_id, "agent_a")
        self.assertEqual(topology.edges[0].volume, 1)

    def test_unit_deny_rate_calculation(self) -> None:
        topology = aggregate_mesh_topology(
            [
                {
                    "source_agent_id": "agent_a",
                    "target_agent_id": "agent_b",
                    "protocol": "mcp",
                    "decision": "allow",
                    "latency_ms": 20,
                    "source_agent_name": "Agent A",
                    "target_agent_name": "Agent B",
                    "source_agent_status": "active",
                    "target_agent_status": "active",
                    "source_trust_tier": "trusted",
                    "target_trust_tier": "trusted",
                },
                {
                    "source_agent_id": "agent_a",
                    "target_agent_id": "agent_b",
                    "protocol": "mcp",
                    "decision": "deny",
                    "latency_ms": 40,
                    "source_agent_name": "Agent A",
                    "target_agent_name": "Agent B",
                    "source_agent_status": "active",
                    "target_agent_status": "active",
                    "source_trust_tier": "trusted",
                    "target_trust_tier": "trusted",
                },
            ]
        )

        self.assertEqual(topology.edges[0].volume, 2)
        self.assertEqual(topology.edges[0].denied_count, 1)
        self.assertEqual(topology.edges[0].deny_rate, 0.5)
        self.assertEqual(topology.edges[0].average_latency_ms, 30)

    def test_api_topology_includes_trust_tier(self) -> None:
        message = self.client.post(
            "/api/v1/mesh/messages",
            headers=self._headers(),
            json={
                "source_agent_id": "mesh_topo_source",
                "target_agent_id": "mesh_topo_target",
                "protocol": "a2a",
                "action": "handoff.request",
                "decision": "allow",
                "latency_ms": 50,
            },
        )
        self.assertEqual(message.status_code, 201)

        response = self.client.get("/api/v1/mesh/topology", headers=self._headers())

        self.assertEqual(response.status_code, 200)
        nodes = {node["agent_id"]: node for node in response.json()["nodes"]}
        self.assertEqual(nodes["mesh_topo_source"]["trust_tier"], "trusted")
        self.assertEqual(nodes["mesh_topo_target"]["trust_tier"], "standard")
        self.assertEqual(response.json()["edges"][0]["average_latency_ms"], 50)


if __name__ == "__main__":
    unittest.main()
