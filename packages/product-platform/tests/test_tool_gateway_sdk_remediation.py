from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.agents.credentials import AgentCredentialRepository
from product_platform.agents.models import CredentialScopeRequest
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


class ToolGatewaySdkRemediationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection, agent_id="agent_gateway_discovery")
            self._insert_agent(connection, agent_id="agent_gateway_no_scope")
            credential_repository = AgentCredentialRepository(connection, DEMO_ORG_ID, DEMO_ENV_ID)
            credential_repository.create_metadata(
                agent_id="agent_gateway_discovery",
                credential_type="bearer",
                raw_token="gateway-discovery-token",
                issuer="sdk-remediation-test",
                expires_at="2030-01-01T00:00:00+00:00",
                scopes=[
                    CredentialScopeRequest(
                        scope="claims.lookup:read",
                        resource_type="tool",
                        resource_id="claims.lookup",
                    )
                ],
                status="active",
            )
            credential_repository.create_metadata(
                agent_id="agent_gateway_no_scope",
                credential_type="bearer",
                raw_token="gateway-no-scope-token",
                issuer="sdk-remediation-test",
                expires_at="2030-01-01T00:00:00+00:00",
                scopes=[
                    CredentialScopeRequest(
                        scope="claims.other:read",
                        resource_type="tool",
                        resource_id="claims.other",
                    )
                ],
                status="active",
            )
            self.repository = ToolRegistryRepository(connection, DEMO_ORG_ID, DEMO_ENV_ID)
            self.lookup_tool_id = self._create_active_tool(
                "claims.lookup",
                owner_team="claims-platform",
                scope="claims.lookup:read",
            )
            self.hidden_tool_id = self._create_active_tool(
                "claims.hidden",
                owner_team="claims-platform",
                scope="claims.hidden:read",
            )
            self.shared_scope_tool_id = self._create_active_tool(
                "claims.shared_scope",
                owner_team="claims-platform",
                scope="claims.lookup:read",
            )
            self.expired_tool_id = self._create_active_tool(
                "claims.expired",
                owner_team="claims-platform",
                scope="claims.expired:read",
            )
            self.repository.grant_agent_tool_permission(
                "agent_gateway_discovery",
                AgentToolPermissionGrantRequest(
                    tool_id=self.lookup_tool_id,
                    scope="claims.lookup:read",
                    granted_reason="SDK discovery test.",
                ),
                granted_by=DEMO_ADMIN_USER_ID,
            )
            self.repository.grant_agent_tool_permission(
                "agent_gateway_discovery",
                AgentToolPermissionGrantRequest(
                    tool_id=self.expired_tool_id,
                    scope="claims.expired:read",
                    granted_reason="SDK discovery expiry test.",
                    expires_at="2020-01-01T00:00:00+00:00",
                ),
                granted_by=DEMO_ADMIN_USER_ID,
            )
            self.repository.grant_agent_tool_permission(
                "agent_gateway_discovery",
                AgentToolPermissionGrantRequest(
                    tool_id=self.shared_scope_tool_id,
                    scope="claims.lookup:read",
                    granted_reason="SDK discovery resource-binding test.",
                ),
                granted_by=DEMO_ADMIN_USER_ID,
            )
            self.repository.grant_agent_tool_permission(
                "agent_gateway_no_scope",
                AgentToolPermissionGrantRequest(
                    tool_id=self.lookup_tool_id,
                    scope="claims.lookup:read",
                    granted_reason="SDK discovery credential-scope test.",
                ),
                granted_by=DEMO_ADMIN_USER_ID,
            )
        self.app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-05-01T00:00:00Z",
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def _insert_agent(self, connection, *, agent_id: str) -> None:
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
                "Gateway discovery fixture.",
                "langgraph",
                "service",
                None,
                DEMO_ADMIN_USER_ID,
                DEMO_ADMIN_USER_ID,
                "active",
                now,
                now,
            ),
        )

    def _create_active_tool(self, name: str, *, owner_team: str, scope: str) -> str:
        tool = self.repository.create_tool(
            ToolDefinitionCreateRequest(
                name=name,
                display_name=name.replace(".", " ").title(),
                owner_team=owner_team,
                required_scope=scope,
                input_schema_json=VALID_INPUT_SCHEMA,
            ),
            created_by=DEMO_ADMIN_USER_ID,
        )
        self.repository.activate_tool(tool["id"], actor_id=DEMO_ADMIN_USER_ID)
        return tool["id"]

    def _headers(self, token: str = "gateway-discovery-token") -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    def test_gateway_discovery_requires_gateway_authentication(self) -> None:
        response = self.client.get("/api/v1/gateway/tools")

        self.assertEqual(response.status_code, 401)
        self.assertIn("missing_authorization", response.json()["message"])

    def test_gateway_discovery_lists_only_callable_active_tools(self) -> None:
        response = self.client.get("/api/v1/gateway/tools", headers=self._headers())

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual([tool["name"] for tool in payload], ["claims.lookup"])
        self.assertEqual(payload[0]["id"], self.lookup_tool_id)
        self.assertNotIn("organization_id", payload[0])
        self.assertNotIn("environment_id", payload[0])
        self.assertNotIn("created_by", payload[0])

    def test_gateway_discovery_honors_owner_team_filter(self) -> None:
        response = self.client.get(
            "/api/v1/gateway/tools",
            headers=self._headers(),
            params={"owner_team": "other-team"},
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), [])

    def test_gateway_discovery_requires_credential_scope_and_permission_scope(self) -> None:
        response = self.client.get(
            "/api/v1/gateway/tools",
            headers=self._headers("gateway-no-scope-token"),
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), [])

    def test_gateway_invocation_requires_credential_resource_binding(self) -> None:
        response = self.client.post(
            "/api/v1/tools/claims.shared_scope/invoke",
            headers=self._headers(),
            json={"payload": {"claim_id": "claim_123"}},
        )

        self.assertEqual(response.status_code, 403, response.text)
        payload = response.json()
        self.assertEqual(payload["reason_code"], "scope_insufficient")


if __name__ == "__main__":
    unittest.main()
