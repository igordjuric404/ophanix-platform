from __future__ import annotations

from pathlib import Path
import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


VALID_POLICY = """version: "1.0"
name: imported-inline
description: Inline import policy
rules:
  - name: block_shell
    condition:
      field: tool_name
      operator: eq
      value: run_shell
    action: deny
"""


class PolicyLibraryPhase2ImportTests(unittest.TestCase):
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
            "X-Request-ID": "req-policy-import",
        }

    def test_api_imports_valid_yaml_body(self) -> None:
        response = self.client.post(
            "/api/v1/policies/import",
            headers=self._headers(),
            json={
                "body_text": VALID_POLICY,
                "body_format": "yaml",
                "scope": "agent",
                "tags": ["imported"],
            },
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertTrue(payload["id"].startswith("pimp_"))
        self.assertEqual(payload["status"], "succeeded")
        self.assertEqual(payload["summary"]["rule_count"], 1)
        self.assertEqual(payload["policy"]["name"], "imported-inline")
        self.assertEqual(payload["policy"]["tags"], ["imported"])
        self.assertEqual(payload["version"]["body_text"], VALID_POLICY)

    def test_api_invalid_yaml_returns_validation_error(self) -> None:
        response = self.client.post(
            "/api/v1/policies/import",
            headers=self._headers(),
            json={
                "body_text": "version: [\nname: broken",
                "body_format": "yaml",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid YAML", response.json()["message"])

    def test_integration_imported_policy_version_body_matches_source(self) -> None:
        source_path = "packages/agent-os/examples/policies/default.yaml"
        source_body = (Path(__file__).resolve().parents[3] / source_path).read_text(
            encoding="utf-8"
        )

        response = self.client.post(
            "/api/v1/policies/import",
            headers=self._headers(),
            json={"source_path": source_path, "scope": "agent"},
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["source_type"], "repo_path")
        self.assertEqual(payload["source_path"], source_path)
        self.assertEqual(payload["version"]["body_text"], source_body)
        self.assertEqual(payload["summary"]["rule_count"], 3)

        export = self.client.get(
            f"/api/v1/policies/{payload['policy']['id']}/export",
            headers=self._headers(),
        )
        self.assertEqual(export.status_code, 200)
        self.assertEqual(export.json()["body_text"], source_body)
        self.assertEqual(export.json()["checksum"], payload["version"]["checksum"])


if __name__ == "__main__":
    unittest.main()
