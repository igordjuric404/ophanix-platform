from __future__ import annotations

import os
import tempfile
import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.api.tenancy import Environment, TenantStore
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


class DiscoveryScanRunnerPhase2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            connection.execute(
                """
                INSERT INTO environments
                    (id, organization_id, name, slug, type, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "env_other",
                    "org_default",
                    "Other",
                    "other",
                    "development",
                    "2026-04-30T00:00:00+00:00",
                    "2026-04-30T00:00:00+00:00",
                ),
            )
        tenant_store = TenantStore(
            environments=[
                Environment(
                    id="env_default",
                    organization_id="org_default",
                    name="Development",
                    slug="development",
                    type="development",
                    created_at="2026-04-30T00:00:00+00:00",
                ),
                Environment(
                    id="env_other",
                    organization_id="org_default",
                    name="Other",
                    slug="other",
                    type="development",
                    created_at="2026-04-30T00:00:00+00:00",
                ),
            ]
        )
        self.app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-04-30T00:00:00Z",
                dev_login_allowed_emails=["admin@example.com"],
                session_secret="test-secret",
            ),
            tenant_store=tenant_store,
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "admin@example.com", "roles": ["Platform Admin"]},
        )
        self.assertEqual(login.status_code, 200)
        self.token = login.json()["access_token"]

    def _headers(self, environment_id: str = "env_default") -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": environment_id,
        }

    def test_api_creates_config_scan_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            response = self.client.post(
                "/api/v1/discovery/targets",
                headers=self._headers(),
                json={
                    "scanner_type": "config",
                    "target_type": "filesystem",
                    "target_value": tmpdir,
                    "config_json": {"paths": [tmpdir], "max_depth": 3},
                    "enabled": True,
                },
            )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertTrue(payload["id"].startswith("target_"))
        self.assertEqual(payload["scanner_type"], "config")
        self.assertEqual(payload["target_type"], "filesystem")
        self.assertEqual(payload["environment_id"], "env_default")
        self.assertTrue(payload["enabled"])

    def test_api_invalid_target_type_is_rejected(self) -> None:
        response = self.client.post(
            "/api/v1/discovery/targets",
            headers=self._headers(),
            json={
                "scanner_type": "unknown",
                "target_type": "filesystem",
                "target_value": os.getcwd(),
                "config_json": {"paths": [os.getcwd()]},
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Unknown scanner type", response.json()["message"])

    def test_api_target_is_scoped_to_environment(self) -> None:
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            first = self.client.post(
                "/api/v1/discovery/targets",
                headers=self._headers("env_default"),
                json={
                    "scanner_type": "config",
                    "target_type": "filesystem",
                    "target_value": first_dir,
                    "config_json": {"paths": [first_dir]},
                },
            )
            second = self.client.post(
                "/api/v1/discovery/targets",
                headers=self._headers("env_other"),
                json={
                    "scanner_type": "config",
                    "target_type": "filesystem",
                    "target_value": second_dir,
                    "config_json": {"paths": [second_dir]},
                },
            )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)

        default_targets = self.client.get(
            "/api/v1/discovery/targets",
            headers=self._headers("env_default"),
        )
        other_targets = self.client.get(
            "/api/v1/discovery/targets",
            headers=self._headers("env_other"),
        )

        self.assertEqual(default_targets.status_code, 200)
        self.assertEqual(other_targets.status_code, 200)
        self.assertEqual([target["id"] for target in default_targets.json()], [first.json()["id"]])
        self.assertEqual([target["id"] for target in other_targets.json()], [second.json()["id"]])


if __name__ == "__main__":
    unittest.main()
