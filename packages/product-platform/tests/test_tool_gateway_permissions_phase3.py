from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import DEMO_ADMIN_USER_ID, DEMO_ENV_ID, DEMO_ORG_ID, seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.tool_gateway.models import (
    AgentToolPermissionGrantRequest,
    ToolDefinitionCreateRequest,
)
from product_platform.tool_gateway.repository import ToolRegistryRepository


VALID_INPUT_SCHEMA = {
    "type": "object",
    "properties": {"claim_id": {"type": "string"}},
    "required": ["claim_id"],
}


class ToolGatewayPermissionsPhase3Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection, agent_id="agent_permissions_expiry", status="active")
        self.connection = self.database.connect()
        self.repository = ToolRegistryRepository(self.connection, DEMO_ORG_ID, DEMO_ENV_ID)

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
                "Tool permission expiration test agent.",
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

    def _create_active_tool(self, *, name: str = "claims.lookup") -> str:
        tool = self.repository.create_tool(
            ToolDefinitionCreateRequest(
                name=name,
                display_name="Claims Lookup",
                owner_team="claims-platform",
                required_scope=f"{name}:read",
                input_schema_json=VALID_INPUT_SCHEMA,
            ),
            created_by=DEMO_ADMIN_USER_ID,
        )
        self.repository.activate_tool(tool["id"], actor_id=DEMO_ADMIN_USER_ID)
        return tool["id"]

    def _grant_body(
        self,
        tool_id: str,
        *,
        expires_at: str | None,
        scope: str = "claims.lookup:read",
    ) -> AgentToolPermissionGrantRequest:
        return AgentToolPermissionGrantRequest(
            tool_id=tool_id,
            scope=scope,
            granted_reason="Temporary access for support workflow.",
            expires_at=expires_at,
        )

    def test_unit_expired_permission_is_not_active(self) -> None:
        with self.database.transaction():
            tool_id = self._create_active_tool()
            row = self.repository.grant_agent_tool_permission(
                "agent_permissions_expiry",
                self._grant_body(tool_id, expires_at="2026-04-30T00:00:00+00:00"),
                granted_by=DEMO_ADMIN_USER_ID,
            )

        active = self.repository.find_active_agent_tool_permission(
            agent_id="agent_permissions_expiry",
            tool_id=tool_id,
            scope="claims.lookup:read",
            now="2026-05-01T00:00:00+00:00",
        )
        listed = self.repository.list_agent_tool_permissions(agent_id="agent_permissions_expiry")

        self.assertIsNone(active)
        self.assertEqual(listed[0]["id"], row["id"])
        self.assertEqual(listed[0]["status"], "active")

    def test_repository_mark_stale_permissions_expired(self) -> None:
        with self.database.transaction():
            expired_tool_id = self._create_active_tool(name="claims.expired")
            future_tool_id = self._create_active_tool(name="claims.future")
            expired = self.repository.grant_agent_tool_permission(
                "agent_permissions_expiry",
                self._grant_body(
                    expired_tool_id,
                    expires_at="2026-04-30T00:00:00+00:00",
                    scope="claims.expired:read",
                ),
                granted_by=DEMO_ADMIN_USER_ID,
            )
            future = self.repository.grant_agent_tool_permission(
                "agent_permissions_expiry",
                self._grant_body(
                    future_tool_id,
                    expires_at="2026-06-01T00:00:00+00:00",
                    scope="claims.future:read",
                ),
                granted_by=DEMO_ADMIN_USER_ID,
            )
            marked = self.repository.mark_expired_agent_tool_permissions(
                now="2026-05-01T00:00:00+00:00",
            )

        self.assertEqual(marked, 1)
        expired_row = self.repository.get_agent_tool_permission(expired["id"])
        future_row = self.repository.get_agent_tool_permission(future["id"])
        self.assertEqual(expired_row["status"], "expired")
        self.assertEqual(future_row["status"], "active")
        expired_history = self.repository.list_agent_tool_permission_history(expired["id"])
        self.assertEqual(expired_history[0]["action"], "expired")
        self.assertEqual(expired_history[0]["previous_status"], "active")
        self.assertEqual(expired_history[0]["new_status"], "expired")

    def test_api_expired_permission_appears_with_expired_status(self) -> None:
        with self.database.transaction():
            tool_id = self._create_active_tool()
            permission = self.repository.grant_agent_tool_permission(
                "agent_permissions_expiry",
                self._grant_body(tool_id, expires_at="2026-04-30T00:00:00+00:00"),
                granted_by=DEMO_ADMIN_USER_ID,
            )
            self.repository.mark_expired_agent_tool_permissions(
                now="2026-05-01T00:00:00+00:00",
            )
        app = create_app(
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
        client = TestClient(app, raise_server_exceptions=False)
        login = client.post(
            "/api/v1/auth/dev-login",
            json={"email": "admin@example.com", "roles": ["Security Admin"]},
        )
        self.assertEqual(login.status_code, 200, login.text)
        headers = {
            "Authorization": f"Bearer {login.json()['access_token']}",
            "X-Environment-ID": "env_default",
        }

        response = client.get(
            "/api/v1/agents/agent_permissions_expiry/tool-permissions",
            headers=headers,
            params={"status": "expired"},
        )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual([row["id"] for row in payload], [permission["id"]])
        self.assertEqual(payload[0]["status"], "expired")
        self.assertEqual(payload[0]["expires_at"], "2026-04-30T00:00:00+00:00")


if __name__ == "__main__":
    unittest.main()
