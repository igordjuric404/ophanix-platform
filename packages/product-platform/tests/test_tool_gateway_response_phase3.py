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
    ToolResponsePolicyPatchRequest,
    ToolUpstreamTargetCreateRequest,
)
from product_platform.tool_gateway.repository import ToolRegistryRepository
from product_platform.tool_gateway.response import process_tool_execution_response


INPUT_SCHEMA = {"type": "object", "properties": {"claim_id": {"type": "string"}}, "required": ["claim_id"]}
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {"claim_status": {"type": "string"}, "token": {"type": "string"}},
    "required": ["claim_status"],
}


class FakeHTTPResponse:
    status_code = 200
    headers = {"content-type": "application/json"}
    text = "{}"

    def __init__(self, body) -> None:
        self._body = body

    def json(self):
        return self._body


class FakeHTTPClient:
    def __init__(self, body) -> None:
        self.body = body

    def request(self, *args, **kwargs):
        return FakeHTTPResponse(self.body)


class ToolGatewayResponsePhase3Tests(unittest.TestCase):
    def test_unit_token_like_values_are_redacted(self) -> None:
        result = process_tool_execution_response(
            {"output_schema_json": None},
            {
                "max_response_bytes": 32768,
                "redaction_rules_json": {"redact_keys": ["token"], "redact_patterns": []},
                "expose_to_agent": 1,
                "strict_output_validation": 1,
            },
            ToolExecutionResult(status="succeeded", body={"token": "secret", "safe": "ok"}),
        )

        self.assertEqual(result.body, {"token": "[redacted]", "safe": "ok"})
        self.assertTrue(result.redaction_applied)

    def test_unit_oversized_response_is_blocked(self) -> None:
        with self.assertRaises(ToolExecutionError) as context:
            process_tool_execution_response(
                {"output_schema_json": None},
                {
                    "max_response_bytes": 10,
                    "redaction_rules_json": {"redact_keys": [], "redact_patterns": []},
                    "expose_to_agent": 1,
                    "strict_output_validation": 1,
                },
                ToolExecutionResult(status="succeeded", body={"body": "x" * 100}),
            )

        self.assertEqual(context.exception.code, "response_too_large")

    def test_api_hidden_response_returns_metadata_without_body(self) -> None:
        client, app, tool_id = self._client_with_tool(FakeHTTPClient({"claim_status": "open"}))
        self._patch_policy(client, tool_id, {"expose_to_agent": False})

        response = client.post(
            "/api/v1/tools/claims.lookup/invoke",
            headers=self._gateway_headers(),
            json={"payload": {"claim_id": "claim_123"}},
        )

        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()["result"]
        self.assertIsNone(result["body"])
        self.assertFalse(result["exposed_to_agent"])

    def test_integration_response_metadata_marks_redaction_applied(self) -> None:
        client, app, tool_id = self._client_with_tool(
            FakeHTTPClient({"claim_status": "open", "token": "secret-token"})
        )
        self._patch_policy(client, tool_id, {"redaction_rules_json": {"redact_keys": ["token"]}})

        response = client.post(
            "/api/v1/tools/claims.lookup/invoke",
            headers=self._gateway_headers(),
            json={"payload": {"claim_id": "claim_123"}},
        )

        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()["result"]
        self.assertEqual(result["body"]["token"], "[redacted]")
        self.assertTrue(result["redaction_applied"])

    def _gateway_headers(self) -> dict[str, str]:
        return {
            "Authorization": "Bearer response-token",
            "X-Request-ID": "req-response",
            "X-Correlation-ID": "corr-response",
        }

    def _client_with_tool(self, http_client: FakeHTTPClient):
        database = create_migrated_test_database()
        with database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection)
            AgentCredentialRepository(connection, DEMO_ORG_ID, DEMO_ENV_ID).create_metadata(
                agent_id="agent_response",
                credential_type="bearer",
                raw_token="response-token",
                issuer="response-test",
                expires_at="2030-01-01T00:00:00+00:00",
                scopes=[CredentialScopeRequest(scope="claims.lookup:read", resource_type="tool", resource_id="claims.lookup")],
                status="active",
            )
            repository = ToolRegistryRepository(connection, DEMO_ORG_ID, DEMO_ENV_ID)
            tool = repository.create_tool(
                ToolDefinitionCreateRequest(
                    name="claims.lookup",
                    display_name="Claims Lookup",
                    owner_team="claims-platform",
                    required_scope="claims.lookup:read",
                    input_schema_json=INPUT_SCHEMA,
                    output_schema_json=OUTPUT_SCHEMA,
                ),
                created_by=DEMO_ADMIN_USER_ID,
            )
            tool = repository.activate_tool(tool["id"], actor_id=DEMO_ADMIN_USER_ID)
            repository.grant_agent_tool_permission(
                "agent_response",
                AgentToolPermissionGrantRequest(tool_id=tool["id"], scope="claims.lookup:read", granted_reason="response fixture"),
                granted_by=DEMO_ADMIN_USER_ID,
            )
            repository.create_upstream_target(
                tool["id"],
                ToolUpstreamTargetCreateRequest(
                    base_url="https://claims.internal.example",
                    path_template="/v1/claims/{claim_id}",
                    method="POST",
                    auth_mode="none",
                    timeout_ms=1200,
                    health_url="https://claims.internal.example/health",
                ),
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
            database=database,
        )
        app.state.tool_gateway_http_client = http_client
        return TestClient(app, raise_server_exceptions=False), app, tool["id"]

    def _patch_policy(self, client: TestClient, tool_id: str, body: dict) -> None:
        login = client.post("/api/v1/auth/dev-login", json={"email": "admin@example.com", "roles": ["Security Admin"]})
        headers = {"Authorization": f"Bearer {login.json()['access_token']}", "X-Environment-ID": DEMO_ENV_ID}
        response = client.patch(f"/api/v1/tools/{tool_id}/response-policy", headers=headers, json=body)
        self.assertEqual(response.status_code, 200, response.text)

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
            ("agent_response", DEMO_ORG_ID, DEMO_ENV_ID, "agent_response", "Response fixture", "langgraph", "service", None, DEMO_ADMIN_USER_ID, DEMO_ADMIN_USER_ID, "active", now, now),
        )


if __name__ == "__main__":
    unittest.main()
