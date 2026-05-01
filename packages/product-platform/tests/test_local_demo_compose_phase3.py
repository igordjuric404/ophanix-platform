from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from product_platform.db.migrator import connect_database
from product_platform.demo.baseline import demo_baseline_status


PACKAGE_DIR = Path(__file__).resolve().parents[1]


class LocalDemoComposePhase3Tests(unittest.TestCase):
    def test_fresh_volume_seed_is_idempotent_and_baseline_healthy(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "ophanix_product.db"
            env = dict(os.environ)
            env["PYTHONPATH"] = str(PACKAGE_DIR / "src")
            env["OPHANIX_DATABASE_URL"] = f"sqlite:///{database_path}"

            first = subprocess.run(
                [sys.executable, "-m", "product_platform.cli", "db", "seed"],
                cwd=PACKAGE_DIR,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            second = subprocess.run(
                [sys.executable, "-m", "product_platform.cli", "db", "seed"],
                cwd=PACKAGE_DIR,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )

            connection = connect_database(f"sqlite:///{database_path}")
            try:
                counts = {
                    "policy_placeholders": _count(connection, "policy_placeholders"),
                    "demo_scenarios": _count(connection, "demo_scenarios"),
                    "mcp_servers": _count(connection, "mcp_servers"),
                    "agents": _count(connection, "agents"),
                }
                baseline = demo_baseline_status(
                    connection,
                    organization_id="org_default",
                    environment_id="env_default",
                )
            finally:
                connection.close()

        self.assertIn("Seeded demo data", first.stdout)
        self.assertIn("Seeded demo data", second.stdout)
        self.assertEqual(
            counts,
            {
                "policy_placeholders": 2,
                "demo_scenarios": 1,
                "mcp_servers": 1,
                "agents": 3,
            },
        )
        self.assertEqual(baseline.overall_status, "healthy")
        self.assertEqual(baseline.missing_items, [])

    def test_compose_uses_migrate_seed_service(self) -> None:
        compose_text = (PACKAGE_DIR / "docker-compose.demo.yml").read_text()

        self.assertIn("migrate-seed:", compose_text)
        self.assertIn('command: ["db", "seed"]', compose_text)
        self.assertIn("condition: service_completed_successfully", compose_text)


def _count(connection: sqlite3.Connection, table_name: str) -> int:
    return int(connection.execute(f"SELECT COUNT(*) AS count FROM {table_name}").fetchone()["count"])


if __name__ == "__main__":
    unittest.main()
