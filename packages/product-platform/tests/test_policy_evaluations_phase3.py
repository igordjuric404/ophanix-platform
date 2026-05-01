from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.audit.store import AuditEventQuery, AuditEventRepository
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


class PolicyEvaluationProducerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection, "agent_mcp_feed", "MCP Feed Agent", 820, identity=True)
            self._insert_agent(connection, "agent_runtime_feed", "Runtime Feed Agent", 500)
        self.app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-05-01T00:00:00Z",
                dev_login_allowed_emails=["platform@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "platform@example.com", "roles": ["Platform Admin"]},
        )
        self.assertEqual(login.status_code, 200)
        self.token = login.json()["access_token"]

    def _headers(self, correlation_id: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
            "X-Correlation-ID": correlation_id,
        }

    def _insert_agent(
        self,
        connection,
        agent_id: str,
        name: str,
        score: int,
        *,
        identity: bool = False,
    ) -> None:
        now = "2026-05-01T00:00:00+00:00"
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
                "Policy evaluation producer test agent",
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
        if identity:
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
                    f"did:producer:{agent_id}",
                    f"fingerprint_{agent_id}",
                    "ed25519",
                    "active",
                    None,
                    now,
                    now,
                ),
            )

    def _create_mcp_server_and_tool(self, correlation_id: str) -> tuple[dict, dict]:
        server = self.client.post(
            "/api/v1/mcp/servers",
            headers=self._headers(correlation_id),
            json={
                "name": "Feed Claims MCP",
                "endpoint_url": "https://mcp.feed.local/rpc",
                "owner_user_id": "user_admin",
                "auth_type": "oauth",
                "status": "active",
                "policy_pack_id": "policy_placeholder_sensitive_tools",
            },
        )
        self.assertEqual(server.status_code, 201, server.text)
        discovery = self.client.post(
            f"/api/v1/mcp/servers/{server.json()['id']}/discover-tools",
            headers=self._headers(correlation_id),
        )
        self.assertEqual(discovery.status_code, 201, discovery.text)
        tools = self.client.get("/api/v1/mcp/tools", headers=self._headers(correlation_id))
        self.assertEqual(tools.status_code, 200, tools.text)
        for tool in tools.json():
            if tool["name"] == "claims.lookup_order":
                return server.json(), tool
        self.fail("Expected claims.lookup_order tool.")

    def test_mcp_proxy_decision_appears_in_policy_evaluation_feed_and_keeps_audit(self) -> None:
        correlation_id = "corr-mcp-policy-feed"
        server, tool = self._create_mcp_server_and_tool(correlation_id)

        call = self.client.post(
            "/api/v1/mcp/proxy/call",
            headers=self._headers(correlation_id),
            json={
                "source_agent_id": "agent_mcp_feed",
                "server_id": server["id"],
                "tool_id": tool["id"],
                "params": {"order_id": "ORD-FEED"},
            },
        )

        self.assertEqual(call.status_code, 201, call.text)
        call_payload = call.json()
        self.assertEqual(call_payload["decision"], "allowed")
        feed = self.client.get(
            "/api/v1/policy-evaluations",
            headers=self._headers(correlation_id),
            params={"correlation_id": correlation_id},
        )
        self.assertEqual(feed.status_code, 200, feed.text)
        rows = feed.json()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["backend"], "mcp-proxy")
        self.assertEqual(rows[0]["decision"], "allow")
        self.assertEqual(rows[0]["agent_id"], "agent_mcp_feed")
        self.assertEqual(rows[0]["resource_id"], tool["id"])
        self.assertEqual(rows[0]["context"]["tool_call_id"], call_payload["id"])
        self.assertEqual(rows[0]["context"]["matched_policy_ref"], "policy_placeholder_sensitive_tools")

        events = AuditEventRepository(self.database.connect()).query(
            AuditEventQuery(
                organization_id="org_default",
                environment_id="env_default",
                resource_type="mcp_tool_call",
                resource_id=call_payload["id"],
            )
        )
        self.assertEqual(events[0].event_type, "mcp.proxy.call.allowed")
        self.assertEqual(events[0].decision, "allowed")

    def test_runtime_decision_appears_in_policy_evaluation_feed_and_keeps_audit(self) -> None:
        session = self.client.post(
            "/api/v1/runtime/sessions",
            headers=self._headers("corr-runtime-session-feed"),
            json={"agent_id": "agent_runtime_feed", "ring": 2},
        )
        self.assertEqual(session.status_code, 201, session.text)
        correlation_id = "corr-runtime-policy-feed"

        action = self.client.post(
            f"/api/v1/runtime/sessions/{session.json()['id']}/actions",
            headers=self._headers(correlation_id),
            json={
                "action_name": "billing.issue_refund",
                "resource_type": "payment",
                "reversibility": "none",
                "is_read_only": False,
            },
        )

        self.assertEqual(action.status_code, 201, action.text)
        action_payload = action.json()
        self.assertEqual(action_payload["decision"], "denied")
        feed = self.client.get(
            "/api/v1/policy-evaluations",
            headers=self._headers(correlation_id),
            params={"correlation_id": correlation_id},
        )
        self.assertEqual(feed.status_code, 200, feed.text)
        rows = feed.json()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["backend"], "runtime-ring")
        self.assertEqual(rows[0]["decision"], "deny")
        self.assertEqual(rows[0]["agent_id"], "agent_runtime_feed")
        self.assertEqual(rows[0]["resource_id"], action_payload["id"])
        self.assertEqual(rows[0]["action"], "billing.issue_refund")
        self.assertEqual(rows[0]["context"]["assigned_ring"], 3)

        events = AuditEventRepository(self.database.connect()).query(
            AuditEventQuery(
                organization_id="org_default",
                environment_id="env_default",
                resource_type="runtime_action",
                resource_id=action_payload["id"],
            )
        )
        self.assertEqual(events[0].event_type, "runtime.action")
        self.assertEqual(events[0].decision, "denied")


if __name__ == "__main__":
    unittest.main()
