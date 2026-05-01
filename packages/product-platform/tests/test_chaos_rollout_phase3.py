from __future__ import annotations

import json
import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.observability.rollouts import evaluate_rollout_gates


class RolloutDefinitionsPhase3Tests(unittest.TestCase):
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
                dev_login_allowed_emails=["rollout@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "rollout@example.com", "roles": ["Platform Admin"]},
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.token = login.json()["access_token"]

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
        }

    def _rollout_payload(self) -> dict:
        return {
            "name": "Demo canary rollout",
            "target_type": "agent",
            "target_id": "agent_demo",
            "strategy": "canary",
            "config": {
                "stages": [5, 25, 100],
                "gates": {
                    "require_slo_healthy": True,
                    "max_policy_deny_rate": 0.02,
                    "min_trust_score": 800,
                    "block_on_open_incident": True,
                },
            },
        }

    def test_create_canary_rollout(self) -> None:
        response = self.client.post(
            "/api/v1/observability/rollouts",
            headers=self._headers(),
            json=self._rollout_payload(),
        )

        self.assertEqual(response.status_code, 201, response.text)
        rollout = response.json()
        self.assertEqual(rollout["strategy"], "canary")
        self.assertEqual(rollout["status"], "ready")
        self.assertEqual(rollout["current_stage"], 0)
        self.assertEqual(rollout["config"]["stages"], [5, 25, 100])
        self.assertEqual(rollout["events"][0]["decision"], "created")

        listed = self.client.get("/api/v1/observability/rollouts", headers=self._headers())
        self.assertEqual(listed.status_code, 200, listed.text)
        self.assertEqual(listed.json()[0]["id"], rollout["id"])

    def test_gate_evaluation_blocks_advance_when_slo_unhealthy(self) -> None:
        evaluation = evaluate_rollout_gates(
            {
                "require_slo_healthy": True,
                "max_policy_deny_rate": 0.02,
                "min_trust_score": 800,
                "block_on_open_incident": True,
            },
            {
                "slo_status": "critical",
                "policy_deny_rate": 0.05,
                "trust_score": 700,
                "open_incidents": 1,
            },
        )

        self.assertEqual(evaluation.decision, "blocked")
        self.assertIn("slo_unhealthy", evaluation.blocked_reasons)
        self.assertIn("policy_deny_rate", evaluation.blocked_reasons)
        self.assertIn("trust_score", evaluation.blocked_reasons)
        self.assertIn("open_incident", evaluation.blocked_reasons)

    def test_rollout_event_stored(self) -> None:
        response = self.client.post(
            "/api/v1/observability/rollouts",
            headers=self._headers(),
            json=self._rollout_payload(),
        )

        self.assertEqual(response.status_code, 201, response.text)
        rollout = response.json()
        with self.database.transaction() as connection:
            event = connection.execute(
                """
                SELECT *
                FROM rollout_events
                WHERE rollout_id = ?
                """,
                (rollout["id"],),
            ).fetchone()
        self.assertIsNotNone(event)
        self.assertEqual(event["stage"], 0)
        self.assertEqual(event["decision"], "created")
        metrics = json.loads(event["metrics_json"])
        self.assertEqual(metrics["strategy"], "canary")
        self.assertEqual(metrics["config"]["gates"]["min_trust_score"], 800)


if __name__ == "__main__":
    unittest.main()
