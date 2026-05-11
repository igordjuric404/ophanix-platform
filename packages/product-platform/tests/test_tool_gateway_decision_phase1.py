from __future__ import annotations

import unittest

from product_platform.db.seed import DEMO_ADMIN_USER_ID, DEMO_ENV_ID, DEMO_ORG_ID, seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.tool_gateway.models import (
    AgentToolPermissionGrantRequest,
    ToolDefinitionCreateRequest,
)
from product_platform.tool_gateway.decision import (
    ToolPolicyDecisionCreate,
    ToolPolicyDecisionRepository,
    ToolPolicyDecisionResult,
    summarize_tool_payload,
    tool_policy_decision_response,
)
from product_platform.tool_gateway.repository import ToolRegistryRepository


VALID_INPUT_SCHEMA = {
    "type": "object",
    "properties": {"claim_id": {"type": "string"}},
    "required": ["claim_id"],
}


class ToolGatewayDecisionPhase1Tests(unittest.TestCase):
    def test_unit_decision_model_serializes_reason_codes(self) -> None:
        decision = ToolPolicyDecisionResult(
            id="decision_1",
            organization_id=DEMO_ORG_ID,
            environment_id=DEMO_ENV_ID,
            agent_id="agent_1",
            tool_id="tool_1",
            permission_id=None,
            decision="deny",
            reason_code="permission_missing",
            reason_message="No active permission binding was found.",
            matched_policy_id=None,
            request_id="req_1",
            correlation_id="corr_1",
            payload_summary={"claim_id": "claim_123"},
            created_at="2026-05-01T00:00:00+00:00",
        )

        payload = decision.model_dump()

        self.assertEqual(payload["decision"], "deny")
        self.assertEqual(payload["reason_code"], "permission_missing")
        self.assertEqual(payload["payload_summary"], {"claim_id": "claim_123"})

    def test_unit_payload_summary_redacts_credential_like_values(self) -> None:
        summary = summarize_tool_payload(
            {
                "claim_id": "claim_123",
                "api_key": "sk-live-secret",
                "nested": {
                    "password": "hunter2",
                    "safe": "visible",
                    "note": "Bearer abcdefghijklmnopqrstuvwxyz123456",
                    "tokens": [{"token": "abc"}, {"value": "ok"}],
                },
                "long_note": "x" * 140,
            }
        )

        self.assertEqual(summary["claim_id"], "claim_123")
        self.assertEqual(summary["api_key"], "[redacted]")
        self.assertEqual(summary["nested"]["password"], "[redacted]")
        self.assertEqual(summary["nested"]["safe"], "visible")
        self.assertEqual(summary["nested"]["note"], "[redacted]")
        self.assertEqual(summary["nested"]["tokens"], "[redacted]")
        self.assertTrue(summary["long_note"].endswith("..."))
        self.assertLessEqual(len(summary["long_note"]), 120)
        self.assertNotIn("hunter2", str(summary))
        self.assertNotIn("sk-live-secret", str(summary))

    def test_integration_decision_record_can_be_persisted_and_fetched(self) -> None:
        database = create_migrated_test_database()
        with database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection)
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
            registry.activate_tool(tool["id"], actor_id=DEMO_ADMIN_USER_ID)
            permission = registry.grant_agent_tool_permission(
                "agent_decision_phase1",
                AgentToolPermissionGrantRequest(
                    tool_id=tool["id"],
                    scope="claims.lookup:read",
                    granted_reason="decision persistence fixture",
                ),
                granted_by=DEMO_ADMIN_USER_ID,
            )
            repository = ToolPolicyDecisionRepository(connection, DEMO_ORG_ID, DEMO_ENV_ID)
            row = repository.create_decision(
                ToolPolicyDecisionCreate(
                    agent_id="agent_decision_phase1",
                    tool_id=tool["id"],
                    permission_id=permission["id"],
                    decision="allow",
                    reason_code="allowed",
                    reason_message="Tool call is allowed.",
                    matched_policy_id="policy_1",
                    request_id="req_1",
                    correlation_id="corr_1",
                    payload_summary={"claim_id": "claim_123"},
                )
            )
            fetched = repository.get_decision(row["id"])

        self.assertIsNotNone(fetched)
        response = tool_policy_decision_response(fetched)
        self.assertTrue(response.id.startswith("decision_"))
        self.assertEqual(response.decision, "allow")
        self.assertEqual(response.reason_code, "allowed")
        self.assertEqual(response.matched_policy_id, "policy_1")
        self.assertEqual(response.payload_summary, {"claim_id": "claim_123"})

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
                "agent_decision_phase1",
                DEMO_ORG_ID,
                DEMO_ENV_ID,
                "agent_decision_phase1",
                "Decision persistence fixture.",
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
