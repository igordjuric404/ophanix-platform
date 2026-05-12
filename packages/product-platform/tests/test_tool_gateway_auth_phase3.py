from __future__ import annotations

import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from unittest.mock import patch

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.agents.credentials import AgentCredentialRepository
from product_platform.agents.models import CredentialScopeRequest
from product_platform.api.settings import Settings
from product_platform.audit.store import AuditEventQuery, AuditEventRepository
from product_platform.db.seed import DEMO_ADMIN_USER_ID, DEMO_ENV_ID, DEMO_ORG_ID, seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.tool_gateway.models import (
    AgentToolPermissionGrantRequest,
    ToolDefinitionCreateRequest,
)
from product_platform.tool_gateway.operational_state import tool_gateway_rate_limit_result
from product_platform.tool_gateway.repository import ToolRegistryRepository


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

    def _production_settings(self, **overrides: Any) -> Settings:
        values: dict[str, Any] = {
            "app_name": "Ophanix Test Platform",
            "environment": "production",
            "build_sha": "test-sha",
            "build_time": "2026-05-01T00:00:00Z",
            "database_url": "postgresql://ophanix:secret@db.example.com:5432/ophanix",
            "session_secret": "test-secret",
            "secret_manager_ref": "env",
            "gateway_token_hash_pepper": "test-pepper",
            "tool_gateway_upstream_host_allowlist": ["*.example.com"],
            "cors_origins": ["https://app.example.com"],
        }
        values.update(overrides)
        return Settings(**values)

    def test_api_verified_request_can_access_gateway_discovery_without_probe_leak(self) -> None:
        response = self.client.get(
            "/api/v1/gateway/tools",
            headers=self._headers(self.raw_token),
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), [])

        probe_response = self.client.get(
            "/api/v1/gateway/principal-probe",
            headers=self._headers(self.raw_token),
        )
        self.assertEqual(probe_response.status_code, 401)
        self.assertEqual(probe_response.json()["code"], "UNAUTHENTICATED")

    def test_api_gateway_cursor_pagination_uses_snapshot_boundary(self) -> None:
        with self.database.transaction() as connection:
            connection.execute(
                "UPDATE credential_scopes SET resource_id = NULL WHERE credential_id = ?",
                (self.credential["id"],),
            )
            registry = ToolRegistryRepository(connection, DEMO_ORG_ID, DEMO_ENV_ID)
            for suffix in ["a", "b", "c"]:
                tool = registry.create_tool(
                    ToolDefinitionCreateRequest(
                        name=f"claims.lookup.{suffix}",
                        display_name=f"Claims Lookup {suffix.upper()}",
                        owner_team="claims-platform",
                        required_scope="claims.lookup:read",
                        input_schema_json={"type": "object"},
                    ),
                    created_by=DEMO_ADMIN_USER_ID,
                )
                tool = registry.activate_tool(tool["id"], actor_id=DEMO_ADMIN_USER_ID)
                registry.grant_agent_tool_permission(
                    "agent_gateway_probe",
                    AgentToolPermissionGrantRequest(
                        tool_id=tool["id"],
                        scope="claims.lookup:read",
                        granted_reason="cursor pagination fixture",
                    ),
                    granted_by=DEMO_ADMIN_USER_ID,
                )

        first = self.client.get(
            "/api/v1/gateway/tools",
            headers=self._headers(self.raw_token),
            params={"pagination": "cursor", "limit": "2"},
        )

        self.assertEqual(first.status_code, 200, first.text)
        first_payload = first.json()
        self.assertEqual(len(first_payload["tools"]), 2)
        self.assertIsNotNone(first_payload["next_cursor"])

        with self.database.transaction() as connection:
            registry = ToolRegistryRepository(connection, DEMO_ORG_ID, DEMO_ENV_ID)
            late_tool = registry.create_tool(
                ToolDefinitionCreateRequest(
                    name="claims.lookup.late",
                    display_name="Claims Lookup Late",
                    owner_team="claims-platform",
                    required_scope="claims.lookup:read",
                    input_schema_json={"type": "object"},
                ),
                created_by=DEMO_ADMIN_USER_ID,
            )
            late_tool = registry.activate_tool(late_tool["id"], actor_id=DEMO_ADMIN_USER_ID)
            registry.grant_agent_tool_permission(
                "agent_gateway_probe",
                AgentToolPermissionGrantRequest(
                    tool_id=late_tool["id"],
                    scope="claims.lookup:read",
                    granted_reason="late cursor pagination fixture",
                ),
                granted_by=DEMO_ADMIN_USER_ID,
            )

        second = self.client.get(
            "/api/v1/gateway/tools",
            headers=self._headers(self.raw_token),
            params={
                "pagination": "cursor",
                "limit": "2",
                "cursor": first_payload["next_cursor"],
            },
        )

        self.assertEqual(second.status_code, 200, second.text)
        returned_names = {
            tool["name"]
            for tool in [*first_payload["tools"], *second.json()["tools"]]
        }
        self.assertEqual(
            returned_names,
            {"claims.lookup.a", "claims.lookup.b", "claims.lookup.c"},
        )
        self.assertNotIn("claims.lookup.late", returned_names)

    def test_api_gateway_cursor_rejects_tampering(self) -> None:
        response = self.client.get(
            "/api/v1/gateway/tools",
            headers=self._headers(self.raw_token),
            params={"pagination": "cursor", "cursor": "not.a.valid.cursor"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid discovery cursor", response.text)

    def test_api_failed_verification_rejects_gateway_discovery(self) -> None:
        response = self.client.get(
            "/api/v1/gateway/tools",
            headers=self._headers("not-a-real-token"),
        )

        self.assertEqual(response.status_code, 401)
        self.assertIn("Gateway authentication failed", response.json()["message"])

    def test_api_gateway_prefix_routes_not_on_runtime_allowlist_require_product_auth(self) -> None:
        response = self.client.get(
            "/api/v1/gateway/not-real",
            headers={"X-Request-ID": "req-gateway-prefix"},
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], "UNAUTHENTICATED")

    def test_api_invalid_request_id_header_is_replaced_for_gateway_requests(self) -> None:
        headers = self._headers(self.raw_token)
        headers["X-Request-ID"] = "bad request id"

        response = self.client.get("/api/v1/gateway/tools", headers=headers)

        self.assertEqual(response.status_code, 200, response.text)
        self.assertNotEqual(response.headers["X-Request-ID"], "bad request id")

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

    def test_api_gateway_body_limit_blocks_streaming_body_without_content_length(self) -> None:
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
            content=iter([b'{"payload":', b'{"claim_id":"claim_123"}}']),
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
            "/api/v1/gateway/tools",
            headers=self._headers(self.raw_token),
        )
        second = client.get(
            "/api/v1/gateway/tools",
            headers=self._headers(self.raw_token),
        )

        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 429)
        self.assertEqual(second.json()["code"], "TOOL_GATEWAY_RATE_LIMITED")
        self.assertEqual(second.headers["Retry-After"], "60")

    def test_api_gateway_rate_limit_is_shared_across_app_instances(self) -> None:
        settings = Settings(
            app_name="Ophanix Test Platform",
            environment="test",
            build_sha="test-sha",
            build_time="2026-05-01T00:00:00Z",
            session_secret="test-secret",
            tool_gateway_rate_limit_window_seconds=60,
            tool_gateway_rate_limit_max_requests=1,
        )
        app_one = create_app(settings, database=self.database)
        app_two = create_app(settings, database=self.database)
        client_one = TestClient(app_one, raise_server_exceptions=False)
        client_two = TestClient(app_two, raise_server_exceptions=False)

        first = client_one.get(
            "/api/v1/gateway/tools",
            headers=self._headers(self.raw_token),
        )
        second = client_two.get(
            "/api/v1/gateway/tools",
            headers=self._headers(self.raw_token),
        )

        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 429)
        self.assertEqual(second.json()["code"], "TOOL_GATEWAY_RATE_LIMITED")

    def test_unit_gateway_rate_limit_increment_is_atomic_across_connections(self) -> None:
        def hit_limit() -> bool:
            with self.database.transaction() as connection:
                return tool_gateway_rate_limit_result(
                    connection,
                    key="agent:atomic-rate-test",
                    overflow_key="agent:atomic-rate-overflow",
                    max_requests=100,
                    window_seconds=60,
                    max_keys=100,
                    now_epoch=1000.0,
                ).limited

        with ThreadPoolExecutor(max_workers=8) as executor:
            limited_results = list(executor.map(lambda _: hit_limit(), range(20)))

        self.assertEqual(limited_results, [False] * 20)
        row = self.database.connect().execute(
            "SELECT request_count FROM tool_gateway_rate_limit_windows"
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["request_count"], 20)

    def test_api_gateway_rate_limit_uses_one_invalid_authorization_bucket_per_client(self) -> None:
        app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-05-01T00:00:00Z",
                session_secret="test-secret",
                tool_gateway_rate_limit_window_seconds=60,
                tool_gateway_rate_limit_max_requests=100,
                tool_gateway_rate_limit_max_keys=1,
            ),
            database=self.database,
        )
        client = TestClient(app, raise_server_exceptions=False)

        first = client.get(
            "/api/v1/gateway/tools",
            headers=self._headers("not-a-real-token-1"),
        )
        second = client.get(
            "/api/v1/gateway/tools",
            headers=self._headers("not-a-real-token-2"),
        )

        self.assertEqual(first.status_code, 401)
        self.assertEqual(second.status_code, 401)
        row = self.database.connect().execute(
            "SELECT COUNT(*) AS count FROM tool_gateway_rate_limit_windows"
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["count"], 2)

    def test_api_gateway_rate_limit_caps_new_authorization_overflow_per_client(self) -> None:
        app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-05-01T00:00:00Z",
                session_secret="test-secret",
                tool_gateway_rate_limit_window_seconds=60,
                tool_gateway_rate_limit_max_requests=1,
                tool_gateway_rate_limit_max_keys=1,
            ),
            database=self.database,
        )
        client = TestClient(app, raise_server_exceptions=False)

        first = client.get(
            "/api/v1/gateway/tools",
            headers=self._headers("not-a-real-token-1"),
        )
        second = client.get(
            "/api/v1/gateway/tools",
            headers=self._headers("not-a-real-token-2"),
        )
        third = client.get(
            "/api/v1/gateway/tools",
            headers=self._headers("not-a-real-token-3"),
        )

        self.assertEqual(first.status_code, 401)
        self.assertEqual(second.status_code, 401)
        self.assertEqual(third.status_code, 429)
        self.assertEqual(third.json()["code"], "TOOL_GATEWAY_RATE_LIMITED")
        row = self.database.connect().execute(
            "SELECT COUNT(*) AS count FROM tool_gateway_rate_limit_windows"
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["count"], 2)

    def test_api_rejects_wildcard_cors_with_credentials_in_production(self) -> None:
        with self.assertRaisesRegex(ValueError, "CORS wildcard origins"):
            create_app(
                self._production_settings(cors_origins=["*"]),
                database=self.database,
            )

    def test_api_disables_openapi_docs_by_default_in_production(self) -> None:
        app = create_app(
            self._production_settings(),
            database=self.database,
        )
        client = TestClient(app, raise_server_exceptions=False)

        self.assertEqual(client.get("/docs").status_code, 404)
        self.assertEqual(client.get("/openapi.json").status_code, 404)
        self.assertEqual(client.get("/api/openapi.json").status_code, 404)

    def test_api_system_config_hides_docs_url_when_docs_disabled(self) -> None:
        app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-05-01T00:00:00Z",
                session_secret="test-secret",
                enable_api_docs=False,
            ),
            database=self.database,
        )
        client = TestClient(app, raise_server_exceptions=False)
        login = client.post("/api/v1/auth/dev-login", json={"email": "admin@example.com"})
        token = login.json()["access_token"]
        config = client.get(
            "/api/v1/system/config",
            headers={"Authorization": f"Bearer {token}"},
        ).json()

        self.assertIsNone(config["docs_url"])

    def test_api_rejects_default_session_secret_in_production(self) -> None:
        with self.assertRaisesRegex(ValueError, "OPHANIX_SESSION_SECRET"):
            create_app(
                self._production_settings(session_secret="dev-secret-change-me"),
                database=self.database,
            )

    def test_api_rejects_non_postgres_database_in_production(self) -> None:
        with self.assertRaisesRegex(ValueError, "postgresql://"):
            create_app(
                self._production_settings(
                    database_url="file:///prod.db",
                )
            )

    def test_api_allows_postgres_database_in_production(self) -> None:
        app = create_app(
            self._production_settings()
        )

        self.assertTrue(app.state.settings.database_url.startswith("postgresql://"))

    def test_api_requires_supported_secret_provider_in_production(self) -> None:
        with self.assertRaisesRegex(ValueError, "OPHANIX_SECRET_MANAGER_REF"):
            create_app(
                self._production_settings(secret_manager_ref=None),
                database=self.database,
            )

    def test_api_requires_gateway_token_hash_pepper_in_production(self) -> None:
        with self.assertRaisesRegex(ValueError, "OPHANIX_GATEWAY_TOKEN_HASH_PEPPER"):
            create_app(
                self._production_settings(gateway_token_hash_pepper=None),
                database=self.database,
            )

    def test_api_rejects_legacy_gateway_token_hash_acceptance_in_production(self) -> None:
        with patch.dict(os.environ, {"OPHANIX_GATEWAY_TOKEN_HASH_ACCEPT_LEGACY": "true"}, clear=False):
            with self.assertRaisesRegex(ValueError, "Legacy gateway token hash acceptance"):
                create_app(
                    self._production_settings(),
                    database=self.database,
                )

    def test_api_rejects_unresolved_upstream_host_bypass_in_production(self) -> None:
        with patch.dict(os.environ, {"OPHANIX_ALLOW_UNRESOLVED_UPSTREAM_HOSTS": "true"}, clear=False):
            with self.assertRaisesRegex(ValueError, "Unresolved upstream hosts"):
                create_app(
                    self._production_settings(),
                    database=self.database,
                )

    def test_api_rejects_disabled_gateway_safety_limits_in_production(self) -> None:
        with self.assertRaisesRegex(ValueError, "production safety limits"):
            create_app(
                self._production_settings(tool_gateway_rate_limit_max_requests=0),
                database=self.database,
            )

    def test_integration_failed_verification_creates_safe_audit_event(self) -> None:
        secret = "missing-secret-token"

        response = self.client.get(
            "/api/v1/gateway/tools",
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
