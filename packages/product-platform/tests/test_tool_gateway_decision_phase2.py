from __future__ import annotations

import unittest

from product_platform.db.seed import DEMO_ADMIN_USER_ID, DEMO_ENV_ID, DEMO_ORG_ID, seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.tool_gateway.auth import GatewayPrincipal
from product_platform.tool_gateway.decision import (
    ToolPolicyDecisionRepository,
    ToolPolicyDecisionService,
)
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


class ToolGatewayDecisionPhase2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection, agent_id="agent_decision_active", status="active")
            self._insert_agent(connection, agent_id="agent_decision_suspended", status="suspended")
        self.connection = self.database.connect()
        self.registry = ToolRegistryRepository(self.connection, DEMO_ORG_ID, DEMO_ENV_ID)
        self.service = ToolPolicyDecisionService(self.connection, DEMO_ORG_ID, DEMO_ENV_ID)

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
                "Decision test agent.",
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

    def _principal(self, *, agent_id: str = "agent_decision_active", scopes: list[str] | None = None) -> GatewayPrincipal:
        return GatewayPrincipal(
            organization_id=DEMO_ORG_ID,
            environment_id=DEMO_ENV_ID,
            agent_id=agent_id,
            credential_id=f"cred_{agent_id}",
            scopes=scopes or ["claims.lookup:read"],
            request_id="req-decision",
        )

    def _create_tool(self, *, name: str = "claims.lookup", active: bool = True) -> dict:
        tool = self.registry.create_tool(
            ToolDefinitionCreateRequest(
                name=name,
                display_name="Claims Lookup",
                owner_team="claims-platform",
                required_scope=f"{name}:read",
                input_schema_json=VALID_INPUT_SCHEMA,
            ),
            created_by=DEMO_ADMIN_USER_ID,
        )
        if active:
            tool = self.registry.activate_tool(tool["id"], actor_id=DEMO_ADMIN_USER_ID)
        return dict(tool)

    def _grant(self, *, agent_id: str, tool_id: str, scope: str) -> dict:
        return dict(
            self.registry.grant_agent_tool_permission(
                agent_id,
                AgentToolPermissionGrantRequest(
                    tool_id=tool_id,
                    scope=scope,
                    granted_reason="decision test grant",
                ),
                granted_by=DEMO_ADMIN_USER_ID,
            )
        )

    def test_unit_active_agent_with_active_permission_is_allowed(self) -> None:
        with self.database.transaction():
            tool = self._create_tool()
            permission = self._grant(
                agent_id="agent_decision_active",
                tool_id=tool["id"],
                scope="claims.lookup:read",
            )
            decision = self.service.evaluate_tool_call(
                self._principal(),
                "claims.lookup",
                {"claim_id": "claim_123", "api_key": "secret"},
                request_id="req-allowed",
                correlation_id="corr-allowed",
            )

        self.assertEqual(decision.decision, "allow")
        self.assertEqual(decision.reason_code, "allowed")
        self.assertEqual(decision.tool_id, tool["id"])
        self.assertEqual(decision.permission_id, permission["id"])
        self.assertEqual(decision.payload_summary["api_key"], "[redacted]")
        persisted = ToolPolicyDecisionRepository(
            self.connection,
            DEMO_ORG_ID,
            DEMO_ENV_ID,
        ).get_decision(decision.id)
        self.assertIsNotNone(persisted)

    def test_unit_suspended_agent_is_denied(self) -> None:
        with self.database.transaction():
            decision = self.service.evaluate_tool_call(
                self._principal(agent_id="agent_decision_suspended"),
                "claims.lookup",
                {"claim_id": "claim_123"},
                request_id="req-suspended",
                correlation_id="corr-suspended",
            )

        self.assertEqual(decision.decision, "deny")
        self.assertEqual(decision.reason_code, "agent_inactive")

    def test_unit_disabled_tool_is_denied(self) -> None:
        with self.database.transaction():
            tool = self._create_tool(name="claims.disabled")
            self.registry.disable_tool(tool["id"], actor_id=DEMO_ADMIN_USER_ID)
            decision = self.service.evaluate_tool_call(
                self._principal(scopes=["claims.disabled:read"]),
                "claims.disabled",
                {"claim_id": "claim_123"},
                request_id="req-disabled",
                correlation_id="corr-disabled",
            )

        self.assertEqual(decision.decision, "deny")
        self.assertEqual(decision.reason_code, "tool_inactive")
        self.assertEqual(decision.tool_id, tool["id"])

    def test_unit_missing_permission_is_denied(self) -> None:
        with self.database.transaction():
            tool = self._create_tool()
            decision = self.service.evaluate_tool_call(
                self._principal(),
                "claims.lookup",
                {"claim_id": "claim_123"},
                request_id="req-missing-permission",
                correlation_id="corr-missing-permission",
            )

        self.assertEqual(decision.decision, "deny")
        self.assertEqual(decision.reason_code, "permission_missing")
        self.assertEqual(decision.tool_id, tool["id"])
        self.assertIsNone(decision.permission_id)

    def test_unit_insufficient_scope_is_denied(self) -> None:
        with self.database.transaction():
            tool = self._create_tool()
            permission = self._grant(
                agent_id="agent_decision_active",
                tool_id=tool["id"],
                scope="claims.lookup:write",
            )
            decision = self.service.evaluate_tool_call(
                self._principal(scopes=["claims.lookup:write"]),
                "claims.lookup",
                {"claim_id": "claim_123"},
                request_id="req-insufficient-scope",
                correlation_id="corr-insufficient-scope",
            )

        self.assertEqual(decision.decision, "deny")
        self.assertEqual(decision.reason_code, "scope_insufficient")
        self.assertEqual(decision.permission_id, permission["id"])


if __name__ == "__main__":
    unittest.main()
