from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.agents.credentials import AgentCredentialRepository
from product_platform.agents.models import CredentialScopeRequest
from product_platform.api.settings import Settings
from product_platform.db.seed import DEMO_ADMIN_USER_ID, DEMO_ENV_ID, DEMO_ORG_ID, seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.tool_gateway.models import ToolDefinitionCreateRequest
from product_platform.tool_gateway.repository import ToolRegistryRepository
from product_platform.tool_gateway.runtime_audit import (
    ToolRuntimeActionCreate,
    ToolRuntimeActionEventCreate,
    ToolRuntimeActionRepository,
    purge_tool_invocation_idempotency_records,
)


class ToolGatewayRuntimeAuditPhase3Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            repository = ToolRuntimeActionRepository(connection, DEMO_ORG_ID, DEMO_ENV_ID)
            self.denied_action = repository.create_action(
                ToolRuntimeActionCreate(
                    request_id="req-runtime-api-denied",
                    correlation_id="corr-runtime-api-denied",
                    action_status="denied",
                    reason_code="permission_missing",
                    payload_summary={"claim_id": "claim_denied"},
                ),
                created_at="2026-05-01T10:00:00+00:00",
            )
            repository.append_event(
                self.denied_action["id"],
                ToolRuntimeActionEventCreate(
                    event_type="tool.runtime.denied",
                    event_summary={"reason_code": "permission_missing"},
                ),
                created_at="2026-05-01T10:00:01+00:00",
            )
            self.completed_action = repository.create_action(
                ToolRuntimeActionCreate(
                    request_id="req-runtime-api-completed",
                    correlation_id="corr-runtime-api-completed",
                    action_status="completed",
                    reason_code="allowed",
                    payload_summary={"claim_id": "claim_completed"},
                    response_summary={"claim_status": "open"},
                ),
                created_at="2026-05-01T11:00:00+00:00",
            )
            repository.append_event(
                self.completed_action["id"],
                ToolRuntimeActionEventCreate(
                    event_type="tool.runtime.completed",
                    event_summary={"upstream_status_code": 200},
                ),
                created_at="2026-05-01T11:00:01+00:00",
            )
            self.other_action = self._create_other_org_action(connection)
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

    def test_api_list_returns_newest_actions_first(self) -> None:
        response = self.client.get("/api/v1/tool-runtime/actions", headers=self._headers())

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(
            [item["request_id"] for item in payload],
            ["req-runtime-api-completed", "req-runtime-api-denied"],
        )

    def test_api_filters_by_denied_status(self) -> None:
        response = self.client.get(
            "/api/v1/tool-runtime/actions",
            headers=self._headers(),
            params={"action_status": "denied"},
        )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["request_id"], "req-runtime-api-denied")

    def test_api_detail_includes_event_timeline(self) -> None:
        response = self.client.get(
            f"/api/v1/tool-runtime/actions/{self.denied_action['id']}",
            headers=self._headers(),
        )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["request_id"], "req-runtime-api-denied")
        self.assertEqual(payload["events"][0]["event_type"], "tool.runtime.denied")

    def test_api_paginates_results(self) -> None:
        response = self.client.get(
            "/api/v1/tool-runtime/actions",
            headers=self._headers(),
            params={"limit": 1, "offset": 1},
        )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["request_id"], "req-runtime-api-denied")

    def test_api_cross_organization_detail_access_is_blocked(self) -> None:
        response = self.client.get(
            f"/api/v1/tool-runtime/actions/{self.other_action['id']}",
            headers=self._headers(),
        )

        self.assertEqual(response.status_code, 404, response.text)

    def test_idempotency_cleanup_marks_stale_in_progress_and_removes_old_terminal_records(self) -> None:
        with self.database.transaction() as connection:
            self._insert_cleanup_agent(connection)
            tool = ToolRegistryRepository(connection, DEMO_ORG_ID, DEMO_ENV_ID).create_tool(
                ToolDefinitionCreateRequest(
                    name="claims.cleanup",
                    display_name="Claims Cleanup",
                    owner_team="claims-platform",
                    required_scope="claims.cleanup:read",
                ),
                created_by=DEMO_ADMIN_USER_ID,
            )
            credential = AgentCredentialRepository(
                connection,
                DEMO_ORG_ID,
                DEMO_ENV_ID,
            ).create_metadata(
                agent_id="agent_cleanup",
                credential_type="bearer",
                raw_token="cleanup-token",
                issuer="cleanup-test",
                expires_at="2030-01-01T00:00:00+00:00",
                scopes=[
                    CredentialScopeRequest(
                        scope="claims.cleanup:read",
                        resource_type="tool",
                        resource_id="claims.cleanup",
                    )
                ],
            )
            connection.execute(
                """
                INSERT INTO tool_invocation_idempotency_records (
                    id, organization_id, environment_id, credential_id, tool_id,
                    idempotency_key, request_hash, request_id, correlation_id,
                    status, response_status_code, response_body_json, error_code,
                    created_at, updated_at
                )
                VALUES
                    (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?),
                    (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?),
                    (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "toolidem_cleanup_old",
                    DEMO_ORG_ID,
                    DEMO_ENV_ID,
                    credential["id"],
                    tool["id"],
                    "old-key",
                    "hash-old",
                    "req-old",
                    None,
                    "completed",
                    200,
                    "{}",
                    None,
                    "2026-05-01T00:00:00+00:00",
                    "2026-05-01T00:00:00+00:00",
                    "toolidem_cleanup_recent",
                    DEMO_ORG_ID,
                    DEMO_ENV_ID,
                    credential["id"],
                    tool["id"],
                    "recent-key",
                    "hash-recent",
                    "req-recent",
                    None,
                    "completed",
                    200,
                    "{}",
                    None,
                    "2026-05-11T00:00:00+00:00",
                    "2026-05-11T00:00:00+00:00",
                    "toolidem_cleanup_in_progress",
                    DEMO_ORG_ID,
                    DEMO_ENV_ID,
                    credential["id"],
                    tool["id"],
                    "in-progress-key",
                    "hash-progress",
                    "req-progress",
                    None,
                    "in_progress",
                    None,
                    None,
                    None,
                    "2026-05-01T00:00:00+00:00",
                    "2026-05-01T00:00:00+00:00",
                ),
            )

        with self.database.transaction() as connection:
            result = purge_tool_invocation_idempotency_records(
                connection,
                retention_seconds=24 * 60 * 60,
                in_progress_ttl_seconds=60 * 60,
                now="2026-05-12T00:00:00+00:00",
            )

        rows = self.database.connect().execute(
            """
            SELECT id, status, error_code
            FROM tool_invocation_idempotency_records
            WHERE id LIKE ?
            ORDER BY id
            """,
            ("toolidem_cleanup_%",),
        ).fetchall()
        self.assertEqual(result.deleted_records, 1)
        self.assertEqual(result.marked_failed_unknown, 1)
        self.assertEqual(
            [(row["id"], row["status"], row["error_code"]) for row in rows],
            [
                (
                    "toolidem_cleanup_in_progress",
                    "failed_unknown",
                    "idempotency_outcome_unknown",
                ),
                ("toolidem_cleanup_recent", "completed", None),
            ],
        )

    def _headers(self) -> dict[str, str]:
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "admin@example.com", "roles": ["Security Admin"]},
        )
        return {
            "Authorization": f"Bearer {login.json()['access_token']}",
            "X-Environment-ID": DEMO_ENV_ID,
        }

    def _create_other_org_action(self, connection):
        now = "2026-05-01T00:00:00+00:00"
        connection.execute(
            """
            INSERT INTO organizations (id, name, slug, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("org_runtime_other", "Other Runtime Org", "runtime-other", now, now),
        )
        connection.execute(
            """
            INSERT INTO environments (
                id, organization_id, name, slug, type, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "env_runtime_other",
                "org_runtime_other",
                "Other Runtime Env",
                "runtime-other",
                "test",
                now,
                now,
            ),
        )
        return ToolRuntimeActionRepository(
            connection,
            "org_runtime_other",
            "env_runtime_other",
        ).create_action(
            ToolRuntimeActionCreate(
                request_id="req-runtime-api-other",
                correlation_id="corr-runtime-api-other",
                action_status="denied",
                reason_code="permission_missing",
                payload_summary={"claim_id": "claim_other"},
            ),
            created_at="2026-05-01T12:00:00+00:00",
        )

    def _insert_cleanup_agent(self, connection) -> None:
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
                "agent_cleanup",
                DEMO_ORG_ID,
                DEMO_ENV_ID,
                "agent_cleanup",
                "Idempotency cleanup fixture.",
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
