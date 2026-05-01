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
            "http://localhost:3000",
            "http://localhost:8088/ready",
            "admin@ophanix.local",
            "Missing optional provider credentials show a warning",
        ):
            self.assertIn(snippet, readme)


if __name__ == "__main__":
    unittest.main()
