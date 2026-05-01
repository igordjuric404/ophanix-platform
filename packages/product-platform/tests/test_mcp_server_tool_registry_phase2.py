from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.mcp.discovery import calculate_schema_hash, normalize_tool_definition


class MCPServerToolRegistryPhase2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
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
            "X-Correlation-ID": "corr-mcp-discovery",
        }

    def _create_server(self) -> dict:
        response = self.client.post(
            "/api/v1/mcp/servers",
            headers=self._headers(),
            json={
                "name": "Claims MCP",
                "endpoint_url": "https://mcp.claims.local/rpc",
                "owner_user_id": "user_admin",
                "auth_type": "oauth",
            },
        )
        self.assertEqual(response.status_code, 201)
        return response.json()

    def test_schema_hash_is_stable(self) -> None:
        schema_a = {
            "type": "object",
            "properties": {
                "order_id": {"type": "string"},
                "amount": {"type": "number"},
            },
            "required": ["order_id", "amount"],
        }
        schema_b = {
            "required": ["order_id", "amount"],
            "properties": {
                "amount": {"type": "number"},
                "order_id": {"type": "string"},
            },
            "type": "object",
        }

        self.assertEqual(calculate_schema_hash(schema_a), calculate_schema_hash(schema_b))
        self.assertTrue(calculate_schema_hash(schema_a).startswith("sha256:"))

    def test_tool_definition_normalization(self) -> None:
        normalized = normalize_tool_definition(
            {
                "name": "claims.lookup_order",
                "title": "Lookup Order",
                "inputSchema": {
                    "properties": {"order_id": {"type": "string"}},
                    "type": "object",
                },
                "annotations": {"readOnlyHint": True},
            }
        )

        self.assertEqual(normalized.name, "claims.lookup_order")
        self.assertEqual(normalized.description, "Lookup Order")
        self.assertEqual(normalized.schema["type"], "object")
        self.assertEqual(normalized.definition["description"], "Lookup Order")
        self.assertEqual(normalized.definition["annotations"]["readOnlyHint"], True)
        self.assertEqual(normalized.schema_hash, calculate_schema_hash(normalized.schema))

    def test_api_discover_tools_creates_tool_versions(self) -> None:
        server = self._create_server()

        discovered = self.client.post(
            f"/api/v1/mcp/servers/{server['id']}/discover-tools",
            headers=self._headers(),
        )

        self.assertEqual(discovered.status_code, 201)
        payload = discovered.json()
        self.assertEqual(payload["server_id"], server["id"])
        self.assertEqual(payload["discovered_count"], 3)
        names = {tool["name"] for tool in payload["tools"]}
        self.assertEqual(
            names,
            {"claims.lookup_order", "claims.issue_refund", "notifications.send_email"},
        )
        refund = next(tool for tool in payload["tools"] if tool["name"] == "claims.issue_refund")
        self.assertTrue(refund["id"].startswith("mcptool_"))
        self.assertTrue(refund["current_version_id"].startswith("mcptv_"))
        self.assertEqual(refund["current_version"]["scan_status"], "not_scanned")
        self.assertTrue(refund["current_version"]["schema_hash"].startswith("sha256:"))
        self.assertEqual(len(refund["versions"]), 1)

        tools = self.client.get("/api/v1/mcp/tools", headers=self._headers())
        self.assertEqual(tools.status_code, 200)
        self.assertEqual(len(tools.json()), 3)

        tool_detail = self.client.get(
            f"/api/v1/mcp/tools/{refund['id']}",
            headers=self._headers(),
        )
        self.assertEqual(tool_detail.status_code, 200)
        self.assertEqual(tool_detail.json()["current_version"]["schema_hash"], refund["current_version"]["schema_hash"])
        self.assertEqual(len(tool_detail.json()["versions"]), 1)

        servers = self.client.get("/api/v1/mcp/servers", headers=self._headers())
        self.assertEqual(servers.status_code, 200)
        self.assertEqual(servers.json()[0]["tool_count"], 3)
        self.assertIsNotNone(servers.json()[0]["last_discovered_at"])


if __name__ == "__main__":
    unittest.main()

