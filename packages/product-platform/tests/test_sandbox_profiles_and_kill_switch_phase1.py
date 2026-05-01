from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


class SandboxProfilesPhase1Tests(unittest.TestCase):
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
                dev_login_allowed_emails=["security@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "security@example.com", "roles": ["Security Admin"]},
        )
        self.assertEqual(login.status_code, 200)
        self.token = login.json()["access_token"]

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
        }

    def _create_profile(self, name: str = "Demo Subprocess Sandbox") -> dict:
        created = self.client.post(
            "/api/v1/runtime/sandbox-profiles",
            headers=self._headers(),
            json={
                "name": name,
                "provider_type": "subprocess",
                "allowed_imports": ["json"],
                "blocked_imports": ["os", "subprocess"],
                "allowed_paths": ["/tmp/ophanix-demo"],
                "network_policy": {"egress": "deny"},
                "resource_limits": {"timeout_seconds": 5, "memory_mb": 128},
            },
        )
        self.assertEqual(created.status_code, 201, created.text)
        return created.json()

    def test_create_sandbox_profile(self) -> None:
        profile = self._create_profile()

        self.assertEqual(profile["name"], "Demo Subprocess Sandbox")
        self.assertEqual(profile["provider_type"], "subprocess")
        self.assertEqual(profile["blocked_imports"], ["os", "subprocess"])
        self.assertIn("demo-only", profile["provider_warning"])

        listed = self.client.get("/api/v1/runtime/sandbox-profiles", headers=self._headers())
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()[0]["id"], profile["id"])

    def test_invalid_provider_type_rejected(self) -> None:
        rejected = self.client.post(
            "/api/v1/runtime/sandbox-profiles",
            headers=self._headers(),
            json={"name": "Unsafe", "provider_type": "firecracker"},
        )

        self.assertEqual(rejected.status_code, 400)
        self.assertIn("Unsupported sandbox provider_type", rejected.json()["message"])

    def test_patch_profile_updates_restrictions(self) -> None:
        profile = self._create_profile()

        patched = self.client.patch(
            f"/api/v1/runtime/sandbox-profiles/{profile['id']}",
            headers=self._headers(),
            json={
                "blocked_imports": ["os", "socket", "subprocess"],
                "status": "disabled",
            },
        )

        self.assertEqual(patched.status_code, 200, patched.text)
        self.assertEqual(patched.json()["status"], "disabled")
        self.assertEqual(patched.json()["blocked_imports"], ["os", "socket", "subprocess"])
        self.assertIn("does not provide production isolation", patched.json()["provider_warning"])


if __name__ == "__main__":
    unittest.main()
