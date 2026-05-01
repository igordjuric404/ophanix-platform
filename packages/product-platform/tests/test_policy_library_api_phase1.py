from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.policies.models import PolicyCreateRequest
from product_platform.policies.repository import PolicyRepository


SAMPLE_POLICY = """version: "1.0"
name: api-policy
rules:
  - name: block_shell
    condition:
      field: tool_name
      operator: eq
      value: run_shell
    action: deny
"""


class PolicyLibraryApiPhase1Tests(unittest.TestCase):
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
                dev_login_allowed_emails=["admin@example.com", "viewer@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def _login(self, email: str, roles: list[str]) -> tuple[str, dict]:
        response = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": email, "roles": roles},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        return payload["access_token"], payload["user"]

    def _headers(self, token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token}",
            "X-Request-ID": "req-policy-library",
        }

    def test_api_creates_policy(self) -> None:
        token, user = self._login("admin@example.com", ["Platform Admin"])

        response = self.client.post(
            "/api/v1/policies",
            headers=self._headers(token),
            json={
                "name": "API Runtime Guardrails",
                "description": "Blocks risky runtime actions.",
                "scope": "runtime-action",
                "tags": ["runtime", "safety"],
            },
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertTrue(payload["id"].startswith("policy_"))
        self.assertEqual(payload["organization_id"], "org_default")
        self.assertEqual(payload["owner_user_id"], user["id"])
        self.assertEqual(payload["slug"], "api-runtime-guardrails")
        self.assertEqual(payload["tags"], ["runtime", "safety"])

    def test_api_creates_multiple_versions_and_gets_detail(self) -> None:
        token, _ = self._login("admin@example.com", ["Platform Admin"])
        policy = self.client.post(
            "/api/v1/policies",
            headers=self._headers(token),
            json={"name": "API MCP Guard", "scope": "mcp-tool"},
        ).json()

        first = self.client.post(
            f"/api/v1/policies/{policy['id']}/versions",
            headers=self._headers(token),
            json={"body_format": "yaml", "body_text": SAMPLE_POLICY, "backend": "native"},
        )
        second = self.client.post(
            f"/api/v1/policies/{policy['id']}/versions",
            headers=self._headers(token),
            json={
                "body_format": "yaml",
                "body_text": SAMPLE_POLICY.replace("run_shell", "delete_file"),
                "backend": "native",
            },
        )
        detail = self.client.get(f"/api/v1/policies/{policy['id']}", headers=self._headers(token))

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertEqual(first.json()["version_number"], 1)
        self.assertEqual(second.json()["version_number"], 2)
        self.assertNotEqual(first.json()["checksum"], second.json()["checksum"])
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["version_count"], 2)
        self.assertEqual(
            [version["version_number"] for version in detail.json()["versions"]],
            [2, 1],
        )

    def test_api_list_is_scoped_by_organization(self) -> None:
        token, _ = self._login("admin@example.com", ["Platform Admin"])
        with self.database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO organizations (id, name, slug, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    "org_other",
                    "Other Org",
                    "other-org",
                    "2026-05-01T00:00:00+00:00",
                    "2026-05-01T00:00:00+00:00",
                ),
            )
            other_policy = PolicyRepository(connection, "org_other").create_policy(
                PolicyCreateRequest(name="Other Org Policy", scope="agent"),
                actor_id="other_user",
            )
        own_policy = self.client.post(
            "/api/v1/policies",
            headers=self._headers(token),
            json={"name": "Own Org Policy", "scope": "agent"},
        ).json()

        response = self.client.get("/api/v1/policies", headers=self._headers(token))

        self.assertEqual(response.status_code, 200)
        ids = [policy["id"] for policy in response.json()]
        self.assertIn(own_policy["id"], ids)
        self.assertNotIn(other_policy["id"], ids)


if __name__ == "__main__":
    unittest.main()
