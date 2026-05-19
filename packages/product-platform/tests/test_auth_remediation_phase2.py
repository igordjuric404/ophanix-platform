from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.agents.credentials import AgentCredentialRepository
from product_platform.agents.models import CredentialScopeRequest
from product_platform.api.settings import Settings
from product_platform.db.seed import DEMO_ADMIN_USER_ID, DEMO_ENV_ID, DEMO_ORG_ID, seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.tool_gateway.delegation import (
    DelegatedAuthorizationCreate,
    ToolDelegationRequirementCreate,
    ToolDelegationRepository,
)
from product_platform.tool_gateway.invocation import ToolExecutionResult
from product_platform.tool_gateway.models import (
    AgentToolPermissionGrantRequest,
    ToolDefinitionCreateRequest,
)
from product_platform.tool_gateway.repository import ToolRegistryRepository
from product_platform.tool_gateway.runtime_audit import (
    ToolRuntimeActionQuery,
    ToolRuntimeActionRepository,
)


class CapturingExecutor:
    def __init__(self) -> None:
        self.principals: list[object] = []

    def execute(self, *, tool, payload, decision, principal):
        self.principals.append(principal)
        return ToolExecutionResult(
            status="succeeded",
            body={"claim_status": "open"},
            upstream_status_code=200,
            latency_ms=4.2,
        )


class AuthRemediationPhase2GatewayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection)
            AgentCredentialRepository(connection, DEMO_ORG_ID, DEMO_ENV_ID).create_metadata(
                agent_id="agent_delegated_auth",
                credential_type="bearer",
                raw_token="delegated-auth-token",
                issuer="delegated-auth-test",
                expires_at="2030-01-01T00:00:00+00:00",
                scopes=[
                    CredentialScopeRequest(
                        scope="claims.lookup:read",
                        resource_type="tool",
                        resource_id="claims.delegated",
                    )
                ],
                status="active",
            )
            registry = ToolRegistryRepository(connection, DEMO_ORG_ID, DEMO_ENV_ID)
            tool = registry.create_tool(
                ToolDefinitionCreateRequest(
                    name="claims.delegated",
                    display_name="Claims Delegated",
                    owner_team="claims-platform",
                    required_scope="claims.lookup:read",
                    input_schema_json={
                        "type": "object",
                        "properties": {"claim_id": {"type": "string"}},
                        "required": ["claim_id"],
                    },
                ),
                created_by=DEMO_ADMIN_USER_ID,
            )
            self.tool_id = tool["id"]
            registry.activate_tool(tool["id"], actor_id=DEMO_ADMIN_USER_ID)
            registry.grant_agent_tool_permission(
                "agent_delegated_auth",
                AgentToolPermissionGrantRequest(
                    tool_id=self.tool_id,
                    scope="claims.lookup:read",
                    granted_reason="delegated authorization fixture",
                ),
                granted_by=DEMO_ADMIN_USER_ID,
            )
            ToolDelegationRepository(connection, DEMO_ORG_ID, DEMO_ENV_ID).create_requirement(
                ToolDelegationRequirementCreate(
                    tool_id=self.tool_id,
                    provider="claims-oauth",
                    required_scopes=["claims.read"],
                    approval_required=True,
                )
            )
        self.app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-05-19T00:00:00Z",
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.executor = CapturingExecutor()
        self.app.state.tool_gateway_executor = self.executor
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def _insert_agent(self, connection) -> None:
        now = "2026-05-19T00:00:00+00:00"
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
                "agent_delegated_auth",
                DEMO_ORG_ID,
                DEMO_ENV_ID,
                "agent_delegated_auth",
                "Delegated authorization fixture.",
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

    def _headers(self, *, delegated: bool = False) -> dict[str, str]:
        headers = {
            "Authorization": "Bearer delegated-auth-token",
            "X-Request-ID": "req-delegated-auth",
            "X-Correlation-ID": "corr-delegated-auth",
        }
        if delegated:
            headers["X-Delegated-User-ID"] = "user_123"
            headers["X-Delegated-Provider-Account-ID"] = "acct_456"
        return headers

    def test_gateway_requires_user_delegation_for_user_tool(self) -> None:
        response = self.client.post(
            "/api/v1/tools/claims.delegated/invoke",
            headers=self._headers(),
            json={"payload": {"claim_id": "claim_123"}},
        )

        self.assertEqual(response.status_code, 403, response.text)
        payload = response.json()
        self.assertEqual(payload["reason_code"], "authorization_required")
        self.assertEqual(payload["error"]["code"], "authorization_required")
        self.assertEqual(payload["error"]["authorization"]["provider"], "claims-oauth")
        self.assertEqual(payload["error"]["authorization"]["required_scopes"], ["claims.read"])
        self.assertEqual(len(self.executor.principals), 0)

        actions = ToolRuntimeActionRepository(
            self.database.connect(),
            DEMO_ORG_ID,
            DEMO_ENV_ID,
        ).list_actions(ToolRuntimeActionQuery(action_status="authorization_pending"))
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["delegated_user_id"], None)
        self.assertEqual(actions[0]["approval_state"], "pending_authorization")
        self.assertIsNotNone(actions[0]["authorization_session_id"])

    def test_gateway_allows_active_delegated_authorization_and_binds_principal(self) -> None:
        with self.database.transaction() as connection:
            ToolDelegationRepository(connection, DEMO_ORG_ID, DEMO_ENV_ID).create_authorization(
                DelegatedAuthorizationCreate(
                    agent_id="agent_delegated_auth",
                    tool_id=self.tool_id,
                    user_id="user_123",
                    provider_account_id="acct_456",
                    provider="claims-oauth",
                    scopes=["claims.read"],
                    approval_state="approved",
                    expires_at="2030-01-01T00:00:00+00:00",
                )
            )

        response = self.client.post(
            "/api/v1/tools/claims.delegated/invoke",
            headers=self._headers(delegated=True),
            json={"payload": {"claim_id": "claim_123"}},
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(self.executor.principals), 1)
        principal = self.executor.principals[0]
        self.assertEqual(principal.delegated_user_id, "user_123")
        self.assertEqual(principal.delegated_provider_account_id, "acct_456")
        self.assertEqual(principal.approval_state, "approved")

        actions = ToolRuntimeActionRepository(
            self.database.connect(),
            DEMO_ORG_ID,
            DEMO_ENV_ID,
        ).list_actions(ToolRuntimeActionQuery(action_status="completed"))
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["delegated_user_id"], "user_123")
        self.assertEqual(actions[0]["provider_account_id"], "acct_456")
        self.assertEqual(actions[0]["approval_state"], "approved")

    def test_gateway_blocks_expired_delegated_authorization(self) -> None:
        with self.database.transaction() as connection:
            ToolDelegationRepository(connection, DEMO_ORG_ID, DEMO_ENV_ID).create_authorization(
                DelegatedAuthorizationCreate(
                    agent_id="agent_delegated_auth",
                    tool_id=self.tool_id,
                    user_id="user_123",
                    provider_account_id="acct_456",
                    provider="claims-oauth",
                    scopes=["claims.read"],
                    approval_state="approved",
                    expires_at="2020-01-01T00:00:00+00:00",
                )
            )

        response = self.client.post(
            "/api/v1/tools/claims.delegated/invoke",
            headers=self._headers(delegated=True),
            json={"payload": {"claim_id": "claim_123"}},
        )

        self.assertEqual(response.status_code, 403, response.text)
        self.assertEqual(response.json()["reason_code"], "delegated_authorization_expired")
        self.assertEqual(len(self.executor.principals), 0)


if __name__ == "__main__":
    unittest.main()
