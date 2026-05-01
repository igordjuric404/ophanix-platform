from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.api.tenancy import apply_organization_scope


class QueryScopeTests(unittest.TestCase):
    def test_query_helper_always_includes_organization_id(self) -> None:
        filters = apply_organization_scope({"status": "active"}, "org_default")

        self.assertEqual(filters["status"], "active")
        self.assertEqual(filters["organization_id"], "org_default")

    def test_query_helper_overrides_untrusted_organization_id(self) -> None:
        filters = apply_organization_scope({"organization_id": "org_other"}, "org_default")

        self.assertEqual(filters["organization_id"], "org_default")


class AuthPhase3Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(
            create_app(
                Settings(
                    app_name="Ophanix Test Platform",
                    environment="test",
                    build_sha="test-sha",
                    build_time="2026-04-30T00:00:00Z",
                    dev_login_allowed_emails=["admin@example.com", "policy@example.com"],
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

    def test_user_cannot_access_another_organization(self) -> None:
        token = self._token_for("admin@example.com", ["Platform Admin"])
        response = self.client.get(
            "/api/v1/environments",
            headers={"Authorization": f"Bearer {token}", "X-Organization-ID": "org_other"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "FORBIDDEN")

    def test_environment_id_is_required_for_environment_scoped_resources(self) -> None:
        token = self._token_for("policy@example.com", ["Policy Admin"])
        response = self.client.post(
            "/api/v1/policies",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["message"], "X-Environment-ID is required.")

    def test_organizations_and_environments_are_scoped_to_current_user(self) -> None:
        token = self._token_for("admin@example.com", ["Platform Admin"])
        headers = {"Authorization": f"Bearer {token}"}

        orgs = self.client.get("/api/v1/organizations", headers=headers)
        envs = self.client.get("/api/v1/environments", headers=headers)

        self.assertEqual(orgs.status_code, 200)
        self.assertEqual(envs.status_code, 200)
        self.assertEqual([org["id"] for org in orgs.json()], ["org_default"])
        self.assertEqual([env["organization_id"] for env in envs.json()], ["org_default"])


if __name__ == "__main__":
    unittest.main()

