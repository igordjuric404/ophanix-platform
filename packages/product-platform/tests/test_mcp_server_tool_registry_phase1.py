from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.api.tenancy import Environment, TenantStore
from product_platform.audit.store import AuditEventQuery, AuditEventRepository
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


class MCPServerToolRegistryPhase1Tests(unittest.TestCase):
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
            tenant_store=TenantStore(
                environments=[
                    Environment(
                        id="env_default",
                        organization_id="org_default",
                        name="Development",
                        slug="development",
                        type="development",
                        created_at="2026-05-01T00:00:00+00:00",
                    ),
                    Environment(
                        id="env_other",
                        organization_id="org_default",
                        name="Other",
                        slug="other",
                        type="development",
                        created_at="2026-05-01T00:00:00+00:00",
                    ),
                ]
            ),
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "admin@example.com", "roles": ["Security Admin"]},
        )
        self.assertEqual(login.status_code, 200)
        self.token = login.json()["access_token"]

    def _headers(self, *, environment_id: str = "env_default") -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": environment_id,
            "X-Correlation-ID": "corr-mcp-registry",
        }

    def _create_server(self, *, name: str = "Claims MCP") -> dict:
        response = self.client.post(
            "/api/v1/mcp/servers",
            headers=self._headers(),
            json={
                "name": name,
                "endpoint_url": "https://mcp.claims.local/rpc",
                "owner_user_id": "user_admin",
                "auth_type": "oauth",
                "status": "registered",
                "policy_pack_id": "policy_placeholder_sensitive_tools",
            },
        )
        self.assertEqual(response.status_code, 201)
        return response.json()

    def test_api_creates_lists_gets_and_patches_mcp_server(self) -> None:
        created = self._create_server()

        self.assertTrue(created["id"].startswith("mcpsrv_"))
        self.assertEqual(created["name"], "Claims MCP")
        self.assertEqual(created["endpoint_url"], "https://mcp.claims.local/rpc")
        self.assertEqual(created["owner_user_id"], "user_admin")
        self.assertEqual(created["owner_email"], "admin@example.com")
        self.assertEqual(created["auth_type"], "oauth")
        self.assertEqual(created["status"], "registered")
        self.assertEqual(created["policy_pack_id"], "policy_placeholder_sensitive_tools")

        listed = self.client.get("/api/v1/mcp/servers", headers=self._headers())
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()[0]["id"], created["id"])

        fetched = self.client.get(
            f"/api/v1/mcp/servers/{created['id']}",
            headers=self._headers(),
        )
        self.assertEqual(fetched.status_code, 200)
        self.assertEqual(fetched.json()["name"], "Claims MCP")

        patched = self.client.patch(
            f"/api/v1/mcp/servers/{created['id']}",
            headers=self._headers(),
            json={"name": "Claims MCP v2", "status": "active"},
        )
        self.assertEqual(patched.status_code, 200)
        self.assertEqual(patched.json()["name"], "Claims MCP v2")
        self.assertEqual(patched.json()["status"], "active")

    def test_api_invalid_endpoint_is_rejected(self) -> None:
        response = self.client.post(
            "/api/v1/mcp/servers",
            headers=self._headers(),
            json={
                "name": "Local Socket MCP",
                "endpoint_url": "file:///tmp/mcp.sock",
                "owner_user_id": "user_admin",
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_api_server_is_environment_scoped(self) -> None:
        created = self._create_server()

        listed = self.client.get(
            "/api/v1/mcp/servers",
            headers=self._headers(environment_id="env_other"),
        )
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json(), [])

        fetched = self.client.get(
            f"/api/v1/mcp/servers/{created['id']}",
            headers=self._headers(environment_id="env_other"),
        )
        self.assertEqual(fetched.status_code, 404)

    def test_api_unknown_owner_is_rejected(self) -> None:
        response = self.client.post(
            "/api/v1/mcp/servers",
            headers=self._headers(),
            json={
                "name": "Orphan MCP",
                "endpoint_url": "https://mcp.orphan.local/rpc",
                "owner_user_id": "user_missing",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Owner user not found", response.json()["message"])

    def test_integration_create_and_status_update_emit_audit_events(self) -> None:
        created = self._create_server()
        patched = self.client.patch(
            f"/api/v1/mcp/servers/{created['id']}",
            headers=self._headers(),
            json={"status": "disabled"},
        )
        self.assertEqual(patched.status_code, 200)

        events = AuditEventRepository(self.database.connect()).query(
            AuditEventQuery(
                organization_id="org_default",
                environment_id="env_default",
                resource_type="mcp_server",
                resource_id=created["id"],
            )
        )

        self.assertEqual([event.event_type for event in events], ["mcp.server.updated", "mcp.server.created"])
        self.assertEqual(events[0].payload_json["previous_status"], "registered")
        self.assertTrue(events[0].payload_json["status_changed"])
        self.assertEqual(events[0].payload_json["status"], "disabled")
        self.assertEqual(events[0].correlation_id, "corr-mcp-registry")
        self.assertEqual(events[1].payload_json["name"], "Claims MCP")


if __name__ == "__main__":
    unittest.main()
