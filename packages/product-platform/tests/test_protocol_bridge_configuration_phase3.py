from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.mesh.bridges import ProtocolBridgeHealthAdapter


class ProtocolBridgeConfigurationPhase3Tests(unittest.TestCase):
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
                dev_login_allowed_emails=["admin@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "admin@example.com", "roles": ["Platform Admin"]},
        )
        self.assertEqual(login.status_code, 200)
        self.token = login.json()["access_token"]

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
        }

    def _create_bridge(self) -> dict:
        response = self.client.post(
            "/api/v1/mesh/protocol-bridges",
            headers=self._headers(),
            json={
                "name": "Health Test MCP Bridge",
                "bridge_type": "mcp",
                "config": {"endpoint": "https://mcp.local/rpc"},
            },
        )
        self.assertEqual(response.status_code, 201)
        return response.json()

    def test_health_adapter_reports_limited_for_configured_bridge(self) -> None:
        result = ProtocolBridgeHealthAdapter().check(
            {
                "bridge_type": "mcp",
                "status": "configured",
                "config_json": '{"endpoint": "https://mcp.local/rpc"}',
            }
        )

        self.assertEqual(result.status, "limited")
        self.assertGreaterEqual(result.latency_ms, 0)
        self.assertIn("placeholder/pass-through", result.message)
        self.assertIn("not reported as healthy", result.message)

    def test_api_health_check_stores_result_and_exposes_current_health(self) -> None:
        bridge = self._create_bridge()

        response = self.client.post(
            f"/api/v1/mesh/protocol-bridges/{bridge['id']}/health-check",
            headers=self._headers(),
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["bridge_id"], bridge["id"])
        self.assertEqual(payload["status"], "limited")

        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM protocol_bridge_health_checks WHERE id = ?",
                (payload["id"],),
            ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["status"], "limited")

        listed = self.client.get("/api/v1/mesh/protocol-bridges", headers=self._headers())
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()[0]["current_health"]["id"], payload["id"])
        self.assertEqual(listed.json()[0]["status"], "limited")

    def test_placeholder_bridge_reports_limited_not_healthy(self) -> None:
        bridge = self._create_bridge()

        response = self.client.post(
            f"/api/v1/mesh/protocol-bridges/{bridge['id']}/health-check",
            headers=self._headers(),
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertNotEqual(payload["status"], "healthy")
        self.assertEqual(payload["status"], "limited")
        self.assertIn("limited", payload["message"])

        detail = self.client.get(
            f"/api/v1/mesh/protocol-bridges/{bridge['id']}",
            headers=self._headers(),
        )
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["current_health"]["status"], "limited")


if __name__ == "__main__":
    unittest.main()
