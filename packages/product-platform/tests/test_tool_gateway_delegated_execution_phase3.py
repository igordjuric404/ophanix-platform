from __future__ import annotations

import json
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
from product_platform.tool_gateway.models import AgentToolPermissionGrantRequest, ToolDefinitionCreateRequest
from product_platform.tool_gateway.repository import ToolRegistryRepository
from product_platform.tool_gateway.runtime_audit import ToolRuntimeActionQuery, ToolRuntimeActionRepository


class CapturingExecutor:
    def __init__(self) -> None:
        self.principals: list[object] = []

    def execute(self, *, tool, payload, decision, principal):
        self.principals.append(principal)
        return ToolExecutionResult(
            status="succeeded",
            body={"claim_status": "open"},
            upstream_status_code=200,
            latency_ms=3.5,
        )


class ToolGatewayDelegatedExecutionPhase3Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection)
            credential = AgentCredentialRepository(connection, DEMO_ORG_ID, DEMO_ENV_ID).create_metadata(
                agent_id="agent_delegated_execution",
                credential_type="bearer",
                raw_token="delegated-execution-token",
                issuer="delegated-execution-test",
                expires_at="2030-01-01T00:00:00+00:00",
                scopes=[
                    CredentialScopeRequest(
                        scope="claims.lookup:read",
                        resource_type="tool",
                        resource_id="claims.delegated.execution",
                    )
                ],
                status="active",
            )
            self.credential_id = credential["id"]
            registry = ToolRegistryRepository(connection, DEMO_ORG_ID, DEMO_ENV_ID)
            tool = registry.create_tool(
                ToolDefinitionCreateRequest(
                    name="claims.delegated.execution",
                    display_name="Claims Delegated Execution",
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
            permission = registry.grant_agent_tool_permission(
                "agent_delegated_execution",
                AgentToolPermissionGrantRequest(
                    tool_id=self.tool_id,
                    scope="claims.lookup:read",
                    granted_reason="phase 3 delegated execution fixture",
                ),
                granted_by=DEMO_ADMIN_USER_ID,
            )
            self.permission_id = permission["id"]
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
                "agent_delegated_execution",
                DEMO_ORG_ID,
                DEMO_ENV_ID,
                "agent_delegated_execution",
                "Delegated execution phase 3 fixture.",
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
            "Authorization": "Bearer delegated-execution-token",
            "X-Request-ID": "req-delegated-execution",
            "X-Correlation-ID": "corr-delegated-execution",
            "X-Delegated-User-ID": "user_123",
            "X-Delegated-Provider-Account-ID": "acct_456",
        }

    def _create_authorization(self, *, approval_state: str) -> dict:
        with self.database.transaction() as connection:
            row = ToolDelegationRepository(connection, DEMO_ORG_ID, DEMO_ENV_ID).create_authorization(
                DelegatedAuthorizationCreate(
                    agent_id="agent_delegated_execution",
                    tool_id=self.tool_id,
                    user_id="user_123",
                    provider_account_id="acct_456",
                    provider="claims-oauth",
                    scopes=["claims.read"],
                    approval_state=approval_state,
                    expires_at="2030-01-01T00:00:00+00:00",
                    access_token_ref="vault:oauth/claims/user_123/access",
                    refresh_token_ref="vault:oauth/claims/user_123/refresh",
                )
            )
        return dict(row)

    def test_allowed_delegated_call_persists_policy_and_runtime_binding(self) -> None:
        authorization = self._create_authorization(approval_state="approved")

        response = self.client.post(
            "/api/v1/tools/claims.delegated.execution/invoke",
            headers=self._headers(),
            json={"payload": {"claim_id": "claim_123"}},
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(self.executor.principals), 1)
        principal = self.executor.principals[0]
        self.assertEqual(principal.delegated_user_id, "user_123")
        self.assertEqual(principal.delegated_provider_account_id, "acct_456")
        self.assertEqual(principal.delegated_authorization_id, authorization["id"])
        self.assertEqual(principal.approval_state, "approved")

        decision = self._decision_for_request()
        self.assertEqual(decision["decision"], "allow")
        self.assertEqual(decision["credential_id"], self.credential_id)
        self.assertEqual(decision["delegated_user_id"], "user_123")
        self.assertEqual(decision["provider_account_id"], "acct_456")
        self.assertEqual(decision["delegated_authorization_id"], authorization["id"])
        self.assertEqual(decision["approval_state"], "approved")

        runtime_action = self._single_runtime_action("completed")
        self.assertEqual(runtime_action["credential_id"], self.credential_id)
        self.assertEqual(runtime_action["delegated_user_id"], "user_123")
        self.assertEqual(runtime_action["provider_account_id"], "acct_456")
        self.assertEqual(runtime_action["delegated_authorization_id"], authorization["id"])
        self.assertEqual(runtime_action["approval_state"], "approved")
        self.assertEqual(runtime_action["decision_id"], decision["id"])

        events = ToolRuntimeActionRepository(
            self.database.connect(),
            DEMO_ORG_ID,
            DEMO_ENV_ID,
        ).list_events(runtime_action["id"])
        allowed_event = next(event for event in events if event["event_type"] == "tool.runtime.allowed")
        allowed_summary = json.loads(allowed_event["event_summary_json"])
        self.assertEqual(allowed_summary["delegation_id"], authorization["id"])
        self.assertEqual(allowed_summary["approval_state"], "approved")

    def test_pending_approval_does_not_execute_and_persists_approval_evidence(self) -> None:
        authorization = self._create_authorization(approval_state="pending_approval")

        response = self.client.post(
            "/api/v1/tools/claims.delegated.execution/invoke",
            headers=self._headers(),
            json={"payload": {"claim_id": "claim_123"}},
        )

        self.assertEqual(response.status_code, 403, response.text)
        self.assertEqual(response.json()["reason_code"], "approval_required")
        self.assertEqual(response.json()["error"]["authorization"]["approval_state"], "pending_approval")
        self.assertEqual(len(self.executor.principals), 0)

        decision = self._decision_for_request()
        self.assertEqual(decision["decision"], "require_approval")
        self.assertEqual(decision["credential_id"], self.credential_id)
        self.assertEqual(decision["delegated_user_id"], "user_123")
        self.assertEqual(decision["provider_account_id"], "acct_456")
        self.assertEqual(decision["delegated_authorization_id"], authorization["id"])
        self.assertEqual(decision["approval_state"], "pending_approval")
        self.assertIsNotNone(decision["authorization_session_id"])

        runtime_action = self._single_runtime_action("approval_required")
        self.assertEqual(runtime_action["credential_id"], self.credential_id)
        self.assertEqual(runtime_action["delegated_authorization_id"], authorization["id"])
        self.assertEqual(runtime_action["approval_state"], "pending_approval")
        self.assertEqual(runtime_action["authorization_session_id"], decision["authorization_session_id"])

    def _decision_for_request(self) -> dict:
        row = self.database.connect().execute(
            """
            SELECT *
            FROM tool_policy_decisions
            WHERE request_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            ("req-delegated-execution",),
        ).fetchone()
        self.assertIsNotNone(row)
        return dict(row)

    def _single_runtime_action(self, status: str) -> dict:
        actions = ToolRuntimeActionRepository(
            self.database.connect(),
            DEMO_ORG_ID,
            DEMO_ENV_ID,
        ).list_actions(ToolRuntimeActionQuery(action_status=status))
        self.assertEqual(len(actions), 1)
        return dict(actions[0])


if __name__ == "__main__":
    unittest.main()
