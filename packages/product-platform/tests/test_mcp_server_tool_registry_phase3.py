from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.audit.store import AuditEventQuery, AuditEventRepository
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


class MCPServerToolRegistryPhase3Tests(unittest.TestCase):
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
            "X-Correlation-ID": "corr-mcp-versioning",
        }

    def _create_server(self, endpoint_url: str = "https://mcp.claims.local/rpc") -> dict:
        response = self.client.post(
            "/api/v1/mcp/servers",
            headers=self._headers(),
            json={
                "name": "Claims MCP",
                "endpoint_url": endpoint_url,
                "owner_user_id": "user_admin",
                "auth_type": "oauth",
            },
        )
        self.assertEqual(response.status_code, 201)
        return response.json()

    def _discover(self, server_id: str) -> dict:
        response = self.client.post(
            f"/api/v1/mcp/servers/{server_id}/discover-tools",
            headers=self._headers(),
        )
        self.assertEqual(response.status_code, 201)
        return response.json()

    def _tool_by_name(self, name: str) -> dict:
        response = self.client.get("/api/v1/mcp/tools", headers=self._headers())
        self.assertEqual(response.status_code, 200)
        return next(tool for tool in response.json() if tool["name"] == name)

    def test_unchanged_schema_does_not_create_duplicate_version(self) -> None:
        server = self._create_server()
        self._discover(server["id"])
        refund = self._tool_by_name("claims.issue_refund")
        first_version_id = refund["current_version_id"]

        self._discover(server["id"])

        detail = self.client.get(f"/api/v1/mcp/tools/{refund['id']}", headers=self._headers())
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["current_version_id"], first_version_id)
        self.assertEqual(len(detail.json()["versions"]), 1)

    def test_changed_schema_creates_new_version_and_audit_event(self) -> None:
        server = self._create_server()
        self._discover(server["id"])
        refund = self._tool_by_name("claims.issue_refund")
        first_hash = refund["current_version"]["schema_hash"]

        patched = self.client.patch(
            f"/api/v1/mcp/servers/{server['id']}",
            headers=self._headers(),
            json={"endpoint_url": "https://mcp.claims.local/rpc?schema=v2"},
        )
        self.assertEqual(patched.status_code, 200)
        self._discover(server["id"])

        detail = self.client.get(f"/api/v1/mcp/tools/{refund['id']}", headers=self._headers())
        self.assertEqual(detail.status_code, 200)
        payload = detail.json()
        self.assertEqual(payload["status"], "changed")
        self.assertEqual(len(payload["versions"]), 2)
        self.assertNotEqual(payload["current_version"]["schema_hash"], first_hash)
        self.assertEqual(payload["current_version_id"], payload["current_version"]["id"])
        self.assertIn("reason", payload["current_version"]["schema"]["properties"])

        events = AuditEventRepository(self.database.connect()).query(
            AuditEventQuery(
                organization_id="org_default",
                environment_id="env_default",
                event_type="mcp.tool.schema.changed",
                resource_type="mcp_tool",
                resource_id=refund["id"],
            )
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].payload_json["previous_schema_hash"], first_hash)
        self.assertEqual(events[0].payload_json["schema_hash"], payload["current_version"]["schema_hash"])
        self.assertEqual(events[0].correlation_id, "corr-mcp-versioning")

    def test_api_current_version_points_to_newest_discovered_version(self) -> None:
        server = self._create_server()
        self._discover(server["id"])
        self.client.patch(
            f"/api/v1/mcp/servers/{server['id']}",
            headers=self._headers(),
            json={"endpoint_url": "https://mcp.claims.local/rpc?schema=v2"},
        )
        self._discover(server["id"])

        refund = self._tool_by_name("claims.issue_refund")

        self.assertEqual(refund["current_version_id"], refund["current_version"]["id"])
        self.assertIn("reason", refund["current_version"]["schema"]["properties"])


if __name__ == "__main__":
    unittest.main()

