from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.agents.simulation import simulate_registration_action
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


class AgentRegistrationSimulationTests(unittest.TestCase):
    def test_simulation_allows_safe_capability_with_policy(self) -> None:
        result = simulate_registration_action(
            agent_id="agent_1",
            capability_names=["claims:read"],
            policy_ids=["policy_placeholder_default_allow"],
        )

        self.assertEqual(result.decision, "allow")
        self.assertEqual(result.action, "claims:read")
        self.assertEqual(result.matched_policy_ids, ["policy_placeholder_default_allow"])


class AgentRegistrationPhase3ApiTests(unittest.TestCase):
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
                "name": "Capability Agent",
                "description": "Needs capabilities.",
                "framework": "langgraph",
                "runtime_type": "service",
                "owner_user_id": self.user["id"],
                "sponsor_user_id": self.user["id"],
            },
        )
        self.assertEqual(response.status_code, 201)
        return response.json()["id"]

    def test_api_stores_requested_capability_as_pending(self) -> None:
        draft_id = self._create_draft()

        response = self.client.patch(
            f"/api/v1/agents/registration-drafts/{draft_id}",
            headers=self._headers(),
            json={
                "capabilities": [
                    {"capability_name": "claims:read", "resource_type": "claim"},
                ],
                "policy_selections": [
                    {
                        "policy_id": "policy_placeholder_default_allow",
                        "selection_type": "policy_binding",
                    }
                ],
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["capabilities"][0]["capability_name"], "claims:read")
        self.assertEqual(payload["capabilities"][0]["resource_type"], "claim")
        self.assertEqual(payload["capabilities"][0]["status"], "pending")
        self.assertEqual(payload["capabilities"][0]["requested_by"], self.user["id"])
        self.assertEqual(
            payload["policy_selections"][0]["policy_id"],
            "policy_placeholder_default_allow",
        )

    def test_api_rejects_invalid_capability_name(self) -> None:
        draft_id = self._create_draft()

        response = self.client.patch(
            f"/api/v1/agents/registration-drafts/{draft_id}",
            headers=self._headers(),
            json={"capabilities": [{"capability_name": "*", "resource_type": "claim"}]},
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["code"], "VALIDATION_ERROR")

    def test_integration_policy_simulation_returns_decision_before_submission(self) -> None:
        draft_id = self._create_draft()
        patch = self.client.patch(
            f"/api/v1/agents/registration-drafts/{draft_id}",
            headers=self._headers(),
            json={
                "capabilities": [
                    {"capability_name": "claims:read", "resource_type": "claim"},
                ],
                "policy_selections": [
                    {
                        "policy_id": "policy_placeholder_default_allow",
                        "selection_type": "policy_binding",
                    }
                ],
            },
        )
        self.assertEqual(patch.status_code, 200)

        response = self.client.post(
            f"/api/v1/agents/registration-drafts/{draft_id}/simulate",
            headers=self._headers(),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["agent_id"], draft_id)
        self.assertEqual(payload["decision"], "allow")
        self.assertEqual(payload["action"], "claims:read")
        self.assertEqual(payload["matched_policy_ids"], ["policy_placeholder_default_allow"])


if __name__ == "__main__":
    unittest.main()
