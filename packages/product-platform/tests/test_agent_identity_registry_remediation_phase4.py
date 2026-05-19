from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


class AgentInventoryDetailRemediationPhase4Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
        self.app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-05-19T00:00:00Z",
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
        self.assertEqual(login.status_code, 200, login.text)
        self.token = login.json()["access_token"]

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
            "X-Correlation-ID": "corr-air-phase4",
        }

    def test_inventory_detail_and_timeline_surface_remediated_state(self) -> None:
        draft = self.client.post(
            "/api/v1/agents/registration-drafts",
            headers=self._headers(),
            json={
                "name": "Inventory Detail Agent",
                "description": "Phase 4 final visibility agent",
                "framework": "langgraph",
                "runtime_type": "service",
                "owner_user_id": "user_admin",
                "sponsor_user_id": "user_admin",
                "capabilities": [{"capability_name": "claims:read", "resource_type": "claim"}],
            },
        )
        self.assertEqual(draft.status_code, 201, draft.text)
        agent_id = draft.json()["id"]

        identity = self.client.post(
            f"/api/v1/agents/registration-drafts/{agent_id}/identity",
            headers=self._headers(),
            json={
                "proof_type": "agentmesh-local",
                "issuer": "local-agentmesh",
                "audience": "env_default",
                "trusted_root_id": "local-agentmesh",
                "trusted_root_version": "2026.05",
            },
        )
        self.assertEqual(identity.status_code, 200, identity.text)
        self.client.post(f"/api/v1/agents/registration-drafts/{agent_id}/submit", headers=self._headers())
        self.client.post(
            f"/api/v1/agents/{agent_id}/approve",
            headers=self._headers(),
            json={"reason": "phase4 approve"},
        )
        activated = self.client.post(
            f"/api/v1/agents/{agent_id}/activate",
            headers=self._headers(),
            json={"reason": "phase4 activate"},
        )
        self.assertEqual(activated.status_code, 200, activated.text)

        detail = self.client.get(f"/api/v1/agents/{agent_id}", headers=self._headers())
        self.assertEqual(detail.status_code, 200, detail.text)
        self.assertEqual(detail.json()["identity"]["issuer"], "local-agentmesh")
        self.assertEqual(detail.json()["identity"]["trusted_root_version"], "2026.05")
        self.assertEqual(detail.json()["capabilities"][0]["capability_name"], "claims:read")

        quarantined = self.client.post(
            f"/api/v1/agents/{agent_id}/quarantine",
            headers=self._headers(),
            json={"reason": "phase4 visibility quarantine"},
        )
        self.assertEqual(quarantined.status_code, 200, quarantined.text)

        filtered = self.client.get("/api/v1/agents?status=quarantined", headers=self._headers())
        self.assertEqual(filtered.status_code, 200, filtered.text)
        self.assertIn(agent_id, {agent["id"] for agent in filtered.json()})

        timeline = self.client.get(f"/api/v1/agents/{agent_id}/timeline", headers=self._headers())
        self.assertEqual(timeline.status_code, 200, timeline.text)
        event_types = {event.get("event_type") for event in timeline.json()}
        self.assertIn("agent.lifecycle", event_types)
        self.assertIn("agent.identity.verified", event_types)
        self.assertTrue(
            any(
                event.get("next_state") == "quarantined"
                or event.get("payload_json", {}).get("lifecycle_state") == "quarantined"
                for event in timeline.json()
            )
        )


if __name__ == "__main__":
    unittest.main()
