from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.integrations.catalog import FRAMEWORK_CATALOG, seed_framework_catalog


class FrameworkCatalogPhase1Tests(unittest.TestCase):
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
                dev_login_allowed_emails=["integrations@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "integrations@example.com", "roles": ["Platform Admin"]},
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.token = login.json()["access_token"]

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
        }

    def test_framework_seed_is_idempotent(self) -> None:
        with self.database.transaction() as connection:
            seed_framework_catalog(connection)
            seed_framework_catalog(connection)
            count = connection.execute(
                "SELECT COUNT(*) AS count FROM integrations WHERE integration_type = ?",
                ("framework",),
            ).fetchone()["count"]

        self.assertEqual(count, len(FRAMEWORK_CATALOG))

    def test_api_lists_frameworks(self) -> None:
        response = self.client.get("/api/v1/integrations/frameworks", headers=self._headers())

        self.assertEqual(response.status_code, 200, response.text)
        frameworks = response.json()
        framework_ids = {framework["id"] for framework in frameworks}
        self.assertEqual(len(frameworks), len(FRAMEWORK_CATALOG))
        self.assertIn("openai_agents", framework_ids)
        self.assertIn("langchain", framework_ids)
        self.assertIn("custom", framework_ids)
        openai = next(framework for framework in frameworks if framework["id"] == "openai_agents")
        self.assertEqual(openai["status"], "primary_demo")
        self.assertEqual(openai["setup_doc_url"], "/docs/integrations/openai-agents")
        self.assertIn("packages/agent-os/examples/openai_agents", openai["example_path"])


if __name__ == "__main__":
    unittest.main()
