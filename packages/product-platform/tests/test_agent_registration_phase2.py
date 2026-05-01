from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.agents.identity import AgentIdentityAdapter
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


class AgentIdentityAdapterTests(unittest.TestCase):
    def test_adapter_creates_valid_identity_object(self) -> None:
        created = AgentIdentityAdapter().create_identity(
            name="Claims Assistant",
            sponsor_email="sponsor@example.com",
            organization="org_default",
            description="Triage agent.",
            capabilities=["claims:read"],
        )

        self.assertTrue(created.did.startswith("did:mesh:"))
        self.assertEqual(created.key_type, "ed25519")
        self.assertEqual(len(created.public_key_fingerprint), 64)
        self.assertEqual(created.bootstrap.did, created.did)
        self.assertIn("BEGIN PRIVATE KEY", created.bootstrap.private_key_pem)


class AgentRegistrationPhase2ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
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
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "admin@example.com", "roles": ["Platform Admin"]},
        )
        self.assertEqual(login.status_code, 200)
        self.token = login.json()["access_token"]
        self.user = login.json()["user"]

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
        }

    def _create_draft(self) -> str:
        response = self.client.post(
            "/api/v1/agents/registration-drafts",
            headers=self._headers(),
            json={
                "name": "Identity Agent",
                "description": "Needs a product identity.",
                "framework": "langgraph",
                "runtime_type": "service",
                "owner_user_id": self.user["id"],
                "sponsor_user_id": self.user["id"],
            },
        )
        self.assertEqual(response.status_code, 201)
        return response.json()["id"]

    def test_api_persists_identity_with_agent(self) -> None:
        draft_id = self._create_draft()

        response = self.client.post(
            f"/api/v1/agents/registration-drafts/{draft_id}/identity",
            headers=self._headers(),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["identity"]["agent_id"], draft_id)
        self.assertTrue(payload["identity"]["did"].startswith("did:mesh:"))
        self.assertEqual(payload["identity"]["key_type"], "ed25519")
        self.assertEqual(payload["identity"]["identity_status"], "active")
        self.assertIn("BEGIN PRIVATE KEY", payload["bootstrap"]["private_key_pem"])

        row = self.database.connect().execute(
            "SELECT * FROM agent_identities WHERE agent_id = ?",
            (draft_id,),
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["did"], payload["identity"]["did"])
        self.assertIsNone(row["bootstrap_material_json"])

    def test_security_response_hides_private_key_after_initial_bootstrap(self) -> None:
        draft_id = self._create_draft()
        first = self.client.post(
            f"/api/v1/agents/registration-drafts/{draft_id}/identity",
            headers=self._headers(),
        )
        self.assertEqual(first.status_code, 200)
        self.assertIn("BEGIN PRIVATE KEY", first.text)

        second = self.client.post(
            f"/api/v1/agents/registration-drafts/{draft_id}/identity",
            headers=self._headers(),
        )

        self.assertEqual(second.status_code, 200)
        payload = second.json()
        self.assertIsNone(payload["bootstrap"])
        self.assertNotIn("PRIVATE KEY", second.text)


if __name__ == "__main__":
    unittest.main()
