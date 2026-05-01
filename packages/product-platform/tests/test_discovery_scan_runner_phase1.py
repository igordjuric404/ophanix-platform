from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.discovery.registry import DiscoveryScannerRegistry


class DiscoveryScanRunnerPhase1Tests(unittest.TestCase):
    def test_unit_registry_includes_expected_builtins(self) -> None:
        registry = DiscoveryScannerRegistry.default()

        scanners = {scanner.scanner_type: scanner for scanner in registry.list_scanners()}

        self.assertEqual(set(scanners), {"process", "config", "github"})
        self.assertEqual(scanners["process"].status, "available")
        self.assertIn("paths", scanners["config"].required_config)
        self.assertIn("repos", scanners["github"].required_config)

    def test_unit_invalid_scanner_config_fails_validation(self) -> None:
        registry = DiscoveryScannerRegistry.default()

        config_errors = registry.validate_config(
            "config",
            {"paths": ["/path/that/does/not/exist"]},
        )
        github_errors = registry.validate_config("github", {})

        self.assertTrue(config_errors)
        self.assertIn("not a valid directory", config_errors[0])
        self.assertEqual(github_errors, ["Either 'repos' (list) or 'org' (string) is required"])

    def test_api_scanner_list_returns_metadata(self) -> None:
        app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-04-30T00:00:00Z",
                dev_login_allowed_emails=["viewer@example.com"],
                session_secret="test-secret",
            )
        )
        client = TestClient(app, raise_server_exceptions=False)
        login = client.post(
            "/api/v1/auth/dev-login",
            json={"email": "viewer@example.com", "roles": ["Viewer"]},
        )
        self.assertEqual(login.status_code, 200)

        response = client.get(
            "/api/v1/discovery/scanners",
            headers={"Authorization": f"Bearer {login.json()['access_token']}"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        scanner_types = {scanner["scanner_type"] for scanner in payload}
        self.assertEqual(scanner_types, {"process", "config", "github"})
        config = next(scanner for scanner in payload if scanner["scanner_type"] == "config")
        self.assertEqual(config["status"], "available")
        self.assertIn("paths", config["required_config"])


if __name__ == "__main__":
    unittest.main()
