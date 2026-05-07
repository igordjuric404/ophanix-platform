from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.audit.store import AuditEventQuery, AuditEventRepository
from product_platform.db.seed import DEMO_ADMIN_USER_ID, DEMO_ENV_ID, DEMO_ORG_ID, seed_demo_data
from product_platform.db.testing import create_migrated_test_database


VALID_INPUT_SCHEMA = {
    "type": "object",
    "properties": {"claim_id": {"type": "string"}},
    "required": ["claim_id"],
}


class ToolGatewayPermissionsPhase2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection, agent_id="agent_permissions_api", status="active")
        self.app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-05-01T00:00:00Z",
                dev_login_allowed_emails=["admin@example.com", "viewer@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        admin_login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "admin@example.com", "roles": ["Security Admin"]},
        )
        self.assertEqual(admin_login.status_code, 200, admin_login.text)
        self.admin_token = admin_login.json()["access_token"]
        viewer_login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "viewer@example.com", "roles": ["Viewer"]},
        )
        self.assertEqual(viewer_login.status_code, 200, viewer_login.text)
        self.viewer_token = viewer_login.json()["access_token"]

    def _insert_agent(self, connection, *, agent_id: str, status: str) -> None:
        now = "2026-05-01T00:00:00+00:00"
        connection.execute(
            """
            INSERT INTO agents (
                id, organization_id, environment_id, name, description, framework,
                runtime_type, endpoint_url, owner_user_id, sponsor_user_id, status,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                agent_id,
                DEMO_ORG_ID,
                DEMO_ENV_ID,
                agent_id,
                "Tool permission API test agent.",
                "langgraph",
                "service",
                None,
                DEMO_ADMIN_USER_ID,
                DEMO_ADMIN_USER_ID,
                status,
                now,
                now,
            ),
        )

    def _headers(self, *, token: str | None = None, correlation_id: str = "corr-permission") -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token or self.admin_token}",
            "X-Environment-ID": "env_default",
            "X-Correlation-ID": correlation_id,
        }

    def _create_active_tool(self, *, name: str = "claims.lookup") -> dict:
        created = self.client.post(
            "/api/v1/tools",
            headers=self._headers(),
            json={
                "name": name,
                "display_name": "Claims Lookup",
                "owner_team": "claims-platform",
                "required_scope": f"{name}:read",
                "input_schema_json": VALID_INPUT_SCHEMA,
            },
        )
        self.assertEqual(created.status_code, 201, created.text)
        activated = self.client.post(
            f"/api/v1/tools/{created.json()['id']}/activate",
            headers=self._headers(),
            json={"reason": "ready for permission tests"},
        )
        self.assertEqual(activated.status_code, 200, activated.text)
        return activated.json()

    def _grant(self, tool_id: str, *, correlation_id: str = "corr-permission") -> dict:
        response = self.client.post(
            "/api/v1/agents/agent_permissions_api/tool-permissions",
            headers=self._headers(correlation_id=correlation_id),
            json={
                "tool_id": tool_id,
                "scope": "claims.lookup:read",
                "granted_reason": "Support workflow needs claim lookup.",
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_api_grants_permission_with_scope(self) -> None:
        tool = self._create_active_tool()

        payload = self._grant(tool["id"])

        self.assertTrue(payload["id"].startswith("agtperm_"))
        self.assertEqual(payload["agent_id"], "agent_permissions_api")
        self.assertEqual(payload["agent_name"], "agent_permissions_api")
        self.assertEqual(payload["tool_id"], tool["id"])
        self.assertEqual(payload["tool_name"], "claims.lookup")
        self.assertEqual(payload["scope"], "claims.lookup:read")
        self.assertEqual(payload["status"], "active")

    def test_api_list_by_agent_returns_tool_metadata(self) -> None:
        tool = self._create_active_tool()
        permission = self._grant(tool["id"])

        response = self.client.get(
            "/api/v1/agents/agent_permissions_api/tool-permissions",
            headers=self._headers(),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual([row["id"] for row in payload], [permission["id"]])
        self.assertEqual(payload[0]["tool_name"], "claims.lookup")
        self.assertEqual(payload[0]["tool_display_name"], "Claims Lookup")

    def test_api_list_by_tool_returns_agent_metadata(self) -> None:
        tool = self._create_active_tool()
        permission = self._grant(tool["id"])

        response = self.client.get(
            f"/api/v1/tools/{tool['id']}/agent-permissions",
            headers=self._headers(),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual([row["id"] for row in payload], [permission["id"]])
        self.assertEqual(payload[0]["agent_name"], "agent_permissions_api")

    def test_api_revoke_requires_reason(self) -> None:
        tool = self._create_active_tool()
        permission = self._grant(tool["id"])

        response = self.client.post(
            f"/api/v1/agent-tool-permissions/{permission['id']}/revoke",
            headers=self._headers(),
            json={},
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("reason", response.text)

    def test_api_writes_require_security_manage_permission(self) -> None:
        tool = self._create_active_tool()

        response = self.client.post(
            "/api/v1/agents/agent_permissions_api/tool-permissions",
            headers=self._headers(token=self.viewer_token),
            json={
                "tool_id": tool["id"],
                "scope": "claims.lookup:read",
                "granted_reason": "viewer should not grant",
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertIn("security:manage", response.json()["message"])

    def test_integration_permission_writes_emit_audit_events(self) -> None:
        tool = self._create_active_tool()
        permission = self._grant(tool["id"], correlation_id="corr-permission-audit")
        patched = self.client.patch(
            f"/api/v1/agent-tool-permissions/{permission['id']}",
            headers=self._headers(correlation_id="corr-permission-audit"),
            json={"scope": "claims.lookup:extended"},
        )
        self.assertEqual(patched.status_code, 200, patched.text)
        paused = self.client.post(
            f"/api/v1/agent-tool-permissions/{permission['id']}/pause",
            headers=self._headers(correlation_id="corr-permission-audit"),
            json={"reason": "Temporary review."},
        )
        self.assertEqual(paused.status_code, 200, paused.text)
        revoked = self.client.post(
            f"/api/v1/agent-tool-permissions/{permission['id']}/revoke",
            headers=self._headers(correlation_id="corr-permission-audit"),
            json={"reason": "Access no longer needed."},
        )
        self.assertEqual(revoked.status_code, 200, revoked.text)

        events = AuditEventRepository(self.database.connect()).query(
            AuditEventQuery(
                organization_id="org_default",
                environment_id="env_default",
                resource_type="agent_tool_permission",
                resource_id=permission["id"],
            )
        )

        self.assertEqual(
            [event.event_type for event in events],
            [
                "agent_tool_permission.revoked",
                "agent_tool_permission.paused",
                "agent_tool_permission.updated",
                "agent_tool_permission.granted",
            ],
        )
        self.assertEqual(events[0].payload_json["reason"], "Access no longer needed.")
        self.assertEqual(events[1].payload_json["reason"], "Temporary review.")
        self.assertEqual(events[2].payload_json["scope"], "claims.lookup:extended")
        self.assertEqual(events[0].correlation_id, "corr-permission-audit")


if __name__ == "__main__":
    unittest.main()
