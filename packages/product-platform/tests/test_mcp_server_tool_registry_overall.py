from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.audit.store import AuditEventQuery, AuditEventRepository
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


class MCPServerToolRegistryOverallTests(unittest.TestCase):
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
            "X-Correlation-ID": "corr-mcp-overall",
        }

    def test_register_discover_change_rediscover_and_audit(self) -> None:
        created = self.client.post(
            "/api/v1/mcp/servers",
            headers=self._headers(),
            json={
                "name": "Claims MCP",
                "endpoint_url": "https://mcp.claims.local/rpc",
                "owner_user_id": "user_admin",
                "auth_type": "oauth",
                "policy_pack_id": "policy_placeholder_sensitive_tools",
            },
        )
        self.assertEqual(created.status_code, 201)
        server_id = created.json()["id"]

        first_discovery = self.client.post(
            f"/api/v1/mcp/servers/{server_id}/discover-tools",
            headers=self._headers(),
        )
        self.assertEqual(first_discovery.status_code, 201)
        refund = next(
            tool for tool in first_discovery.json()["tools"] if tool["name"] == "claims.issue_refund"
        )
        first_hash = refund["current_version"]["schema_hash"]
        self.assertEqual(len(refund["versions"]), 1)

        patched = self.client.patch(
            f"/api/v1/mcp/servers/{server_id}",
            headers=self._headers(),
            json={"endpoint_url": "https://mcp.claims.local/rpc?schema=v2"},
        )
        self.assertEqual(patched.status_code, 200)

        second_discovery = self.client.post(
            f"/api/v1/mcp/servers/{server_id}/discover-tools",
            headers=self._headers(),
        )
        self.assertEqual(second_discovery.status_code, 201)
        changed_refund = next(
            tool for tool in second_discovery.json()["tools"] if tool["name"] == "claims.issue_refund"
        )
        self.assertEqual(changed_refund["status"], "changed")
        self.assertNotEqual(changed_refund["current_version"]["schema_hash"], first_hash)

        detail = self.client.get(f"/api/v1/mcp/tools/{refund['id']}", headers=self._headers())
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(len(detail.json()["versions"]), 2)
        self.assertEqual(detail.json()["current_version_id"], detail.json()["current_version"]["id"])
        self.assertIn("reason", detail.json()["current_version"]["schema"]["properties"])

        servers = self.client.get("/api/v1/mcp/servers", headers=self._headers())
        self.assertEqual(servers.status_code, 200)
        self.assertEqual(servers.json()[0]["tool_count"], 3)
        self.assertIsNotNone(servers.json()[0]["last_discovered_at"])

        events = AuditEventRepository(self.database.connect()).query(
            AuditEventQuery(
                organization_id="org_default",
                environment_id="env_default",
                resource_type="mcp_tool",
                resource_id=refund["id"],
                event_type="mcp.tool.schema.changed",
            )
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].payload_json["previous_schema_hash"], first_hash)
        self.assertEqual(events[0].correlation_id, "corr-mcp-overall")


if __name__ == "__main__":
    unittest.main()

