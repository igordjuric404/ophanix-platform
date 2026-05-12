from __future__ import annotations

import unittest
from unittest.mock import patch

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
from product_platform.tool_gateway.invocation import ToolExecutionError, ToolExecutionResult, invocation_request_hash
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


class SecretLeakingErrorExecutor:
    def execute(self, *, tool, payload, decision, principal):
        raise ToolExecutionError(
            code="custom_executor_failed",
            message="upstream failed Authorization: Bearer secret-token-123 token=raw-secret",
            status_code=502,
        )


class SecretLeakingResultExecutor:
    def execute(self, *, tool, payload, decision, principal):
        return ToolExecutionResult(
            status="failed",
            error={
                "code": "custom_result_failed",
                "message": "password=hunter2 and Bearer secret-token-456",
            },
        )


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
        self.assertEqual(payload["decision"]["reason_code"], "allowed")
        self.assertNotIn("permission_id", payload["decision"])
        self.assertNotIn("id", payload["decision"])
        self.assertEqual(len(executor.calls), 1)
        self.assertEqual(executor.calls[0]["payload"], {"claim_id": "claim_123"})
        row = self.database.connect().execute(
            "SELECT permission_id FROM tool_policy_decisions WHERE request_id = ?",
            ("req-allowed-exec",),
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["permission_id"], permission_id)

    def test_api_idempotency_key_replays_completed_response_without_reexecuting(self) -> None:
        self._grant_permission()
        executor = FakeInvocationExecutor(result={"claim_status": "open"})
        self.app.state.tool_gateway_executor = executor

        first = self.client.post(
            "/api/v1/tools/claims.lookup/invoke",
            headers={**self._headers(request_id="req-idem-first"), "Idempotency-Key": "idem-claim-1"},
            json={"payload": {"claim_id": "claim_123"}},
        )
        second = self.client.post(
            "/api/v1/tools/claims.lookup/invoke",
            headers={**self._headers(request_id="req-idem-second"), "Idempotency-Key": "idem-claim-1"},
            json={"payload": {"claim_id": "claim_123"}},
        )

        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(second.headers["Idempotency-Replayed"], "true")
        self.assertEqual(second.json()["request_id"], "req-idem-first")
        self.assertEqual(second.json()["result"], {"claim_status": "open"})
        self.assertEqual(len(executor.calls), 1)

    def test_api_idempotency_key_conflict_blocks_different_payload(self) -> None:
        self._grant_permission()
        executor = FakeInvocationExecutor(result={"claim_status": "open"})
        self.app.state.tool_gateway_executor = executor

        first = self.client.post(
            "/api/v1/tools/claims.lookup/invoke",
            headers={**self._headers(request_id="req-idem-conflict-first"), "Idempotency-Key": "idem-conflict-1"},
            json={"payload": {"claim_id": "claim_123"}},
        )
        second = self.client.post(
            "/api/v1/tools/claims.lookup/invoke",
            headers={**self._headers(request_id="req-idem-conflict-second"), "Idempotency-Key": "idem-conflict-1"},
            json={"payload": {"claim_id": "claim_456"}},
        )

        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 409, second.text)
        self.assertEqual(second.json()["error"]["code"], "idempotency_conflict")
        self.assertEqual(len(executor.calls), 1)

    def test_api_reports_idempotency_persistence_failure_after_success(self) -> None:
        self._grant_permission()
        executor = FakeInvocationExecutor(result={"claim_status": "open"})
        self.app.state.tool_gateway_executor = executor

        with patch(
            "product_platform.api.app.ToolInvocationIdempotencyRepository.complete_invocation",
            side_effect=RuntimeError("database unavailable"),
        ):
            response = self.client.post(
                "/api/v1/tools/claims.lookup/invoke",
                headers={
                    **self._headers(request_id="req-idem-persist-fail"),
                    "Idempotency-Key": "idem-persist-fail-1",
                },
                json={"payload": {"claim_id": "claim_123"}},
            )

        self.assertEqual(response.status_code, 503, response.text)
        self.assertEqual(response.headers["Idempotency-Persistence"], "failed")
        self.assertEqual(
            response.json()["error"]["code"],
            "idempotency_persistence_failed",
        )
        self.assertIn("outcome is unknown", response.json()["error"]["message"])
        self.assertEqual(len(executor.calls), 1)

        row = self.database.connect().execute(
            """
            SELECT status, response_status_code, response_body_json
            FROM tool_invocation_idempotency_records
            WHERE idempotency_key = ?
            """,
            ("idem-persist-fail-1",),
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["status"], "in_progress")
        self.assertIsNone(row["response_status_code"])
        self.assertIsNone(row["response_body_json"])

        retry = self.client.post(
            "/api/v1/tools/claims.lookup/invoke",
            headers={
                **self._headers(request_id="req-idem-persist-fail-retry"),
                "Idempotency-Key": "idem-persist-fail-1",
            },
            json={"payload": {"claim_id": "claim_123"}},
        )

        self.assertEqual(retry.status_code, 409, retry.text)
        self.assertEqual(retry.json()["error"]["code"], "idempotency_in_progress")
        self.assertEqual(len(executor.calls), 1)

    def test_api_reports_idempotency_persistence_failure_after_upstream_error(self) -> None:
        self._grant_permission()
        self.app.state.tool_gateway_executor = SecretLeakingErrorExecutor()

        with patch(
            "product_platform.api.app.ToolInvocationIdempotencyRepository.complete_invocation",
            side_effect=RuntimeError("database unavailable"),
        ):
            response = self.client.post(
                "/api/v1/tools/claims.lookup/invoke",
                headers={
                    **self._headers(request_id="req-idem-persist-fail-error"),
                    "Idempotency-Key": "idem-persist-fail-error-1",
                },
                json={"payload": {"claim_id": "claim_123"}},
            )

        self.assertEqual(response.status_code, 503, response.text)
        self.assertEqual(response.headers["Idempotency-Persistence"], "failed")
        self.assertEqual(
            response.json()["error"]["code"],
            "idempotency_persistence_failed",
        )
        self.assertNotIn("secret-token-123", response.text)
        self.assertNotIn("raw-secret", response.text)

        row = self.database.connect().execute(
            """
            SELECT status, response_status_code, response_body_json
            FROM tool_invocation_idempotency_records
            WHERE idempotency_key = ?
            """,
            ("idem-persist-fail-error-1",),
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["status"], "in_progress")
        self.assertIsNone(row["response_status_code"])
        self.assertIsNone(row["response_body_json"])

    def test_api_stale_idempotency_record_returns_terminal_unknown_without_executing(self) -> None:
        self._grant_permission()
        executor = FakeInvocationExecutor(result={"claim_status": "open"})
        self.app.state.tool_gateway_executor = executor
        credential = self.database.connect().execute(
            "SELECT id FROM agent_credentials WHERE agent_id = ?",
            ("agent_invoke_phase3",),
        ).fetchone()
        self.assertIsNotNone(credential)
        with self.database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO tool_invocation_idempotency_records (
                    id, organization_id, environment_id, credential_id, tool_id,
                    idempotency_key, request_hash, request_id, correlation_id,
                    status, response_status_code, response_body_json, error_code,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "toolidem_stale_fixture",
                    DEMO_ORG_ID,
                    DEMO_ENV_ID,
                    credential["id"],
                    self.tool["id"],
                    "idem-stale-1",
                    invocation_request_hash(
                        tool_name="claims.lookup",
                        payload={"claim_id": "claim_123"},
                    ),
                    "req-old-stale",
                    "corr-old-stale",
                    "in_progress",
                    None,
                    None,
                    None,
                    "2026-05-01T00:00:00+00:00",
                    "2026-05-01T00:00:00+00:00",
                ),
            )

        response = self.client.post(
            "/api/v1/tools/claims.lookup/invoke",
            headers={**self._headers(request_id="req-idem-stale"), "Idempotency-Key": "idem-stale-1"},
            json={"payload": {"claim_id": "claim_123"}},
        )

        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(response.json()["error"]["code"], "idempotency_stale")
        self.assertIn("unknown", response.json()["error"]["message"])
        self.assertEqual(executor.calls, [])
        row = self.database.connect().execute(
            "SELECT status, error_code FROM tool_invocation_idempotency_records WHERE id = ?",
            ("toolidem_stale_fixture",),
        ).fetchone()
        self.assertEqual(row["status"], "failed_unknown")
        self.assertEqual(row["error_code"], "idempotency_outcome_unknown")

    def test_api_rejects_mismatched_header_and_body_idempotency_keys(self) -> None:
        self._grant_permission()
        self.app.state.tool_gateway_executor = FakeInvocationExecutor(result={"ok": True})

        response = self.client.post(
            "/api/v1/tools/claims.lookup/invoke",
            headers={**self._headers(request_id="req-idem-mismatch"), "Idempotency-Key": "idem-header"},
            json={
                "payload": {"claim_id": "claim_123"},
                "idempotency_key": "idem-body",
            },
        )

        self.assertEqual(response.status_code, 400, response.text)

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
        self.assertEqual(payload["reason_code"], "tool_call_denied")
        self.assertEqual(payload["error"]["code"], "tool_call_denied")
        self.assertEqual(payload["error"]["message"], "Tool call denied by gateway policy.")
        self.assertIsNone(payload["decision"])

    def test_api_sanitizes_custom_executor_error_messages_before_returning_to_agent(self) -> None:
        self._grant_permission()
        self.app.state.tool_gateway_executor = SecretLeakingErrorExecutor()

        response = self.client.post(
            "/api/v1/tools/claims.lookup/invoke",
            headers=self._headers(request_id="req-secret-exc"),
            json={"payload": {"claim_id": "claim_123"}},
        )

        self.assertEqual(response.status_code, 502, response.text)
        text = response.text
        self.assertIn("[redacted]", text)
        self.assertNotIn("secret-token-123", text)
        self.assertNotIn("raw-secret", text)

    def test_api_sanitizes_custom_failed_result_error_messages_before_returning_to_agent(self) -> None:
        self._grant_permission()
        self.app.state.tool_gateway_executor = SecretLeakingResultExecutor()

        response = self.client.post(
            "/api/v1/tools/claims.lookup/invoke",
            headers=self._headers(request_id="req-secret-result"),
            json={"payload": {"claim_id": "claim_123"}},
        )

        self.assertEqual(response.status_code, 502, response.text)
        text = response.text
        self.assertIn("[redacted]", text)
        self.assertNotIn("hunter2", text)
        self.assertNotIn("secret-token-456", text)

    def test_integration_decision_record_created_for_allowed_and_denied_calls(self) -> None:
        permission_id = self._grant_permission()
        self.app.state.tool_gateway_executor = FakeInvocationExecutor(result={"ok": True})
        allowed = self.client.post(
            "/api/v1/tools/claims.lookup/invoke",
            headers=self._headers(request_id="req-record-allowed"),
            json={"payload": {"claim_id": "claim_123"}},
        )
        self.assertEqual(allowed.status_code, 200, allowed.text)
        with self.database.transaction() as connection:
            ToolRegistryRepository(connection, DEMO_ORG_ID, DEMO_ENV_ID).revoke_agent_tool_permission(
                permission_id,
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
