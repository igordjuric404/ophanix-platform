from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings


class ProductApiShellPhase2Tests(unittest.TestCase):
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

    def _auth_headers(self, request_id: str | None = None) -> dict[str, str]:
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "admin@example.com"},
        )
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        if request_id:
            headers["X-Request-ID"] = request_id
        return headers

    def test_supplied_request_id_is_echoed(self) -> None:
        response = self.client.get(
            "/health",
            headers={"X-Request-ID": "req-provided", "X-Correlation-ID": "corr-provided"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["X-Request-ID"], "req-provided")
        self.assertEqual(response.headers["X-Correlation-ID"], "corr-provided")

    def test_missing_request_id_is_created(self) -> None:
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["X-Request-ID"])
        self.assertEqual(response.headers["X-Correlation-ID"], response.headers["X-Request-ID"])

    def test_validation_errors_use_standard_error_format(self) -> None:
        response = self.client.get(
            "/api/v1/system/dependencies?required_only=definitely-not-bool",
            headers=self._auth_headers("req-validation"),
        )

        self.assertEqual(response.status_code, 422)
        payload = response.json()
        self.assertEqual(payload["code"], "VALIDATION_ERROR")
        self.assertEqual(payload["request_id"], "req-validation")
        self.assertIn("errors", payload["details"])
        self.assertEqual(response.headers["X-Request-ID"], "req-validation")

    def test_http_errors_use_standard_error_format(self) -> None:
        response = self.client.get(
            "/api/v1/system/not-found-probe",
            headers=self._auth_headers("req-http-error"),
        )

        self.assertEqual(response.status_code, 404)
        payload = response.json()
        self.assertEqual(payload["code"], "HTTP_ERROR")
        self.assertEqual(payload["message"], "Probe not found.")
        self.assertEqual(payload["request_id"], "req-http-error")

    def test_unhandled_errors_use_standard_error_format(self) -> None:
        app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-04-30T00:00:00Z",
            )
        )

        @app.get("/boom")
        async def boom() -> None:
            raise RuntimeError("boom")

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/boom", headers={"X-Request-ID": "req-unhandled"})

        self.assertEqual(response.status_code, 500)
        payload = response.json()
        self.assertEqual(payload["code"], "INTERNAL_ERROR")
        self.assertEqual(payload["message"], "Internal server error.")
        self.assertEqual(payload["request_id"], "req-unhandled")
        self.assertEqual(payload["details"]["error_type"], "RuntimeError")


if __name__ == "__main__":
    unittest.main()
