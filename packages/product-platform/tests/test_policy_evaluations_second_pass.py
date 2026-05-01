from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.integrations.secrets import DemoLocalSecretProvider


POLICY_BODY = """version: "1.0"
name: policy-second-pass-guard
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


class PolicyEvaluationSecondPassTests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
        self.secret_provider = DemoLocalSecretProvider()
        self.app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-05-01T00:00:00Z",
                dev_login_allowed_emails=["second-pass@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.app.state.secret_provider = self.secret_provider
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "second-pass@example.com", "roles": ["Platform Admin"]},
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.token = login.json()["access_token"]
        self.user = login.json()["user"]

    def _headers(self, correlation_id: str = "corr-policy-second-pass") -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
            "X-Correlation-ID": correlation_id,
        }

    def _create_policy_version(self) -> tuple[str, str]:
        policy = self.client.post(
            "/api/v1/policies",
            headers=self._headers("corr-policy-create"),
            json={"name": "Second Pass Guard", "scope": "mcp-tool", "status": "active"},
        )
        self.assertEqual(policy.status_code, 201, policy.text)
        version = self.client.post(
            f"/api/v1/policies/{policy.json()['id']}/versions",
            headers=self._headers("corr-policy-version"),
            json={
                "body_text": POLICY_BODY,
                "body_format": "yaml",
                "backend": "native",
                "status": "active",
            },
        )
        self.assertEqual(version.status_code, 201, version.text)
        return policy.json()["id"], version.json()["id"]

    def _simulate_policy(
        self,
        *,
        policy_id: str,
        version_id: str,
        tool_name: str,
        correlation_id: str,
    ) -> dict:
        response = self.client.post(
            "/api/v1/policy-evaluations/simulate",
            headers=self._headers(correlation_id),
            json={
                "policy_id": policy_id,
                "policy_version_id": version_id,
                "agent_id": "agent_summary",
                "action": "mcp.call",
                "resource_type": "mcp-tool",
                "resource_id": f"demo.{tool_name}",
                "context": {"tool_name": tool_name},
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_summary_returns_decision_mode_action_counts_and_daily_trends(self) -> None:
        policy_id, version_id = self._create_policy_version()
        self._simulate_policy(
            policy_id=policy_id,
            version_id=version_id,
            tool_name="view_customer",
            correlation_id="corr-summary-allow",
        )
        self._simulate_policy(
            policy_id=policy_id,
            version_id=version_id,
            tool_name="delete_customer",
            correlation_id="corr-summary-deny",
        )

        response = self.client.get(
            "/api/v1/policy-evaluations/summary",
            headers=self._headers("corr-summary-read"),
        )

        self.assertEqual(response.status_code, 200, response.text)
        summary = response.json()
        self.assertEqual(summary["total_count"], 2)
        self.assertEqual(summary["decision_counts"], {"allow": 1, "deny": 1})
        self.assertEqual(summary["mode_counts"], {"simulate": 2})
        self.assertEqual(summary["action_counts"], {"mcp.call": 2})
        self.assertEqual(len(summary["time_buckets"]), 1)
        self.assertEqual(summary["time_buckets"][0]["total_count"], 2)
        self.assertEqual(summary["time_buckets"][0]["decision_counts"], {"allow": 1, "deny": 1})

        filtered = self.client.get(
            "/api/v1/policy-evaluations/summary",
            headers=self._headers("corr-summary-filtered"),
            params={"decision": "deny"},
        )
        self.assertEqual(filtered.status_code, 200, filtered.text)
        self.assertEqual(filtered.json()["total_count"], 1)
        self.assertEqual(filtered.json()["decision_counts"], {"deny": 1})

    def test_policy_evaluation_stream_returns_sse_rows_after_last_event_id(self) -> None:
        policy_id, version_id = self._create_policy_version()
        first = self._simulate_policy(
            policy_id=policy_id,
            version_id=version_id,
            tool_name="view_customer",
            correlation_id="corr-stream-first",
        )
        second = self._simulate_policy(
            policy_id=policy_id,
            version_id=version_id,
            tool_name="delete_customer",
            correlation_id="corr-stream-second",
        )

        response = self.client.get(
            "/api/v1/policy-evaluations/stream",
            headers=self._headers("corr-stream-read"),
            params={"environment_id": "env_default", "last_event_id": first["id"]},
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn("text/event-stream", response.headers["content-type"])
        self.assertIn("event: policy_evaluation", response.text)
        self.assertIn(f"id: {second['id']}", response.text)
        self.assertNotIn(f"id: {first['id']}", response.text)

    def test_agent_registration_simulation_persists_policy_feed_row(self) -> None:
        draft = self.client.post(
            "/api/v1/agents/registration-drafts",
            headers=self._headers("corr-agent-draft"),
            json={
                "name": "Second Pass Registration Agent",
                "description": "Needs registration simulation.",
                "framework": "langgraph",
                "runtime_type": "service",
                "owner_user_id": self.user["id"],
                "sponsor_user_id": self.user["id"],
            },
        )
        self.assertEqual(draft.status_code, 201, draft.text)
        draft_id = draft.json()["id"]
        patch = self.client.patch(
            f"/api/v1/agents/registration-drafts/{draft_id}",
            headers=self._headers("corr-agent-patch"),
            json={
                "capabilities": [
                    {"capability_name": "admin:delete", "resource_type": "claim"},
                ],
                "policy_selections": [
                    {
                        "policy_id": "policy_placeholder_default_allow",
                        "selection_type": "policy_binding",
                    }
                ],
            },
        )
        self.assertEqual(patch.status_code, 200, patch.text)

        response = self.client.post(
            f"/api/v1/agents/registration-drafts/{draft_id}/simulate",
            headers=self._headers("corr-agent-feed"),
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["decision"], "deny")
        feed = self.client.get(
            "/api/v1/policy-evaluations",
            headers=self._headers("corr-agent-feed-read"),
            params={"correlation_id": "corr-agent-feed"},
        )
        self.assertEqual(feed.status_code, 200, feed.text)
        rows = feed.json()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["backend"], "agent-registration")
        self.assertEqual(rows[0]["decision"], "deny")
        self.assertEqual(rows[0]["agent_id"], draft_id)
        self.assertEqual(rows[0]["target_type"], "agent")
        self.assertEqual(rows[0]["resource_type"], "agent_registration_draft")
        self.assertEqual(rows[0]["resource_id"], draft_id)
        self.assertEqual(rows[0]["context"]["matched_policy_ids"], ["policy_placeholder_default_allow"])

    def test_provider_credential_health_test_persists_policy_feed_row(self) -> None:
        credential = self.client.post(
            "/api/v1/integrations/provider-credentials",
            headers=self._headers("corr-provider-create"),
            json={
                "name": "Invalid provider key",
                "provider_type": "model_provider",
                "secret_value": "invalid-secret",
            },
        )
        self.assertEqual(credential.status_code, 201, credential.text)

        response = self.client.post(
            f"/api/v1/integrations/provider-credentials/{credential.json()['id']}/test",
            headers=self._headers("corr-provider-feed"),
        )

        self.assertEqual(response.status_code, 201, response.text)
        health = response.json()
        self.assertEqual(health["status"], "failed")
        feed = self.client.get(
            "/api/v1/policy-evaluations",
            headers=self._headers("corr-provider-feed-read"),
            params={"correlation_id": "corr-provider-feed"},
        )
        self.assertEqual(feed.status_code, 200, feed.text)
        rows = feed.json()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["backend"], "integration-health")
        self.assertEqual(rows[0]["decision"], "deny")
        self.assertEqual(rows[0]["action"], "integration.provider_credential.test")
        self.assertEqual(rows[0]["resource_type"], "provider_credential")
        self.assertEqual(rows[0]["resource_id"], credential.json()["id"])
        self.assertEqual(rows[0]["context"]["health_check_id"], health["id"])
        self.assertEqual(rows[0]["context"]["provider_type"], "model_provider")


if __name__ == "__main__":
    unittest.main()
