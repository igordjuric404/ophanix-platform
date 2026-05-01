from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.audit.store import AuditEventQuery, AuditEventRepository
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


class AgentRegistrationPhase4ApiTests(unittest.TestCase):
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
                dev_login_allowed_emails=["admin@example.com", "viewer@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.admin_token, self.admin_user = self._login("admin@example.com", ["Platform Admin"])
        self.viewer_token, self.viewer_user = self._login("viewer@example.com", ["Viewer"])

    def _login(self, email: str, roles: list[str]) -> tuple[str, dict]:
        response = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": email, "roles": roles},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        return payload["access_token"], payload["user"]

    def _headers(self, token: str | None = None) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token or self.admin_token}",
            "X-Environment-ID": "env_default",
        }

    def _create_ready_draft(self) -> str:
        draft = self.client.post(
            "/api/v1/agents/registration-drafts",
            headers=self._headers(),
            json={
                "name": "Lifecycle Agent",
                "description": "Ready for approval.",
                "framework": "langgraph",
                "runtime_type": "service",
                "owner_user_id": self.admin_user["id"],
                "sponsor_user_id": self.admin_user["id"],
            },
        )
        self.assertEqual(draft.status_code, 201)
        draft_id = draft.json()["id"]
        identity = self.client.post(
            f"/api/v1/agents/registration-drafts/{draft_id}/identity",
            headers=self._headers(),
        )
        self.assertEqual(identity.status_code, 200)
        patch = self.client.patch(
            f"/api/v1/agents/registration-drafts/{draft_id}",
            headers=self._headers(),
            json={
                "capabilities": [{"capability_name": "claims:read", "resource_type": "claim"}],
                "policy_selections": [
                    {
                        "policy_id": "policy_placeholder_default_allow",
                        "selection_type": "policy_binding",
                    }
                ],
            },
        )
        self.assertEqual(patch.status_code, 200)
        return draft_id

    def _submit(self, draft_id: str) -> dict:
        response = self.client.post(
            f"/api/v1/agents/registration-drafts/{draft_id}/submit",
            headers=self._headers(),
        )
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_submit_changes_status_to_pending_approval(self) -> None:
        draft_id = self._create_ready_draft()

        payload = self._submit(draft_id)

        self.assertEqual(payload["id"], draft_id)
        self.assertEqual(payload["status"], "pending_approval")

    def test_unauthorized_user_cannot_approve(self) -> None:
        draft_id = self._create_ready_draft()
        self._submit(draft_id)

        response = self.client.post(
            f"/api/v1/agents/{draft_id}/approve",
            headers=self._headers(self.viewer_token),
            json={"reason": "viewer should not approve"},
        )

        self.assertEqual(response.status_code, 403)

    def test_approved_agent_can_be_activated(self) -> None:
        draft_id = self._create_ready_draft()
        self._submit(draft_id)
        approved = self.client.post(
            f"/api/v1/agents/{draft_id}/approve",
            headers=self._headers(),
            json={"reason": "looks good"},
        )
        self.assertEqual(approved.status_code, 200)
        self.assertEqual(approved.json()["status"], "provisioned")
        self.assertEqual(approved.json()["capabilities"][0]["status"], "approved")

        activated = self.client.post(
            f"/api/v1/agents/{draft_id}/activate",
            headers=self._headers(),
            json={"reason": "initial launch"},
        )

        self.assertEqual(activated.status_code, 200)
        self.assertEqual(activated.json()["status"], "active")
        job = self.database.connect().execute(
            "SELECT * FROM background_jobs WHERE job_type = ? AND organization_id = ?",
            ("agent.credential.issue", "org_default"),
        ).fetchone()
        self.assertIsNotNone(job)
        self.assertEqual(job["status"], "queued")

    def test_activation_emits_lifecycle_audit_event(self) -> None:
        draft_id = self._create_ready_draft()
        self._submit(draft_id)
        approve = self.client.post(
            f"/api/v1/agents/{draft_id}/approve",
            headers=self._headers(),
        )
        self.assertEqual(approve.status_code, 200)

        activate = self.client.post(
            f"/api/v1/agents/{draft_id}/activate",
            headers=self._headers(),
        )
        self.assertEqual(activate.status_code, 200)

        events = AuditEventRepository(self.database.connect()).query(
            AuditEventQuery(
                organization_id="org_default",
                event_type="agent.lifecycle",
                agent_id=draft_id,
            )
        )
        states = [event.payload_json["lifecycle_state"] for event in events]
        self.assertIn("active", states)


if __name__ == "__main__":
    unittest.main()
