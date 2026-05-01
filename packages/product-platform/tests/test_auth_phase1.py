from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings


class AuthPhase1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(
            create_app(
                Settings(
                    app_name="Ophanix Test Platform",
                    environment="test",
                    build_sha="test-sha",
                    build_time="2026-04-30T00:00:00Z",
                    dev_login_allowed_emails=["admin@example.com"],
                    session_secret="test-secret",
                )
            ),
            raise_server_exceptions=False,
        )

    def test_unauthenticated_api_request_is_rejected(self) -> None:
        response = self.client.get("/api/v1/auth/me", headers={"X-Request-ID": "req-auth"})

        self.assertEqual(response.status_code, 401)
        payload = response.json()
        self.assertEqual(payload["code"], "UNAUTHENTICATED")
        self.assertEqual(payload["request_id"], "req-auth")

    def test_dev_login_returns_current_user(self) -> None:
        response = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "admin@example.com", "display_name": "Admin User"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["token_type"], "bearer")
        self.assertTrue(payload["access_token"])
        self.assertEqual(payload["user"]["email"], "admin@example.com")
        self.assertEqual(payload["user"]["display_name"], "Admin User")
        self.assertIn("Platform Admin", payload["user"]["roles"])
        self.assertIn("ophanix_session", response.cookies)

    def test_current_user_is_available_in_route_dependency(self) -> None:
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "admin@example.com"},
        )
        token = login.json()["access_token"]

        response = self.client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["email"], "admin@example.com")
        self.assertEqual(payload["actor_type"], "user")

    def test_dev_login_rejects_email_outside_allowlist(self) -> None:
        response = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "intruder@example.com"},
            headers={"X-Request-ID": "req-denied-login"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["request_id"], "req-denied-login")


if __name__ == "__main__":
    unittest.main()

