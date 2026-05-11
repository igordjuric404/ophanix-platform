from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.agents.credentials import AgentCredentialRepository
from product_platform.agents.models import CredentialScopeRequest
from product_platform.api.settings import Settings
from product_platform.db.seed import DEMO_ADMIN_USER_ID, DEMO_ENV_ID, DEMO_ORG_ID, seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.tool_gateway.models import ToolDefinitionCreateRequest
from product_platform.tool_gateway.models import AgentToolPermissionGrantRequest
from product_platform.tool_gateway.repository import ToolRegistryRepository
from product_platform.tool_gateway.runtime_audit import (
    ToolRuntimeActionQuery,
    ToolRuntimeActionRepository,
)
from product_platform.tool_gateway.invocation import ToolInvocationRequest


VALID_INPUT_SCHEMA = {
    "type": "object",
    "properties": {"claim_id": {"type": "string"}},
    "required": ["claim_id"],
    "additionalProperties": False,
}


class ToolGatewayInvocationPhase2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection)
            AgentCredentialRepository(connection, DEMO_ORG_ID, DEMO_ENV_ID).create_metadata(
                agent_id="agent_invoke_phase2",
                credential_type="bearer",
                raw_token="invoke-token-phase2",
                issuer="invoke-test",
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
            registry = ToolRegistryRepository(connection, DEMO_ORG_ID, DEMO_ENV_ID)
            tool = registry.create_tool(
                ToolDefinitionCreateRequest(
                    name="claims.lookup",
                    display_name="Claims Lookup",
                    owner_team="claims-platform",
                    required_scope="claims.lookup:read",
                    input_schema_json=VALID_INPUT_SCHEMA,
                ),
                created_by=DEMO_ADMIN_USER_ID,
            )
            self.tool_id = tool["id"]
            registry.activate_tool(tool["id"], actor_id=DEMO_ADMIN_USER_ID)
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

    def _insert_agent(self, connection) -> None:
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
                "agent_invoke_phase2",
                DEMO_ORG_ID,
                DEMO_ENV_ID,
                "agent_invoke_phase2",
                "Invocation payload validation fixture.",
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

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": "Bearer invoke-token-phase2",
            "X-Request-ID": "req-invoke-phase2",
            "X-Correlation-ID": "corr-invoke-phase2",
        }

    def test_api_valid_payload_reaches_policy_decision(self) -> None:
        response = self.client.post(
            "/api/v1/tools/claims.lookup/invoke",
            headers=self._headers(),
            json={"payload": {"claim_id": "claim_123"}},
        )

        self.assertEqual(response.status_code, 403, response.text)
        payload = response.json()
        self.assertEqual(payload["tool_name"], "claims.lookup")
        self.assertEqual(payload["reason_code"], "permission_missing")
        self.assertEqual(payload["decision"]["reason_code"], "permission_missing")

    def test_api_missing_required_payload_field_is_denied_before_schema_for_unauthorized_agent(self) -> None:
        response = self.client.post(
            "/api/v1/tools/claims.lookup/invoke",
            headers=self._headers(),
            json={"payload": {}},
        )

        self.assertEqual(response.status_code, 403)
        payload = response.json()
        self.assertEqual(payload["error"]["code"], "permission_missing")

    def test_api_missing_required_payload_field_returns_422_after_authorization(self) -> None:
        with self.database.transaction() as connection:
            ToolRegistryRepository(
                connection,
                DEMO_ORG_ID,
                DEMO_ENV_ID,
            ).grant_agent_tool_permission(
                "agent_invoke_phase2",
                AgentToolPermissionGrantRequest(
                    tool_id=self.tool_id,
                    scope="claims.lookup:read",
                    granted_reason="schema validation fixture",
                ),
                granted_by=DEMO_ADMIN_USER_ID,
            )

        response = self.client.post(
            "/api/v1/tools/claims.lookup/invoke",
            headers=self._headers(),
            json={"payload": {}},
        )

        self.assertEqual(response.status_code, 422)
        payload = response.json()
        self.assertEqual(payload["code"], "SCHEMA_VALIDATION_ERROR")
        self.assertEqual(payload["message"], "Payload failed schema validation.")
        self.assertEqual(payload["details"]["field"], "payload")
        actions = ToolRuntimeActionRepository(
            self.database.connect(),
            DEMO_ORG_ID,
            DEMO_ENV_ID,
        ).list_actions(ToolRuntimeActionQuery(action_status="validation_failed"))
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["error_code"], "schema_validation_failed")

    def test_api_unknown_tool_returns_policy_denial_without_schema_oracle(self) -> None:
        response = self.client.post(
            "/api/v1/tools/claims.missing/invoke",
            headers=self._headers(),
            json={"payload": {"claim_id": "claim_123"}},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"]["code"], "tool_missing")

    def test_unit_direct_http_payload_rejects_non_finite_numbers(self) -> None:
        with self.assertRaises(ValueError):
            ToolInvocationRequest(payload={"claim_id": float("nan")})

    def test_unit_direct_http_correlation_id_rejects_unsupported_characters(self) -> None:
        with self.assertRaises(ValueError):
            ToolInvocationRequest(payload={}, correlation_id="bad id with spaces")


if __name__ == "__main__":
    unittest.main()
