from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.audit.store import AuditEventQuery, AuditEventRepository
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


class CredentialPhase3Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent_with_identity(connection)
        self.app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-04-30T00:00:00Z",
                dev_login_allowed_emails=["admin@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.admin_token, self.admin_user = self._login("admin@example.com", ["Platform Admin"])

    def _insert_agent_with_identity(self, connection) -> None:
        now = "2026-04-30T00:00:00+00:00"
        connection.execute(
            """
            INSERT INTO agents (
                id, organization_id, environment_id, name, description, framework,
                runtime_type, endpoint_url, owner_user_id, sponsor_user_id, status,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "agent_rotation_demo",
                "org_default",
                "env_default",
                "Rotation Demo",
                "Agent used for credential rotation tests.",
                "langgraph",
                "service",
                None,
                "user_admin",
                "user_admin",
                "active",
                now,
                now,
            ),
        )
        connection.execute(
            """
            INSERT INTO agent_identities (
                id, agent_id, did, public_key_fingerprint, key_type,
                identity_status, bootstrap_material_json, bootstrap_retrieved_at,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "ident_rotation_demo",
                "agent_rotation_demo",
                "did:agentmesh:test:rotation-demo",
                "fingerprint",
                "ed25519",
                "active",
                None,
                now,
                now,
            ),
        )
        connection.execute(
            """
            INSERT INTO agent_capabilities (
                id, agent_id, capability_name, resource_type, status,
                requested_by, approved_by, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "cap_rotation_read",
                "agent_rotation_demo",
                "claims:read",
                "claim",
                "approved",
                "user_admin",
                "user_admin",
                now,
            ),
        )

    def _login(self, email: str, roles: list[str]) -> tuple[str, dict]:
        response = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": email, "roles": roles},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        return payload["access_token"], payload["user"]

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.admin_token}",
            "X-Environment-ID": "env_default",
        }

    def _issue(self) -> dict:
        response = self.client.post(
            "/api/v1/agents/agent_rotation_demo/credentials",
            headers=self._headers(),
            json={
                "credential_type": "bearer",
                "issuer": "local-agentmesh",
                "ttl_seconds": 600,
                "issued_for": "phase3-test",
                "scopes": [{"scope": "claims:read", "resource_type": "claim"}],
            },
        )
        self.assertEqual(response.status_code, 201)
        return response.json()

    def test_api_rotate_creates_new_active_credential(self) -> None:
        original = self._issue()["credential"]

        response = self.client.post(
            f"/api/v1/credentials/{original['id']}/rotate",
            headers=self._headers(),
            json={"reason": "scheduled rotation"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["rotation_id"].startswith("rot_"))
        self.assertEqual(payload["previous_credential"]["id"], original["id"])
        self.assertEqual(payload["previous_credential"]["status"], "revoked")
        self.assertNotEqual(payload["credential"]["id"], original["id"])
        self.assertEqual(payload["credential"]["status"], "active")
        self.assertTrue(payload["token"])

    def test_api_rotate_revokes_old_credential(self) -> None:
        original = self._issue()["credential"]

        rotate = self.client.post(
            f"/api/v1/credentials/{original['id']}/rotate",
            headers=self._headers(),
            json={"reason": "compromised token"},
        )
        self.assertEqual(rotate.status_code, 200)

        revoked = self.client.get(
            "/api/v1/agents/agent_rotation_demo/credentials?status=revoked",
            headers=self._headers(),
        )
        self.assertEqual(revoked.status_code, 200)
        self.assertEqual([item["id"] for item in revoked.json()], [original["id"]])

    def test_api_revoke_requires_reason(self) -> None:
        original = self._issue()["credential"]

        response = self.client.post(
            f"/api/v1/credentials/{original['id']}/revoke",
            headers=self._headers(),
            json={},
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("Reason is required", response.json()["message"])

    def test_integration_rotation_emits_audit_lifecycle_and_revocation_events(self) -> None:
        original = self._issue()["credential"]

        response = self.client.post(
            f"/api/v1/credentials/{original['id']}/rotate",
            headers=self._headers(),
            json={"reason": "routine rollover"},
        )
        self.assertEqual(response.status_code, 200)
        new_credential_id = response.json()["credential"]["id"]

        rotation = self.database.connect().execute(
            "SELECT * FROM credential_rotations WHERE previous_credential_id = ?",
            (original["id"],),
        ).fetchone()
        self.assertIsNotNone(rotation)
        self.assertEqual(rotation["new_credential_id"], new_credential_id)
        self.assertEqual(rotation["status"], "completed")

        events = AuditEventRepository(self.database.connect()).query(
            AuditEventQuery(
                organization_id="org_default",
                agent_id="agent_rotation_demo",
                limit=20,
            )
        )
        event_types = {event.event_type for event in events}
        self.assertIn("agent.credential.rotated", event_types)
        self.assertIn("agent.credential.revocation_published", event_types)

        lifecycle = self.database.connect().execute(
            """
            SELECT *
            FROM agent_lifecycle_events
            WHERE agent_id = ? AND reason = ?
            """,
            ("agent_rotation_demo", "credential rotated"),
        ).fetchall()
        self.assertEqual(len(lifecycle), 1)
        self.assertIn(new_credential_id, lifecycle[0]["metadata_json"])


if __name__ == "__main__":
    unittest.main()
