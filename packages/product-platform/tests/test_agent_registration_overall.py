from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.audit.store import AuditEventQuery, AuditEventRepository
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


class AgentRegistrationOverallValidationTests(unittest.TestCase):
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

    def test_register_demo_agent_end_to_end(self) -> None:
        draft = self.client.post(
            "/api/v1/agents/registration-drafts",
            headers=self._headers(),
            json={
                "name": "Demo Support Agent",
                "description": "Handles support ticket triage.",
                "framework": "langgraph",
                "runtime_type": "service",
                "endpoint_url": "https://agents.example.test/support",
                "owner_user_id": self.user["id"],
                "sponsor_user_id": self.user["id"],
            },
        )
        self.assertEqual(draft.status_code, 201)
        agent_id = draft.json()["id"]

        identity = self.client.post(
            f"/api/v1/agents/registration-drafts/{agent_id}/identity",
            headers=self._headers(),
        )
        self.assertEqual(identity.status_code, 200)
        self.assertTrue(identity.json()["identity"]["did"].startswith("did:mesh:"))
        self.assertIn("BEGIN PRIVATE KEY", identity.json()["bootstrap"]["private_key_pem"])

        selections = self.client.patch(
            f"/api/v1/agents/registration-drafts/{agent_id}",
            headers=self._headers(),
            json={
                "capabilities": [{"capability_name": "support:read", "resource_type": "ticket"}],
                "policy_selections": [
                    {
                        "policy_id": "policy_placeholder_default_allow",
                        "selection_type": "policy_binding",
                    }
                ],
            },
        )
        self.assertEqual(selections.status_code, 200)
        self.assertEqual(selections.json()["capabilities"][0]["status"], "pending")

        simulation = self.client.post(
            f"/api/v1/agents/registration-drafts/{agent_id}/simulate",
            headers=self._headers(),
        )
        self.assertEqual(simulation.status_code, 200)
        self.assertEqual(simulation.json()["decision"], "allow")

        submitted = self.client.post(
            f"/api/v1/agents/registration-drafts/{agent_id}/submit",
            headers=self._headers(),
        )
        self.assertEqual(submitted.status_code, 200)
        self.assertEqual(submitted.json()["status"], "pending_approval")

        approved = self.client.post(
            f"/api/v1/agents/{agent_id}/approve",
            headers=self._headers(),
        )
        self.assertEqual(approved.status_code, 200)
        self.assertEqual(approved.json()["capabilities"][0]["status"], "approved")

        activated = self.client.post(
            f"/api/v1/agents/{agent_id}/activate",
            headers=self._headers(),
        )
        self.assertEqual(activated.status_code, 200)
        self.assertEqual(activated.json()["status"], "active")

        events = AuditEventRepository(self.database.connect()).query(
            AuditEventQuery(organization_id="org_default", agent_id=agent_id, limit=20)
        )
        event_types = {event.event_type for event in events}
        lifecycle_states = {
            event.payload_json.get("lifecycle_state")
            for event in events
            if event.event_type == "agent.lifecycle"
        }

        self.assertIn("agent.registration_draft.created", event_types)
        self.assertIn("agent.registration_submitted", event_types)
        self.assertIn("agent.lifecycle", event_types)
        self.assertIn("provisioned", lifecycle_states)
        self.assertIn("active", lifecycle_states)


if __name__ == "__main__":
    unittest.main()
