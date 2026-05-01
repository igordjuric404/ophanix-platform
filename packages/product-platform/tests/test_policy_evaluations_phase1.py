from __future__ import annotations

import time
import unittest

from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.policies.bindings import PolicyBindingRepository
from product_platform.policies.evaluations import PolicyBackendDecision, PolicyEvaluationAdapter
from product_platform.policies.models import (
    PolicyBindingCreateRequest,
    PolicyCreateRequest,
    PolicyEvaluationRequest,
    PolicyVersionCreateRequest,
)
from product_platform.policies.repository import PolicyRepository


POLICY_BODY = """version: "1.0"
name: delete-customer-guard
rules:
  - name: deny_delete_customer
    condition:
      field: tool_name
      operator: eq
      value: delete_customer
    action: deny
    message: Customer deletion requires approval.
defaults:
  action: allow
"""


class PolicyEvaluationAdapterPhase1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            policy_repository = PolicyRepository(connection, "org_default")
            policy = policy_repository.create_policy(
                PolicyCreateRequest(name="Delete Customer Guard", scope="mcp-tool", status="active"),
                actor_id="user_admin",
            )
            version = policy_repository.create_version(
                policy["id"],
                PolicyVersionCreateRequest(
                    body_text=POLICY_BODY,
                    body_format="yaml",
                    backend="native",
                    status="active",
                ),
                actor_id="user_admin",
            )
        self.connection = self.database.connect()
        self.policy_id = policy["id"]
        self.version_id = version["id"]

    def test_explicit_policy_allows_when_no_rule_matches(self) -> None:
        adapter = PolicyEvaluationAdapter(self.connection, "org_default", "env_default")

        result = adapter.evaluate(
            PolicyEvaluationRequest(
                policy_id=self.policy_id,
                policy_version_id=self.version_id,
                action="mcp.call",
                context={"tool_name": "view_customer"},
            ),
            correlation_id="corr-policy-allow",
        )

        self.assertEqual(result.decision, "allow")
        self.assertEqual(result.policy_action, "allow")
        self.assertIsNone(result.matched_rule)
        self.assertEqual(result.policy_id, self.policy_id)
        self.assertEqual(result.policy_version_id, self.version_id)
        self.assertEqual(result.backend, "native")
        self.assertFalse(result.error)
        self.assertGreaterEqual(result.latency_ms, 0)
        self.assertEqual(result.context["action"], "mcp.call")

    def test_active_binding_denies_with_matched_rule_and_reason(self) -> None:
        with self.database.transaction() as connection:
            binding = PolicyBindingRepository(connection, "org_default", "env_default").create_binding(
                PolicyBindingCreateRequest(
                    policy_id=self.policy_id,
                    policy_version_id=self.version_id,
                    target_type="mcp-tool",
                    target_id="demo.delete_customer",
                    mode="enforce",
                    priority=20,
                ),
                actor_id="user_admin",
            )
        adapter = PolicyEvaluationAdapter(self.connection, "org_default", "env_default")

        result = adapter.evaluate(
            PolicyEvaluationRequest(
                target_type="mcp-tool",
                target_id="demo.delete_customer",
                action="mcp.call",
                context={"tool_name": "delete_customer"},
                mode="live",
            ),
            correlation_id="corr-policy-deny",
        )

        self.assertEqual(result.decision, "deny")
        self.assertEqual(result.policy_action, "deny")
        self.assertEqual(result.matched_rule, "deny_delete_customer")
        self.assertEqual(result.reason, "Customer deletion requires approval.")
        self.assertEqual(result.binding_id, binding["id"])
        self.assertEqual(result.binding_mode, "enforce")
        self.assertEqual(result.policy_id, self.policy_id)
        self.assertEqual(result.policy_version_id, self.version_id)
        self.assertFalse(result.error)

    def test_unsupported_backend_fails_closed(self) -> None:
        with self.database.transaction() as connection:
            policy_repository = PolicyRepository(connection, "org_default")
            policy = policy_repository.create_policy(
                PolicyCreateRequest(name="External Guard", scope="mcp-tool", status="active"),
                actor_id="user_admin",
            )
            version = policy_repository.create_version(
                policy["id"],
                PolicyVersionCreateRequest(
                    body_text="package agentos\nallow := true",
                    body_format="rego",
                    backend="opa",
                    status="active",
                ),
                actor_id="user_admin",
            )
        adapter = PolicyEvaluationAdapter(self.connection, "org_default", "env_default")

        result = adapter.evaluate(
            PolicyEvaluationRequest(
                policy_id=policy["id"],
                policy_version_id=version["id"],
                action="mcp.call",
                context={"tool_name": "delete_customer"},
            ),
            correlation_id="corr-policy-fail-closed",
        )

        self.assertEqual(result.decision, "deny")
        self.assertEqual(result.policy_action, "deny")
        self.assertTrue(result.error)
        self.assertIn("failed closed", result.reason)
        self.assertIn("No local evaluator", result.reason)
        self.assertEqual(result.policy_id, policy["id"])
        self.assertEqual(result.policy_version_id, version["id"])

    def test_latency_is_captured_for_backend_hook(self) -> None:
        def slow_backend(_version, _context) -> PolicyBackendDecision:
            time.sleep(0.002)
            return PolicyBackendDecision(
                allowed=True,
                action="allow",
                reason="Backend hook allowed the action.",
            )

        adapter = PolicyEvaluationAdapter(
            self.connection,
            "org_default",
            "env_default",
            backend_evaluators={"opa": slow_backend},
        )

        result = adapter.evaluate(
            PolicyEvaluationRequest(
                policy_id=self.policy_id,
                policy_version_id=self.version_id,
                action="mcp.call",
                context={"tool_name": "delete_customer"},
                backend="opa",
            ),
            correlation_id="corr-policy-latency",
        )

        self.assertEqual(result.decision, "allow")
        self.assertEqual(result.backend, "opa")
        self.assertFalse(result.error)
        self.assertGreater(result.latency_ms, 0)


if __name__ == "__main__":
    unittest.main()
