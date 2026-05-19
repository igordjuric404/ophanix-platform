from __future__ import annotations

import unittest
from typing import Any

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.tool_gateway.runtime_audit import (
    ToolRuntimeActionCreate,
    ToolRuntimeActionRepository,
)


TRACE_ID = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
PARENT_SPAN_ID = "bbbbbbbbbbbbbbbb"
SPAN_ID = "cccccccccccccccc"
TRACEPARENT = f"00-{TRACE_ID}-{PARENT_SPAN_ID}-01"


class ObservabilityTraceEvalPhase2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection, "agent_trace", "Trace Test Agent", 840)
        self.app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-05-20T00:00:00Z",
                dev_login_allowed_emails=["trace@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "trace@example.com", "roles": ["Platform Admin"]},
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.token = login.json()["access_token"]

    def _headers(self, correlation_id: str = "corr-trace-phase2") -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
            "X-Correlation-ID": correlation_id,
            "traceparent": TRACEPARENT,
        }

    def _insert_agent(self, connection: Any, agent_id: str, name: str, score: int) -> None:
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
                "Trace/eval observability test agent",
                "langgraph",
                "service",
                "user_admin",
                "user_admin",
                "active",
                score,
                "trusted",
                now,
                now,
            ),
        )
        connection.execute(
            """
            INSERT INTO agent_identities (
                id, agent_id, did, public_key_fingerprint, key_type,
                identity_status, bootstrap_material_json, bootstrap_retrieved_at, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"ident_{agent_id}",
                agent_id,
                f"did:trace:{agent_id}",
                f"fingerprint_{agent_id}",
                "ed25519",
                "active",
                None,
                now,
                now,
            ),
        )

    def _create_trace(self) -> dict[str, Any]:
        response = self.client.post(
            "/api/v1/observability/traces",
            headers=self._headers(),
            json={
                "trace_id": TRACE_ID,
                "name": "Refund investigation trace",
                "status": "ok",
                "agent_id": "agent_trace",
                "started_at": "2026-05-20T00:01:00+00:00",
                "ended_at": "2026-05-20T00:01:02+00:00",
                "metadata": {"scenario": "trace-ingestion"},
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_trace_ingestion_and_query_api_round_trip(self) -> None:
        trace = self._create_trace()
        span = self.client.post(
            f"/api/v1/observability/traces/{TRACE_ID}/spans",
            headers=self._headers(),
            json={
                "span_id": SPAN_ID,
                "parent_span_id": PARENT_SPAN_ID,
                "span_kind": "tool",
                "name": "lookup_order",
                "status": "ok",
                "start_time": "2026-05-20T00:01:00+00:00",
                "end_time": "2026-05-20T00:01:01+00:00",
                "latency_ms": 1000,
                "resource_type": "tool",
                "resource_id": "lookup_order",
                "attributes": {"tool.name": "lookup_order"},
            },
        )

        self.assertEqual(span.status_code, 201, span.text)
        detail = self.client.get(f"/api/v1/observability/traces/{TRACE_ID}", headers=self._headers())
        self.assertEqual(detail.status_code, 200, detail.text)
        payload = detail.json()
        self.assertEqual(payload["trace"]["id"], trace["id"])
        self.assertEqual(payload["trace"]["trace_id"], TRACE_ID)
        self.assertEqual(payload["spans"][0]["span_id"], SPAN_ID)
        self.assertEqual(payload["spans"][0]["attributes"]["tool.name"], "lookup_order")

    def test_runtime_to_tool_call_trace_linkage(self) -> None:
        session = self.client.post(
            "/api/v1/runtime/sessions",
            headers=self._headers("corr-runtime-link"),
            json={
                "agent_id": "agent_trace",
                "ring": 2,
                "metadata": {"purpose": "trace-linkage"},
            },
        )
        self.assertEqual(session.status_code, 201, session.text)
        action = self.client.post(
            f"/api/v1/runtime/sessions/{session.json()['id']}/actions",
            headers=self._headers("corr-runtime-link"),
            json={
                "action_name": "lookup_order",
                "resource_type": "tool",
                "is_read_only": True,
            },
        )
        self.assertEqual(action.status_code, 201, action.text)
        with self.database.transaction() as connection:
            ToolRuntimeActionRepository(connection, "org_default", "env_default").create_action(
                ToolRuntimeActionCreate(
                    request_id="req_trace_tool",
                    correlation_id="corr-runtime-link",
                    trace_id=TRACE_ID,
                    span_id="dddddddddddddddd",
                    parent_span_id=SPAN_ID,
                    traceparent=TRACEPARENT,
                    agent_id="agent_trace",
                    action_status="completed",
                    reason_code="allowed",
                    latency_ms=42,
                    payload_summary={"tool": "lookup_order"},
                    response_summary={"status": "ok"},
                )
            )

        detail = self.client.get(f"/api/v1/observability/traces/{TRACE_ID}", headers=self._headers())
        self.assertEqual(detail.status_code, 200, detail.text)
        payload = detail.json()
        self.assertEqual(payload["runtime_sessions"][0]["id"], session.json()["id"])
        self.assertEqual(payload["runtime_actions"][0]["id"], action.json()["id"])
        self.assertEqual(payload["tool_runtime_actions"][0]["request_id"], "req_trace_tool")
        self.assertEqual(payload["policy_evaluations"][0]["correlation_id"], "corr-runtime-link")

    def test_eval_result_links_to_trace_and_dataset(self) -> None:
        self._create_trace()
        created = self.client.post(
            "/api/v1/observability/eval-results",
            headers=self._headers(),
            json={
                "trace_id": TRACE_ID,
                "span_id": SPAN_ID,
                "dataset_id": "dataset_refunds",
                "dataset_name": "Refund QA",
                "evaluator_name": "groundedness",
                "score": 0.94,
                "label": "pass",
                "passed": True,
                "feedback": {"note": "answer cited policy source"},
                "metadata": {"run_id": "eval_run_1"},
            },
        )

        self.assertEqual(created.status_code, 201, created.text)
        detail = self.client.get(f"/api/v1/observability/traces/{TRACE_ID}", headers=self._headers())
        self.assertEqual(detail.status_code, 200, detail.text)
        evals = detail.json()["eval_results"]
        self.assertEqual(evals[0]["dataset_id"], "dataset_refunds")
        self.assertEqual(evals[0]["evaluator_name"], "groundedness")
        self.assertEqual(evals[0]["score"], 0.94)
        self.assertTrue(evals[0]["passed"])


if __name__ == "__main__":
    unittest.main()
