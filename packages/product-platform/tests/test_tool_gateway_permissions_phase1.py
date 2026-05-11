from __future__ import annotations

import unittest

from product_platform.db.seed import DEMO_ADMIN_USER_ID, DEMO_ENV_ID, DEMO_ORG_ID, seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.tool_gateway.models import (
    AgentToolPermissionGrantRequest,
    ToolDefinitionCreateRequest,
)
from product_platform.tool_gateway.repository import (
    AgentToolPermissionValidationError,
    DuplicateAgentToolPermissionError,
    ToolRegistryRepository,
)


VALID_INPUT_SCHEMA = {
    "type": "object",
    "properties": {"claim_id": {"type": "string"}},
    "required": ["claim_id"],
}


class ToolGatewayPermissionsPhase1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection, agent_id="agent_permissions_active", status="active")
            self._insert_agent(connection, agent_id="agent_permissions_suspended", status="suspended")
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
                "Tool permission test agent.",
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

    def _grant_body(self, tool_id: str, *, scope: str = "claims.lookup:read") -> AgentToolPermissionGrantRequest:
        return AgentToolPermissionGrantRequest(
            tool_id=tool_id,
            scope=scope,
            granted_reason="Support workflow needs claim lookup.",
        )

    def test_unit_permission_expiration_requires_timezone(self) -> None:
        with self.assertRaises(ValueError):
            AgentToolPermissionGrantRequest(
                tool_id="tool_1",
                scope="claims.lookup:read",
                expires_at="2030-01-01T00:00:00",
            )

    def test_unit_permission_expiration_is_normalized_to_utc(self) -> None:
        body = AgentToolPermissionGrantRequest(
            tool_id="tool_1",
            scope="claims.lookup:read",
            expires_at="2030-01-01T01:00:00+01:00",
        )

        self.assertEqual(body.expires_at, "2030-01-01T00:00:00+00:00")

    def test_integration_grants_permission_for_active_agent_and_tool(self) -> None:
        with self.database.transaction():
            tool_id = self._create_active_tool()
            row = self.repository.grant_agent_tool_permission(
                "agent_permissions_active",
                self._grant_body(tool_id),
                granted_by=DEMO_ADMIN_USER_ID,
            )

        self.assertTrue(row["id"].startswith("agtperm_"))
        self.assertEqual(row["agent_id"], "agent_permissions_active")
        self.assertEqual(row["agent_name"], "agent_permissions_active")
        self.assertEqual(row["tool_id"], tool_id)
        self.assertEqual(row["tool_name"], "claims.lookup")
        self.assertEqual(row["scope"], "claims.lookup:read")
        self.assertEqual(row["status"], "active")

        history = self.connection.execute(
            "SELECT * FROM agent_tool_permission_history WHERE permission_id = ?",
            (row["id"],),
        ).fetchall()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["action"], "granted")
        self.assertEqual(history[0]["new_status"], "active")

    def test_integration_duplicate_active_grant_is_rejected(self) -> None:
        with self.database.transaction():
            tool_id = self._create_active_tool()
            self.repository.grant_agent_tool_permission(
                "agent_permissions_active",
                self._grant_body(tool_id),
                granted_by=DEMO_ADMIN_USER_ID,
            )
            with self.assertRaisesRegex(DuplicateAgentToolPermissionError, "already has"):
                self.repository.grant_agent_tool_permission(
                    "agent_permissions_active",
                    self._grant_body(tool_id),
                    granted_by=DEMO_ADMIN_USER_ID,
                )

    def test_integration_grant_to_retired_tool_is_rejected(self) -> None:
        with self.database.transaction():
            tool_id = self._create_active_tool()
            self.connection.execute(
                "UPDATE tool_definitions SET status = 'retired' WHERE id = ?",
                (tool_id,),
            )
            with self.assertRaisesRegex(AgentToolPermissionValidationError, "active tool"):
                self.repository.grant_agent_tool_permission(
                    "agent_permissions_active",
                    self._grant_body(tool_id),
                    granted_by=DEMO_ADMIN_USER_ID,
                )

    def test_integration_grant_to_inactive_agent_is_rejected(self) -> None:
        with self.database.transaction():
            tool_id = self._create_active_tool()
            with self.assertRaisesRegex(AgentToolPermissionValidationError, "active agent"):
                self.repository.grant_agent_tool_permission(
                    "agent_permissions_suspended",
                    self._grant_body(tool_id),
                    granted_by=DEMO_ADMIN_USER_ID,
                )

    def test_repository_active_lookup_ignores_revoked_permissions(self) -> None:
        with self.database.transaction():
            tool_id = self._create_active_tool()
            row = self.repository.grant_agent_tool_permission(
                "agent_permissions_active",
                self._grant_body(tool_id),
                granted_by=DEMO_ADMIN_USER_ID,
            )
            self.repository.revoke_agent_tool_permission(
                row["id"],
                actor_id=DEMO_ADMIN_USER_ID,
                reason="Access no longer needed.",
            )

        active = self.repository.find_active_agent_tool_permission(
            agent_id="agent_permissions_active",
            tool_id=tool_id,
            scope="claims.lookup:read",
        )
        all_rows = self.repository.list_agent_tool_permissions(agent_id="agent_permissions_active")

        self.assertIsNone(active)
        self.assertEqual(len(all_rows), 1)
        self.assertEqual(all_rows[0]["status"], "revoked")


if __name__ == "__main__":
    unittest.main()
