from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.demo.catalog import CUSTOMER_SUPPORT_REFUND_SCENARIO, seed_demo_scenarios
from product_platform.demo.models import parse_required_services
from product_platform.demo.repository import DemoScenarioRepository


class DemoScenarioCatalogPhase1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
        self.connection = self.database.connect()
        self.repository = DemoScenarioRepository(
            self.connection,
            "org_default",
            "env_default",
        )
        self.app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-05-01T00:00:00Z",
                dev_login_allowed_emails=["demo@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "demo@example.com", "roles": ["Operator"]},
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.token = login.json()["access_token"]

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
        }

    def test_integration_scenario_seed_is_idempotent(self) -> None:
        with self.database.transaction() as connection:
            seed_demo_scenarios(connection, "org_default", "env_default")
            seed_demo_scenarios(connection, "org_default", "env_default")
            scenario_count = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM demo_scenarios
                WHERE organization_id = ? AND environment_id = ?
                """,
                ("org_default", "env_default"),
            ).fetchone()["count"]
            step_count = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM demo_steps
                WHERE scenario_id = ?
                """,
                (CUSTOMER_SUPPORT_REFUND_SCENARIO["id"],),
            ).fetchone()["count"]

        self.assertEqual(scenario_count, 1)
        self.assertEqual(step_count, len(CUSTOMER_SUPPORT_REFUND_SCENARIO["steps"]))

    def test_unit_required_services_list_is_parseable(self) -> None:
        row = self.repository.get_scenario(CUSTOMER_SUPPORT_REFUND_SCENARIO["id"])
        self.assertIsNotNone(row)

        services = parse_required_services(row["required_services_json"])

        service_keys = {service.key for service in services}
        self.assertIn("product-api", service_keys)
        self.assertIn("database", service_keys)
        self.assertIn("worker", service_keys)
        self.assertIn("sample-mcp-server", service_keys)
        self.assertTrue(next(service for service in services if service.key == "product-api").required)
        self.assertFalse(
            next(service for service in services if service.key == "provider-credential").required
        )

    def test_repository_detail_returns_ordered_steps_and_proof_areas(self) -> None:
        detail = self.repository.get_detail("customer-support-refund")

        self.assertIsNotNone(detail)
        self.assertEqual(detail.slug, "customer-support-refund")
        self.assertEqual(
            [step.action_type for step in detail.steps],
            [
                "register_agents",
                "import_policies",
                "register_mcp_server",
                "run_agent_prompt",
                "request_approval",
                "rotate_credential",
                "run_discovery",
                "run_saga",
                "generate_report",
            ],
        )
        proof_areas = {link.area for step in detail.steps for link in step.proof_links}
        self.assertEqual(
            proof_areas,
            {
                "Agents",
                "Policies",
                "MCP",
                "Mesh",
                "Runtime",
                "Trust",
                "Discovery",
                "Compliance",
                "Observability",
            },
        )

    def test_api_lists_seeded_scenario(self) -> None:
        response = self.client.get("/api/v1/demo/scenarios", headers=self._headers())

        self.assertEqual(response.status_code, 200, response.text)
        scenarios = response.json()
        self.assertEqual(len(scenarios), 1)
        self.assertEqual(scenarios[0]["slug"], "customer-support-refund")
        self.assertIn("required_services", scenarios[0])
        self.assertGreaterEqual(len(scenarios[0]["required_services"]), 4)

    def test_api_scenario_detail_returns_ordered_steps(self) -> None:
        response = self.client.get(
            "/api/v1/demo/scenarios/demo_scenario_customer_support_refund",
            headers=self._headers(),
        )

        self.assertEqual(response.status_code, 200, response.text)
        detail = response.json()
        step_orders = [step["step_order"] for step in detail["steps"]]
        self.assertEqual(step_orders, sorted(step_orders))
        self.assertEqual(step_orders, list(range(1, 10)))
        self.assertEqual(detail["steps"][0]["action_type"], "register_agents")
        self.assertEqual(detail["steps"][-1]["action_type"], "generate_report")


if __name__ == "__main__":
    unittest.main()
