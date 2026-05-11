from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.agents.credentials import AgentCredentialRepository
from product_platform.agents.models import CredentialScopeRequest
from product_platform.api.settings import Settings
from product_platform.audit.store import AuditEventQuery, AuditEventRepository
from product_platform.db.seed import DEMO_ADMIN_USER_ID, DEMO_ENV_ID, DEMO_ORG_ID, seed_demo_data
from product_platform.db.testing import create_migrated_test_database


class ToolGatewayAuthPhase3Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        self.raw_token = "gateway-probe-token"
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection)
            repository = AgentCredentialRepository(connection, DEMO_ORG_ID, DEMO_ENV_ID)
            self.credential = repository.create_metadata(
                agent_id="agent_gateway_probe",
                credential_type="bearer",
                raw_token=self.raw_token,
                issuer="gateway-test",
                expires_at="2030-01-01T00:00:00+00:00",
                scopes=[
                    CredentialScopeRequest(
                        scope="claims.lookup:read",
                        resource_type="tool",
                        resource_id="claims.lookup",
                    )
                ],
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
                "agent_gateway_probe",
                DEMO_ORG_ID,
                DEMO_ENV_ID,
                "Gateway Probe",
                "Agent used by gateway auth probe tests.",
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

    def _headers(self, token: str | None = None) -> dict[str, str]:
        headers = {
            "X-Request-ID": "req-gateway-probe",
            "X-Correlation-ID": "corr-gateway-probe",
            "X-Environment-ID": DEMO_ENV_ID,
        }
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def test_api_verified_request_exposes_gateway_principal_to_route_handler(self) -> None:
        response = self.client.get(
            "/api/v1/gateway/principal-probe",
            headers=self._headers(self.raw_token),
        )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["organization_id"], DEMO_ORG_ID)
        self.assertEqual(payload["environment_id"], DEMO_ENV_ID)
        self.assertEqual(payload["agent_id"], "agent_gateway_probe")
        self.assertEqual(payload["credential_id"], self.credential["id"])
        self.assertEqual(payload["scopes"], ["claims.lookup:read"])
        self.assertEqual(payload["request_id"], "req-gateway-probe")
        self.assertTrue(self.app.state.gateway_principal_probe_executed)

    def test_api_failed_verification_does_not_execute_route_handler(self) -> None:
        self.app.state.gateway_principal_probe_executed = False

        response = self.client.get(
            "/api/v1/gateway/principal-probe",
            headers=self._headers("not-a-real-token"),
        )

        self.assertEqual(response.status_code, 401)
        self.assertIn("Gateway authentication failed", response.json()["message"])
        self.assertFalse(self.app.state.gateway_principal_probe_executed)

    def test_api_gateway_prefix_routes_not_on_runtime_allowlist_require_product_auth(self) -> None:
        response = self.client.get(
            "/api/v1/gateway/not-real",
            headers={"X-Request-ID": "req-gateway-prefix"},
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], "UNAUTHENTICATED")

    def test_api_gateway_body_limit_blocks_large_invocations_before_auth(self) -> None:
        app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-05-01T00:00:00Z",
                session_secret="test-secret",
                tool_gateway_max_body_bytes=10,
            ),
            database=self.database,
        )
        client = TestClient(app, raise_server_exceptions=False)

        response = client.post(
            "/api/v1/tools/claims.lookup/invoke",
            headers=self._headers(self.raw_token),
            content=b'{"payload":{"claim_id":"claim_123"}}',
        )

        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json()["code"], "REQUEST_BODY_TOO_LARGE")

    def test_api_gateway_rate_limit_blocks_excess_runtime_requests(self) -> None:
        app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-05-01T00:00:00Z",
                session_secret="test-secret",
                tool_gateway_rate_limit_window_seconds=60,
                tool_gateway_rate_limit_max_requests=1,
            ),
            database=self.database,
        )
        client = TestClient(app, raise_server_exceptions=False)

        first = client.get(
            "/api/v1/gateway/principal-probe",
            headers=self._headers(self.raw_token),
        )
        second = client.get(
            "/api/v1/gateway/principal-probe",
            headers=self._headers(self.raw_token),
        )

        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 429)
        self.assertEqual(second.json()["code"], "TOOL_GATEWAY_RATE_LIMITED")

    def test_api_rejects_wildcard_cors_with_credentials_in_production(self) -> None:
        with self.assertRaisesRegex(ValueError, "CORS wildcard origins"):
            create_app(
                Settings(
                    app_name="Ophanix Test Platform",
                    environment="production",
                    build_sha="test-sha",
                    build_time="2026-05-01T00:00:00Z",
                    session_secret="test-secret",
                    cors_origins=["*"],
                ),
                database=self.database,
            )

    def test_integration_failed_verification_creates_safe_audit_event(self) -> None:
        secret = "missing-secret-token"

        response = self.client.get(
            "/api/v1/gateway/principal-probe",
            headers=self._headers(secret),
        )
        self.assertEqual(response.status_code, 401)

        events = AuditEventRepository(self.database.connect()).query(
            AuditEventQuery(
                organization_id=DEMO_ORG_ID,
                environment_id=DEMO_ENV_ID,
                event_type="gateway.token_verification.failed",
                resource_type="gateway_token_verification",
            )
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].decision, "deny")
        self.assertEqual(events[0].payload_json["reason_code"], "credential_not_found")
        self.assertEqual(events[0].payload_json["request_id"], "req-gateway-probe")
        self.assertNotIn(secret, str(events[0].payload_json))


if __name__ == "__main__":
    unittest.main()
