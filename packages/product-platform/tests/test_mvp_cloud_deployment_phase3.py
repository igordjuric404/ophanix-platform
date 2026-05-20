from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.deployment.security import cloud_security_checks


class MVPCloudDeploymentPhase3Tests(unittest.TestCase):
    def test_security_status_reports_idp_tls_network_and_cors(self) -> None:
        settings = Settings(
            deployment_mode="cloud",
            idp_issuer_url="https://idp.example.com/oauth2/default",
            idp_audience="api://ophanix-product-platform",
            idp_jwks_url="https://idp.example.com/oauth2/default/keys",
            tls_certificate_ref="managed-certificates/ophanix",
            internal_cidrs=["10.0.0.0/8"],
            cors_origins=["https://app.example.com"],
            session_secret="test-secret",
        )

        checks = {check.key: check for check in cloud_security_checks(settings)}

        self.assertEqual(checks["identity_provider"].status, "healthy")
        self.assertEqual(checks["tls"].status, "healthy")
        self.assertEqual(checks["internal_network"].status, "healthy")
        self.assertEqual(checks["cors"].status, "healthy")

    def test_unauthenticated_api_calls_are_rejected(self) -> None:
        client = TestClient(create_app(Settings(session_secret="test-secret")), raise_server_exceptions=False)

        response = client.get("/api/v1/demo/scenarios", headers={"X-Environment-ID": "env_default"})

        self.assertEqual(response.status_code, 401)

    def test_cors_allows_only_configured_frontend_domain(self) -> None:
        app = create_app(
            Settings(
                cors_origins=["https://app.example.com"],
                session_secret="test-secret",
            )
        )
        client = TestClient(app, raise_server_exceptions=False)

        allowed = client.get(
            "/health",
            headers={
                "Origin": "https://app.example.com",
            },
        )
        denied = client.get(
            "/health",
            headers={
                "Origin": "https://evil.example.com",
            },
        )

        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(allowed.headers["access-control-allow-origin"], "https://app.example.com")
        self.assertNotEqual(
            denied.headers.get("access-control-allow-origin"),
            "https://evil.example.com",
        )


if __name__ == "__main__":
    unittest.main()
