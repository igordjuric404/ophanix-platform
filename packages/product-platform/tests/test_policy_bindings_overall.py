from __future__ import annotations

import unittest

import yaml
from agent_os.policies.evaluator import PolicyEvaluator
from agent_os.policies.schema import PolicyDocument
from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.policies.bindings import PolicyBindingRepository
from product_platform.policies.models import PolicyBindingResolutionContext


POLICY_BODY = """version: "1.0"
name: mcp-delete-guard
rules:
  - name: deny_delete_customer
    condition:
      field: tool_name
      operator: eq
      value: delete_customer
    action: deny
    message: Customer deletion requires a governed rollout.
"""


class PolicyBindingsOverallValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
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
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "admin@example.com", "roles": ["Policy Admin"]},
        )
        self.assertEqual(login.status_code, 200)
        self.token = login.json()["access_token"]

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}", "X-Environment-ID": "env_default"}

    def test_bind_mcp_tool_shadow_promote_enforce_and_exception(self) -> None:
        policy = self.client.post(
            "/api/v1/policies",
            headers=self._headers(),
            json={"name": "MCP Delete Guard", "scope": "mcp-tool"},
        )
        self.assertEqual(policy.status_code, 201)
        version = self.client.post(
            f"/api/v1/policies/{policy.json()['id']}/versions",
            headers=self._headers(),
            json={"body_text": POLICY_BODY, "body_format": "yaml"},
        )
        self.assertEqual(version.status_code, 201)
        binding = self.client.post(
            "/api/v1/policy-bindings",
            headers=self._headers(),
            json={
                "policy_id": policy.json()["id"],
                "policy_version_id": version.json()["id"],
                "target_type": "mcp-tool",
                "target_id": "demo.delete_customer",
                "mode": "shadow",
                "rollout_percentage": 100,
            },
        )
        self.assertEqual(binding.status_code, 201)

        shadow = self._evaluate_demo_tool("corr-overall-shadow")
        self.assertTrue(shadow["applied"])
        self.assertEqual(shadow["mode"], "shadow")
        self.assertEqual(shadow["decision"], "deny")
        self.assertFalse(shadow["enforced_denial"])

        promoted = self.client.post(
            f"/api/v1/policy-bindings/{binding.json()['id']}/promote",
            headers=self._headers(),
            json={"mode": "enforce", "rollout_percentage": 100, "reason": "shadow validation passed"},
        )
        self.assertEqual(promoted.status_code, 200)
        enforced = self._evaluate_demo_tool("corr-overall-enforce")
        self.assertEqual(enforced["mode"], "enforce")
        self.assertEqual(enforced["decision"], "deny")
        self.assertTrue(enforced["enforced_denial"])

        exception = self.client.post(
            f"/api/v1/policy-bindings/{binding.json()['id']}/exceptions",
            headers=self._headers(),
            json={"reason": "customer export maintenance", "expires_at": "2026-05-02T00:00:00+00:00"},
        )
        self.assertEqual(exception.status_code, 201)
        excepted = self._evaluate_demo_tool(
            "corr-overall-exception",
            now="2026-05-01T12:00:00+00:00",
        )
        self.assertFalse(excepted["applied"])
        self.assertFalse(excepted["enforced_denial"])

    def _evaluate_demo_tool(self, correlation_id: str, *, now: str | None = None) -> dict[str, object]:
        connection = self.database.connect()
        repository = PolicyBindingRepository(connection, "org_default", "env_default")
        resolved = repository.resolve_bindings(
            PolicyBindingResolutionContext(
                organization_id="org_default",
                environment_id="env_default",
                target_type="mcp-tool",
                target_id="demo.delete_customer",
                correlation_id=correlation_id,
            ),
            now=now,
        )
        if not resolved:
            return {"applied": False, "mode": None, "decision": "allow", "enforced_denial": False}
        binding = resolved[0]
        version = connection.execute(
            "SELECT body_text FROM policy_versions WHERE id = ?",
            (binding["policy_version_id"],),
        ).fetchone()
        self.assertIsNotNone(version)
        document = PolicyDocument.model_validate(yaml.safe_load(version["body_text"]))
        decision = PolicyEvaluator([document]).evaluate({"tool_name": "delete_customer"})
        return {
            "applied": True,
            "mode": binding["mode"],
            "decision": decision.action,
            "enforced_denial": binding["mode"] == "enforce" and not decision.allowed,
        }


if __name__ == "__main__":
    unittest.main()
