from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.audit.events import mcp_call_event, policy_decision_event
from product_platform.api.settings import Settings


class AuditOverallValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-04-30T00:00:00Z",
                dev_login_allowed_emails=["admin@example.com"],
                session_secret="test-secret",
            )
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "admin@example.com", "roles": ["Platform Admin"]},
        )
        self.headers = {
            "Authorization": f"Bearer {login.json()['access_token']}",
            "X-Environment-ID": "env_default",
        }

    def tearDown(self) -> None:
        database = getattr(self.app.state, "database", None)
        if database is not None:
            database.close()

    def test_two_sources_query_hash_verify_and_stream(self) -> None:
        policy_event = policy_decision_event(
            organization_id="org_default",
            environment_id="env_default",
            actor_id="user_admin",
            policy_id="policy_1",
            decision="allow",
            matched_rule="allow-read",
            reason="Read-only action.",
            correlation_id="corr-overall",
        )
        mcp_event = mcp_call_event(
            organization_id="org_default",
            environment_id="env_default",
            agent_id="agent_1",
            server_id="server_1",
            tool_name="read_file",
            decision="allow",
        )

        first = self.client.post(
            "/api/v1/audit/events",
            json=policy_event.model_dump(),
            headers=self.headers,
        )
        second = self.client.post(
            "/api/v1/audit/events",
            json=mcp_event.model_dump(),
            headers=self.headers,
        )
        listed = self.client.get("/api/v1/audit/events", headers=self.headers)
        verified = self.client.post("/api/v1/audit/verify-range", headers=self.headers)
        streamed = self.client.get("/api/v1/audit/events/stream", headers=self.headers)

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertEqual({event["event_type"] for event in listed.json()}, {"policy.decision", "mcp.call"})
        self.assertTrue(verified.json()["valid"])
        self.assertIn("policy.decision", streamed.text)
        self.assertIn("mcp.call", streamed.text)


if __name__ == "__main__":
    unittest.main()

