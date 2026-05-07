from __future__ import annotations

import unittest

import httpx
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
    ToolUpstreamTargetCreateRequest,
)
from product_platform.tool_gateway.repository import ToolRegistryRepository


VALID_INPUT_SCHEMA = {
    "type": "object",
    "properties": {"claim_id": {"type": "string"}},
    "required": ["claim_id"],
    "additionalProperties": False,
}


class FakeHTTPResponse:
    def __init__(self, *, status_code: int, body, headers: dict[str, str] | None = None) -> None:
        self.status_code = status_code
        self._body = body
        self.headers = headers or {"content-type": "application/json"}
        self.text = str(body)

    def json(self):
        return self._body


class FakeHTTPClient:
    def __init__(self, response: FakeHTTPResponse | Exception) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    def request(self, method: str, url: str, *, json, headers, timeout: float):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "json": json,
                "headers": headers,
                "timeout": timeout,
            }
        )
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class ToolGatewayForwardingPhase3Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection)
            AgentCredentialRepository(connection, DEMO_ORG_ID, DEMO_ENV_ID).create_metadata(
                agent_id="agent_forward_phase3",
                credential_type="bearer",
                raw_token="forward-token-phase3",
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
            tool = registry.activate_tool(tool["id"], actor_id=DEMO_ADMIN_USER_ID)
            self.tool_id = tool["id"]
            registry.grant_agent_tool_permission(
                "agent_forward_phase3",
                AgentToolPermissionGrantRequest(
                    tool_id=self.tool_id,
                    scope="claims.lookup:read",
                    granted_reason="forwarding fixture",
                ),
                granted_by=DEMO_ADMIN_USER_ID,
            )
            registry.create_upstream_target(
                self.tool_id,
                ToolUpstreamTargetCreateRequest(
                    base_url="https://claims.internal.example",
                    path_template="/v1/claims/{claim_id}",
                    method="POST",
                    auth_mode="none",
                    timeout_ms=1200,
                    health_url="https://claims.internal.example/health",
                ),
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
                "agent_forward_phase3",
                DEMO_ORG_ID,
                DEMO_ENV_ID,
                "agent_forward_phase3",
                "Forwarding HTTP fixture.",
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

    def _headers(self, *, request_id: str = "req-forward-phase3", correlation_id: str = "corr-forward-phase3") -> dict[str, str]:
        return {
            "Authorization": "Bearer forward-token-phase3",
            "X-Request-ID": request_id,
            "X-Correlation-ID": correlation_id,
        }

    def test_integration_successful_upstream_call_returns_body(self) -> None:
        fake_client = FakeHTTPClient(
            FakeHTTPResponse(status_code=200, body={"claim_status": "open"})
        )
        self.app.state.tool_gateway_http_client = fake_client

        response = self.client.post(
            "/api/v1/tools/claims.lookup/invoke",
            headers=self._headers(),
            json={"payload": {"claim_id": "claim_123"}},
        )

        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()["result"]
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["body"], {"claim_status": "open"})
        self.assertEqual(result["upstream_status_code"], 200)
        self.assertEqual(fake_client.calls[0]["method"], "POST")
        self.assertEqual(
            fake_client.calls[0]["url"],
            "https://claims.internal.example/v1/claims/claim_123",
        )
        self.assertEqual(fake_client.calls[0]["json"], {"claim_id": "claim_123"})
        self.assertEqual(fake_client.calls[0]["timeout"], 1.2)

    def test_integration_request_id_and_correlation_id_are_forwarded(self) -> None:
        fake_client = FakeHTTPClient(FakeHTTPResponse(status_code=200, body={"ok": True}))
        self.app.state.tool_gateway_http_client = fake_client

        response = self.client.post(
            "/api/v1/tools/claims.lookup/invoke",
            headers=self._headers(request_id="req-forwarded", correlation_id="corr-forwarded"),
            json={"payload": {"claim_id": "claim_123"}},
        )

        self.assertEqual(response.status_code, 200)
        forwarded_headers = fake_client.calls[0]["headers"]
        self.assertEqual(forwarded_headers["X-Request-ID"], "req-forwarded")
        self.assertEqual(forwarded_headers["X-Correlation-ID"], "corr-forwarded")
        self.assertEqual(forwarded_headers["X-Ophanix-Agent-ID"], "agent_forward_phase3")

    def test_integration_timeout_returns_gateway_timeout_error(self) -> None:
        self.app.state.tool_gateway_http_client = FakeHTTPClient(
            httpx.TimeoutException("too slow")
        )

        response = self.client.post(
            "/api/v1/tools/claims.lookup/invoke",
            headers=self._headers(request_id="req-timeout"),
            json={"payload": {"claim_id": "claim_123"}},
        )

        self.assertEqual(response.status_code, 504, response.text)
        self.assertEqual(response.json()["error"]["code"], "upstream_timeout")

    def test_integration_upstream_500_returns_structured_execution_failure(self) -> None:
        self.app.state.tool_gateway_http_client = FakeHTTPClient(
            FakeHTTPResponse(status_code=500, body={"error": "boom"})
        )

        response = self.client.post(
            "/api/v1/tools/claims.lookup/invoke",
            headers=self._headers(request_id="req-upstream-500"),
            json={"payload": {"claim_id": "claim_123"}},
        )

        self.assertEqual(response.status_code, 502, response.text)
        payload = response.json()
        self.assertEqual(payload["error"]["code"], "upstream_error")
        self.assertEqual(payload["result"]["status"], "failed")
        self.assertEqual(payload["result"]["upstream_status_code"], 500)
        self.assertEqual(payload["result"]["body"], {"error": "boom"})


if __name__ == "__main__":
    unittest.main()
