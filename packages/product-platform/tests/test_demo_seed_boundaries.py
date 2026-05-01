from __future__ import annotations

import unittest

from product_platform.db.seed import DEMO_ADMIN_USER_ID, seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.demo.baseline import demo_baseline_status
from product_platform.demo.reset import DemoEnvironmentResetService, demo_reset_run_response


class DemoSeedBoundaryTests(unittest.TestCase):
    def test_generic_seed_does_not_insert_demo_baseline_agents_or_mcp(self) -> None:
        database = create_migrated_test_database()
        with database.transaction() as connection:
            seed_demo_data(connection)
            seed_demo_data(connection)
            counts = _counts(connection)
            baseline = demo_baseline_status(
                connection,
                organization_id="org_default",
                environment_id="env_default",
            )

        self.assertEqual(counts["agents"], 0)
        self.assertEqual(counts["mcp_servers"], 0)
        self.assertEqual(counts["policy_placeholders"], 2)
        self.assertEqual(counts["demo_scenarios"], 1)
        self.assertEqual(baseline.overall_status, "degraded")
        self.assertIn("agent_demo_support", baseline.missing_items)
        self.assertIn("mcp_demo_refund", baseline.missing_items)

    def test_baseline_seed_is_idempotent_and_healthy_when_explicit(self) -> None:
        database = create_migrated_test_database()
        with database.transaction() as connection:
            seed_demo_data(connection, include_baseline=True)
            seed_demo_data(connection, include_baseline=True)
            counts = _counts(connection)
            baseline = demo_baseline_status(
                connection,
                organization_id="org_default",
                environment_id="env_default",
            )

        self.assertEqual(counts["agents"], 3)
        self.assertEqual(counts["mcp_servers"], 1)
        self.assertEqual(baseline.overall_status, "healthy")
        self.assertEqual(baseline.missing_items, [])

    def test_demo_reset_explicitly_restores_baseline_fixtures(self) -> None:
        database = create_migrated_test_database()
        with database.transaction() as connection:
            seed_demo_data(connection)
            reset = DemoEnvironmentResetService(
                connection,
                "org_default",
                "env_default",
            ).reset(requested_by=DEMO_ADMIN_USER_ID)
            response = demo_reset_run_response(reset)
            baseline = demo_baseline_status(
                connection,
                organization_id="org_default",
                environment_id="env_default",
            )

        self.assertEqual(response.status, "succeeded")
        self.assertEqual(response.summary["seeded"]["agents"], 3)
        self.assertEqual(response.summary["seeded"]["mcp_servers"], 1)
        self.assertEqual(baseline.overall_status, "healthy")


def _counts(connection) -> dict[str, int]:
    return {
        "agents": int(connection.execute("SELECT COUNT(*) AS count FROM agents").fetchone()["count"]),
        "mcp_servers": int(connection.execute("SELECT COUNT(*) AS count FROM mcp_servers").fetchone()["count"]),
        "policy_placeholders": int(
            connection.execute("SELECT COUNT(*) AS count FROM policy_placeholders").fetchone()["count"]
        ),
        "demo_scenarios": int(
            connection.execute("SELECT COUNT(*) AS count FROM demo_scenarios").fetchone()["count"]
        ),
    }


if __name__ == "__main__":
    unittest.main()
