from __future__ import annotations

import json
import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


class ProtocolBridgeConfigurationPhase1Tests(unittest.TestCase):
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

    def test_api_creates_lists_gets_and_patches_bridge(self) -> None:
        created = self.client.post(
            "/api/v1/mesh/protocol-bridges",
            headers=self._headers(),
            json={
                "name": "MCP Claims Bridge",
                "bridge_type": "mcp",
                "config": {
                    "endpoint": "https://mcp.local/rpc",
                    "secret_id": "secret_mcp_claims",
                },
            },
        )

        self.assertEqual(created.status_code, 201)
        created_payload = created.json()
        self.assertEqual(created_payload["name"], "MCP Claims Bridge")
        self.assertEqual(created_payload["bridge_type"], "mcp")
        self.assertEqual(created_payload["status"], "configured")
        self.assertEqual(created_payload["config"]["secret_id"], "secret_mcp_claims")

        listed = self.client.get("/api/v1/mesh/protocol-bridges", headers=self._headers())
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()[0]["id"], created_payload["id"])

        fetched = self.client.get(
            f"/api/v1/mesh/protocol-bridges/{created_payload['id']}",
            headers=self._headers(),
        )
        self.assertEqual(fetched.status_code, 200)
        self.assertEqual(fetched.json()["config"]["endpoint"], "https://mcp.local/rpc")

        patched = self.client.patch(
            f"/api/v1/mesh/protocol-bridges/{created_payload['id']}",
            headers=self._headers(),
            json={"name": "MCP Claims Bridge v2", "status": "active"},
        )
        self.assertEqual(patched.status_code, 200)
        self.assertEqual(patched.json()["name"], "MCP Claims Bridge v2")
        self.assertEqual(patched.json()["status"], "active")

    def test_api_invalid_bridge_type_is_rejected(self) -> None:
        response = self.client.post(
            "/api/v1/mesh/protocol-bridges",
            headers=self._headers(),
            json={
                "name": "FTP Bridge",
                "bridge_type": "ftp",
                "config": {},
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_raw_secrets_are_not_persisted_in_bridge_config(self) -> None:
        response = self.client.post(
            "/api/v1/mesh/protocol-bridges",
            headers=self._headers(),
            json={
                "name": "A2A Sensitive Bridge",
                "bridge_type": "a2a",
                "config": {
                    "endpoint": "https://a2a.local",
                    "api_key": "raw-api-key",
                    "nested": {"password": "raw-password", "token_secret_id": "sec_token"},
                    "secret_id": "sec_a2a_bridge",
                },
            },
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["config"]["api_key"], "[redacted]")
        self.assertEqual(payload["config"]["nested"]["password"], "[redacted]")
        self.assertEqual(payload["config"]["nested"]["token_secret_id"], "sec_token")
        self.assertEqual(payload["config"]["secret_id"], "sec_a2a_bridge")

        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT config_json FROM protocol_bridges WHERE id = ?",
                (payload["id"],),
            ).fetchone()
        stored_config = json.loads(row["config_json"])
        stored_json = json.dumps(stored_config, sort_keys=True)
        self.assertNotIn("raw-api-key", stored_json)
        self.assertNotIn("raw-password", stored_json)
        self.assertEqual(stored_config["api_key"], "[redacted]")
        self.assertEqual(stored_config["secret_id"], "sec_a2a_bridge")


if __name__ == "__main__":
    unittest.main()
