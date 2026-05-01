from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.api_keys import ApiKeyStore
from product_platform.api.rbac import Permission
from product_platform.api.settings import Settings


class ApiKeyHashTests(unittest.TestCase):
    def test_api_key_hash_verification(self) -> None:
        store = ApiKeyStore("pepper")
        record, secret = store.create_key(
            organization_id="org_default",
            name="CI key",
            scopes=[Permission.SYSTEM_READ],
            kind="ci",
        )

        self.assertNotEqual(record.hashed_secret, secret)
        self.assertTrue(store.verify_secret(secret, record.hashed_secret))
        self.assertFalse(store.verify_secret(secret + "-wrong", record.hashed_secret))


class AuthPhase4Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-04-30T00:00:00Z",
                dev_login_allowed_emails=["admin@example.com"],
                session_secret="test-secret",
            )
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "admin@example.com", "roles": ["Platform Admin"]},
        )
        self.admin_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    def _create_key(self, scopes: list[str]) -> dict:
        response = self.client.post(
            "/api/v1/api-keys",
            json={"name": "Scoped key", "scopes": scopes, "kind": "ci"},
            headers=self.admin_headers,
        )
        self.assertEqual(response.status_code, 201)
        return response.json()

    def test_api_key_creation_returns_one_time_secret_and_list_hides_it(self) -> None:
        created = self._create_key([Permission.SYSTEM_READ])

        self.assertTrue(created["secret"].startswith("opx_"))
        self.assertEqual(created["key"]["name"], "Scoped key")
        records = self.app.state.api_key_store.records
        self.assertNotIn(created["secret"], records[created["key"]["id"]].hashed_secret)

        listed = self.client.get("/api/v1/api-keys", headers=self.admin_headers)
        self.assertEqual(listed.status_code, 200)
        self.assertNotIn("secret", listed.json()[0])

    def test_revoked_key_is_rejected(self) -> None:
        created = self._create_key([Permission.TENANT_READ])
        secret = created["secret"]
        key_id = created["key"]["id"]
        revoke = self.client.delete(f"/api/v1/api-keys/{key_id}", headers=self.admin_headers)
        self.assertEqual(revoke.status_code, 204)

        response = self.client.get(
            "/api/v1/organizations",
            headers={"Authorization": f"Bearer {secret}"},
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], "UNAUTHENTICATED")

    def test_scope_limited_key_cannot_access_forbidden_route(self) -> None:
        created = self._create_key([Permission.SYSTEM_READ])
        response = self.client.post(
            "/api/v1/policies",
            headers={
                "Authorization": f"Bearer {created['secret']}",
                "X-Environment-ID": "env_default",
            },
        )

        self.assertEqual(response.status_code, 403)

    def test_api_key_records_last_used_time(self) -> None:
        created = self._create_key([Permission.TENANT_READ])
        key_id = created["key"]["id"]
        response = self.client.get(
            "/api/v1/organizations",
            headers={"Authorization": f"Bearer {created['secret']}"},
        )

        self.assertEqual(response.status_code, 200)
        listed = self.client.get("/api/v1/api-keys", headers=self.admin_headers).json()
        matching = [key for key in listed if key["id"] == key_id][0]
        self.assertIsNotNone(matching["last_used_at"])


if __name__ == "__main__":
    unittest.main()

