from __future__ import annotations

import json
import time
import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.api_keys import DatabaseApiKeyStore
from product_platform.api.rbac import Permission
from product_platform.api.settings import Settings
from product_platform.audit.store import AuditEventQuery, AuditEventRepository


class ApiKeyLifecycleRemediationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-05-19T00:00:00Z",
                dev_login_allowed_emails=["admin@example.com"],
                session_secret="test-secret",
            )
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "admin@example.com", "roles": ["Platform Admin"]},
        )
        self.assertEqual(login.status_code, 200, login.text)
        login_body = login.json()
        self.admin_user_id = login_body["user"]["id"]
        self.admin_headers = {
            "Authorization": f"Bearer {login_body['access_token']}",
            "X-Environment-ID": "env_default",
        }
        warmup = self.client.get("/api/v1/api-keys", headers=self.admin_headers)
        self.assertEqual(warmup.status_code, 200, warmup.text)

    def tearDown(self) -> None:
        self.app.state.database.close()

    def _create_key(self, scopes: list[str], **overrides: object) -> dict:
        body: dict[str, object] = {"name": "Lifecycle key", "scopes": scopes, "kind": "ci"}
        body.update(overrides)
        response = self.client.post("/api/v1/api-keys", json=body, headers=self.admin_headers)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def _audit_events(self, event_type: str | None = None) -> list:
        with self.app.state.database.transaction() as connection:
            return AuditEventRepository(connection).query(
                AuditEventQuery(
                    organization_id="org_default",
                    event_type=event_type,
                    limit=100,
                )
            )

    def test_api_key_creation_applies_expiry_policy_and_records_creator(self) -> None:
        created = self._create_key([Permission.TENANT_READ])

        self.assertIsNotNone(created["key"]["expires_at"])
        self.assertGreater(created["key"]["expires_at"], int(time.time()))
        self.assertEqual(created["key"]["created_by"], self.admin_user_id)
        self.assertIsNone(created["key"]["revoked_by"])
        self.assertIsNone(created["key"]["revoked_reason"])

        created_events = self._audit_events("admin.api_key.created")
        self.assertTrue(created_events)
        payload = created_events[0].payload_json
        self.assertEqual(payload["key_id"], created["key"]["id"])
        self.assertEqual(payload["created_by"], self.admin_user_id)
        self.assertNotIn(created["secret"], json.dumps(payload))

    def test_api_key_rotation_revokes_old_key_and_keeps_replacement_working(self) -> None:
        created = self._create_key([Permission.TENANT_READ])
        key_id = created["key"]["id"]
        old_secret = created["secret"]

        rotation = self.client.post(
            f"/api/v1/api-keys/{key_id}/rotate",
            json={
                "reason": "scheduled control rotation",
                "expires_at": int(time.time()) + 7200,
            },
            headers=self.admin_headers,
        )

        self.assertEqual(rotation.status_code, 201, rotation.text)
        body = rotation.json()
        self.assertTrue(body["secret"].startswith("opx_"))
        self.assertNotEqual(body["replacement_key"]["id"], key_id)
        self.assertEqual(body["replacement_key"]["rotated_from_key_id"], key_id)
        self.assertEqual(body["previous_key"]["rotated_to_key_id"], body["replacement_key"]["id"])
        self.assertEqual(body["previous_key"]["revoked_by"], self.admin_user_id)
        self.assertEqual(body["previous_key"]["revoked_reason"], "scheduled control rotation")

        old_response = self.client.get(
            "/api/v1/organizations",
            headers={"Authorization": f"Bearer {old_secret}"},
        )
        new_response = self.client.get(
            "/api/v1/organizations",
            headers={"Authorization": f"Bearer {body['secret']}"},
        )

        self.assertEqual(old_response.status_code, 401)
        self.assertEqual(new_response.status_code, 200)

        event_types = {event.event_type for event in self._audit_events()}
        self.assertIn("admin.api_key.rotated", event_types)
        self.assertIn("admin.api_key.revoked", event_types)
        failure_events = self._audit_events("auth.api_key.authentication_failed")
        self.assertTrue(
            any(event.payload_json.get("reason_code") == "api_key_revoked" for event in failure_events)
        )

    def test_api_key_revoke_persists_actor_reason_and_audits_revoked_use(self) -> None:
        created = self._create_key([Permission.TENANT_READ])
        key_id = created["key"]["id"]

        revoke = self.client.request(
            "DELETE",
            f"/api/v1/api-keys/{key_id}",
            json={"reason": "incident response"},
            headers=self.admin_headers,
        )

        self.assertEqual(revoke.status_code, 204, revoke.text)
        listed = self.client.get("/api/v1/api-keys", headers=self.admin_headers)
        matching = [key for key in listed.json() if key["id"] == key_id][0]
        self.assertEqual(matching["revoked_by"], self.admin_user_id)
        self.assertEqual(matching["revoked_reason"], "incident response")

        response = self.client.get(
            "/api/v1/organizations",
            headers={"Authorization": f"Bearer {created['secret']}"},
        )

        self.assertEqual(response.status_code, 401)
        failure_events = self._audit_events("auth.api_key.authentication_failed")
        self.assertTrue(
            any(
                event.resource_id == key_id
                and event.payload_json.get("reason_code") == "api_key_revoked"
                for event in failure_events
            )
        )

    def test_expired_key_and_environment_scope_violation_are_rejected_and_audited(self) -> None:
        with self.app.state.database.transaction() as connection:
            expired_record, expired_secret = DatabaseApiKeyStore(connection, "test-secret").create_key(
                organization_id="org_default",
                name="Expired key",
                scopes=[Permission.TENANT_READ],
                kind="ci",
                environment_ids=["env_default"],
                expires_at=int(time.time()) - 60,
                created_by=self.admin_user_id,
            )

        expired_response = self.client.get(
            "/api/v1/organizations",
            headers={"Authorization": f"Bearer {expired_secret}"},
        )

        self.assertEqual(expired_response.status_code, 401)

        created_environment = self.client.post(
            "/api/v1/environments",
            json={"name": "Other", "slug": "other-phase-three", "type": "development"},
            headers=self.admin_headers,
        )
        self.assertEqual(created_environment.status_code, 201, created_environment.text)
        scoped = self._create_key([Permission.POLICY_WRITE])
        scoped_response = self.client.post(
            "/api/v1/policies",
            headers={
                "Authorization": f"Bearer {scoped['secret']}",
                "X-Environment-ID": created_environment.json()["id"],
            },
        )

        self.assertEqual(scoped_response.status_code, 403)
        failure_events = self._audit_events("auth.api_key.authentication_failed")
        self.assertTrue(
            any(
                event.resource_id == expired_record.id
                and event.payload_json.get("reason_code") == "api_key_expired"
                for event in failure_events
            )
        )
        scope_events = self._audit_events("auth.api_key.scope_violation")
        self.assertTrue(
            any(
                event.resource_id == scoped["key"]["id"]
                and event.payload_json.get("requested_environment_id")
                == created_environment.json()["id"]
                for event in scope_events
            )
        )


if __name__ == "__main__":
    unittest.main()
