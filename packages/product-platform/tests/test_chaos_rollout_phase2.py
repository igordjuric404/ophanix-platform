from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.observability.chaos import evaluate_chaos_run


class ChaosRunExecutionPhase2Tests(unittest.TestCase):
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
                dev_login_allowed_emails=["chaos-run@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "chaos-run@example.com", "roles": ["Platform Admin"]},
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

    def _create_experiment(self) -> dict:
        response = self.client.post(
            "/api/v1/observability/chaos/experiments",
            headers=self._headers(),
            json={
                "name": "Demo latency experiment",
                "fault_type": "latency",
                "target_type": "agent",
                "target_id": "agent_demo",
                "blast_radius": {"max_agents": 1, "environment": "demo"},
                "guardrails": {"max_error_rate": 0.05, "max_duration_seconds": 60},
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_run_starts_and_completes(self) -> None:
        experiment = self._create_experiment()

        response = self.client.post(
            f"/api/v1/observability/chaos/experiments/{experiment['id']}/run",
            headers=self._headers(),
            json={"observed_metrics": {"error_rate": 0.01, "duration_seconds": 10}},
        )

        self.assertEqual(response.status_code, 201, response.text)
        run = response.json()
        self.assertEqual(run["experiment_id"], experiment["id"])
        self.assertEqual(run["status"], "completed")
        self.assertFalse(run["result"]["guardrail_breached"])

    def test_guardrail_breach_stops_run(self) -> None:
        result = evaluate_chaos_run(
            {"max_error_rate": 0.05},
            {"error_rate": 0.2},
        )

        self.assertEqual(result.status, "stopped")
        self.assertTrue(result.guardrail_breached)
        self.assertEqual(result.breached_guardrails, ["max_error_rate"])

    def test_run_emits_audit_event(self) -> None:
        experiment = self._create_experiment()

        response = self.client.post(
            f"/api/v1/observability/chaos/experiments/{experiment['id']}/run",
            headers=self._headers("corr_chaos_run"),
            json={"observed_metrics": {"error_rate": 0.01}},
        )

        self.assertEqual(response.status_code, 201, response.text)
        with self.database.transaction() as connection:
            audit = connection.execute(
                """
                SELECT *
                FROM audit_events
                WHERE event_type = ?
                  AND resource_id = ?
                  AND correlation_id = ?
                """,
                ("chaos.run.completed", response.json()["id"], "corr_chaos_run"),
            ).fetchone()
        self.assertIsNotNone(audit)


if __name__ == "__main__":
    unittest.main()
