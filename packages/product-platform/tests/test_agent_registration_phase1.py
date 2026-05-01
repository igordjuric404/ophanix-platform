from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.audit.store import AuditEventQuery, AuditEventRepository
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


class AgentRegistrationPhase1Tests(unittest.TestCase):
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

    def _login(self, email: str, roles: list[str]) -> tuple[str, dict]:
        response = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": email, "roles": roles},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        return payload["access_token"], payload["user"]

    def _headers(self, token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token}",
            "X-Environment-ID": "env_default",
            "X-Request-ID": "req-agent-registration",
        }

    def _draft_body(self, user_id: str, *, name: str = "Claims Assistant") -> dict:
        return {
            "name": name,
            "description": "Triages incoming claims and drafts next actions.",
            "framework": "langgraph",
            "runtime_type": "service",
            "endpoint_url": "https://agents.example.test/claims",
            "owner_user_id": user_id,
            "sponsor_user_id": user_id,
        }

    def test_api_creates_registration_draft(self) -> None:
        token, user = self._login("admin@example.com", ["Platform Admin"])

        response = self.client.post(
            "/api/v1/agents/registration-drafts",
            headers=self._headers(token),
            json=self._draft_body(user["id"]),
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertTrue(payload["id"].startswith("agent_"))
        self.assertEqual(payload["organization_id"], "org_default")
        self.assertEqual(payload["environment_id"], "env_default")
        self.assertEqual(payload["name"], "Claims Assistant")
        self.assertEqual(payload["owner_user_id"], user["id"])
        self.assertEqual(payload["sponsor_user_id"], user["id"])
        self.assertEqual(payload["framework"], "langgraph")
        self.assertEqual(payload["runtime_type"], "service")
        self.assertEqual(payload["status"], "draft")

    def test_api_duplicate_name_is_rejected_per_environment(self) -> None:
        token, user = self._login("admin@example.com", ["Platform Admin"])
        first = self.client.post(
            "/api/v1/agents/registration-drafts",
            headers=self._headers(token),
            json=self._draft_body(user["id"], name="Duplicate Agent"),
        )
        self.assertEqual(first.status_code, 201)

        duplicate = self.client.post(
            "/api/v1/agents/registration-drafts",
            headers=self._headers(token),
            json=self._draft_body(user["id"], name="duplicate agent"),
        )

        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(duplicate.json()["code"], "HTTP_ERROR")
        self.assertIn("already exists", duplicate.json()["message"])

    def test_viewer_cannot_create_registration_draft(self) -> None:
        token, user = self._login("viewer@example.com", ["Viewer"])

        response = self.client.post(
            "/api/v1/agents/registration-drafts",
            headers=self._headers(token),
            json=self._draft_body(user["id"]),
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "HTTP_ERROR")

    def test_integration_audit_event_is_emitted_for_draft_creation(self) -> None:
        token, user = self._login("admin@example.com", ["Platform Admin"])

        response = self.client.post(
            "/api/v1/agents/registration-drafts",
            headers=self._headers(token),
            json=self._draft_body(user["id"], name="Audited Agent"),
        )
        self.assertEqual(response.status_code, 201)
        agent_id = response.json()["id"]

        events = AuditEventRepository(self.database.connect()).query(
            AuditEventQuery(
                organization_id="org_default",
                event_type="agent.registration_draft.created",
                agent_id=agent_id,
            )
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].resource_type, "agent")
        self.assertEqual(events[0].resource_id, agent_id)
        self.assertEqual(events[0].actor_id, user["id"])
        self.assertEqual(events[0].payload_json["name"], "Audited Agent")
        self.assertEqual(events[0].payload_json["status"], "draft")


if __name__ == "__main__":
    unittest.main()
