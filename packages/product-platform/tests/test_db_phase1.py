from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest

from product_platform.api.settings import Settings
from product_platform.db.migrator import MigrationRunner, connect_database


EXPECTED_MIGRATIONS = [
    "0001",
    "0002",
    "0003",
    "0004",
    "0005",
    "0006",
    "0007",
    "0008",
    "0009",
    "0010",
    "0011",
    "0012",
    "0013",
]


class DatabaseMigrationPhase1Tests(unittest.TestCase):
    def test_migration_applies_to_empty_database(self) -> None:
        connection = sqlite3.connect(":memory:")
        try:
            connection.row_factory = sqlite3.Row
            runner = MigrationRunner(connection)

            applied = runner.apply_all()
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

            self.assertEqual(applied, EXPECTED_MIGRATIONS)
            self.assertIn("organizations", tables)
            self.assertIn("environments", tables)
            self.assertIn("api_keys", tables)
            self.assertIn("audit_events", tables)
            self.assertIn("agents", tables)
            self.assertIn("agent_lifecycle_events", tables)
            self.assertIn("agent_credentials", tables)
            self.assertIn("credential_scopes", tables)
            self.assertIn("credential_rotations", tables)
            self.assertIn("credential_issuers", tables)
            self.assertIn("discovery_targets", tables)
            self.assertIn("discovery_runs", tables)
            self.assertIn("discovery_raw_findings", tables)
            self.assertIn("discovery_findings", tables)
            self.assertIn("discovery_evidence", tables)
            self.assertIn("discovery_suppressions", tables)
            self.assertIn("reconciliation_actions", tables)
            self.assertIn("policies", tables)
            self.assertIn("policy_versions", tables)
            self.assertIn("policy_imports", tables)
            self.assertIn("policy_lint_results", tables)
            self.assertIn("policy_bindings", tables)
            self.assertIn("policy_exceptions", tables)
            self.assertIn("policy_rollout_events", tables)
            self.assertIn("trust_scores", tables)
            self.assertIn("trust_events", tables)
            self.assertIn("trust_rules", tables)
            self.assertIn("trust_recalculation_runs", tables)
            self.assertIn("trust_cards", tables)
            self.assertIn("trust_card_revocations", tables)
            self.assertIn("trust_thresholds", tables)
            self.assertIn("handshake_events", tables)
            self.assertIn("mesh_messages", tables)
            self.assertIn("mesh_handoffs", tables)
            self.assertIn("mesh_topology_snapshots", tables)
            self.assertIn("protocol_bridges", tables)
            self.assertIn("protocol_bridge_routes", tables)
            self.assertIn("protocol_bridge_health_checks", tables)
            self.assertEqual(runner.applied_versions(), EXPECTED_MIGRATIONS)
        finally:
            connection.close()

    def test_migration_can_be_rolled_back(self) -> None:
        connection = sqlite3.connect(":memory:")
        try:
            connection.row_factory = sqlite3.Row
            runner = MigrationRunner(connection)
            runner.apply_all()

            rolled_back = runner.rollback_last()
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

            self.assertEqual(rolled_back, "0013")
            self.assertNotIn("protocol_bridges", tables)
            self.assertNotIn("protocol_bridge_routes", tables)
            self.assertNotIn("protocol_bridge_health_checks", tables)
            self.assertIn("mesh_messages", tables)
            self.assertIn("mesh_handoffs", tables)
            self.assertIn("mesh_topology_snapshots", tables)
            self.assertIn("trust_thresholds", tables)
            self.assertIn("trust_cards", tables)
            self.assertIn("trust_scores", tables)
            self.assertIn("policy_bindings", tables)
            self.assertIn("policy_lint_results", tables)
            self.assertIn("policies", tables)
            self.assertIn("discovery_findings", tables)
            self.assertIn("discovery_targets", tables)
            self.assertIn("agent_credentials", tables)
            self.assertIn("agents", tables)
            self.assertIn("organizations", tables)
            self.assertEqual(
                runner.applied_versions(),
                [
                    "0001",
                    "0002",
                    "0003",
                    "0004",
                    "0005",
                    "0006",
                    "0007",
                    "0008",
                    "0009",
                    "0010",
                    "0011",
                    "0012",
                ],
            )

            rolled_back = runner.rollback_last()
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

            self.assertEqual(rolled_back, "0012")
            self.assertNotIn("mesh_messages", tables)
            self.assertNotIn("mesh_handoffs", tables)
            self.assertNotIn("mesh_topology_snapshots", tables)
            self.assertIn("trust_thresholds", tables)
            self.assertIn("trust_cards", tables)
            self.assertIn("trust_scores", tables)
            self.assertIn("policy_bindings", tables)
            self.assertIn("policy_lint_results", tables)
            self.assertIn("policies", tables)
            self.assertIn("discovery_findings", tables)
            self.assertIn("discovery_targets", tables)
            self.assertIn("agent_credentials", tables)
            self.assertIn("agents", tables)
            self.assertIn("organizations", tables)
            self.assertEqual(
                runner.applied_versions(),
                [
                    "0001",
                    "0002",
                    "0003",
                    "0004",
                    "0005",
                    "0006",
                    "0007",
                    "0008",
                    "0009",
                    "0010",
                    "0011",
                ],
            )

            rolled_back = runner.rollback_last()
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

            self.assertEqual(rolled_back, "0011")
            self.assertNotIn("trust_thresholds", tables)
            self.assertNotIn("handshake_events", tables)
            self.assertIn("trust_cards", tables)
            self.assertIn("trust_scores", tables)
            self.assertIn("policy_bindings", tables)
            self.assertIn("policy_lint_results", tables)
            self.assertIn("policies", tables)
            self.assertIn("discovery_findings", tables)
            self.assertIn("discovery_targets", tables)
            self.assertIn("agent_credentials", tables)
            self.assertIn("agents", tables)
            self.assertIn("organizations", tables)
            self.assertEqual(
                runner.applied_versions(),
                ["0001", "0002", "0003", "0004", "0005", "0006", "0007", "0008", "0009", "0010"],
            )

            rolled_back = runner.rollback_last()
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

            self.assertEqual(rolled_back, "0010")
            self.assertNotIn("trust_cards", tables)
            self.assertIn("trust_scores", tables)
            self.assertIn("policy_bindings", tables)
            self.assertIn("policy_lint_results", tables)
            self.assertIn("policies", tables)
            self.assertIn("discovery_findings", tables)
            self.assertIn("discovery_targets", tables)
            self.assertIn("agent_credentials", tables)
            self.assertIn("agents", tables)
            self.assertIn("organizations", tables)
            self.assertEqual(
                runner.applied_versions(),
                ["0001", "0002", "0003", "0004", "0005", "0006", "0007", "0008", "0009"],
            )

            rolled_back = runner.rollback_last()
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

            self.assertEqual(rolled_back, "0009")
            self.assertNotIn("trust_scores", tables)
            self.assertIn("policy_bindings", tables)
            self.assertIn("policy_lint_results", tables)
            self.assertIn("policies", tables)
            self.assertIn("discovery_findings", tables)
            self.assertIn("discovery_targets", tables)
            self.assertIn("agent_credentials", tables)
            self.assertIn("agents", tables)
            self.assertIn("organizations", tables)
            self.assertEqual(
                runner.applied_versions(),
                ["0001", "0002", "0003", "0004", "0005", "0006", "0007", "0008"],
            )

            rolled_back = runner.rollback_last()
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

            self.assertEqual(rolled_back, "0008")
            self.assertNotIn("policy_bindings", tables)
            self.assertIn("policy_lint_results", tables)
            self.assertIn("policies", tables)
            self.assertIn("discovery_findings", tables)
            self.assertIn("discovery_targets", tables)
            self.assertIn("agent_credentials", tables)
            self.assertIn("agents", tables)
            self.assertIn("organizations", tables)
            self.assertEqual(
                runner.applied_versions(),
                ["0001", "0002", "0003", "0004", "0005", "0006", "0007"],
            )

            rolled_back = runner.rollback_last()
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

            self.assertEqual(rolled_back, "0007")
            self.assertNotIn("policy_lint_results", tables)
            self.assertIn("policies", tables)
            self.assertIn("discovery_findings", tables)
            self.assertIn("discovery_targets", tables)
            self.assertIn("agent_credentials", tables)
            self.assertIn("agents", tables)
            self.assertIn("organizations", tables)
            self.assertEqual(
                runner.applied_versions(),
                ["0001", "0002", "0003", "0004", "0005", "0006"],
            )

            rolled_back = runner.rollback_last()
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

            self.assertEqual(rolled_back, "0006")
            self.assertNotIn("policies", tables)
            self.assertIn("discovery_findings", tables)
            self.assertIn("discovery_targets", tables)
            self.assertIn("agent_credentials", tables)
            self.assertIn("agents", tables)
            self.assertIn("organizations", tables)
            self.assertEqual(runner.applied_versions(), ["0001", "0002", "0003", "0004", "0005"])

            rolled_back = runner.rollback_last()
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

            self.assertEqual(rolled_back, "0005")
            self.assertNotIn("discovery_findings", tables)
            self.assertIn("discovery_targets", tables)
            self.assertIn("agent_credentials", tables)
            self.assertIn("agents", tables)
            self.assertIn("organizations", tables)
            self.assertEqual(runner.applied_versions(), ["0001", "0002", "0003", "0004"])

            rolled_back = runner.rollback_last()
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

            self.assertEqual(rolled_back, "0004")
            self.assertNotIn("discovery_targets", tables)
            self.assertIn("agent_credentials", tables)
            self.assertIn("agents", tables)
            self.assertIn("organizations", tables)
            self.assertEqual(runner.applied_versions(), ["0001", "0002", "0003"])

            rolled_back = runner.rollback_last()
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

            self.assertEqual(rolled_back, "0003")
            self.assertNotIn("agent_credentials", tables)
            self.assertIn("agents", tables)
            self.assertIn("organizations", tables)
            self.assertEqual(runner.applied_versions(), ["0001", "0002"])

            rolled_back = runner.rollback_last()
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

            self.assertEqual(rolled_back, "0002")
            self.assertNotIn("agents", tables)
            self.assertIn("organizations", tables)
            self.assertEqual(runner.applied_versions(), ["0001"])

            rolled_back = runner.rollback_last()
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

            self.assertEqual(rolled_back, "0001")
            self.assertNotIn("organizations", tables)
            self.assertNotIn("schema_migrations", tables)
        finally:
            connection.close()

    def test_local_test_database_can_be_created_and_migrated(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            database_path = os.path.join(tmpdir, "test_product.db")
            settings = Settings(database_url=f"sqlite:///{database_path}")
            runner = MigrationRunner.from_settings(settings)

            applied = runner.apply_all()
            runner.connection.close()
            reopened = connect_database(f"sqlite:///{database_path}")
            try:
                count = reopened.execute(
                    "SELECT COUNT(*) AS count FROM schema_migrations"
                ).fetchone()["count"]
            finally:
                reopened.close()

        self.assertEqual(applied, EXPECTED_MIGRATIONS)
        self.assertEqual(count, len(EXPECTED_MIGRATIONS))


if __name__ == "__main__":
    unittest.main()
