from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.audit.store import AuditEventQuery, AuditEventRepository
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.mcp.models import MCPProxyCallRequest
from product_platform.mcp.proxy import MCPProxyDecisionService, MCPProxyRepository, mcp_tool_call_response


class MCPProxyTrafficPhase1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection, "agent_high", "High Trust Agent", 820)
            self._insert_agent(connection, "agent_no_identity", "No Identity Agent", 820, identity=False)
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
            json={"email": "admin@example.com", "roles": ["Security Admin"]},
        )
        self.assertEqual(login.status_code, 200)
        self.token = login.json()["access_token"]

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
            "X-Correlation-ID": "corr-mcp-proxy",
        }

    def _insert_agent(self, connection, agent_id: str, name: str, score: int, *, identity: bool = True) -> None:
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
                "MCP proxy test agent",
                "langgraph",
                "service",
                "user_admin",
                "user_admin",
                "active",
                score,
                "trusted",
                now,
                now,
            ),
        )
        if not identity:
            return
        connection.execute(
            """
            INSERT INTO agent_identities (
                id, agent_id, did, public_key_fingerprint, key_type,
                identity_status, bootstrap_material_json, bootstrap_retrieved_at, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"ident_{agent_id}",
                agent_id,
                f"did:mcp:{agent_id}",
                f"fingerprint_{agent_id}",
                "ed25519",
                "active",
                None,
                now,
                now,
            ),
        )

    def _create_server_and_discover(self) -> tuple[dict, dict]:
        server = self.client.post(
            "/api/v1/mcp/servers",
            headers=self._headers(),
            json={
                "name": "Claims MCP",
                "endpoint_url": "https://mcp.claims.local/rpc",
                "owner_user_id": "user_admin",
                "auth_type": "oauth",
                "status": "active",
                "policy_pack_id": "policy_placeholder_sensitive_tools",
            },
        )
        self.assertEqual(server.status_code, 201)
        discovery = self.client.post(
            f"/api/v1/mcp/servers/{server.json()['id']}/discover-tools",
            headers=self._headers(),
        )
        self.assertEqual(discovery.status_code, 201)
        lookup = self._tool_by_name("claims.lookup_order")
        return server.json(), lookup

    def _tool_by_name(self, name: str) -> dict:
        tools = self.client.get("/api/v1/mcp/tools", headers=self._headers())
        self.assertEqual(tools.status_code, 200)
        for tool in tools.json():
            if tool["name"] == name:
                return tool
        self.fail(f"Expected MCP tool {name}.")

    def test_allowed_call_is_persisted_and_policy_linked(self) -> None:
        server, tool = self._create_server_and_discover()

        response = self.client.post(
            "/api/v1/mcp/proxy/call",
            headers=self._headers(),
            json={
                "source_agent_id": "agent_high",
                "server_id": server["id"],
                "tool_id": tool["id"],
                "params": {"order_id": "ORD-100"},
            },
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["decision"], "allowed")
        self.assertEqual(payload["matched_policy_id"], "policy_placeholder_sensitive_tools")
        self.assertEqual(payload["trust_score"], 820)
        self.assertEqual(payload["response"]["status"], "ready_for_review")

        traffic = self.client.get("/api/v1/mcp/traffic?decision=allowed", headers=self._headers())
        self.assertEqual(traffic.status_code, 200)
        self.assertEqual(traffic.json()[0]["id"], payload["id"])

        events = AuditEventRepository(self.database.connect()).query(
            AuditEventQuery(
                organization_id="org_default",
                environment_id="env_default",
                resource_type="mcp_tool_call",
                resource_id=payload["id"],
            )
        )
        self.assertEqual(events[0].event_type, "mcp.proxy.call.allowed")
        self.assertEqual(events[0].decision, "allowed")

    def test_denied_call_is_persisted(self) -> None:
        server, tool = self._create_server_and_discover()

        response = self.client.post(
            "/api/v1/mcp/proxy/call",
            headers=self._headers(),
            json={
                "source_agent_id": "agent_high",
                "server_id": server["id"],
                "tool_id": tool["id"],
                "params": {"order_id": "ORD-100; rm -rf /"},
            },
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["decision"], "denied")
        self.assertEqual(payload["gateway_stage"], "builtin_pattern")
        self.assertIn("dangerous pattern", payload["reason"])

        traffic = self.client.get("/api/v1/mcp/traffic?decision=denied", headers=self._headers())
        self.assertEqual(traffic.status_code, 200)
        self.assertEqual(traffic.json()[0]["id"], payload["id"])

    def test_missing_agent_identity_fails_closed(self) -> None:
        server, tool = self._create_server_and_discover()

        with self.database.transaction() as connection:
            repository = MCPProxyRepository(connection, "org_default", "env_default")
            row = MCPProxyDecisionService(repository).evaluate_and_record(
                MCPProxyCallRequest(
                    source_agent_id="agent_no_identity",
                    server_id=server["id"],
                    tool_id=tool["id"],
                    params={"order_id": "ORD-100"},
                ),
                request_correlation_id="corr-unit",
            )
            payload = mcp_tool_call_response(row)

        self.assertEqual(payload.decision, "denied")
        self.assertEqual(payload.reason, "missing_identity")
        self.assertEqual(payload.gateway_stage, "identity")
        self.assertEqual(payload.correlation_id, "corr-unit")


if __name__ == "__main__":
    unittest.main()
