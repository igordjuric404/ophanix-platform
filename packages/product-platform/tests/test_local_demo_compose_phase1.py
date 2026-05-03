from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.testing import create_migrated_test_database


PACKAGE_DIR = Path(__file__).resolve().parents[1]


class LocalDemoComposePhase1Tests(unittest.TestCase):
    def test_compose_config_validates_expected_core_services(self) -> None:
        result = subprocess.run(
            [
                "docker",
                "compose",
                "--env-file",
                ".env.example",
                "-f",
                "docker-compose.demo.yml",
                "config",
            ],
            cwd=PACKAGE_DIR,
            check=True,
            capture_output=True,
            text=True,
        )

        for service in ("frontend:", "api:", "worker:", "postgres:", "redis:"):
            self.assertIn(service, result.stdout)
        self.assertIn("healthcheck:", result.stdout)

    def test_demo_dockerfile_installs_runtime_sibling_packages(self) -> None:
        dockerfile = (PACKAGE_DIR / "Dockerfile.demo").read_text()

        self.assertIn("COPY packages/agent-mesh/pyproject.toml", dockerfile)
        self.assertIn("COPY packages/agent-discovery/pyproject.toml", dockerfile)
        self.assertIn("packages/product-platform/README.md", dockerfile)
        self.assertIn("python -m pip install ./packages/agent-mesh", dockerfile)
        self.assertIn("python -m pip install ./packages/agent-discovery", dockerfile)
        self.assertIn("python -m pip install -e ./packages/product-platform", dockerfile)

    def test_api_health_and_ready_report_compose_dependencies(self) -> None:
        database = create_migrated_test_database()
        app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-05-01T00:00:00Z",
                session_secret="test-secret",
            ),
            database=database,
        )
        client = TestClient(app, raise_server_exceptions=False)

        health = client.get("/health")
        ready = client.get("/ready")

        self.assertEqual(health.status_code, 200, health.text)
        self.assertEqual(ready.status_code, 200, ready.text)
        dependency_names = {item["name"] for item in ready.json()["dependencies"]}
        self.assertIn("database", dependency_names)
        self.assertIn("redis", dependency_names)
        self.assertIn("worker", dependency_names)

    def test_worker_noop_command_succeeds(self) -> None:
        env = dict(os.environ)
        env["PYTHONPATH"] = str(PACKAGE_DIR / "src")
        result = subprocess.run(
            [sys.executable, "-m", "product_platform.cli", "worker", "noop"],
            cwd=PACKAGE_DIR,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )

        self.assertIn("Worker no-op job succeeded: True", result.stdout)


if __name__ == "__main__":
    unittest.main()
