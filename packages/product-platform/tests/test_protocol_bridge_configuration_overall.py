from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.audit.store import AuditEventQuery, AuditEventRepository
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


class ProtocolBridgeConfigurationOverallTests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection, "support_agent", "Support Agent")
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
            "X-Correlation-ID": "corr-protocol-bridge-overall",
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
                "Overall protocol bridge validation agent",
                "langgraph",
                "service",
                "owner",
                "sponsor",
                "active",
                780,
                "trusted",
                now,
                now,
            ),
        )

    def test_demo_mcp_bridge_route_health_and_audit_are_visible(self) -> None:
        bridge_response = self.client.post(
            "/api/v1/mesh/protocol-bridges",
            headers=self._headers(),
            json={
                "name": "Demo MCP Server Bridge",
                "bridge_type": "mcp",
                "config": {
                    "endpoint": "https://mcp.demo.local/rpc",
                    "secret_id": "secret_demo_mcp",
                },
            },
        )
        self.assertEqual(bridge_response.status_code, 201)
        bridge = bridge_response.json()

        route_response = self.client.post(
            f"/api/v1/mesh/protocol-bridges/{bridge['id']}/routes",
            headers=self._headers(),
            json={
                "source_protocol": "a2a",
                "target_protocol": "mcp",
                "source_agent_id": "support_agent",
            },
        )
        self.assertEqual(route_response.status_code, 201)
        route = route_response.json()

        health_response = self.client.post(
            f"/api/v1/mesh/protocol-bridges/{bridge['id']}/health-check",
            headers=self._headers(),
        )
        self.assertEqual(health_response.status_code, 201)
        health = health_response.json()
        self.assertEqual(health["status"], "limited")

        detail_response = self.client.get(
            f"/api/v1/mesh/protocol-bridges/{bridge['id']}",
            headers=self._headers(),
        )
        self.assertEqual(detail_response.status_code, 200)
        detail = detail_response.json()
        self.assertEqual(detail["current_health"]["id"], health["id"])
        self.assertEqual(detail["routes"][0]["id"], route["id"])
        self.assertEqual(detail["routes"][0]["source_agent_name"], "Support Agent")

        list_response = self.client.get("/api/v1/mesh/protocol-bridges", headers=self._headers())
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json()[0]["current_health"]["status"], "limited")

        events = AuditEventRepository(self.database.connect()).query(
            AuditEventQuery(
                organization_id="org_default",
                environment_id="env_default",
                resource_type="protocol_bridge_route",
            )
        )
        self.assertEqual(events[0].event_type, "protocol_bridge.route.changed")
        self.assertEqual(events[0].resource_id, route["id"])
        self.assertEqual(events[0].correlation_id, "corr-protocol-bridge-overall")


if __name__ == "__main__":
    unittest.main()
