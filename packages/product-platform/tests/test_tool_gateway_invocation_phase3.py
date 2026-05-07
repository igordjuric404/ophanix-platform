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
    "additionalProperties": False,
}


class FakeInvocationExecutor:
    def __init__(self, result: dict) -> None:
        self.result = result
        self.calls: list[dict[str, object]] = []

    def execute(self, *, tool, payload, decision, principal):
        self.calls.append(
            {
                "tool_name": tool["name"],
                "payload": payload,
                "decision_id": decision.id,
                "agent_id": principal.agent_id,
            }
        )
        return self.result


class ToolGatewayInvocationPhase3Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection)
            AgentCredentialRepository(connection, DEMO_ORG_ID, DEMO_ENV_ID).create_metadata(
                agent_id="agent_invoke_phase3",
                credential_type="bearer",
                raw_token="invoke-token-phase3",
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
            self.registry = ToolRegistryRepository(connection, DEMO_ORG_ID, DEMO_ENV_ID)
            self.tool = self.registry.create_tool(
                ToolDefinitionCreateRequest(
                    name="claims.lookup",
                    display_name="Claims Lookup",
                    owner_team="claims-platform",
                    required_scope="claims.lookup:read",
                    input_schema_json=VALID_INPUT_SCHEMA,
                ),
                created_by=DEMO_ADMIN_USER_ID,
            )
            self.registry.activate_tool(self.tool["id"], actor_id=DEMO_ADMIN_USER_ID)
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
                "agent_invoke_phase3",
                DEMO_ORG_ID,
                DEMO_ENV_ID,
                "agent_invoke_phase3",
                "Invocation decision fixture.",
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

    def _headers(self, *, request_id: str = "req-invoke-phase3") -> dict[str, str]:
        return {
            "Authorization": "Bearer invoke-token-phase3",
            "X-Request-ID": request_id,
            "X-Correlation-ID": f"corr-{request_id}",
        }

    def _grant_permission(self) -> str:
        with self.database.transaction() as connection:
            permission = ToolRegistryRepository(
                connection,
                DEMO_ORG_ID,
                DEMO_ENV_ID,
            ).grant_agent_tool_permission(
                "agent_invoke_phase3",
                AgentToolPermissionGrantRequest(
                    tool_id=self.tool["id"],
                    scope="claims.lookup:read",
                    granted_reason="allowed invocation fixture",
                ),
                granted_by=DEMO_ADMIN_USER_ID,
            )
            return permission["id"]

    def test_api_allowed_decision_calls_executor_once(self) -> None:
        permission_id = self._grant_permission()
        executor = FakeInvocationExecutor(result={"claim_status": "open"})
        self.app.state.tool_gateway_executor = executor

        response = self.client.post(
            "/api/v1/tools/claims.lookup/invoke",
            headers=self._headers(request_id="req-allowed-exec"),
            json={"payload": {"claim_id": "claim_123"}},
        )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["result"], {"claim_status": "open"})
        self.assertEqual(payload["decision"]["decision"], "allow")
        self.assertEqual(payload["decision"]["permission_id"], permission_id)
        self.assertEqual(len(executor.calls), 1)
        self.assertEqual(executor.calls[0]["payload"], {"claim_id": "claim_123"})

    def test_api_denied_decision_does_not_call_executor(self) -> None:
        executor = FakeInvocationExecutor(result={"should_not": "run"})
        self.app.state.tool_gateway_executor = executor

        response = self.client.post(
            "/api/v1/tools/claims.lookup/invoke",
            headers=self._headers(request_id="req-denied-no-exec"),
            json={"payload": {"claim_id": "claim_123"}},
        )

        self.assertEqual(response.status_code, 403, response.text)
        self.assertEqual(executor.calls, [])

    def test_api_denial_response_includes_reason_code(self) -> None:
        response = self.client.post(
            "/api/v1/tools/claims.lookup/invoke",
            headers=self._headers(request_id="req-denial-reason"),
            json={"payload": {"claim_id": "claim_123"}},
        )

        self.assertEqual(response.status_code, 403)
        payload = response.json()
        self.assertEqual(payload["reason_code"], "permission_missing")
        self.assertEqual(payload["error"]["code"], "permission_missing")

    def test_integration_decision_record_created_for_allowed_and_denied_calls(self) -> None:
        self._grant_permission()
        self.app.state.tool_gateway_executor = FakeInvocationExecutor(result={"ok": True})
        allowed = self.client.post(
            "/api/v1/tools/claims.lookup/invoke",
            headers=self._headers(request_id="req-record-allowed"),
            json={"payload": {"claim_id": "claim_123"}},
        )
        self.assertEqual(allowed.status_code, 200, allowed.text)
        with self.database.transaction() as connection:
            ToolRegistryRepository(connection, DEMO_ORG_ID, DEMO_ENV_ID).revoke_agent_tool_permission(
                allowed.json()["decision"]["permission_id"],
                actor_id=DEMO_ADMIN_USER_ID,
                reason="switch to denied fixture",
            )
        denied = self.client.post(
            "/api/v1/tools/claims.lookup/invoke",
            headers=self._headers(request_id="req-record-denied"),
            json={"payload": {"claim_id": "claim_456"}},
        )
        self.assertEqual(denied.status_code, 403, denied.text)

        rows = self.database.connect().execute(
            """
            SELECT decision, reason_code, request_id
            FROM tool_policy_decisions
            WHERE organization_id = ? AND environment_id = ?
            ORDER BY created_at ASC, id ASC
            """,
            (DEMO_ORG_ID, DEMO_ENV_ID),
        ).fetchall()

        self.assertEqual(
            [(row["decision"], row["reason_code"], row["request_id"]) for row in rows],
            [
                ("allow", "allowed", "req-record-allowed"),
                ("deny", "permission_missing", "req-record-denied"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
