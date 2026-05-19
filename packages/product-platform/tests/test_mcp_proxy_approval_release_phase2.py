from __future__ import annotations

import json
import unittest
from typing import Any

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.policies.bindings import PolicyBindingRepository
from product_platform.policies.models import (
    PolicyBindingCreateRequest,
    PolicyCreateRequest,
    PolicyVersionCreateRequest,
)
from product_platform.policies.repository import PolicyRepository

from test_mcp_proxy_governance_phase1 import (
    APPROVAL_POLICY_BODY,
    DENY_POLICY_BODY,
    _RealMCPHTTPServer,
)


class MCPProxyApprovalReleasePhase2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.mcp_server = _RealMCPHTTPServer()
        self.mcp_server.start()
        self.addCleanup(self.mcp_server.stop)
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection, "agent_high", "High Trust Agent", 820)
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
            json={"email": "admin@example.com", "roles": ["Security Admin"]},
        )
        self.assertEqual(login.status_code, 200)
        self.token = login.json()["access_token"]

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
            "X-Correlation-ID": "corr-approval-release",
        }

    def _insert_agent(self, connection: Any, agent_id: str, name: str, score: int) -> None:
        now = "2026-05-19T00:00:00+00:00"
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
                "Approval release test agent",
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

    def _create_real_server_and_tool(self) -> tuple[dict[str, Any], dict[str, Any]]:
        server = self.client.post(
            "/api/v1/mcp/servers",
            headers=self._headers(),
            json={
                "name": "Real Claims MCP",
                "endpoint_url": self.mcp_server.url,
                "owner_user_id": "user_admin",
                "auth_type": "none",
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
        return server.json(), discovery.json()["tools"][0]

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

    def _bind_policy(self, tool_id: str, body_text: str, name: str) -> tuple[str, str, str]:
        with self.database.transaction() as connection:
            policy_repository = PolicyRepository(connection, "org_default")
            policy = policy_repository.create_policy(
                PolicyCreateRequest(name=name, scope="mcp-tool", status="active"),
                actor_id="user_admin",
            )
            version = policy_repository.create_version(
                policy["id"],
                PolicyVersionCreateRequest(
                    body_text=body_text,
                    body_format="yaml",
                    backend="native",
                    status="active",
                ),
                actor_id="user_admin",
            )
            binding = PolicyBindingRepository(connection, "org_default", "env_default").create_binding(
                PolicyBindingCreateRequest(
                    policy_id=policy["id"],
                    policy_version_id=version["id"],
                    target_type="mcp-tool",
                    target_id=tool_id,
                    mode="enforce",
                    priority=100,
                ),
                actor_id="user_admin",
            )
        return policy["id"], version["id"], binding["id"]

    def _escalate_call(self, order_id: str = "ORD-ORIGINAL") -> dict[str, Any]:
        server, tool = self._create_real_server_and_tool()
        self._bind_policy(tool["id"], APPROVAL_POLICY_BODY, "Approval Release Guard")
        self.mcp_server.clear_requests()
        call = self.client.post(
            "/api/v1/mcp/proxy/call",
            headers=self._headers(),
            json={
                "source_agent_id": "agent_high",
                "server_id": server["id"],
                "tool_id": tool["id"],
                "params": {"order_id": order_id},
            },
        )
        self.assertEqual(call.status_code, 201, call.text)
        self.assertEqual(call.json()["decision"], "escalated")
        approval = self.client.get("/api/v1/mcp/approvals?status=pending", headers=self._headers())
        self.assertEqual(approval.status_code, 200)
        payload = approval.json()[0]
        self.assertEqual(payload["tool_call_id"], call.json()["id"])
        return payload

    def test_approval_release_uses_reviewed_payload_not_mutated_summary(self) -> None:
        approval = self._escalate_call(order_id="ORD-ORIGINAL")
        with self.database.transaction() as connection:
            connection.execute(
                "UPDATE mcp_tool_calls SET params_summary_json = ? WHERE id = ?",
                (json.dumps({"order_id": "ORD-TAMPERED"}), approval["tool_call_id"]),
            )

        released = self.client.post(
            f"/api/v1/mcp/approvals/{approval['id']}/approve",
            headers=self._headers(),
            json={"reason": "Reviewed original order lookup."},
        )

        self.assertEqual(released.status_code, 200, released.text)
        tool_call = released.json()["tool_call"]
        self.assertEqual(tool_call["decision"], "allowed")
        self.assertEqual(tool_call["response"]["structuredContent"]["order_id"], "ORD-ORIGINAL")
        self.assertEqual(self.mcp_server.methods, ["tools/call"])

    def test_expired_approval_cannot_be_released(self) -> None:
        approval = self._escalate_call(order_id="ORD-EXPIRED")
        with self.database.transaction() as connection:
            connection.execute(
                "UPDATE mcp_approvals SET expires_at = ? WHERE id = ?",
                ("2026-05-18T00:00:00+00:00", approval["id"]),
            )

        released = self.client.post(
            f"/api/v1/mcp/approvals/{approval['id']}/approve",
            headers=self._headers(),
            json={"reason": "Too late."},
        )

        self.assertEqual(released.status_code, 400)
        self.assertIn("expired", released.json()["message"].lower())
        self.assertEqual(self.mcp_server.methods, [])

    def test_approval_release_revalidates_changed_policy(self) -> None:
        server, tool = self._create_real_server_and_tool()
        policy_id, _version_id, binding_id = self._bind_policy(
            tool["id"],
            APPROVAL_POLICY_BODY,
            "Approval Revalidation Guard",
        )
        self.mcp_server.clear_requests()
        call = self.client.post(
            "/api/v1/mcp/proxy/call",
            headers=self._headers(),
            json={
                "source_agent_id": "agent_high",
                "server_id": server["id"],
                "tool_id": tool["id"],
                "params": {"order_id": "ORD-POLICY-CHANGE"},
            },
        )
        self.assertEqual(call.status_code, 201, call.text)
        approval = self.client.get("/api/v1/mcp/approvals?status=pending", headers=self._headers()).json()[0]
        with self.database.transaction() as connection:
            connection.execute(
                "UPDATE policy_versions SET status = 'inactive' WHERE policy_id = ?",
                (policy_id,),
            )
            deny_version = PolicyRepository(connection, "org_default").create_version(
                policy_id,
                PolicyVersionCreateRequest(
                    body_text=DENY_POLICY_BODY,
                    body_format="yaml",
                    backend="native",
                    status="active",
                ),
                actor_id="user_admin",
            )
            connection.execute(
                "UPDATE policy_bindings SET policy_version_id = ? WHERE id = ?",
                (deny_version["id"], binding_id),
            )

        released = self.client.post(
            f"/api/v1/mcp/approvals/{approval['id']}/approve",
            headers=self._headers(),
            json={"reason": "Policy changed after review."},
        )

        self.assertEqual(released.status_code, 400)
        self.assertIn("blocked real lookup", released.json()["message"].lower())
        self.assertEqual(self.mcp_server.methods, [])


if __name__ == "__main__":
    unittest.main()
