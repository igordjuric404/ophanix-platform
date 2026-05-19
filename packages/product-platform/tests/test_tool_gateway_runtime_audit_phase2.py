from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.agents.credentials import AgentCredentialRepository
from product_platform.agents.models import CredentialScopeRequest
from product_platform.api.settings import Settings
from product_platform.db.seed import DEMO_ADMIN_USER_ID, DEMO_ENV_ID, DEMO_ORG_ID, seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.tool_gateway.invocation import ToolExecutionResult
from product_platform.tool_gateway.models import (
    AgentToolPermissionGrantRequest,
    ToolDefinitionCreateRequest,
)
from product_platform.tool_gateway.repository import ToolRegistryRepository


INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "claim_id": {"type": "string"},
        "api_key": {"type": "string"},
    },
    "required": ["claim_id"],
}
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "claim_status": {"type": "string"},
        "token": {"type": "string"},
        "note": {"type": "string"},
    },
    "required": ["claim_status"],
}
TRACE_ID = "44444444444444444444444444444444"
PARENT_SPAN_ID = "5555555555555555"
TRACEPARENT = f"00-{TRACE_ID}-{PARENT_SPAN_ID}-01"


class FakeRuntimeExecutor:
    def __init__(self, result: ToolExecutionResult) -> None:
        self.result = result
        self.calls: list[dict[str, object]] = []

    def execute(self, *, tool, payload, decision, principal):
        self.calls.append({"tool_name": tool["name"], "decision_id": decision.id})
        return self.result


class ToolGatewayRuntimeAuditPhase2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection)
            credentials = AgentCredentialRepository(connection, DEMO_ORG_ID, DEMO_ENV_ID)
            self.active_credential = credentials.create_metadata(
                agent_id="agent_runtime_phase2",
                credential_type="bearer",
                raw_token="runtime-token-phase2-secret",
                issuer="runtime-test",
                expires_at="2030-01-01T00:00:00+00:00",
                scopes=[
                    CredentialScopeRequest(
                        scope="claims.lookup:read",
                        resource_type="tool",
                        resource_id="claims.runtime",
                    )
                ],
                status="active",
            )
            self.revoked_credential = credentials.create_metadata(
                agent_id="agent_runtime_phase2",
                credential_type="bearer",
                raw_token="runtime-token-phase2-revoked-secret",
                issuer="runtime-test",
                expires_at="2030-01-01T00:00:00+00:00",
                scopes=[
                    CredentialScopeRequest(
                        scope="claims.lookup:read",
                        resource_type="tool",
                        resource_id="claims.runtime",
                    )
                ],
                status="revoked",
            )
            self.registry = ToolRegistryRepository(connection, DEMO_ORG_ID, DEMO_ENV_ID)
            self.tool = self.registry.create_tool(
                ToolDefinitionCreateRequest(
                    name="claims.runtime",
                    display_name="Claims Runtime",
                    owner_team="claims-platform",
                    required_scope="claims.lookup:read",
                    input_schema_json=INPUT_SCHEMA,
                    output_schema_json=OUTPUT_SCHEMA,
                ),
                created_by=DEMO_ADMIN_USER_ID,
            )
            self.tool = self.registry.activate_tool(self.tool["id"], actor_id=DEMO_ADMIN_USER_ID)
        self.app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-05-01T00:00:00Z",
                dev_login_allowed_emails=["admin@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def test_integration_denied_invocation_writes_one_denied_action(self) -> None:
        response = self.client.post(
            "/api/v1/tools/claims.runtime/invoke",
            headers=self._gateway_headers(request_id="req-runtime-denied"),
            json={"payload": {"claim_id": "claim_123", "api_key": "payload-secret"}},
        )

        self.assertEqual(response.status_code, 403, response.text)
        action = self._runtime_actions()[0]
        self.assertEqual(action["action_status"], "denied")
        self.assertEqual(action["reason_code"], "permission_missing")
        self.assertEqual(action["request_id"], "req-runtime-denied")
        self.assertIsNotNone(action["decision_id"])
        self.assertNotIn("payload-secret", str(dict(action)))
        self.assertEqual(self._event_types(action["id"]), ["tool.runtime.denied"])

    def test_integration_invocation_records_w3c_trace_context(self) -> None:
        headers = self._gateway_headers(request_id="req-runtime-trace")
        headers.update(
            {
                "traceparent": TRACEPARENT,
                "tracestate": "vendor=tool-gateway",
                "baggage": "tenant=demo,tool=claims",
            }
        )

        response = self.client.post(
            "/api/v1/tools/claims.runtime/invoke",
            headers=headers,
            json={"payload": {"claim_id": "claim_123"}},
        )

        self.assertEqual(response.status_code, 403, response.text)
        self.assertEqual(response.headers["traceparent"].split("-")[1], TRACE_ID)
        action = self._runtime_actions()[0]
        self.assertEqual(action["trace_id"], TRACE_ID)
        self.assertRegex(action["span_id"], r"^[0-9a-f]{16}$")
        self.assertEqual(action["parent_span_id"], PARENT_SPAN_ID)
        self.assertEqual(action["traceparent"].split("-")[1], TRACE_ID)
        self.assertEqual(action["tracestate"], "vendor=tool-gateway")
        self.assertEqual(action["baggage"], "tenant=demo,tool=claims")

    def test_integration_allowed_invocation_writes_forwarded_and_completed_states(self) -> None:
        permission_id = self._grant_permission()
        self.app.state.tool_gateway_executor = FakeRuntimeExecutor(
            ToolExecutionResult(
                status="succeeded",
                body={"claim_status": "open", "token": "secret-token"},
                upstream_status_code=200,
                latency_ms=12.5,
            )
        )

        response = self.client.post(
            "/api/v1/tools/claims.runtime/invoke",
            headers=self._gateway_headers(request_id="req-runtime-allowed"),
            json={"payload": {"claim_id": "claim_123"}},
        )

        self.assertEqual(response.status_code, 200, response.text)
        action = self._runtime_actions()[0]
        self.assertEqual(action["action_status"], "completed")
        self.assertEqual(action["permission_id"], permission_id)
        self.assertEqual(action["upstream_status_code"], 200)
        self.assertEqual(action["error_code"], None)
        self.assertEqual(
            self._event_types(action["id"]),
            ["tool.runtime.allowed", "tool.runtime.forwarded", "tool.runtime.completed"],
        )
        self.assertNotIn("secret-token", str(dict(action)))

    def test_integration_upstream_failure_records_error_code(self) -> None:
        self._grant_permission()
        self.app.state.tool_gateway_executor = FakeRuntimeExecutor(
            ToolExecutionResult(
                status="failed",
                body={"error": "upstream failed", "token": "secret-token"},
                upstream_status_code=500,
                latency_ms=40.0,
                error={"code": "upstream_error", "message": "Upstream returned status 500."},
            )
        )

        response = self.client.post(
            "/api/v1/tools/claims.runtime/invoke",
            headers=self._gateway_headers(request_id="req-runtime-upstream-failed"),
            json={"payload": {"claim_id": "claim_123"}},
        )

        self.assertEqual(response.status_code, 502, response.text)
        action = self._runtime_actions()[0]
        self.assertEqual(action["action_status"], "upstream_failed")
        self.assertEqual(action["error_code"], "upstream_error")
        self.assertEqual(action["upstream_status_code"], 500)
        self.assertEqual(self._event_types(action["id"])[-1], "tool.runtime.upstream_failed")
        self.assertNotIn("secret-token", str(dict(action)))

    def test_integration_response_blocked_records_error_code(self) -> None:
        self._grant_permission()
        self._patch_policy({"max_response_bytes": 20})
        self.app.state.tool_gateway_executor = FakeRuntimeExecutor(
            ToolExecutionResult(
                status="succeeded",
                body={"claim_status": "open", "note": "x" * 100},
                upstream_status_code=200,
                latency_ms=25.0,
            )
        )

        response = self.client.post(
            "/api/v1/tools/claims.runtime/invoke",
            headers=self._gateway_headers(request_id="req-runtime-response-blocked"),
            json={"payload": {"claim_id": "claim_123"}},
        )

        self.assertEqual(response.status_code, 502, response.text)
        action = self._runtime_actions()[0]
        self.assertEqual(action["action_status"], "response_blocked")
        self.assertEqual(action["error_code"], "response_too_large")
        self.assertEqual(self._event_types(action["id"])[-1], "tool.runtime.response_blocked")

    def test_security_identified_auth_failure_writes_action_without_raw_bearer_token(self) -> None:
        response = self.client.post(
            "/api/v1/tools/claims.runtime/invoke",
            headers=self._gateway_headers(
                token="runtime-token-phase2-revoked-secret",
                request_id="req-runtime-auth-failed",
            ),
            json={"payload": {"claim_id": "claim_123"}},
        )

        self.assertEqual(response.status_code, 401, response.text)
        action = self._runtime_actions()[0]
        self.assertEqual(action["action_status"], "authentication_failed")
        self.assertEqual(action["agent_id"], "agent_runtime_phase2")
        self.assertEqual(action["credential_id"], self.revoked_credential["id"])
        self.assertEqual(action["error_code"], "credential_inactive")
        self.assertNotIn("runtime-token-phase2-revoked-secret", self._runtime_audit_text())

    def _gateway_headers(
        self,
        *,
        token: str = "runtime-token-phase2-secret",
        request_id: str,
    ) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token}",
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
                "agent_runtime_phase2",
                AgentToolPermissionGrantRequest(
                    tool_id=self.tool["id"],
                    scope="claims.lookup:read",
                    granted_reason="runtime audit route fixture",
                ),
                granted_by=DEMO_ADMIN_USER_ID,
            )
            return permission["id"]

    def _patch_policy(self, body: dict) -> None:
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "admin@example.com", "roles": ["Security Admin"]},
        )
        headers = {
            "Authorization": f"Bearer {login.json()['access_token']}",
            "X-Environment-ID": DEMO_ENV_ID,
        }
        response = self.client.patch(
            f"/api/v1/tools/{self.tool['id']}/response-policy",
            headers=headers,
            json=body,
        )
        self.assertEqual(response.status_code, 200, response.text)

    def _runtime_actions(self):
        return self.database.connect().execute(
            """
            SELECT *
            FROM tool_runtime_actions
            WHERE organization_id = ? AND environment_id = ?
            ORDER BY created_at ASC, id ASC
            """,
            (DEMO_ORG_ID, DEMO_ENV_ID),
        ).fetchall()

    def _event_types(self, action_id: str) -> list[str]:
        rows = self.database.connect().execute(
            """
            SELECT event_type
            FROM tool_runtime_action_events
            WHERE runtime_action_id = ?
            ORDER BY created_at ASC, id ASC
            """,
            (action_id,),
        ).fetchall()
        return [row["event_type"] for row in rows]

    def _runtime_audit_text(self) -> str:
        rows = self.database.connect().execute(
            """
            SELECT
                request_id, correlation_id, payload_summary_json,
                response_summary_json, error_code
            FROM tool_runtime_actions
            ORDER BY created_at ASC, id ASC
            """
        ).fetchall()
        event_rows = self.database.connect().execute(
            """
            SELECT event_type, event_summary_json
            FROM tool_runtime_action_events
            ORDER BY created_at ASC, id ASC
            """
        ).fetchall()
        return f"{[dict(row) for row in rows]} {[dict(row) for row in event_rows]}"

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
                "agent_runtime_phase2",
                DEMO_ORG_ID,
                DEMO_ENV_ID,
                "agent_runtime_phase2",
                "Runtime audit route fixture.",
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


if __name__ == "__main__":
    unittest.main()
