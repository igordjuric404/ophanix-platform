from __future__ import annotations

import json
import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.audit.store import AuditEventQuery, AuditEventRepository
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.mcp.proxy import MCPResponseSanitizer


class MCPProxyTrafficPhase3Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection, "agent_high", "High Trust Agent", 820)
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
            "X-Correlation-ID": "corr-mcp-sanitizer",
        }

    def _insert_agent(self, connection, agent_id: str, name: str, score: int) -> None:
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
                "MCP proxy sanitizer test agent",
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
            },
        )
        self.assertEqual(server.status_code, 201)
        discovery = self.client.post(
            f"/api/v1/mcp/servers/{server.json()['id']}/discover-tools",
            headers=self._headers(),
        )
        self.assertEqual(discovery.status_code, 201)
        return server.json(), self._tool_by_name("claims.lookup_order")

    def _tool_by_name(self, name: str) -> dict:
        tools = self.client.get("/api/v1/mcp/tools", headers=self._headers())
        self.assertEqual(tools.status_code, 200)
        for tool in tools.json():
            if tool["name"] == name:
                return tool
        self.fail(f"Expected MCP tool {name}.")

    def test_response_scanner_flags_credential_fixture(self) -> None:
        result = MCPResponseSanitizer().scan_and_sanitize(
            {
                "status": "ready",
                "debug_token": "sk-demo1234567890abcdefghijklmnop",
            },
            tool_name="claims.lookup_order",
        )

        self.assertEqual(result.action, "redacted")
        self.assertIn("credential_leak", {threat["category"] for threat in result.threats})
        self.assertEqual(result.response["debug_token"], "[REDACTED]")

    def test_sanitized_response_hides_sensitive_value(self) -> None:
        server, tool = self._create_server_and_discover()

        response = self.client.post(
            "/api/v1/mcp/proxy/call",
            headers=self._headers(),
            json={
                "source_agent_id": "agent_high",
                "server_id": server["id"],
                "tool_id": tool["id"],
                "params": {"order_id": "ORD-300", "include_secret": True},
            },
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["decision"], "allowed")
        self.assertEqual(payload["sanitizer_action"], "redacted")
        self.assertEqual(payload["response"]["debug_token"], "[REDACTED]")
        self.assertNotIn("sk-demo", json.dumps(payload["response"]))

    def test_sanitizer_action_is_persisted_and_audited(self) -> None:
        server, tool = self._create_server_and_discover()
        response = self.client.post(
            "/api/v1/mcp/proxy/call",
            headers=self._headers(),
            json={
                "source_agent_id": "agent_high",
                "server_id": server["id"],
                "tool_id": tool["id"],
                "params": {"order_id": "ORD-300", "include_secret": True},
            },
        )
        self.assertEqual(response.status_code, 201)
        call_id = response.json()["id"]

        traffic = self.client.get("/api/v1/mcp/traffic", headers=self._headers())
        self.assertEqual(traffic.status_code, 200)
        self.assertEqual(traffic.json()[0]["id"], call_id)
        self.assertEqual(traffic.json()[0]["sanitizer_action"], "redacted")

        events = AuditEventRepository(self.database.connect()).query(
            AuditEventQuery(
                organization_id="org_default",
                environment_id="env_default",
                resource_type="mcp_tool_call",
                resource_id=call_id,
            )
        )
        self.assertIn("mcp.proxy.response.sanitized", {event.event_type for event in events})


if __name__ == "__main__":
    unittest.main()
