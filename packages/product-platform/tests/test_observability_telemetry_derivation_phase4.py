from __future__ import annotations

import unittest
from typing import Any

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import DEMO_ADMIN_USER_ID, DEMO_ENV_ID, DEMO_ORG_ID, seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.tool_gateway.runtime_audit import ToolRuntimeActionCreate, ToolRuntimeActionRepository


TRACE_ID = "77777777777777777777777777777777"


class ObservabilityTelemetryDerivationPhase4Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection)
        self.app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-05-01T00:00:00Z",
                dev_login_allowed_emails=["observability@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "observability@example.com", "roles": ["Platform Admin"]},
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.token = login.json()["access_token"]

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": DEMO_ENV_ID,
        }

    def test_manual_slo_and_cost_ingestion_are_labeled_manual(self) -> None:
        slo = self.client.post(
            "/api/v1/observability/slo",
            headers=self._headers(),
            json={
                "name": "Manual import SLO",
                "target_type": "agent",
                "target_id": "agent_observability_phase4",
                "sli": "task_success_rate",
                "target_value": 0.99,
                "window": "30d",
            },
        )
        self.assertEqual(slo.status_code, 201, slo.text)

        measurement = self.client.post(
            f"/api/v1/observability/slo/{slo.json()['id']}/measurements",
            headers=self._headers(),
            json={"value": 0.995, "good_events": 199, "total_events": 200},
        )
        self.assertEqual(measurement.status_code, 201, measurement.text)
        self.assertEqual(measurement.json()["source"], "manual")
        self.assertIsNone(measurement.json()["source_resource_type"])
        self.assertIsNone(measurement.json()["source_resource_id"])

        cost = self.client.post(
            "/api/v1/observability/cost-events",
            headers=self._headers(),
            json={
                "target_type": "agent",
                "target_id": "agent_observability_phase4",
                "provider": "openai",
                "model": "gpt-5.4",
                "amount": 0.12,
                "units": 120,
                "correlation_id": "corr-manual-phase4",
            },
        )
        self.assertEqual(cost.status_code, 201, cost.text)
        self.assertEqual(cost.json()["source"], "manual")
        self.assertIsNone(cost.json()["source_resource_type"])
        self.assertIsNone(cost.json()["source_resource_id"])

    def test_runtime_tool_telemetry_derives_slo_cost_and_incidents(self) -> None:
        slo = self.client.post(
            "/api/v1/observability/slo",
            headers=self._headers(),
            json={
                "name": "Latency under 100ms",
                "target_type": "agent",
                "target_id": "agent_observability_phase4",
                "sli": "latency_under_100ms",
                "target_value": 0.95,
                "window": "1h",
            },
        )
        self.assertEqual(slo.status_code, 201, slo.text)
        budget = self.client.post(
            "/api/v1/observability/cost-budgets",
            headers=self._headers(),
            json={
                "target_type": "agent",
                "target_id": "agent_observability_phase4",
                "period": "monthly",
                "amount_limit": 1.0,
                "action_on_breach": "throttle",
            },
        )
        self.assertEqual(budget.status_code, 201, budget.text)

        self._create_tool_action(
            request_id="req-phase4-fast-model",
            action_status="completed",
            latency_ms=80.0,
            created_at="2026-05-20T10:00:00+00:00",
            response_summary={
                "model_usage": {
                    "provider": "openai",
                    "model": "gpt-5.4",
                    "cost_usd": 1.2,
                    "total_tokens": 1200,
                }
            },
        )
        self._create_tool_action(
            request_id="req-phase4-slow-failed",
            action_status="upstream_failed",
            latency_ms=250.0,
            created_at="2026-05-20T10:01:00+00:00",
            response_summary={"error": "timeout"},
        )

        slos = self.client.get("/api/v1/observability/slo", headers=self._headers())
        self.assertEqual(slos.status_code, 200, slos.text)
        measurements = slos.json()[0]["measurements"]
        self.assertGreaterEqual(len(measurements), 2)
        latest = measurements[0]
        self.assertEqual(latest["slo_id"], slo.json()["id"])
        self.assertEqual(latest["source"], "runtime_telemetry")
        self.assertEqual(latest["source_resource_type"], "telemetry_window")
        self.assertEqual(latest["good_events"], 1)
        self.assertEqual(latest["total_events"], 2)
        self.assertEqual(latest["status"], "exhausted")
        self.assertEqual(latest["metadata"]["latency_threshold_ms"], 100)

        costs = self.client.get("/api/v1/observability/costs", headers=self._headers())
        self.assertEqual(costs.status_code, 200, costs.text)
        self.assertEqual(costs.json()["budgets"][0]["status"], "breached")
        self.assertEqual(costs.json()["events"][0]["source"], "runtime_telemetry")
        self.assertEqual(costs.json()["events"][0]["source_resource_type"], "tool_runtime_action")
        self.assertEqual(costs.json()["events"][0]["provider"], "openai")
        self.assertEqual(costs.json()["events"][0]["model"], "gpt-5.4")
        self.assertEqual(costs.json()["events"][0]["amount"], 1.2)
        self.assertEqual(costs.json()["events"][0]["units"], 1200)
        self.assertEqual(costs.json()["events"][0]["trace_id"], TRACE_ID)

        incidents = self.client.get("/api/v1/observability/incidents", headers=self._headers())
        self.assertEqual(incidents.status_code, 200, incidents.text)
        self.assertEqual({incident["source"] for incident in incidents.json()}, {"runtime_telemetry"})
        self.assertIn("slo_objective", {incident["source_resource_type"] for incident in incidents.json()})
        self.assertIn("cost_budget", {incident["source_resource_type"] for incident in incidents.json()})
        self.assertTrue(all(incident["status"] == "open" for incident in incidents.json()))

        derived = self.client.post(
            "/api/v1/observability/telemetry/derive",
            headers=self._headers(),
            json={
                "target_type": "agent",
                "target_id": "agent_observability_phase4",
                "create_incidents": True,
            },
        )
        self.assertEqual(derived.status_code, 201, derived.text)
        self.assertEqual(derived.json()["skipped_duplicate_cost_events"], 1)

    def _create_tool_action(
        self,
        *,
        request_id: str,
        action_status: str,
        latency_ms: float,
        created_at: str,
        response_summary: dict[str, Any],
    ) -> None:
        with self.database.transaction() as connection:
            repository = ToolRuntimeActionRepository(connection, DEMO_ORG_ID, DEMO_ENV_ID)
            repository.create_action(
                ToolRuntimeActionCreate(
                    request_id=request_id,
                    correlation_id="corr-phase4-telemetry",
                    trace_id=TRACE_ID,
                    span_id="8888888888888888",
                    agent_id="agent_observability_phase4",
                    action_status=action_status,
                    latency_ms=latency_ms,
                    payload_summary={"tool_name": "llm.invoke"},
                    response_summary=response_summary,
                ),
                created_at=created_at,
            )

    def _insert_agent(self, connection: Any) -> None:
        now = "2026-05-20T00:00:00+00:00"
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
                "agent_observability_phase4",
                DEMO_ORG_ID,
                DEMO_ENV_ID,
                "Observability Phase 4 Agent",
                "Telemetry derivation fixture.",
                "langgraph",
                "service",
                DEMO_ADMIN_USER_ID,
                DEMO_ADMIN_USER_ID,
                "active",
                91,
                "trusted",
                now,
                now,
            ),
        )


if __name__ == "__main__":
    unittest.main()
