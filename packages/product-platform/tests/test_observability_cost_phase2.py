from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.observability.costs import evaluate_cost_budget


class ObservabilityCostPhase2Tests(unittest.TestCase):
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
                dev_login_allowed_emails=["cost@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "cost@example.com", "roles": ["Platform Admin"]},
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.token = login.json()["access_token"]

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
        }

    def _create_budget(self, *, amount_limit: float = 1.0, action: str = "kill_switch") -> dict:
        response = self.client.post(
            "/api/v1/observability/cost-budgets",
            headers=self._headers(),
            json={
                "target_type": "agent",
                "target_id": "agent_demo",
                "period": "monthly",
                "amount_limit": amount_limit,
                "action_on_breach": action,
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_breach_action_computed(self) -> None:
        result = evaluate_cost_budget(amount_limit=100, used_amount=125, action_on_breach="throttle")

        self.assertEqual(result.status, "breached")
        self.assertEqual(result.breach_action, "throttle")
        self.assertEqual(result.usage_ratio, 1.25)

    def test_create_budget(self) -> None:
        budget = self._create_budget(amount_limit=10, action="warn")

        self.assertEqual(budget["target_type"], "agent")
        self.assertEqual(budget["used_amount"], 0)
        self.assertEqual(budget["status"], "active")

        listed = self.client.get("/api/v1/observability/cost-budgets", headers=self._headers())
        self.assertEqual(listed.status_code, 200, listed.text)
        self.assertEqual(listed.json()[0]["id"], budget["id"])

    def test_cost_event_updates_budget_used_amount(self) -> None:
        budget = self._create_budget(amount_limit=1.0, action="kill_switch")
        event = self.client.post(
            "/api/v1/observability/cost-events",
            headers=self._headers(),
            json={
                "target_type": "agent",
                "target_id": "agent_demo",
                "provider": "openai",
                "model": "gpt-5.4",
                "amount": 1.25,
                "units": 1000,
                "correlation_id": "corr_cost_1",
                "created_at": "2026-05-01T00:20:00+00:00",
            },
        )
        self.assertEqual(event.status_code, 201, event.text)
        self.assertEqual(event.json()["correlation_id"], "corr_cost_1")

        budgets = self.client.get("/api/v1/observability/cost-budgets", headers=self._headers())
        self.assertEqual(budgets.status_code, 200, budgets.text)
        updated = next(item for item in budgets.json() if item["id"] == budget["id"])
        self.assertEqual(updated["used_amount"], 1.25)
        self.assertEqual(updated["status"], "breached")
        self.assertEqual(updated["breach_action"], "kill_switch")

        dashboard = self.client.get("/api/v1/observability/costs", headers=self._headers())
        self.assertEqual(dashboard.status_code, 200, dashboard.text)
        self.assertEqual(dashboard.json()["total_amount"], 1.25)
        self.assertEqual(dashboard.json()["by_provider"]["openai"], 1.25)
        self.assertEqual(dashboard.json()["by_model"]["gpt-5.4"], 1.25)


if __name__ == "__main__":
    unittest.main()
