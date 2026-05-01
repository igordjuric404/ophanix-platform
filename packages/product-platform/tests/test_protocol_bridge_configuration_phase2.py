from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.audit.store import AuditEventQuery, AuditEventRepository
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


class ProtocolBridgeConfigurationPhase2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection, "route_source", "Route Source")
            self._insert_agent(connection, "route_target", "Route Target")
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

    def _headers(self, *, correlation_id: str = "corr-bridge-route") -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
            "X-Correlation-ID": correlation_id,
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
                "Protocol bridge route test agent",
                "langgraph",
                "service",
                "owner",
                "sponsor",
                "active",
                770,
                "trusted",
                now,
                now,
            ),
        )

    def _create_bridge(self) -> dict:
        response = self.client.post(
            "/api/v1/mesh/protocol-bridges",
            headers=self._headers(),
            json={
                "name": "Route Test Bridge",
                "bridge_type": "mcp",
                "config": {"endpoint": "https://mcp.local/rpc"},
            },
        )
        self.assertEqual(response.status_code, 201)
        return response.json()

    def test_api_creates_a2a_to_mcp_route(self) -> None:
        bridge = self._create_bridge()

        response = self.client.post(
            f"/api/v1/mesh/protocol-bridges/{bridge['id']}/routes",
            headers=self._headers(),
            json={
                "source_protocol": "a2a",
                "target_protocol": "mcp",
                "source_agent_id": "route_source",
                "target_agent_id": "route_target",
            },
        )

        self.assertEqual(response.status_code, 201)
        route = response.json()
        self.assertEqual(route["bridge_id"], bridge["id"])
        self.assertEqual(route["source_protocol"], "a2a")
        self.assertEqual(route["target_protocol"], "mcp")
        self.assertEqual(route["source_agent_name"], "Route Source")
        self.assertEqual(route["target_agent_name"], "Route Target")
        self.assertIsNone(route["policy_binding_id"])
        self.assertTrue(route["enabled"])

        detail = self.client.get(
            f"/api/v1/mesh/protocol-bridges/{bridge['id']}",
            headers=self._headers(),
        )
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["routes"][0]["id"], route["id"])

    def test_route_with_unknown_agent_is_rejected(self) -> None:
        bridge = self._create_bridge()

        response = self.client.post(
            f"/api/v1/mesh/protocol-bridges/{bridge['id']}/routes",
            headers=self._headers(),
            json={
                "source_protocol": "a2a",
                "target_protocol": "mcp",
                "source_agent_id": "missing_agent",
                "target_agent_id": "route_target",
            },
        )

        self.assertEqual(response.status_code, 404)

    def test_invalid_route_protocol_is_rejected(self) -> None:
        bridge = self._create_bridge()

        response = self.client.post(
            f"/api/v1/mesh/protocol-bridges/{bridge['id']}/routes",
            headers=self._headers(),
            json={
                "source_protocol": "ftp",
                "target_protocol": "mcp",
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_route_change_emits_audit_event(self) -> None:
        bridge = self._create_bridge()
        response = self.client.post(
            f"/api/v1/mesh/protocol-bridges/{bridge['id']}/routes",
            headers=self._headers(correlation_id="corr-route-audit"),
            json={
                "source_protocol": "a2a",
                "target_protocol": "mcp",
                "source_agent_id": "route_source",
                "target_agent_id": "route_target",
            },
        )
        self.assertEqual(response.status_code, 201)

        events = AuditEventRepository(self.database.connect()).query(
            AuditEventQuery(
                organization_id="org_default",
                environment_id="env_default",
                resource_type="protocol_bridge_route",
            )
        )

        self.assertEqual(events[0].event_type, "protocol_bridge.route.changed")
        self.assertEqual(events[0].resource_id, response.json()["id"])
        self.assertEqual(events[0].correlation_id, "corr-route-audit")
        self.assertEqual(events[0].payload_json["source_protocol"], "a2a")


if __name__ == "__main__":
    unittest.main()
