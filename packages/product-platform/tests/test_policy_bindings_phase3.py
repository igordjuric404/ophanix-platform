from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.audit.store import AuditEventQuery, AuditEventRepository
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.policies.bindings import PolicyBindingRepository
from product_platform.policies.models import PolicyBindingResolutionContext


POLICY_BODY = """version: "1.0"
name: rollout-policy
rules:
  - name: block_shell
    condition:
      field: tool_name
      operator: eq
      value: run_shell
    action: deny
"""


class PolicyBindingsPhase3PromotionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            now = "2026-05-01T00:00:00+00:00"
            connection.execute(
                """
                INSERT INTO agents (
                    id, organization_id, environment_id, name, description, framework,
                    runtime_type, owner_user_id, sponsor_user_id, status, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "agent_default",
                    "org_default",
                    "env_default",
                    "Claims Agent",
                    "",
                    "langgraph",
                    "service",
                    "owner",
                    "sponsor",
                    "active",
                    now,
                    now,
                ),
            )
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
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
            "X-Correlation-ID": "corr-policy-rollout",
        }

    def _create_binding(self, *, mode: str = "shadow", rollout_percentage: int = 10) -> dict:
        policy = self.client.post(
            "/api/v1/policies",
            headers=self._headers(),
            json={"name": "Rollout Guard", "scope": "agent"},
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
                "target_type": "agent",
                "target_id": "agent_default",
                "mode": mode,
                "rollout_percentage": rollout_percentage,
            },
        )
        self.assertEqual(binding.status_code, 201)
        return binding.json()

    def test_api_promote_shadow_to_enforce(self) -> None:
        binding = self._create_binding(mode="shadow", rollout_percentage=10)

        promoted = self.client.post(
            f"/api/v1/policy-bindings/{binding['id']}/promote",
            headers=self._headers(),
            json={"mode": "enforce", "rollout_percentage": 100, "reason": "ready for enforcement"},
        )
        row = self.database.connect().execute(
            "SELECT * FROM policy_rollout_events WHERE binding_id = ?",
            (binding["id"],),
        ).fetchone()

        self.assertEqual(promoted.status_code, 200)
        self.assertEqual(promoted.json()["mode"], "enforce")
        self.assertEqual(promoted.json()["rollout_percentage"], 100)
        self.assertIsNotNone(row)
        self.assertEqual(row["previous_percentage"], 10)
        self.assertEqual(row["next_percentage"], 100)
        self.assertEqual(row["reason"], "ready for enforcement")
        events = AuditEventRepository(self.database.connect()).query(
            AuditEventQuery(
                organization_id="org_default",
                event_type="policy.binding.promoted",
                policy_id=promoted.json()["policy_id"],
            )
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].resource_id, binding["id"])
        self.assertEqual(events[0].payload_json["reason"], "ready for enforcement")
        self.assertEqual(events[0].correlation_id, "corr-policy-rollout")

    def test_api_exception_requires_expiration_or_explicit_no_expiry_permission(self) -> None:
        binding = self._create_binding()

        missing_expiry = self.client.post(
            f"/api/v1/policy-bindings/{binding['id']}/exceptions",
            headers=self._headers(),
            json={"reason": "too broad"},
        )
        approved = self.client.post(
            f"/api/v1/policy-bindings/{binding['id']}/exceptions",
            headers=self._headers(),
            json={"reason": "board-approved standing exception", "no_expiry_approved": True},
        )

        self.assertEqual(missing_expiry.status_code, 422)
        self.assertEqual(approved.status_code, 201)
        self.assertIsNone(approved.json()["expires_at"])
        events = AuditEventRepository(self.database.connect()).query(
            AuditEventQuery(
                organization_id="org_default",
                event_type="policy.binding.exception_created",
                resource_id=binding["id"],
            )
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].payload_json["exception_id"], approved.json()["id"])
        self.assertEqual(events[0].payload_json["reason"], "board-approved standing exception")
        self.assertEqual(events[0].correlation_id, "corr-policy-rollout")

    def test_integration_expired_exception_no_longer_applies(self) -> None:
        binding = self._create_binding(rollout_percentage=100)
        exception = self.client.post(
            f"/api/v1/policy-bindings/{binding['id']}/exceptions",
            headers=self._headers(),
            json={"reason": "short maintenance", "expires_at": "2026-05-01T01:00:00+00:00"},
        )
        self.assertEqual(exception.status_code, 201)

        repository = PolicyBindingRepository(
            self.database.connect(),
            "org_default",
            "env_default",
        )
        context = PolicyBindingResolutionContext(
            organization_id="org_default",
            environment_id="env_default",
            target_type="agent",
            target_id="agent_default",
            agent_id="agent_default",
            correlation_id="corr-expired-exception",
        )
        before_expiry = repository.resolve_bindings(context, now="2026-05-01T00:30:00+00:00")
        after_expiry = repository.resolve_bindings(context, now="2026-05-01T02:00:00+00:00")

        self.assertEqual(before_expiry, [])
        self.assertEqual([row["id"] for row in after_expiry], [binding["id"]])


if __name__ == "__main__":
    unittest.main()
