from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.audit.store import AuditEventQuery, AuditEventRepository
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


class CredentialOverallValidationTests(unittest.TestCase):
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
                "agent_overall_demo",
                "org_default",
                "env_default",
                "Overall Credential Demo",
                "Agent used for end-to-end credential validation.",
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
                "ident_overall_demo",
                "agent_overall_demo",
                "did:agentmesh:test:overall-demo",
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
                "cap_overall_read",
                "agent_overall_demo",
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

    def test_issue_verify_rotate_reject_old_token_and_surface_audit_state(self) -> None:
        issued = self.client.post(
            "/api/v1/agents/agent_overall_demo/credentials",
            headers=self._headers(),
            json={
                "credential_type": "bearer",
                "issuer": "local-agentmesh",
                "ttl_seconds": 600,
                "issued_for": "overall-validation",
                "scopes": [{"scope": "claims:read", "resource_type": "claim"}],
            },
        )
        self.assertEqual(issued.status_code, 201)
        issued_payload = issued.json()
        old_credential = issued_payload["credential"]
        old_token = issued_payload["token"]

        verified = self.client.post(
            f"/api/v1/credentials/{old_credential['id']}/verify",
            headers=self._headers(),
            json={"token": old_token},
        )
        self.assertEqual(verified.status_code, 200)
        self.assertTrue(verified.json()["valid"])

        rotated = self.client.post(
            f"/api/v1/credentials/{old_credential['id']}/rotate",
            headers=self._headers(),
            json={"reason": "overall validation rotation"},
        )
        self.assertEqual(rotated.status_code, 200)
        rotated_payload = rotated.json()
        new_credential = rotated_payload["credential"]
        new_token = rotated_payload["token"]

        old_rejected = self.client.post(
            f"/api/v1/credentials/{old_credential['id']}/verify",
            headers=self._headers(),
            json={"token": old_token},
        )
        self.assertEqual(old_rejected.status_code, 200)
        self.assertFalse(old_rejected.json()["valid"])
        self.assertEqual(old_rejected.json()["status"], "revoked")

        new_verified = self.client.post(
            f"/api/v1/credentials/{new_credential['id']}/verify",
            headers=self._headers(),
            json={"token": new_token},
        )
        self.assertEqual(new_verified.status_code, 200)
        self.assertTrue(new_verified.json()["valid"])

        listed = self.client.get(
            "/api/v1/agents/agent_overall_demo/credentials",
            headers=self._headers(),
        )
        self.assertEqual(listed.status_code, 200)
        statuses = {credential["id"]: credential["status"] for credential in listed.json()}
        self.assertEqual(statuses[old_credential["id"]], "revoked")
        self.assertEqual(statuses[new_credential["id"]], "active")

        events = AuditEventRepository(self.database.connect()).query(
            AuditEventQuery(
                organization_id="org_default",
                agent_id="agent_overall_demo",
                limit=20,
            )
        )
        event_types = {event.event_type for event in events}
        self.assertIn("agent.credential.issued", event_types)
        self.assertIn("agent.credential.rotated", event_types)
        self.assertIn("agent.credential.revocation_published", event_types)


if __name__ == "__main__":
    unittest.main()
