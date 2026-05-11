from __future__ import annotations

import unittest

from product_platform.db.seed import DEMO_ADMIN_USER_ID, DEMO_ENV_ID, DEMO_ORG_ID, seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.tool_gateway.auth import GatewayCredentialScope, GatewayPrincipal
from product_platform.tool_gateway.decision import (
    ToolPolicyDecisionRepository,
    ToolPolicyDecisionService,
    ToolPolicyHookContext,
    ToolPolicyHookResult,
    tool_policy_decision_response,
)
from product_platform.tool_gateway.models import (
    AgentToolPermissionGrantRequest,
    ToolDefinitionCreateRequest,
)
from product_platform.tool_gateway.repository import ToolRegistryRepository


VALID_INPUT_SCHEMA = {
    "type": "object",
    "properties": {"claim_id": {"type": "string"}},
    "required": ["claim_id"],
}


class AllowHook:
    def __init__(self, *, matched_policy_id: str = "policy_allow") -> None:
        self.matched_policy_id = matched_policy_id
        self.contexts: list[ToolPolicyHookContext] = []

    def evaluate(self, context: ToolPolicyHookContext) -> ToolPolicyHookResult:
        self.contexts.append(context)
        return ToolPolicyHookResult(decision="allow", matched_policy_id=self.matched_policy_id)


class DenyHook:
    def evaluate(self, context: ToolPolicyHookContext) -> ToolPolicyHookResult:
        return ToolPolicyHookResult(
            decision="deny",
            matched_policy_id="policy_deny",
            reason_message="Denied by fixture policy.",
        )


class ErrorHook:
    def evaluate(self, context: ToolPolicyHookContext) -> ToolPolicyHookResult:
        raise RuntimeError("policy backend unavailable")


class ToolGatewayDecisionPhase3Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection)
        self.connection = self.database.connect()
        self.registry = ToolRegistryRepository(self.connection, DEMO_ORG_ID, DEMO_ENV_ID)

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
                "agent_decision_policy",
                DEMO_ORG_ID,
                DEMO_ENV_ID,
                "agent_decision_policy",
                "Decision policy hook fixture.",
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

    def _principal(self) -> GatewayPrincipal:
        return GatewayPrincipal(
            organization_id=DEMO_ORG_ID,
            environment_id=DEMO_ENV_ID,
            agent_id="agent_decision_policy",
            credential_id="cred_policy",
            scopes=["claims.lookup:read"],
            scope_grants=[
                GatewayCredentialScope(
                    scope="claims.lookup:read",
                    resource_type="tool",
                    resource_id="claims.lookup",
                )
            ],
            request_id="req-policy",
        )

    def _seed_allowed_fixture(self) -> tuple[str, str]:
        tool = self.registry.create_tool(
            ToolDefinitionCreateRequest(
                name="claims.lookup",
                display_name="Claims Lookup",
                owner_team="claims-platform",
                required_scope="claims.lookup:read",
                input_schema_json=VALID_INPUT_SCHEMA,
            ),
            created_by=DEMO_ADMIN_USER_ID,
        )
        self.registry.activate_tool(tool["id"], actor_id=DEMO_ADMIN_USER_ID)
        permission = self.registry.grant_agent_tool_permission(
            "agent_decision_policy",
            AgentToolPermissionGrantRequest(
                tool_id=tool["id"],
                scope="claims.lookup:read",
                granted_reason="policy hook fixture",
            ),
            granted_by=DEMO_ADMIN_USER_ID,
        )
        return tool["id"], permission["id"]

    def test_unit_policy_allow_preserves_allow_decision(self) -> None:
        hook = AllowHook()
        with self.database.transaction():
            tool_id, permission_id = self._seed_allowed_fixture()
            decision = ToolPolicyDecisionService(
                self.connection,
                DEMO_ORG_ID,
                DEMO_ENV_ID,
                policy_hook=hook,
            ).evaluate_tool_call(
                self._principal(),
                "claims.lookup",
                {"claim_id": "claim_123"},
                request_id="req-policy-allow",
                correlation_id="corr-policy-allow",
            )

        self.assertEqual(decision.decision, "allow")
        self.assertEqual(decision.reason_code, "allowed")
        self.assertEqual(decision.matched_policy_id, "policy_allow")
        self.assertEqual(hook.contexts[0].tool_id, tool_id)
        self.assertEqual(hook.contexts[0].permission_id, permission_id)
        self.assertEqual(hook.contexts[0].payload_summary, {"claim_id": "claim_123"})

    def test_unit_policy_deny_overrides_permission(self) -> None:
        with self.database.transaction():
            self._seed_allowed_fixture()
            decision = ToolPolicyDecisionService(
                self.connection,
                DEMO_ORG_ID,
                DEMO_ENV_ID,
                policy_hook=DenyHook(),
            ).evaluate_tool_call(
                self._principal(),
                "claims.lookup",
                {"claim_id": "claim_123"},
                request_id="req-policy-deny",
                correlation_id="corr-policy-deny",
            )

        self.assertEqual(decision.decision, "deny")
        self.assertEqual(decision.reason_code, "policy_denied")
        self.assertEqual(decision.reason_message, "Denied by fixture policy.")
        self.assertEqual(decision.matched_policy_id, "policy_deny")

    def test_unit_policy_exception_returns_policy_error_deny(self) -> None:
        with self.database.transaction():
            self._seed_allowed_fixture()
            decision = ToolPolicyDecisionService(
                self.connection,
                DEMO_ORG_ID,
                DEMO_ENV_ID,
                policy_hook=ErrorHook(),
            ).evaluate_tool_call(
                self._principal(),
                "claims.lookup",
                {"claim_id": "claim_123"},
                request_id="req-policy-error",
                correlation_id="corr-policy-error",
            )

        self.assertEqual(decision.decision, "deny")
        self.assertEqual(decision.reason_code, "policy_error")
        self.assertIsNone(decision.matched_policy_id)

    def test_integration_matched_policy_id_is_persisted(self) -> None:
        with self.database.transaction():
            self._seed_allowed_fixture()
            decision = ToolPolicyDecisionService(
                self.connection,
                DEMO_ORG_ID,
                DEMO_ENV_ID,
                policy_hook=AllowHook(matched_policy_id="policy_persisted"),
            ).evaluate_tool_call(
                self._principal(),
                "claims.lookup",
                {"claim_id": "claim_123"},
                request_id="req-policy-persisted",
                correlation_id="corr-policy-persisted",
            )

        row = ToolPolicyDecisionRepository(
            self.connection,
            DEMO_ORG_ID,
            DEMO_ENV_ID,
        ).get_decision(decision.id)
        self.assertIsNotNone(row)
        persisted = tool_policy_decision_response(row)
        self.assertEqual(persisted.matched_policy_id, "policy_persisted")
        self.assertEqual(persisted.decision, "allow")

    def test_integration_payload_summary_redacts_common_pii_keys(self) -> None:
        hook = AllowHook()
        with self.database.transaction():
            self._seed_allowed_fixture()
            decision = ToolPolicyDecisionService(
                self.connection,
                DEMO_ORG_ID,
                DEMO_ENV_ID,
                policy_hook=hook,
            ).evaluate_tool_call(
                self._principal(),
                "claims.lookup",
                {
                    "claim_id": "claim_123",
                    "customer_email": "patient@example.test",
                    "ssn": "123-45-6789",
                },
                request_id="req-policy-pii",
                correlation_id="corr-policy-pii",
            )

        self.assertEqual(decision.payload_summary["customer_email"], "[redacted]")
        self.assertEqual(decision.payload_summary["ssn"], "[redacted]")
        self.assertEqual(hook.contexts[0].payload_summary["customer_email"], "[redacted]")


if __name__ == "__main__":
    unittest.main()
