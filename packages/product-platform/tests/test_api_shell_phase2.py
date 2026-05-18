from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.auth import DevLoginRequest
from product_platform.api.settings import Settings
from product_platform.db.testing import create_test_database


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

    def test_api_body_limit_blocks_large_non_gateway_request_before_auth(self) -> None:
        app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-04-30T00:00:00Z",
                dev_login_allowed_emails=["admin@example.com"],
                session_secret="test-secret",
                api_max_body_bytes=10,
                tool_gateway_max_body_bytes=1_000,
            )
        )
        client = TestClient(app, raise_server_exceptions=False)

        response = client.post(
            "/api/v1/auth/dev-login",
            headers={"Content-Type": "application/json"},
            content=b'{"email":"admin@example.com"}',
        )

        self.assertEqual(response.status_code, 413)
        payload = response.json()
        self.assertEqual(payload["code"], "REQUEST_BODY_TOO_LARGE")
        self.assertEqual(payload["message"], "API request body exceeds the configured size limit.")

    def test_production_http_errors_do_not_leak_route_specific_details(self) -> None:
        database = create_test_database()
        try:
            app = create_app(
                Settings(
                    app_name="Ophanix Test Platform",
                    environment="production",
                    build_sha="test-sha",
                    build_time="2026-04-30T00:00:00Z",
                    database_url=database.database_url,
                    session_secret="production-test-secret",
                    secret_manager_ref="env",
                    gateway_token_hash_pepper="test-pepper",
                    api_key_hash_pepper="test-api-key-pepper",
                    tool_gateway_upstream_host_allowlist=["*.example.com"],
                ),
                database=database,
            )
            token = app.state.auth_service.login(DevLoginRequest(email="admin@example.com")).access_token
            client = TestClient(app, raise_server_exceptions=False)

            response = client.get(
                "/api/v1/system/not-found-probe",
                headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req-prod-http"},
            )
        finally:
            database.close()

        self.assertEqual(response.status_code, 404)
        payload = response.json()
        self.assertEqual(payload["message"], "Resource not found.")
        self.assertNotIn("Probe not found", response.text)

    def test_production_validation_errors_do_not_echo_invalid_input(self) -> None:
        database = create_test_database()
        try:
            app = create_app(
                Settings(
                    app_name="Ophanix Test Platform",
                    environment="production",
                    build_sha="test-sha",
                    build_time="2026-04-30T00:00:00Z",
                    database_url=database.database_url,
                    session_secret="production-test-secret",
                    secret_manager_ref="env",
                    gateway_token_hash_pepper="test-pepper",
                    api_key_hash_pepper="test-api-key-pepper",
                    tool_gateway_upstream_host_allowlist=["*.example.com"],
                ),
                database=database,
            )
            token = app.state.auth_service.login(DevLoginRequest(email="admin@example.com")).access_token
            client = TestClient(app, raise_server_exceptions=False)

            response = client.get(
                "/api/v1/system/dependencies?required_only=definitely-not-bool",
                headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req-prod-validation"},
            )
        finally:
            database.close()

        self.assertEqual(response.status_code, 422)
        payload = response.json()
        self.assertEqual(payload["code"], "VALIDATION_ERROR")
        self.assertEqual(payload["details"]["errors"][0]["msg"], "Invalid request value.")
        self.assertNotIn("definitely-not-bool", response.text)


if __name__ == "__main__":
    unittest.main()
