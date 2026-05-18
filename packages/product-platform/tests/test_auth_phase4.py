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
                dev_login_allowed_emails=["admin@example.com", "security@example.com"],
                session_secret="test-secret",
            )
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "admin@example.com", "roles": ["Platform Admin"]},
        )
        self.admin_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    def _headers_for(self, email: str, roles: list[str]) -> dict[str, str]:
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": email, "roles": roles},
        )
        self.assertEqual(login.status_code, 200, login.text)
        return {"Authorization": f"Bearer {login.json()['access_token']}"}

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
        with self.app.state.database.transaction() as connection:
            row = connection.execute(
                "SELECT hashed_secret FROM api_keys WHERE id = ?",
                (created["key"]["id"],),
            ).fetchone()
        self.assertIsNotNone(row)
        self.assertNotIn(created["secret"], row["hashed_secret"])

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

    def test_api_key_creation_rejects_unknown_scope(self) -> None:
        response = self.client.post(
            "/api/v1/api-keys",
            json={"name": "Bad key", "scopes": ["policy:*"], "kind": "ci"},
            headers=self.admin_headers,
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Unknown API key scope", response.text)

    def test_api_key_creation_cannot_delegate_ungranted_scope(self) -> None:
        security_headers = self._headers_for("security@example.com", ["Security Admin"])

        response = self.client.post(
            "/api/v1/api-keys",
            json={"name": "Too broad", "scopes": [Permission.JOB_CANCEL], "kind": "ci"},
            headers=security_headers,
        )

        self.assertEqual(response.status_code, 403)
        self.assertIn("Cannot delegate", response.text)

    def test_api_key_creation_normalizes_duplicate_scopes(self) -> None:
        created = self._create_key(["", Permission.SYSTEM_READ, Permission.SYSTEM_READ])

        self.assertEqual(created["key"]["scopes"], [Permission.SYSTEM_READ])

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

    def test_api_key_authentication_survives_app_recreation(self) -> None:
        created = self._create_key([Permission.TENANT_READ])
        database = self.app.state.database
        second_app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-04-30T00:00:00Z",
                dev_login_allowed_emails=["admin@example.com"],
                session_secret="test-secret",
            ),
            database=database,
        )
        second_client = TestClient(second_app, raise_server_exceptions=False)

        response = second_client.get(
            "/api/v1/organizations",
            headers={"Authorization": f"Bearer {created['secret']}"},
        )

        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
