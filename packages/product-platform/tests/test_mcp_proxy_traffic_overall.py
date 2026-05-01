from __future__ import annotations

import json
import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.audit.store import AuditEventQuery, AuditEventRepository
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.mcp.discovery import calculate_schema_hash


class MCPProxyTrafficOverallTests(unittest.TestCase):
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
            json={"email": "admin@example.com", "roles": ["Security Admin"]},
        )
        self.assertEqual(login.status_code, 200)
        self.token = login.json()["access_token"]

    def _headers(self, correlation_id: str = "corr-mcp-overall") -> dict[str, str]:
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
                "MCP proxy overall test agent",
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

    def _create_server_and_discover(self) -> tuple[dict, dict, dict]:
        server = self.client.post(
            "/api/v1/mcp/servers",
            headers=self._headers(),
            json={
                "name": "Claims MCP",
                "endpoint_url": "https://mcp.claims.local/rpc",
                "owner_user_id": "user_admin",
                "auth_type": "oauth",
                "status": "active",
                "policy_pack_id": "policy_placeholder_sensitive_tools",
            },
        )
        self.assertEqual(server.status_code, 201)
        discovery = self.client.post(
            f"/api/v1/mcp/servers/{server.json()['id']}/discover-tools",
            headers=self._headers(),
        )
        self.assertEqual(discovery.status_code, 201)
        return (
            server.json(),
            self._tool_by_name("claims.lookup_order"),
            self._tool_by_name("claims.issue_refund"),
        )

    def _tool_by_name(self, name: str) -> dict:
        tools = self.client.get("/api/v1/mcp/tools", headers=self._headers())
        self.assertEqual(tools.status_code, 200)
        for tool in tools.json():
            if tool["name"] == name:
                return tool
        self.fail(f"Expected MCP tool {name}.")

    def _insert_shell_tool(self, server_id: str) -> dict:
        now = "2026-05-01T00:06:00+00:00"
        schema = {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
            "additionalProperties": False,
        }
        definition = {
            "name": "shell.exec",
            "description": "Execute a shell command.",
            "inputSchema": schema,
        }
        with self.database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO mcp_tools (
                    id, server_id, name, description, current_version_id,
                    risk_level, status, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "mcptool_shell_exec",
                    server_id,
                    "shell.exec",
                    "Execute a shell command.",
                    None,
                    "critical",
                    "active",
                    now,
                    now,
                ),
            )
            connection.execute(
                """
                INSERT INTO mcp_tool_versions (
                    id, tool_id, schema_json, schema_hash, definition_json,
                    discovered_at, scan_status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "mcptv_shell_exec",
                    "mcptool_shell_exec",
                    json.dumps(schema, sort_keys=True),
                    calculate_schema_hash(schema),
                    json.dumps(definition, sort_keys=True),
                    now,
                    "not_scanned",
                ),
            )
            connection.execute(
                "UPDATE mcp_tools SET current_version_id = ? WHERE id = ?",
                ("mcptv_shell_exec", "mcptool_shell_exec"),
            )
        return self._tool_by_name("shell.exec")

    def test_proxy_flow_records_visible_traffic_approvals_and_audit(self) -> None:
        server, lookup_tool, refund_tool = self._create_server_and_discover()

        allowed = self.client.post(
            "/api/v1/mcp/proxy/call",
            headers=self._headers("corr-mcp-allowed"),
            json={
                "source_agent_id": "agent_high",
                "server_id": server["id"],
                "tool_id": lookup_tool["id"],
                "params": {"order_id": "ORD-400"},
            },
        )
        self.assertEqual(allowed.status_code, 201)
        allowed_payload = allowed.json()
        self.assertEqual(allowed_payload["decision"], "allowed")
        self.assertEqual(allowed_payload["response"]["status"], "ready_for_review")

        refund = self.client.post(
            "/api/v1/mcp/proxy/call",
            headers=self._headers("corr-mcp-refund"),
            json={
                "source_agent_id": "agent_high",
                "server_id": server["id"],
                "tool_id": refund_tool["id"],
                "params": {"order_id": "ORD-401", "amount": 55.0},
            },
        )
        self.assertEqual(refund.status_code, 201)
        refund_payload = refund.json()
        self.assertEqual(refund_payload["decision"], "escalated")
        self.assertIsNone(refund_payload["response"])

        approvals = self.client.get("/api/v1/mcp/approvals?status=pending", headers=self._headers())
        self.assertEqual(approvals.status_code, 200)
        approval = approvals.json()[0]
        self.assertEqual(approval["tool_call_id"], refund_payload["id"])
        self.assertEqual(approval["tool_call"]["matched_policy_id"], "policy_placeholder_sensitive_tools")

        approved = self.client.post(
            f"/api/v1/mcp/approvals/{approval['id']}/approve",
            headers=self._headers("corr-mcp-approve"),
            json={"reason": "Overall validation approves a bounded refund."},
        )
        self.assertEqual(approved.status_code, 200)
        approved_payload = approved.json()
        self.assertEqual(approved_payload["status"], "approved")
        self.assertEqual(approved_payload["tool_call"]["decision"], "allowed")
        self.assertEqual(approved_payload["tool_call"]["gateway_stage"], "approval_granted")

        shell_tool = self._insert_shell_tool(server["id"])
        denied = self.client.post(
            "/api/v1/mcp/proxy/call",
            headers=self._headers("corr-mcp-shell"),
            json={
                "source_agent_id": "agent_high",
                "server_id": server["id"],
                "tool_id": shell_tool["id"],
                "params": {"command": "whoami"},
            },
        )
        self.assertEqual(denied.status_code, 201)
        denied_payload = denied.json()
        self.assertEqual(denied_payload["decision"], "denied")
        self.assertEqual(denied_payload["gateway_stage"], "deny_list")

        traffic = self.client.get("/api/v1/mcp/traffic", headers=self._headers())
        self.assertEqual(traffic.status_code, 200)
        traffic_by_id = {call["id"]: call for call in traffic.json()}
        self.assertEqual(traffic_by_id[allowed_payload["id"]]["decision"], "allowed")
        self.assertEqual(traffic_by_id[refund_payload["id"]]["decision"], "allowed")
        self.assertEqual(traffic_by_id[denied_payload["id"]]["decision"], "denied")

        approved_approvals = self.client.get("/api/v1/mcp/approvals?status=approved", headers=self._headers())
        self.assertEqual(approved_approvals.status_code, 200)
        self.assertEqual(approved_approvals.json()[0]["id"], approval["id"])

        audit = AuditEventRepository(self.database.connect())
        allowed_events = audit.query(
            AuditEventQuery(
                organization_id="org_default",
                environment_id="env_default",
                resource_type="mcp_tool_call",
                resource_id=allowed_payload["id"],
            )
        )
        refund_events = audit.query(
            AuditEventQuery(
                organization_id="org_default",
                environment_id="env_default",
                resource_type="mcp_tool_call",
                resource_id=refund_payload["id"],
            )
        )
        shell_events = audit.query(
            AuditEventQuery(
                organization_id="org_default",
                environment_id="env_default",
                resource_type="mcp_tool_call",
                resource_id=denied_payload["id"],
            )
        )
        approval_events = audit.query(
            AuditEventQuery(
                organization_id="org_default",
                environment_id="env_default",
                resource_type="mcp_approval",
                resource_id=approval["id"],
            )
        )
        self.assertIn("mcp.proxy.call.allowed", {event.event_type for event in allowed_events})
        self.assertIn("mcp.proxy.call.escalated", {event.event_type for event in refund_events})
        self.assertIn("mcp.proxy.call.denied", {event.event_type for event in shell_events})
        self.assertIn("mcp.approval.approved", {event.event_type for event in approval_events})


if __name__ == "__main__":
    unittest.main()
