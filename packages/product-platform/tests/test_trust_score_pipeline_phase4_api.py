from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.audit.events import AuditEventEnvelope
from product_platform.audit.store import AuditEventRepository
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


class TrustScorePipelinePhase4ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection, "agent_api", "API Agent")
        self.app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-05-01T00:00:00Z",
                dev_login_allowed_emails=["admin@example.com", "viewer@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "admin@example.com", "roles": ["Platform Admin"]},
        )
        self.assertEqual(login.status_code, 200)
        self.token = login.json()["access_token"]

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
        }

    def _headers_for_role(self, email: str, role: str) -> dict[str, str]:
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": email, "roles": [role]},
        )
        self.assertEqual(login.status_code, 200, login.text)
        return {
            "Authorization": f"Bearer {login.json()['access_token']}",
            "X-Environment-ID": "env_default",
        }

    def _insert_agent(self, connection, agent_id: str, name: str) -> None:
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
                agent_id,
                "org_default",
                "env_default",
                name,
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

    def _insert_policy_allow_event(self) -> None:
        with self.database.transaction() as connection:
            AuditEventRepository(connection).insert(
                AuditEventEnvelope(
                    organization_id="org_default",
                    environment_id="env_default",
                    event_type="policy.decision",
                    source_component="policy-engine",
                    actor_type="agent",
                    agent_id="agent_api",
                    decision="allow",
                    resource_type="policy",
                    resource_id="policy_1",
                    payload_json={},
                )
            )

    def test_trust_api_recalculates_and_lists_scores_events_and_rules(self) -> None:
        self._insert_policy_allow_event()

        recalc = self.client.post(
            "/api/v1/trust/recalculate",
            headers=self._headers(),
            json={"agent_id": "agent_api"},
        )
        scores = self.client.get("/api/v1/trust/scores", headers=self._headers())
        score = self.client.get("/api/v1/trust/scores/agent_api", headers=self._headers())
        events = self.client.get(
            "/api/v1/trust/events?dimension=policy_compliance",
            headers=self._headers(),
        )
        rules = self.client.get("/api/v1/trust/rules", headers=self._headers())

        self.assertEqual(recalc.status_code, 201)
        self.assertEqual(recalc.json()["status"], "completed")
        self.assertEqual(scores.status_code, 200)
        self.assertEqual(scores.json()[0]["agent_name"], "API Agent")
        self.assertEqual(score.status_code, 200)
        self.assertEqual(score.json()["score"], 508)
        self.assertEqual(events.status_code, 200)
        self.assertEqual(events.json()[0]["source_event_id"][:4], "evt_")
        self.assertEqual(rules.status_code, 200)
        self.assertIn("policy.decision.allow", [rule["event_type"] for rule in rules.json()])

    def test_trust_recalculation_rejects_read_only_users(self) -> None:
        response = self.client.post(
            "/api/v1/trust/recalculate",
            headers=self._headers_for_role("viewer@example.com", "Viewer"),
            json={"agent_id": "agent_api"},
        )

        self.assertEqual(response.status_code, 403)

    def test_trust_rule_patch_updates_enabled_state(self) -> None:
        rules = self.client.get("/api/v1/trust/rules", headers=self._headers())
        self.assertEqual(rules.status_code, 200)
        allow_rule = [
            rule for rule in rules.json() if rule["event_type"] == "policy.decision.allow"
        ][0]

        patched = self.client.patch(
            f"/api/v1/trust/rules/{allow_rule['id']}",
            headers=self._headers(),
            json={"enabled": False},
        )

        self.assertEqual(patched.status_code, 200)
        self.assertEqual(patched.json()["enabled"], False)


if __name__ == "__main__":
    unittest.main()
