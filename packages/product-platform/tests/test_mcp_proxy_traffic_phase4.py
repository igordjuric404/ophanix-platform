from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.audit.store import AuditEventQuery, AuditEventRepository
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


class MCPProxyTrafficPhase4Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection, "agent_high", "High Trust Agent", 820)
        self.app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-05-01T00:00:00Z",
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

    def _headers(self, correlation_id: str = "corr-mcp-rate-limit") -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
            "X-Correlation-ID": correlation_id,
        }

    def _insert_agent(self, connection, agent_id: str, name: str, score: int) -> None:
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
                "MCP proxy rate-limit test agent",
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
                f"did:mcp:{agent_id}",
                f"fingerprint_{agent_id}",
                "ed25519",
                "active",
                None,
                now,
                now,
            ),
        )

    def _create_server_and_clean_tool(self) -> tuple[dict, dict]:
        server = self.client.post(
            "/api/v1/mcp/servers",
            headers=self._headers(),
            json={
                "name": "Claims MCP",
                "endpoint_url": "https://mcp.claims.local/rpc",
                "owner_user_id": "user_admin",
                "auth_type": "oauth",
                "status": "active",
            },
        )
        self.assertEqual(server.status_code, 201, server.text)
        discovery = self.client.post(
            f"/api/v1/mcp/servers/{server.json()['id']}/discover-tools",
            headers=self._headers(),
        )
        self.assertEqual(discovery.status_code, 201, discovery.text)
        self._mark_server_tools_clean(server.json()["id"])
        return server.json(), self._tool_by_name("claims.lookup_order")

    def _mark_server_tools_clean(self, server_id: str) -> None:
        with self.database.transaction() as connection:
            connection.execute(
                """
                UPDATE mcp_tool_versions
                SET scan_status = 'passed'
                WHERE tool_id IN (SELECT id FROM mcp_tools WHERE server_id = ?)
                """,
                (server_id,),
            )
            connection.execute(
                """
                UPDATE mcp_tools
                SET status = 'active', risk_level = 'low'
                WHERE server_id = ?
                """,
                (server_id,),
            )

    def _tool_by_name(self, name: str) -> dict:
        tools = self.client.get("/api/v1/mcp/tools", headers=self._headers())
        self.assertEqual(tools.status_code, 200, tools.text)
        for tool in tools.json():
            if tool["name"] == name:
                return tool
        self.fail(f"Expected MCP tool {name}.")

    def _proxy_call(self, server_id: str, tool_id: str, *, correlation_id: str) -> dict:
        response = self.client.post(
            "/api/v1/mcp/proxy/call",
            headers=self._headers(correlation_id),
            json={
                "source_agent_id": "agent_high",
                "server_id": server_id,
                "tool_id": tool_id,
                "params": {"order_id": correlation_id},
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_rate_limit_create_and_list(self) -> None:
        created = self.client.post(
            "/api/v1/mcp/rate-limits",
            headers=self._headers(),
            json={
                "target_type": "mcp-tool",
                "target_id": "mcptool_demo",
                "window_seconds": 60,
                "max_calls": 12,
                "enabled": True,
            },
        )

        self.assertEqual(created.status_code, 201)
        payload = created.json()
        self.assertEqual(payload["target_type"], "mcp-tool")
        self.assertEqual(payload["max_calls"], 12)
        self.assertEqual(payload["enabled"], True)

        listed = self.client.get(
            "/api/v1/mcp/rate-limits?target_type=mcp-tool&enabled=true",
            headers=self._headers(),
        )
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()[0]["id"], payload["id"])

    def test_mcp_proxy_rate_limit_enforced(self) -> None:
        server, tool = self._create_server_and_clean_tool()
        created = self.client.post(
            "/api/v1/mcp/rate-limits",
            headers=self._headers(),
            json={
                "target_type": "mcp-tool",
                "target_id": tool["id"],
                "window_seconds": 60,
                "max_calls": 1,
                "enabled": True,
            },
        )
        self.assertEqual(created.status_code, 201, created.text)

        first = self._proxy_call(server["id"], tool["id"], correlation_id="corr-mcp-rate-first")
        second = self._proxy_call(server["id"], tool["id"], correlation_id="corr-mcp-rate-second")

        self.assertEqual(first["decision"], "allowed")
        self.assertEqual(second["decision"], "denied")
        self.assertEqual(second["gateway_stage"], "rate_limit")
        self.assertIn(created.json()["id"], second["reason"])
        self.assertIn("retry after", second["reason"].lower())
        events = AuditEventRepository(self.database.connect()).query(
            AuditEventQuery(
                organization_id="org_default",
                environment_id="env_default",
                resource_type="mcp_tool_call",
                resource_id=second["id"],
            )
        )
        self.assertEqual(events[0].event_type, "mcp.proxy.call.denied")

    def test_mcp_proxy_rate_limit_shared_across_app_instances(self) -> None:
        server, tool = self._create_server_and_clean_tool()
        created = self.client.post(
            "/api/v1/mcp/rate-limits",
            headers=self._headers(),
            json={
                "target_type": "mcp-server",
                "target_id": server["id"],
                "window_seconds": 60,
                "max_calls": 1,
                "enabled": True,
            },
        )
        self.assertEqual(created.status_code, 201, created.text)
        first = self._proxy_call(server["id"], tool["id"], correlation_id="corr-mcp-rate-instance-a")
        self.assertEqual(first["decision"], "allowed")

        second_app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-05-01T00:00:00Z",
                dev_login_allowed_emails=["admin@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        second_client = TestClient(second_app, raise_server_exceptions=False)
        login = second_client.post(
            "/api/v1/auth/dev-login",
            json={"email": "admin@example.com", "roles": ["Security Admin"]},
        )
        self.assertEqual(login.status_code, 200, login.text)
        second = second_client.post(
            "/api/v1/mcp/proxy/call",
            headers={
                "Authorization": f"Bearer {login.json()['access_token']}",
                "X-Environment-ID": "env_default",
                "X-Correlation-ID": "corr-mcp-rate-instance-b",
            },
            json={
                "source_agent_id": "agent_high",
                "server_id": server["id"],
                "tool_id": tool["id"],
                "params": {"order_id": "ORD-INSTANCE-B"},
            },
        )

        self.assertEqual(second.status_code, 201, second.text)
        self.assertEqual(second.json()["decision"], "denied")
        self.assertEqual(second.json()["gateway_stage"], "rate_limit")

    def test_mcp_proxy_cost_budget_denial(self) -> None:
        server, tool = self._create_server_and_clean_tool()
        budget = self.client.post(
            "/api/v1/observability/cost-budgets",
            headers=self._headers("corr-mcp-cost-budget-create"),
            json={
                "target_type": "mcp-tool",
                "target_id": tool["id"],
                "period": "monthly",
                "amount_limit": 1.0,
                "action_on_breach": "throttle",
            },
        )
        self.assertEqual(budget.status_code, 201, budget.text)
        cost_event = self.client.post(
            "/api/v1/observability/cost-events",
            headers=self._headers("corr-mcp-cost-event"),
            json={
                "target_type": "mcp-tool",
                "target_id": tool["id"],
                "provider": "mcp",
                "model": "claims.lookup_order",
                "amount": 1.25,
                "units": 1,
                "correlation_id": "corr-mcp-cost-event",
            },
        )
        self.assertEqual(cost_event.status_code, 201, cost_event.text)

        call = self._proxy_call(server["id"], tool["id"], correlation_id="corr-mcp-cost-denied")

        self.assertEqual(call["decision"], "denied")
        self.assertEqual(call["gateway_stage"], "cost_budget")
        self.assertIn(budget.json()["id"], call["reason"])
        self.assertIn("throttle", call["reason"])
        events = AuditEventRepository(self.database.connect()).query(
            AuditEventQuery(
                organization_id="org_default",
                environment_id="env_default",
                resource_type="mcp_tool_call",
                resource_id=call["id"],
            )
        )
        self.assertEqual(events[0].event_type, "mcp.proxy.call.denied")


if __name__ == "__main__":
    unittest.main()
