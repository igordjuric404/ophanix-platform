from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.audit.store import AuditEventQuery, AuditEventRepository
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.runtime.models import RuntimeActionCreateRequest
from product_platform.runtime.rings import RuntimeRingAdapter


class RuntimeSessionsPhase2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection, "agent_high", "High Trust Runtime Agent", "active", 820)
            self._insert_agent(connection, "agent_low", "Low Trust Runtime Agent", "active", 500)
        self.app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-05-01T00:00:00Z",
                dev_login_allowed_emails=["platform@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "platform@example.com", "roles": ["Platform Admin"]},
        )
        self.assertEqual(login.status_code, 200)
        self.token = login.json()["access_token"]

    def _headers(self, correlation_id: str = "corr-runtime-action") -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
            "X-Correlation-ID": correlation_id,
        }

    def _insert_agent(self, connection, agent_id: str, name: str, status: str, score: int) -> None:
        now = "2026-05-01T00:00:00+00:00"
        connection.execute(
            """
            INSERT INTO agents (
                id, organization_id, environment_id, name, description, framework,
                runtime_type, owner_user_id, sponsor_user_id, status, trust_score,
                trust_tier, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                agent_id,
                "org_default",
                "env_default",
                name,
                "Runtime ring decision test agent",
                "langgraph",
                "service",
                "user_admin",
                "user_admin",
                status,
                score,
                "trusted",
                now,
                now,
            ),
        )

    def _create_session(self, agent_id: str) -> dict:
        created = self.client.post(
            "/api/v1/runtime/sessions",
            headers=self._headers(),
            json={"agent_id": agent_id, "ring": 2},
        )
        self.assertEqual(created.status_code, 201)
        return created.json()

    def test_privileged_action_maps_to_required_ring_one(self) -> None:
        body = RuntimeActionCreateRequest(
            action_name="billing.issue_refund",
            resource_type="payment",
            reversibility="none",
            is_read_only=False,
        )

        self.assertEqual(RuntimeRingAdapter().classify_required_ring(body), 1)

    def test_low_trust_fails_ring_one_action(self) -> None:
        body = RuntimeActionCreateRequest(
            action_name="billing.issue_refund",
            resource_type="payment",
            reversibility="none",
            is_read_only=False,
        )

        result = RuntimeRingAdapter().evaluate(body, agent_trust_score=500)

        self.assertEqual(result.required_ring, 1)
        self.assertEqual(result.assigned_ring, 3)
        self.assertEqual(result.decision, "denied")
        self.assertIn("insufficient", result.reason)

    def test_runtime_action_persists_ring_decision_and_audit(self) -> None:
        session = self._create_session("agent_low")

        action = self.client.post(
            f"/api/v1/runtime/sessions/{session['id']}/actions",
            headers=self._headers("corr-runtime-denied"),
            json={
                "action_name": "billing.issue_refund",
                "resource_type": "payment",
                "reversibility": "none",
                "is_read_only": False,
            },
        )

        self.assertEqual(action.status_code, 201)
        payload = action.json()
        self.assertEqual(payload["decision"], "denied")
        self.assertEqual(payload["required_ring"], 1)
        self.assertEqual(payload["ring_decision"]["agent_trust_score"], 500)
        self.assertEqual(payload["ring_decision"]["assigned_ring"], 3)

        decisions = self.client.get(
            "/api/v1/runtime/ring-decisions?result=denied",
            headers=self._headers(),
        )
        self.assertEqual(decisions.status_code, 200)
        self.assertEqual(decisions.json()[0]["runtime_action_id"], payload["id"])

        detail = self.client.get(f"/api/v1/runtime/sessions/{session['id']}", headers=self._headers())
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["actions"][0]["ring_decision"]["result"], "denied")

        events = AuditEventRepository(self.database.connect()).query(
            AuditEventQuery(
                organization_id="org_default",
                environment_id="env_default",
                resource_type="runtime_action",
                resource_id=payload["id"],
            )
        )
        self.assertEqual(events[0].event_type, "runtime.action")
        self.assertEqual(events[0].decision, "denied")
        self.assertEqual(events[0].correlation_id, "corr-runtime-denied")


if __name__ == "__main__":
    unittest.main()
