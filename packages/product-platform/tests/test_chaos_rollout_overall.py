from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


class ChaosRolloutOverallValidationTests(unittest.TestCase):
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
                dev_login_allowed_emails=["overall-chaos@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "overall-chaos@example.com", "roles": ["Platform Admin"]},
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.token = login.json()["access_token"]

    def _headers(self, correlation_id: str | None = None) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
        }
        if correlation_id:
            headers["X-Correlation-ID"] = correlation_id
        return headers

    def test_chaos_slo_impact_blocks_rollout_advance(self) -> None:
        slo = self.client.post(
            "/api/v1/observability/slo",
            headers=self._headers(),
            json={
                "name": "Demo task success",
                "target_type": "agent",
                "target_id": "agent_demo",
                "sli": "task_success_rate",
                "target_value": 0.99,
                "window": "30d",
            },
        )
        self.assertEqual(slo.status_code, 201, slo.text)

        experiment = self.client.post(
            "/api/v1/observability/chaos/experiments",
            headers=self._headers(),
            json={
                "name": "Safe latency experiment",
                "fault_type": "latency",
                "target_type": "agent",
                "target_id": "agent_demo",
                "blast_radius": {"max_agents": 1, "environment": "demo"},
                "guardrails": {"max_error_rate": 0.05, "max_duration_seconds": 60},
            },
        )
        self.assertEqual(experiment.status_code, 201, experiment.text)

        run = self.client.post(
            f"/api/v1/observability/chaos/experiments/{experiment.json()['id']}/run",
            headers=self._headers("corr_overall_chaos"),
            json={"observed_metrics": {"error_rate": 0.2, "duration_seconds": 10}},
        )
        self.assertEqual(run.status_code, 201, run.text)
        self.assertEqual(run.json()["status"], "stopped")
        self.assertTrue(run.json()["result"]["guardrail_breached"])

        slos = self.client.get("/api/v1/observability/slo", headers=self._headers())
        self.assertEqual(slos.status_code, 200, slos.text)
        self.assertEqual(slos.json()[0]["status"], "exhausted")
        self.assertEqual(slos.json()[0]["measurements"][0]["metadata"]["source"], "chaos_run")

        incidents = self.client.get(
            "/api/v1/observability/incidents",
            headers=self._headers(),
        )
        self.assertEqual(incidents.status_code, 200, incidents.text)
        self.assertEqual(incidents.json()[0]["status"], "open")
        self.assertEqual(incidents.json()[0]["correlation_id"], "corr_overall_chaos")

        rollout = self.client.post(
            "/api/v1/observability/rollouts",
            headers=self._headers(),
            json={
                "name": "Guarded canary",
                "target_type": "agent",
                "target_id": "agent_demo",
                "strategy": "canary",
                "config": {
                    "stages": [5, 25, 100],
                    "gates": {
                        "require_slo_healthy": True,
                        "block_on_open_incident": True,
                    },
                },
            },
        )
        self.assertEqual(rollout.status_code, 201, rollout.text)

        advance = self.client.post(
            f"/api/v1/observability/rollouts/{rollout.json()['id']}/advance",
            headers=self._headers(),
            json={"metrics": {}},
        )
        self.assertEqual(advance.status_code, 200, advance.text)
        blocked = advance.json()
        self.assertEqual(blocked["status"], "blocked")
        self.assertEqual(blocked["current_stage"], 0)
        self.assertEqual(blocked["events"][0]["decision"], "blocked")
        self.assertIn("slo_unhealthy", blocked["events"][0]["metrics"]["blocked_reasons"])
        self.assertIn("open_incident", blocked["events"][0]["metrics"]["blocked_reasons"])


if __name__ == "__main__":
    unittest.main()
