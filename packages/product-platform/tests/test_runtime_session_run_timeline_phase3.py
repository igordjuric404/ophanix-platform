from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


TRACE_ID = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
SESSION_PARENT_SPAN_ID = "bbbbbbbbbbbbbbbb"
ACTION_PARENT_SPAN_ID = "cccccccccccccccc"
SESSION_TRACEPARENT = f"00-{TRACE_ID}-{SESSION_PARENT_SPAN_ID}-01"
ACTION_TRACEPARENT = f"00-{TRACE_ID}-{ACTION_PARENT_SPAN_ID}-01"


class RuntimeSessionRunTimelinePhase3Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection, "agent_timeline", "Timeline Runtime Agent")
        self.app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-05-20T00:00:00Z",
                dev_login_allowed_emails=["timeline@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "timeline@example.com", "roles": ["Platform Admin"]},
        )
        self.assertEqual(login.status_code, 200)
        self.token = login.json()["access_token"]

    def _headers(self, correlation_id: str = "corr-runtime-timeline") -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
            "X-Correlation-ID": correlation_id,
        }

    def _insert_agent(self, connection, agent_id: str, name: str) -> None:
        now = "2026-05-20T00:00:00+00:00"
        connection.execute(
            """
            INSERT INTO agents (
                id, organization_id, environment_id, name, description, framework,
                runtime_type, owner_user_id, sponsor_user_id, status, trust_score,
                trust_tier, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                agent_id,
                "org_default",
                "env_default",
                name,
                "Runtime timeline test agent",
                "langgraph",
                "service",
                "user_admin",
                "user_admin",
                "active",
                820,
                "trusted",
                now,
                now,
            ),
        )

    def test_session_run_timeline_binds_user_action_policy_and_trace(self) -> None:
        session_headers = self._headers("corr-runtime-timeline-session")
        session_headers.update(
            {
                "traceparent": SESSION_TRACEPARENT,
                "tracestate": "vendor=timeline",
                "baggage": "memory_scope=session",
            }
        )
        created = self.client.post(
            "/api/v1/runtime/sessions",
            headers=session_headers,
            json={
                "agent_id": "agent_timeline",
                "ring": 2,
                "metadata": {"thread_id": "thread-runtime-demo", "memory_scope": "session"},
            },
        )
        self.assertEqual(created.status_code, 201, created.text)
        session = created.json()
        self.assertIsNotNone(session["created_by_user_id"])
        self.assertEqual(session["memory_scope"], "session")
        self.assertEqual(session["thread_id"], "thread-runtime-demo")

        action_headers = self._headers("corr-runtime-timeline-action")
        action_headers.update(
            {
                "traceparent": ACTION_TRACEPARENT,
                "tracestate": "vendor=timeline-action",
                "baggage": "step=refund",
            }
        )
        action = self.client.post(
            f"/api/v1/runtime/sessions/{session['id']}/actions",
            headers=action_headers,
            json={
                "action_name": "billing.issue_refund",
                "resource_type": "payment",
                "reversibility": "none",
                "is_read_only": False,
            },
        )
        self.assertEqual(action.status_code, 201, action.text)
        action_payload = action.json()

        runs = self.client.get(
            f"/api/v1/runtime/sessions/{session['id']}/runs",
            headers=self._headers("corr-runtime-timeline-read"),
        )

        self.assertEqual(runs.status_code, 200, runs.text)
        run_payloads = runs.json()
        self.assertEqual(len(run_payloads), 1)
        run = run_payloads[0]
        self.assertEqual(run["session_id"], session["id"])
        self.assertEqual(run["thread_id"], "thread-runtime-demo")
        self.assertEqual(run["started_by_user_id"], session["created_by_user_id"])
        self.assertEqual(run["trace_id"], TRACE_ID)
        self.assertEqual(len(run["steps"]), 1)
        step = run["steps"][0]
        self.assertEqual(step["runtime_action_id"], action_payload["id"])
        self.assertEqual(step["policy_decision_id"], action_payload["ring_decision"]["id"])
        self.assertEqual(step["trace_id"], TRACE_ID)
        self.assertEqual(step["span_id"], action_payload["span_id"])
        self.assertEqual(step["status"], action_payload["decision"])
        self.assertEqual(step["artifact_links"], [])

    def test_run_timeline_read_is_environment_scoped(self) -> None:
        created = self.client.post(
            "/api/v1/runtime/sessions",
            headers=self._headers("corr-runtime-timeline-auth"),
            json={"agent_id": "agent_timeline", "ring": 2},
        )
        self.assertEqual(created.status_code, 201, created.text)

        wrong_environment_headers = self._headers("corr-runtime-timeline-auth-wrong-env")
        wrong_environment_headers["X-Environment-ID"] = "env_other"
        response = self.client.get(
            f"/api/v1/runtime/sessions/{created.json()['id']}/runs",
            headers=wrong_environment_headers,
        )

        self.assertEqual(response.status_code, 403)
        self.assertIn("environment", response.json()["message"].lower())


if __name__ == "__main__":
    unittest.main()
