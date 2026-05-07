from __future__ import annotations

import unittest

from product_platform.db.seed import DEMO_ADMIN_USER_ID, DEMO_ENV_ID, DEMO_ORG_ID, seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.tool_gateway.decision import (
    ToolPolicyDecisionCreate,
    ToolPolicyDecisionRepository,
)
from product_platform.tool_gateway.models import (
    AgentToolPermissionGrantRequest,
    ToolDefinitionCreateRequest,
)
from product_platform.tool_gateway.repository import ToolRegistryRepository
from product_platform.tool_gateway.runtime_audit import (
    ToolRuntimeActionCreate,
    ToolRuntimeActionEventCreate,
    ToolRuntimeActionQuery,
    ToolRuntimeActionRepository,
    ToolRuntimeActionUpdate,
    tool_runtime_action_detail_response,
    tool_runtime_action_response,
)


VALID_INPUT_SCHEMA = {
    "type": "object",
    "properties": {"claim_id": {"type": "string"}},
    "required": ["claim_id"],
}


class ToolGatewayRuntimeAuditPhase1Tests(unittest.TestCase):
    def test_integration_creates_runtime_action_for_denied_decision(self) -> None:
        database = create_migrated_test_database()
        with database.transaction() as connection:
            fixture = self._fixture(connection)
            decision = self._decision(
                connection,
                fixture,
                decision="deny",
                reason_code="permission_missing",
                request_id="req-runtime-denied",
            )
            repository = ToolRuntimeActionRepository(connection, DEMO_ORG_ID, DEMO_ENV_ID)

            row = repository.create_action(
                ToolRuntimeActionCreate(
                    request_id="req-runtime-denied",
                    correlation_id="corr-runtime-denied",
                    agent_id=fixture["agent_id"],
                    credential_id=None,
                    tool_id=fixture["tool_id"],
                    permission_id=None,
                    decision_id=decision["id"],
                    action_status="denied",
                    reason_code="permission_missing",
                    payload_summary={"claim_id": "claim_123"},
                ),
                created_at="2026-05-01T10:00:00+00:00",
            )
            repository.append_event(
                row["id"],
                ToolRuntimeActionEventCreate(
                    event_type="tool.runtime.denied",
                    event_summary={"reason_code": "permission_missing"},
                ),
                created_at="2026-05-01T10:00:01+00:00",
            )
            fetched = repository.get_action_detail(row["id"])

        response = tool_runtime_action_detail_response(fetched)
        self.assertEqual(response.action_status, "denied")
        self.assertEqual(response.reason_code, "permission_missing")
        self.assertEqual(response.decision_id, decision["id"])
        self.assertEqual(response.events[0].event_type, "tool.runtime.denied")

    def test_integration_creates_runtime_action_for_allowed_call(self) -> None:
        database = create_migrated_test_database()
        with database.transaction() as connection:
            fixture = self._fixture(connection, with_permission=True)
            decision = self._decision(
                connection,
                fixture,
                decision="allow",
                reason_code="allowed",
                permission_id=fixture["permission_id"],
                request_id="req-runtime-allowed",
            )
            repository = ToolRuntimeActionRepository(connection, DEMO_ORG_ID, DEMO_ENV_ID)

            row = repository.create_action(
                ToolRuntimeActionCreate(
                    request_id="req-runtime-allowed",
                    correlation_id="corr-runtime-allowed",
                    agent_id=fixture["agent_id"],
                    credential_id=None,
                    tool_id=fixture["tool_id"],
                    permission_id=fixture["permission_id"],
                    decision_id=decision["id"],
                    action_status="allowed",
                    reason_code="allowed",
                    payload_summary={"claim_id": "claim_123"},
                ),
                created_at="2026-05-01T11:00:00+00:00",
            )
            repository.update_action(
                row["id"],
                ToolRuntimeActionUpdate(
                    action_status="completed",
                    upstream_status_code=200,
                    latency_ms=34,
                    response_summary={"claim_status": "open"},
                    redaction_applied=False,
                ),
                updated_at="2026-05-01T11:00:02+00:00",
            )
            fetched = repository.get_action(row["id"])

        response = tool_runtime_action_response(fetched)
        self.assertEqual(response.action_status, "completed")
        self.assertEqual(response.permission_id, fixture["permission_id"])
        self.assertEqual(response.upstream_status_code, 200)
        self.assertEqual(response.response_summary, {"claim_status": "open"})

    def test_integration_payload_and_response_summaries_exclude_secret_like_values(self) -> None:
        database = create_migrated_test_database()
        with database.transaction() as connection:
            fixture = self._fixture(connection)
            decision = self._decision(
                connection,
                fixture,
                decision="deny",
                reason_code="permission_missing",
                request_id="req-runtime-redacted",
            )
            repository = ToolRuntimeActionRepository(connection, DEMO_ORG_ID, DEMO_ENV_ID)

            row = repository.create_action(
                ToolRuntimeActionCreate(
                    request_id="req-runtime-redacted",
                    correlation_id=None,
                    agent_id=fixture["agent_id"],
                    credential_id=None,
                    tool_id=fixture["tool_id"],
                    permission_id=None,
                    decision_id=decision["id"],
                    action_status="denied",
                    reason_code="permission_missing",
                    payload_summary={
                        "claim_id": "claim_123",
                        "authorization": "Bearer raw-token",
                        "nested": {"password": "hunter2"},
                    },
                    response_summary={"token": "secret-token", "claim_status": "open"},
                ),
            )

        response = tool_runtime_action_response(row)
        serialized = str(response.model_dump())
        self.assertEqual(response.payload_summary["authorization"], "[redacted]")
        self.assertEqual(response.payload_summary["nested"]["password"], "[redacted]")
        self.assertEqual(response.response_summary["token"], "[redacted]")
        self.assertNotIn("raw-token", serialized)
        self.assertNotIn("hunter2", serialized)
        self.assertNotIn("secret-token", serialized)

    def test_repository_filters_by_agent_tool_status_and_time(self) -> None:
        database = create_migrated_test_database()
        with database.transaction() as connection:
            fixture = self._fixture(connection)
            decision = self._decision(
                connection,
                fixture,
                decision="deny",
                reason_code="permission_missing",
                request_id="req-runtime-filter-decision",
            )
            repository = ToolRuntimeActionRepository(connection, DEMO_ORG_ID, DEMO_ENV_ID)
            repository.create_action(
                ToolRuntimeActionCreate(
                    request_id="req-runtime-filter-old",
                    correlation_id=None,
                    agent_id=fixture["agent_id"],
                    credential_id=None,
                    tool_id=fixture["tool_id"],
                    permission_id=None,
                    decision_id=decision["id"],
                    action_status="denied",
                    reason_code="permission_missing",
                    payload_summary={"claim_id": "old"},
                ),
                created_at="2026-05-01T09:00:00+00:00",
            )
            repository.create_action(
                ToolRuntimeActionCreate(
                    request_id="req-runtime-filter-new",
                    correlation_id=None,
                    agent_id=fixture["agent_id"],
                    credential_id=None,
                    tool_id=fixture["tool_id"],
                    permission_id=None,
                    decision_id=decision["id"],
                    action_status="completed",
                    reason_code="allowed",
                    payload_summary={"claim_id": "new"},
                ),
                created_at="2026-05-02T09:00:00+00:00",
            )

            rows = repository.list_actions(
                ToolRuntimeActionQuery(
                    agent_id=fixture["agent_id"],
                    tool_id=fixture["tool_id"],
                    action_status="denied",
                    created_from="2026-05-01T00:00:00+00:00",
                    created_to="2026-05-01T23:59:59+00:00",
                )
            )

        self.assertEqual([row["request_id"] for row in rows], ["req-runtime-filter-old"])

    def _fixture(self, connection, *, with_permission: bool = False) -> dict[str, str | None]:
        seed_demo_data(connection)
        agent_id = "agent_runtime_phase1"
        self._insert_agent(connection, agent_id)
        registry = ToolRegistryRepository(connection, DEMO_ORG_ID, DEMO_ENV_ID)
        tool = registry.create_tool(
            ToolDefinitionCreateRequest(
                name="claims.runtime",
                display_name="Claims Runtime",
                owner_team="claims-platform",
                required_scope="claims.lookup:read",
                input_schema_json=VALID_INPUT_SCHEMA,
            ),
            created_by=DEMO_ADMIN_USER_ID,
        )
        tool = registry.activate_tool(tool["id"], actor_id=DEMO_ADMIN_USER_ID)
        permission_id = None
        if with_permission:
            permission = registry.grant_agent_tool_permission(
                agent_id,
                AgentToolPermissionGrantRequest(
                    tool_id=tool["id"],
                    scope="claims.lookup:read",
                    granted_reason="runtime audit fixture",
                ),
                granted_by=DEMO_ADMIN_USER_ID,
            )
            permission_id = permission["id"]
        return {"agent_id": agent_id, "tool_id": tool["id"], "permission_id": permission_id}

    def _decision(
        self,
        connection,
        fixture: dict[str, str | None],
        *,
        decision: str,
        reason_code: str,
        request_id: str,
        permission_id: str | None = None,
    ):
        return ToolPolicyDecisionRepository(connection, DEMO_ORG_ID, DEMO_ENV_ID).create_decision(
            ToolPolicyDecisionCreate(
                agent_id=fixture["agent_id"],
                tool_id=fixture["tool_id"],
                permission_id=permission_id,
                decision=decision,
                reason_code=reason_code,
                reason_message="Runtime audit fixture.",
                matched_policy_id=None,
                request_id=request_id,
                correlation_id=f"corr-{request_id}",
                payload_summary={"claim_id": "claim_123"},
            )
        )

    def _insert_agent(self, connection, agent_id: str) -> None:
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
                agent_id,
                DEMO_ORG_ID,
                DEMO_ENV_ID,
                agent_id,
                "Runtime audit fixture.",
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
