from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.agents.credentials import AgentCredentialRepository
from product_platform.agents.models import CredentialScopeRequest
from product_platform.api.settings import Settings
from product_platform.db.seed import DEMO_ADMIN_USER_ID, DEMO_ENV_ID, DEMO_ORG_ID, seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.tool_gateway.invocation import ToolExecutionError, ToolExecutionResult
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


class ResultExecutor:
    def __init__(self, result: ToolExecutionResult) -> None:
        self.result = result
        self.calls: list[dict[str, object]] = []

    def execute(self, *, tool, payload, decision, principal):
        self.calls.append({"tool_name": tool["name"], "payload": payload})
        return self.result


class ErrorExecutor:
    def execute(self, *, tool, payload, decision, principal):
        raise ToolExecutionError(
            code="executor_unavailable",
            message="Executor is unavailable.",
            status_code=502,
        )


class ToolGatewayForwardingPhase1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection)
            AgentCredentialRepository(connection, DEMO_ORG_ID, DEMO_ENV_ID).create_metadata(
                agent_id="agent_forward_phase1",
                credential_type="bearer",
                raw_token="forward-token-phase1",
                issuer="forward-test",
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
            self.tool = registry.create_tool(
                ToolDefinitionCreateRequest(
                    name="claims.lookup",
                    display_name="Claims Lookup",
                    owner_team="claims-platform",
                    required_scope="claims.lookup:read",
                    input_schema_json=VALID_INPUT_SCHEMA,
                ),
                created_by=DEMO_ADMIN_USER_ID,
            )
            registry.activate_tool(self.tool["id"], actor_id=DEMO_ADMIN_USER_ID)
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
                "agent_forward_phase1",
                DEMO_ORG_ID,
                DEMO_ENV_ID,
                "agent_forward_phase1",
                "Forwarding executor fixture.",
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

    def _headers(self, *, request_id: str = "req-forward-phase1") -> dict[str, str]:
        return {
            "Authorization": "Bearer forward-token-phase1",
            "X-Request-ID": request_id,
            "X-Correlation-ID": f"corr-{request_id}",
        }

    def _grant_permission(self) -> None:
        with self.database.transaction() as connection:
            ToolRegistryRepository(connection, DEMO_ORG_ID, DEMO_ENV_ID).grant_agent_tool_permission(
                "agent_forward_phase1",
                AgentToolPermissionGrantRequest(
                    tool_id=self.tool["id"],
                    scope="claims.lookup:read",
                    granted_reason="forwarding fixture",
                ),
                granted_by=DEMO_ADMIN_USER_ID,
            )

    def test_unit_execution_result_serializes_metadata(self) -> None:
        result = ToolExecutionResult(
            status="succeeded",
            body={"ok": True},
            headers_summary={"content-type": "application/json"},
            latency_ms=12.5,
            upstream_status_code=200,
        )

        self.assertEqual(result.model_dump()["status"], "succeeded")
        self.assertEqual(result.model_dump()["body"], {"ok": True})
        self.assertEqual(result.model_dump()["headers_summary"]["content-type"], "application/json")

    def test_api_structured_executor_result_maps_to_invocation_response(self) -> None:
        self._grant_permission()
        executor = ResultExecutor(
            ToolExecutionResult(
                status="succeeded",
                body={"claim_status": "open"},
                headers_summary={"content-type": "application/json"},
                latency_ms=4.2,
                upstream_status_code=200,
            )
        )
        self.app.state.tool_gateway_executor = executor

        response = self.client.post(
            "/api/v1/tools/claims.lookup/invoke",
            headers=self._headers(request_id="req-structured-result"),
            json={"payload": {"claim_id": "claim_123"}},
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["result"]["status"], "succeeded")
        self.assertEqual(response.json()["result"]["body"], {"claim_status": "open"})
        self.assertEqual(len(executor.calls), 1)

    def test_api_denied_calls_still_skip_executor(self) -> None:
        executor = ResultExecutor(
            ToolExecutionResult(status="succeeded", body={"should_not": "run"})
        )
        self.app.state.tool_gateway_executor = executor

        response = self.client.post(
            "/api/v1/tools/claims.lookup/invoke",
            headers=self._headers(request_id="req-denied-skip-forwarding"),
            json={"payload": {"claim_id": "claim_123"}},
        )

        self.assertEqual(response.status_code, 403, response.text)
        self.assertEqual(executor.calls, [])

    def test_api_executor_errors_map_to_controlled_gateway_error(self) -> None:
        self._grant_permission()
        self.app.state.tool_gateway_executor = ErrorExecutor()

        response = self.client.post(
            "/api/v1/tools/claims.lookup/invoke",
            headers=self._headers(request_id="req-executor-error"),
            json={"payload": {"claim_id": "claim_123"}},
        )

        self.assertEqual(response.status_code, 502, response.text)
        payload = response.json()
        self.assertEqual(payload["error"]["code"], "executor_unavailable")
        self.assertEqual(payload["reason_code"], "allowed")
        self.assertEqual(payload["decision"]["decision"], "allow")


if __name__ == "__main__":
    unittest.main()
