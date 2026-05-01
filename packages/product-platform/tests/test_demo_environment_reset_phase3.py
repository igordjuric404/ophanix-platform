from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.demo.baseline import DEMO_BASELINE_MCP_SERVER_ID


class DemoEnvironmentResetPhase3Tests(unittest.TestCase):
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
                dev_login_allowed_emails=["baseline@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "baseline@example.com", "roles": ["Operator"]},
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.token = login.json()["access_token"]

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
        }

    def test_api_baseline_is_healthy_after_reset(self) -> None:
        reset = self.client.post(
            "/api/v1/demo/reset",
            headers=self._headers(),
            json={"confirmation": "RESET"},
        )
        self.assertEqual(reset.status_code, 201, reset.text)

        response = self.client.get(
            "/api/v1/demo/baseline-status",
            headers=self._headers(),
        )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        checks = {check["key"]: check for check in payload["checks"]}
        self.assertEqual(payload["overall_status"], "healthy")
        self.assertEqual(payload["missing_items"], [])
        self.assertEqual(checks["policy-pack"]["status"], "healthy")
        self.assertEqual(checks["demo-scenario"]["status"], "healthy")
        self.assertEqual(checks["sample-agents"]["count"], 3)
        self.assertEqual(checks["mcp-server"]["status"], "healthy")
        self.assertFalse(checks["provider-credential"]["required"])

    def test_api_missing_mcp_server_returns_degraded(self) -> None:
        with self.database.transaction() as connection:
            connection.execute(
                "DELETE FROM mcp_servers WHERE id = ?",
                (DEMO_BASELINE_MCP_SERVER_ID,),
            )

        response = self.client.get(
            "/api/v1/demo/baseline-status",
            headers=self._headers(),
        )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        checks = {check["key"]: check for check in payload["checks"]}
        self.assertEqual(payload["overall_status"], "degraded")
        self.assertIn(DEMO_BASELINE_MCP_SERVER_ID, payload["missing_items"])
        self.assertEqual(checks["mcp-server"]["status"], "degraded")
        self.assertEqual(checks["mcp-server"]["missing"], [DEMO_BASELINE_MCP_SERVER_ID])


if __name__ == "__main__":
    unittest.main()
