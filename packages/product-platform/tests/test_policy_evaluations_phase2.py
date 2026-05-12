from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.api.tenancy import Environment, TenantStore
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


POLICY_BODY = """version: "1.0"
name: api-delete-customer-guard
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


class PolicyEvaluationAPITests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        now = "2026-05-01T00:00:00+00:00"
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            connection.execute(
                """
                INSERT INTO environments
                    (id, organization_id, name, slug, type, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT DO NOTHING
                """,
                ("env_second", "org_default", "Second", "second", "development", now, now),
            )
        tenant_store = TenantStore(
            environments=[
                Environment(
                    id="env_default",
                    organization_id="org_default",
                    name="Development",
                    slug="development",
                    type="development",
                    created_at=now,
                ),
                Environment(
                    id="env_second",
                    organization_id="org_default",
                    name="Second",
                    slug="second",
                    type="development",
                    created_at=now,
                ),
            ]
        )
        self.app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time=now,
                dev_login_allowed_emails=["admin@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
            tenant_store=tenant_store,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "admin@example.com", "roles": ["Policy Admin"]},
        )
        self.assertEqual(login.status_code, 200)
        self.token = login.json()["access_token"]

    def _headers(
        self,
        *,
        environment_id: str = "env_default",
        correlation_id: str = "corr-policy-api",
    ) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": environment_id,
            "X-Correlation-ID": correlation_id,
        }

    def _create_policy_version(self) -> tuple[str, str]:
        policy = self.client.post(
            "/api/v1/policies",
            headers=self._headers(),
            json={"name": "API Delete Customer Guard", "scope": "mcp-tool", "status": "active"},
        )
        self.assertEqual(policy.status_code, 201, policy.text)
        version = self.client.post(
            f"/api/v1/policies/{policy.json()['id']}/versions",
            headers=self._headers(),
            json={
                "body_text": POLICY_BODY,
                "body_format": "yaml",
                "backend": "native",
                "status": "active",
            },
        )
        self.assertEqual(version.status_code, 201, version.text)
        return policy.json()["id"], version.json()["id"]

    def test_simulation_is_persisted_and_readable_by_detail(self) -> None:
        policy_id, version_id = self._create_policy_version()

        response = self.client.post(
            "/api/v1/policy-evaluations/simulate",
            headers=self._headers(correlation_id="corr-simulate-persist"),
            json={
                "policy_id": policy_id,
                "policy_version_id": version_id,
                "action": "mcp.call",
                "context": {"tool_name": "view_customer"},
            },
        )

        self.assertEqual(response.status_code, 201, response.text)
        evaluation = response.json()
        self.assertEqual(evaluation["mode"], "simulate")
        self.assertEqual(evaluation["decision"], "allow")
        self.assertEqual(evaluation["policy_id"], policy_id)
        detail = self.client.get(
            f"/api/v1/policy-evaluations/{evaluation['id']}",
            headers=self._headers(correlation_id="corr-simulate-persist"),
        )
        self.assertEqual(detail.status_code, 200, detail.text)
        self.assertEqual(detail.json()["id"], evaluation["id"])
        self.assertEqual(detail.json()["context"]["tool_name"], "view_customer")

    def test_live_evaluation_persists_and_emits_policy_decision_audit_event(self) -> None:
        policy_id, version_id = self._create_policy_version()

        response = self.client.post(
            "/api/v1/policy-evaluations/evaluate",
            headers=self._headers(correlation_id="corr-live-audit"),
            json={
                "policy_id": policy_id,
                "policy_version_id": version_id,
                "agent_id": "agent_live_eval",
                "action": "mcp.call",
                "resource_type": "mcp-tool",
                "resource_id": "demo.delete_customer",
                "context": {"tool_name": "delete_customer"},
            },
        )

        self.assertEqual(response.status_code, 201, response.text)
        evaluation = response.json()
        self.assertEqual(evaluation["mode"], "live")
        self.assertEqual(evaluation["decision"], "deny")
        audit = self.client.get(
            "/api/v1/audit/events",
            headers=self._headers(correlation_id="corr-live-audit"),
            params={"event_type": "policy.decision", "correlation_id": "corr-live-audit"},
        )
        self.assertEqual(audit.status_code, 200, audit.text)
        events = audit.json()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["resource_type"], "policy_evaluation")
        self.assertEqual(events[0]["resource_id"], evaluation["id"])
        self.assertEqual(events[0]["decision"], "deny")
        self.assertEqual(events[0]["policy_id"], policy_id)
        self.assertEqual(events[0]["policy_version_id"], version_id)

    def test_feed_filters_by_decision_mode_and_agent(self) -> None:
        policy_id, version_id = self._create_policy_version()
        for agent_id, tool_name, correlation_id in [
            ("agent_filter_allow", "view_customer", "corr-filter-allow"),
            ("agent_filter_deny", "delete_customer", "corr-filter-deny"),
        ]:
            response = self.client.post(
                "/api/v1/policy-evaluations/simulate",
                headers=self._headers(correlation_id=correlation_id),
                json={
                    "policy_id": policy_id,
                    "policy_version_id": version_id,
                    "agent_id": agent_id,
                    "action": "mcp.call",
                    "context": {"tool_name": tool_name},
                },
            )
            self.assertEqual(response.status_code, 201, response.text)

        filtered = self.client.get(
            "/api/v1/policy-evaluations",
            headers=self._headers(correlation_id="corr-filter-list"),
            params={"decision": "deny", "mode": "simulate", "agent_id": "agent_filter_deny"},
        )

        self.assertEqual(filtered.status_code, 200, filtered.text)
        rows = filtered.json()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["decision"], "deny")
        self.assertEqual(rows[0]["agent_id"], "agent_filter_deny")
        self.assertEqual(rows[0]["policy_id"], policy_id)

    def test_environment_scoping_prevents_cross_environment_reads(self) -> None:
        policy_id, version_id = self._create_policy_version()
        response = self.client.post(
            "/api/v1/policy-evaluations/simulate",
            headers=self._headers(environment_id="env_second", correlation_id="corr-second-env"),
            json={
                "policy_id": policy_id,
                "policy_version_id": version_id,
                "action": "mcp.call",
                "context": {"tool_name": "view_customer"},
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        second_env_id = response.json()["id"]

        default_list = self.client.get(
            "/api/v1/policy-evaluations",
            headers=self._headers(environment_id="env_default", correlation_id="corr-default-list"),
            params={"correlation_id": "corr-second-env"},
        )
        self.assertEqual(default_list.status_code, 200, default_list.text)
        self.assertEqual(default_list.json(), [])
        default_detail = self.client.get(
            f"/api/v1/policy-evaluations/{second_env_id}",
            headers=self._headers(environment_id="env_default", correlation_id="corr-default-detail"),
        )
        self.assertEqual(default_detail.status_code, 404)


if __name__ == "__main__":
    unittest.main()
