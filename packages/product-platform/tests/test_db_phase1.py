from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest

from product_platform.api.settings import Settings
from product_platform.db.migrator import MigrationRunner, connect_database


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

            self.assertEqual(applied, ["0001", "0002", "0003", "0004", "0005"])
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
            self.assertEqual(runner.applied_versions(), ["0001", "0002", "0003", "0004", "0005"])
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

        self.assertEqual(applied, ["0001", "0002", "0003", "0004", "0005"])
        self.assertEqual(count, 5)


if __name__ == "__main__":
    unittest.main()
