from __future__ import annotations

import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from product_platform import __version__, create_app
from product_platform.api.settings import Settings


class ProductApiShellPhase1Tests(unittest.TestCase):
    def setUp(self) -> None:
        settings = Settings(
            app_name="Ophanix Test Platform",
            environment="test",
            build_sha="test-sha",
            build_time="2026-04-30T00:00:00Z",
            dev_login_allowed_emails=["admin@example.com"],
            session_secret="test-secret",
        )
        self.app = create_app(settings)
        self.client = TestClient(self.app)

    def test_app_factory_returns_fastapi_instance(self) -> None:
        self.assertIsInstance(self.app, FastAPI)

    def test_health_returns_200_with_status_payload(self) -> None:
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["version"], __version__)
        self.assertIn("uptime_seconds", payload)
        self.assertIsInstance(payload["dependencies"], list)

    def test_version_includes_app_version_and_build_metadata(self) -> None:
        response = self.client.get("/version")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["app"], "Ophanix Test Platform")
        self.assertEqual(payload["version"], __version__)
        self.assertEqual(payload["build_sha"], "test-sha")
        self.assertEqual(payload["build_time"], "2026-04-30T00:00:00Z")
        self.assertEqual(payload["environment"], "test")

    def test_system_endpoints_are_available(self) -> None:
        self.assertEqual(self.client.get("/ready").status_code, 200)
        self.assertEqual(self.client.get("/api/openapi.json").status_code, 200)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "admin@example.com"},
        )
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        self.assertEqual(self.client.get("/api/v1/system/config", headers=headers).status_code, 200)
        self.assertEqual(
            self.client.get("/api/v1/system/dependencies", headers=headers).status_code,
            200,
        )


if __name__ == "__main__":
    unittest.main()
