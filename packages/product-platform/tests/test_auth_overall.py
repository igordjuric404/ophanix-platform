from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.rbac import Permission
from product_platform.api.settings import Settings


class AuthOverallValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(
            create_app(
                Settings(
                    app_name="Ophanix Test Platform",
                    environment="test",
                    build_sha="test-sha",
                    build_time="2026-04-30T00:00:00Z",
                    dev_login_allowed_emails=["admin@example.com", "viewer@example.com"],
                    session_secret="test-secret",
                )
            ),
            raise_server_exceptions=False,
        )

    def _token_for(self, email: str, roles: list[str]) -> str:
        response = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": email, "roles": roles},
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["access_token"]

    def test_platform_admin_can_create_environment_and_api_key(self) -> None:
        token = self._token_for("admin@example.com", ["Platform Admin"])
        headers = {"Authorization": f"Bearer {token}"}

        environment = self.client.post(
            "/api/v1/environments",
            json={"name": "Staging", "slug": "staging", "type": "staging"},
            headers=headers,
        )
        api_key = self.client.post(
            "/api/v1/api-keys",
            json={"name": "Workflow key", "scopes": [Permission.JOB_RUN], "kind": "ci"},
            headers=headers,
        )

        self.assertEqual(environment.status_code, 201)
        self.assertEqual(environment.json()["slug"], "staging")
        self.assertEqual(api_key.status_code, 201)
        self.assertTrue(api_key.json()["secret"].startswith("opx_"))

    def test_viewer_can_inspect_but_not_mutate_resources(self) -> None:
        token = self._token_for("viewer@example.com", ["Viewer"])
        headers = {"Authorization": f"Bearer {token}"}

        orgs = self.client.get("/api/v1/organizations", headers=headers)
        envs = self.client.get("/api/v1/environments", headers=headers)
        environment_create = self.client.post(
            "/api/v1/environments",
            json={"name": "Blocked", "slug": "blocked", "type": "development"},
            headers=headers,
        )
        api_key_create = self.client.post(
            "/api/v1/api-keys",
            json={"name": "Blocked key", "scopes": [Permission.SYSTEM_READ], "kind": "ci"},
            headers=headers,
        )

        self.assertEqual(orgs.status_code, 200)
        self.assertEqual(envs.status_code, 200)
        self.assertEqual(environment_create.status_code, 403)
        self.assertEqual(api_key_create.status_code, 403)


if __name__ == "__main__":
    unittest.main()

