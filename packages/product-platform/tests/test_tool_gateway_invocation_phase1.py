from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.agents.credentials import AgentCredentialRepository
from product_platform.agents.models import CredentialScopeRequest
from product_platform.api.settings import Settings
from product_platform.db.seed import DEMO_ADMIN_USER_ID, DEMO_ENV_ID, DEMO_ORG_ID, seed_demo_data
from product_platform.db.testing import create_migrated_test_database


class ToolGatewayInvocationPhase1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection)
            AgentCredentialRepository(connection, DEMO_ORG_ID, DEMO_ENV_ID).create_metadata(
                agent_id="agent_invoke_phase1",
                credential_type="bearer",
                raw_token="invoke-token-phase1",
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
                "agent_invoke_phase1",
                DEMO_ORG_ID,
                DEMO_ENV_ID,
                "agent_invoke_phase1",
                "Invocation route contract fixture.",
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

    def _headers(self, *, request_id: str = "req-invoke-phase1", correlation_id: str = "corr-invoke-phase1") -> dict[str, str]:
        return {
            "Authorization": "Bearer invoke-token-phase1",
            "X-Request-ID": request_id,
            "X-Correlation-ID": correlation_id,
        }

    def test_api_missing_token_returns_401(self) -> None:
        response = self.client.post(
            "/api/v1/tools/claims.lookup/invoke",
            json={"payload": {"claim_id": "claim_123"}},
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["message"], "Gateway authentication failed.")
        self.assertNotIn("missing_authorization", response.text)

    def test_api_valid_token_reaches_route_handler(self) -> None:
        response = self.client.post(
            "/api/v1/tools/claims.missing/invoke",
            headers=self._headers(),
            json={"payload": {"claim_id": "claim_123"}},
        )

        self.assertEqual(response.status_code, 403)
        payload = response.json()
        self.assertEqual(payload["error"]["code"], "tool_call_denied")
        self.assertIsNone(payload["decision"])

    def test_api_correlation_and_request_id_are_preserved(self) -> None:
        response = self.client.post(
            "/api/v1/tools/claims.missing/invoke",
            headers=self._headers(request_id="req-preserved", correlation_id="corr-preserved"),
            json={"payload": {"claim_id": "claim_123"}},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["request_id"], "req-preserved")
        self.assertEqual(response.headers["X-Request-ID"], "req-preserved")
        self.assertEqual(response.headers["X-Correlation-ID"], "corr-preserved")


if __name__ == "__main__":
    unittest.main()
