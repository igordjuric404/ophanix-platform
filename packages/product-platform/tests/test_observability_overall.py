from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.audit.events import AuditEventEnvelope
from product_platform.audit.store import AuditEventRepository
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


class ObservabilityOverallTests(unittest.TestCase):
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
            "X-Environment-ID": "env_default",
        }

    def test_overall_observability_dashboard_flow(self) -> None:
        slo = self.client.post(
            "/api/v1/observability/slo",
            headers=self._headers(),
            json={
                "name": "Demo agent task success",
                "target_type": "agent",
                "target_id": "agent_demo",
                "sli": "task_success_rate",
                "target_value": 0.99,
                "window": "30d",
            },
        )
        self.assertEqual(slo.status_code, 201, slo.text)
        slo_id = slo.json()["id"]

        healthy = self.client.post(
            f"/api/v1/observability/slo/{slo_id}/measurements",
            headers=self._headers(),
            json={"value": 0.995, "good_events": 199, "total_events": 200},
        )
        self.assertEqual(healthy.status_code, 201, healthy.text)
        degraded = self.client.post(
            f"/api/v1/observability/slo/{slo_id}/measurements",
            headers=self._headers(),
            json={"value": 0.95, "good_events": 95, "total_events": 100},
        )
        self.assertEqual(degraded.status_code, 201, degraded.text)
        self.assertEqual(degraded.json()["status"], "exhausted")

        budget = self.client.post(
            "/api/v1/observability/cost-budgets",
            headers=self._headers(),
            json={
                "target_type": "agent",
                "target_id": "agent_demo",
                "period": "monthly",
                "amount_limit": 1.0,
                "action_on_breach": "throttle",
            },
        )
        self.assertEqual(budget.status_code, 201, budget.text)
        cost = self.client.post(
            "/api/v1/observability/cost-events",
            headers=self._headers(),
            json={
                "target_type": "agent",
                "target_id": "agent_demo",
                "provider": "openai",
                "model": "gpt-5.4",
                "amount": 1.2,
                "units": 1200,
                "correlation_id": "corr_observability_overall",
            },
        )
        self.assertEqual(cost.status_code, 201, cost.text)

        with self.database.transaction() as connection:
            repository = AuditEventRepository(connection)
            first = repository.insert(
                AuditEventEnvelope(
                    organization_id="org_default",
                    environment_id="env_default",
                    event_type="policy.decision",
                    source_component="policy-engine",
                    actor_type="system",
                    resource_type="policy",
                    resource_id="pol_default",
                    decision="deny",
                    severity="critical",
                    correlation_id="corr_observability_overall",
                    payload_json={"reason": "repeated denials"},
                )
            )
            second = repository.insert(
                AuditEventEnvelope(
                    organization_id="org_default",
                    environment_id="env_default",
                    event_type="mcp.call",
                    source_component="mcp-proxy",
                    actor_type="agent",
                    resource_type="mcp_server",
                    resource_id="mcp_demo",
                    decision="deny",
                    severity="warning",
                    correlation_id="corr_observability_overall",
                    payload_json={"tool": "dangerous_tool"},
                )
            )

        incident = self.client.post(
            "/api/v1/observability/incidents/from-event",
            headers=self._headers(),
            json={"source_event_id": first.id, "title": "Repeated denials"},
        )
        self.assertEqual(incident.status_code, 201, incident.text)
        self.assertIn(second.id, incident.json()["related_event_ids"])

        slos = self.client.get("/api/v1/observability/slo", headers=self._headers())
        self.assertEqual(slos.status_code, 200, slos.text)
        self.assertEqual(slos.json()[0]["status"], "exhausted")
        self.assertGreaterEqual(len(slos.json()[0]["measurements"]), 2)

        costs = self.client.get("/api/v1/observability/costs", headers=self._headers())
        self.assertEqual(costs.status_code, 200, costs.text)
        self.assertEqual(costs.json()["total_amount"], 1.2)
        self.assertEqual(costs.json()["budgets"][0]["status"], "breached")
        self.assertEqual(costs.json()["budgets"][0]["breach_action"], "throttle")

        incidents = self.client.get("/api/v1/observability/incidents", headers=self._headers())
        self.assertEqual(incidents.status_code, 200, incidents.text)
        self.assertEqual(incidents.json()[0]["id"], incident.json()["id"])
        self.assertIn(first.id, incidents.json()[0]["related_event_ids"])
        self.assertIn(second.id, incidents.json()[0]["related_event_ids"])


if __name__ == "__main__":
    unittest.main()
