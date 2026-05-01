from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.audit.store import AuditEventQuery, AuditEventRepository
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


class MCPProxyTrafficPhase2Tests(unittest.TestCase):
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
                dev_login_allowed_emails=[
                    "admin@example.com",
                    "operator@example.com",
                    "viewer@example.com",
                ],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.security_token = self._login("admin@example.com", ["Security Admin"])
        self.operator_token = self._login("operator@example.com", ["Operator"])
        self.viewer_token = self._login("viewer@example.com", ["Viewer"])

    def _login(self, email: str, roles: list[str]) -> str:
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": email, "roles": roles},
        )
        self.assertEqual(login.status_code, 200)
        return login.json()["access_token"]

    def _headers(self, token: str | None = None) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token or self.security_token}",
            "X-Environment-ID": "env_default",
            "X-Correlation-ID": "corr-mcp-approval",
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
                "MCP proxy approval test agent",
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

    def _create_server_and_discover(self) -> tuple[dict, dict]:
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
        return server.json(), self._tool_by_name("claims.issue_refund")

    def _tool_by_name(self, name: str) -> dict:
        tools = self.client.get("/api/v1/mcp/tools", headers=self._headers())
        self.assertEqual(tools.status_code, 200)
        for tool in tools.json():
            if tool["name"] == name:
                return tool
        self.fail(f"Expected MCP tool {name}.")

    def _escalate_refund_call(self) -> dict:
        server, tool = self._create_server_and_discover()
        call = self.client.post(
            "/api/v1/mcp/proxy/call",
            headers=self._headers(),
            json={
                "source_agent_id": "agent_high",
                "server_id": server["id"],
                "tool_id": tool["id"],
                "params": {"order_id": "ORD-200", "amount": 44.5},
            },
        )
        self.assertEqual(call.status_code, 201)
        self.assertEqual(call.json()["decision"], "escalated")
        return call.json()

    def test_escalated_call_creates_pending_approval(self) -> None:
        call = self._escalate_refund_call()

        approvals = self.client.get("/api/v1/mcp/approvals?status=pending", headers=self._headers())

        self.assertEqual(approvals.status_code, 200)
        self.assertEqual(approvals.json()[0]["tool_call_id"], call["id"])
        self.assertEqual(approvals.json()[0]["status"], "pending")
        self.assertEqual(approvals.json()[0]["tool_call"]["decision"], "escalated")
        self.assertIsNone(call["response"])

    def test_approve_requires_security_admin_or_operator(self) -> None:
        self._escalate_refund_call()
        approval = self.client.get("/api/v1/mcp/approvals?status=pending", headers=self._headers()).json()[0]

        forbidden = self.client.post(
            f"/api/v1/mcp/approvals/{approval['id']}/approve",
            headers=self._headers(self.viewer_token),
            json={"reason": "Viewer should not decide."},
        )
        self.assertEqual(forbidden.status_code, 403)

        approved = self.client.post(
            f"/api/v1/mcp/approvals/{approval['id']}/approve",
            headers=self._headers(self.operator_token),
            json={"reason": "Operator approved refund."},
        )

        self.assertEqual(approved.status_code, 200)
        payload = approved.json()
        self.assertEqual(payload["status"], "approved")
        self.assertEqual(payload["tool_call"]["decision"], "allowed")
        self.assertEqual(payload["tool_call"]["gateway_stage"], "approval_granted")
        self.assertEqual(payload["tool_call"]["response"]["ok"], True)

    def test_deny_requires_reason(self) -> None:
        self._escalate_refund_call()
        approval = self.client.get("/api/v1/mcp/approvals?status=pending", headers=self._headers()).json()[0]

        missing_reason = self.client.post(
            f"/api/v1/mcp/approvals/{approval['id']}/deny",
            headers=self._headers(),
            json={},
        )
        self.assertEqual(missing_reason.status_code, 400)
        self.assertIn("reason", missing_reason.json()["message"])

        denied = self.client.post(
            f"/api/v1/mcp/approvals/{approval['id']}/deny",
            headers=self._headers(),
            json={"reason": "Refund amount exceeded reviewer appetite."},
        )

        self.assertEqual(denied.status_code, 200)
        self.assertEqual(denied.json()["status"], "denied")
        self.assertEqual(denied.json()["tool_call"]["decision"], "denied")
        self.assertEqual(denied.json()["tool_call"]["gateway_stage"], "approval_denied")

    def test_approval_decision_emits_audit_event(self) -> None:
        self._escalate_refund_call()
        approval = self.client.get("/api/v1/mcp/approvals?status=pending", headers=self._headers()).json()[0]

        approved = self.client.post(
            f"/api/v1/mcp/approvals/{approval['id']}/approve",
            headers=self._headers(),
            json={"reason": "Security reviewed refund context."},
        )
        self.assertEqual(approved.status_code, 200)

        events = AuditEventRepository(self.database.connect()).query(
            AuditEventQuery(
                organization_id="org_default",
                environment_id="env_default",
                resource_type="mcp_approval",
                resource_id=approval["id"],
            )
        )

        self.assertEqual(events[0].event_type, "mcp.approval.approved")
        self.assertEqual(events[0].decision, "allow")
        self.assertEqual(events[0].correlation_id, "corr-mcp-approval")


if __name__ == "__main__":
    unittest.main()
