from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


class MCPProxyTrafficPhase4Tests(unittest.TestCase):
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
            json={"email": "admin@example.com", "roles": ["Security Admin"]},
        )
        self.assertEqual(login.status_code, 200)
        self.token = login.json()["access_token"]

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
        }

    def test_rate_limit_create_and_list(self) -> None:
        created = self.client.post(
            "/api/v1/mcp/rate-limits",
            headers=self._headers(),
            json={
                "target_type": "mcp-tool",
                "target_id": "mcptool_demo",
                "window_seconds": 60,
                "max_calls": 12,
                "enabled": True,
            },
        )

        self.assertEqual(created.status_code, 201)
        payload = created.json()
        self.assertEqual(payload["target_type"], "mcp-tool")
        self.assertEqual(payload["max_calls"], 12)
        self.assertEqual(payload["enabled"], True)

        listed = self.client.get(
            "/api/v1/mcp/rate-limits?target_type=mcp-tool&enabled=true",
            headers=self._headers(),
        )
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()[0]["id"], payload["id"])


if __name__ == "__main__":
    unittest.main()
