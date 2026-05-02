from __future__ import annotations

import unittest
from pathlib import Path


PACKAGE_DIR = Path(__file__).resolve().parents[1]


class LocalDemoComposePhase4Tests(unittest.TestCase):
    def test_local_demo_readme_documents_commands_urls_and_degraded_behavior(self) -> None:
        readme = (PACKAGE_DIR / "LOCAL_DEMO.md").read_text()

        for snippet in (
            "docker compose --env-file .env -f docker-compose.demo.yml up --build",
            "docker compose --env-file .env -f docker-compose.demo.yml logs -f api worker sample-mcp",
            "docker compose --env-file .env -f docker-compose.demo.yml down --volumes",
            "docker compose --env-file .env -f docker-compose.demo.yml run --rm migrate-seed db seed",
            "sh deploy/local-demo-smoke.sh",
            "http://localhost:3000",
            "http://localhost:8088/ready",
            "admin@example.com",
            "Missing optional provider credentials show a warning",
        ):
            self.assertIn(snippet, readme)

    def test_local_demo_smoke_script_exercises_compose_ready_reset_and_run(self) -> None:
        script = (PACKAGE_DIR / "deploy/local-demo-smoke.sh").read_text()

        self.assertIn("docker compose --env-file $ENV_FILE -f docker-compose.demo.yml", script)
        self.assertIn("up --build --wait", script)
        self.assertIn("/ready", script)
        self.assertIn("/api/v1/demo/reset", script)
        self.assertIn("/api/v1/demo/baseline-status", script)
        self.assertIn("/api/v1/demo/scenarios/customer-support-refund/runs", script)
        self.assertIn("down", script)


if __name__ == "__main__":
    unittest.main()
