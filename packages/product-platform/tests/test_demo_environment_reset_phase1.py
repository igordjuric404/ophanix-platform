from __future__ import annotations

import unittest

from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.demo.catalog import CUSTOMER_SUPPORT_REFUND_SCENARIO
from product_platform.demo.repository import DemoScenarioRepository
from product_platform.demo.reset import demo_reset_scope, query_demo_markers


class DemoEnvironmentResetPhase1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)

    def test_unit_reset_scope_includes_expected_demo_tables(self) -> None:
        scope = demo_reset_scope()

        self.assertEqual(
            scope.clear_order,
            ("demo_step_runs", "demo_runs"),
        )
        self.assertEqual(scope.marker_tables, ("demo_runs", "demo_step_runs"))

    def test_unit_preserved_tables_are_excluded_from_clear_order(self) -> None:
        scope = demo_reset_scope()

        preserved = set(scope.preserved_tables)
        self.assertIn("users", preserved)
        self.assertIn("organizations", preserved)
        self.assertIn("environments", preserved)
        self.assertIn("provider_credentials", preserved)
        self.assertIn("demo_scenarios", preserved)
        self.assertIn("demo_steps", preserved)
        self.assertTrue(preserved.isdisjoint(scope.clear_order))

    def test_integration_demo_marker_counts_are_queryable(self) -> None:
        with self.database.transaction() as connection:
            repository = DemoScenarioRepository(connection, "org_default", "env_default")
            repository.create_run(
                CUSTOMER_SUPPORT_REFUND_SCENARIO["id"],
                started_by="user_admin",
            )

            counts = query_demo_markers(
                connection,
                organization_id="org_default",
                environment_id="env_default",
            )

        self.assertEqual(counts["demo_runs"], 1)
        self.assertEqual(
            counts["demo_step_runs"],
            len(CUSTOMER_SUPPORT_REFUND_SCENARIO["steps"]),
        )


if __name__ == "__main__":
    unittest.main()
