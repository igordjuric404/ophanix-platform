from __future__ import annotations

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.audit.store import AuditEventQuery, AuditEventRepository
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.policies.bindings import PolicyBindingRepository
from product_platform.policies.models import (
    PolicyBindingCreateRequest,
    PolicyCreateRequest,
    PolicyVersionCreateRequest,
)
from product_platform.policies.repository import PolicyRepository


APPROVAL_POLICY_BODY = """version: "1.0"
name: real-mcp-approval-release
rules:
  - name: approve_real_lookup
    condition:
      field: tool_name
      operator: eq
      value: real.lookup_order
    action: require_approval
    message: Bound policy requires approval for real lookup.
defaults:
  action: allow
"""


DENY_POLICY_BODY = """version: "1.0"
name: real-mcp-release-deny
rules:
  - name: deny_real_lookup
    condition:
      field: tool_name
      operator: eq
      value: real.lookup_order
    action: deny
    message: Bound policy now blocks real lookup.
defaults:
  action: allow
"""


class MCPProxyGovernancePhase2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.mcp_server = _RealMCPHTTPServer()
        self.mcp_server.start()
        self.addCleanup(self.mcp_server.stop)

        self.database = create_migrated_test_database()
        self.addCleanup(self.database.close)
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection, "agent_high", "High Trust Agent", 820)

        self.app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-05-19T00:00:00Z",
                dev_login_allowed_emails=["admin@example.com", "operator@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.security_token = self._login("admin@example.com", ["Security Admin"])
        self.operator_token = self._login("operator@example.com", ["Operator"])

    def _login(self, email: str, roles: list[str]) -> str:
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": email, "roles": roles},
        )
        self.assertEqual(login.status_code, 200, login.text)
        return login.json()["access_token"]

    def _headers(self, token: str | None = None) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token or self.security_token}",
            "X-Environment-ID": "env_default",
            "X-Correlation-ID": "corr-mcp-approval-release",
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
                "MCP proxy approval release test agent",
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

    def _create_real_server_and_discover(self) -> tuple[dict[str, Any], dict[str, Any]]:
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
        self.assertEqual(discovery.json()["tools"][0]["name"], "real.lookup_order")
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

    def _bind_policy(self, tool_id: str, body_text: str, name: str, *, priority: int) -> tuple[str, str]:
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
            PolicyBindingRepository(connection, "org_default", "env_default").create_binding(
                PolicyBindingCreateRequest(
                    policy_id=policy["id"],
                    policy_version_id=version["id"],
                    target_type="mcp-tool",
                    target_id=tool_id,
                    mode="enforce",
                    priority=priority,
                ),
                actor_id="user_admin",
            )
        return policy["id"], version["id"]

    def _create_pending_real_approval(self, params: dict[str, Any] | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
        server, tool = self._create_real_server_and_discover()
        self._bind_policy(tool["id"], APPROVAL_POLICY_BODY, "Real MCP Approval Release", priority=100)
        self.mcp_server.clear_requests()

        response = self.client.post(
            "/api/v1/mcp/proxy/call",
            headers=self._headers(),
            json={
                "source_agent_id": "agent_high",
                "server_id": server["id"],
                "tool_id": tool["id"],
                "params": params or {"order_id": "ORD-PENDING-1"},
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["decision"], "escalated")
        self.assertEqual(self.mcp_server.methods, [])

        approvals = self.client.get("/api/v1/mcp/approvals?status=pending", headers=self._headers())
        self.assertEqual(approvals.status_code, 200, approvals.text)
        self.assertEqual(len(approvals.json()), 1)
        return approvals.json()[0], tool

    def test_approved_call_releases_only_original_payload(self) -> None:
        approval, _tool = self._create_pending_real_approval(
            {"order_id": "ORD-ORIGINAL-1", "api_token": "secret-token-value"}
        )
        self.assertIsNotNone(approval["payload_hash"])
        self.assertIsNotNone(approval["expires_at"])
        self.assertEqual(approval["release_status"], "pending")

        with self.database.transaction() as connection:
            connection.execute(
                """
                UPDATE mcp_tool_calls
                SET params_summary_json = ?
                WHERE id = ?
                """,
                (json.dumps({"order_id": "ORD-TAMPERED-1"}, sort_keys=True), approval["tool_call_id"]),
            )
        self.mcp_server.clear_requests()

        approved = self.client.post(
            f"/api/v1/mcp/approvals/{approval['id']}/approve",
            headers=self._headers(self.operator_token),
            json={"reason": "Operator approved reviewed lookup.", "idempotency_key": "release-original"},
        )

        self.assertEqual(approved.status_code, 200, approved.text)
        payload = approved.json()
        self.assertEqual(payload["status"], "approved")
        self.assertEqual(payload["release_status"], "completed")
        self.assertEqual(payload["tool_call"]["decision"], "allowed")
        self.assertEqual(payload["tool_call"]["gateway_stage"], "approval_granted")
        self.assertEqual(
            payload["tool_call"]["response"]["structuredContent"]["order_id"],
            "ORD-ORIGINAL-1",
        )
        self.assertNotIn("secret-token-value", json.dumps(payload, sort_keys=True))
        self.assertEqual(self.mcp_server.methods, ["tools/call"])
        self.assertEqual(
            self.mcp_server.requests[-1]["params"]["arguments"]["order_id"],
            "ORD-ORIGINAL-1",
        )

    def test_expired_approval_cannot_be_released(self) -> None:
        approval, _tool = self._create_pending_real_approval({"order_id": "ORD-EXPIRED-1"})
        with self.database.transaction() as connection:
            connection.execute(
                """
                UPDATE mcp_approvals
                SET expires_at = ?
                WHERE id = ?
                """,
                ("2000-01-01T00:00:00+00:00", approval["id"]),
            )
        self.mcp_server.clear_requests()

        expired = self.client.post(
            f"/api/v1/mcp/approvals/{approval['id']}/approve",
            headers=self._headers(self.operator_token),
            json={"reason": "Trying to approve too late.", "idempotency_key": "release-expired"},
        )

        self.assertEqual(expired.status_code, 400, expired.text)
        self.assertIn("expired", expired.text.lower())
        self.assertEqual(self.mcp_server.methods, [])
        with self.database.transaction() as connection:
            approval_row = connection.execute(
                "SELECT status, release_status FROM mcp_approvals WHERE id = ?",
                (approval["id"],),
            ).fetchone()
            call_row = connection.execute(
                "SELECT decision, gateway_stage FROM mcp_tool_calls WHERE id = ?",
                (approval["tool_call_id"],),
            ).fetchone()
        self.assertEqual(approval_row["status"], "expired")
        self.assertEqual(approval_row["release_status"], "expired")
        self.assertEqual(call_row["decision"], "denied")
        self.assertEqual(call_row["gateway_stage"], "approval_expired")
        events = AuditEventRepository(self.database.connect()).query(
            AuditEventQuery(
                organization_id="org_default",
                environment_id="env_default",
                resource_type="mcp_approval",
                resource_id=approval["id"],
            )
        )
        self.assertEqual(events[0].event_type, "mcp.approval.expired")
        self.assertEqual(events[0].decision, "deny")

    def test_policy_change_between_request_and_release_is_revalidated(self) -> None:
        approval, tool = self._create_pending_real_approval({"order_id": "ORD-POLICY-1"})
        self._bind_policy(tool["id"], DENY_POLICY_BODY, "Real MCP Release Deny", priority=200)
        self.mcp_server.clear_requests()

        rejected = self.client.post(
            f"/api/v1/mcp/approvals/{approval['id']}/approve",
            headers=self._headers(self.operator_token),
            json={"reason": "Operator approved stale request.", "idempotency_key": "release-policy"},
        )

        self.assertEqual(rejected.status_code, 400, rejected.text)
        self.assertIn("policy", rejected.text.lower())
        self.assertEqual(self.mcp_server.methods, [])
        with self.database.transaction() as connection:
            approval_row = connection.execute(
                "SELECT status, release_status FROM mcp_approvals WHERE id = ?",
                (approval["id"],),
            ).fetchone()
            call_row = connection.execute(
                "SELECT decision, gateway_stage, reason FROM mcp_tool_calls WHERE id = ?",
                (approval["tool_call_id"],),
            ).fetchone()
        self.assertEqual(approval_row["status"], "denied")
        self.assertEqual(approval_row["release_status"], "rejected")
        self.assertEqual(call_row["decision"], "denied")
        self.assertEqual(call_row["gateway_stage"], "approval_revalidation")
        self.assertIn("Bound policy now blocks", call_row["reason"])
        events = AuditEventRepository(self.database.connect()).query(
            AuditEventQuery(
                organization_id="org_default",
                environment_id="env_default",
                resource_type="mcp_approval",
                resource_id=approval["id"],
            )
        )
        self.assertEqual(events[0].event_type, "mcp.approval.release_denied")
        self.assertEqual(events[0].decision, "deny")


class _RealMCPHTTPServer:
    def __init__(self) -> None:
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _RealMCPRequestHandler)
        self._server.requests: list[dict[str, Any]] = []  # type: ignore[attr-defined]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def url(self) -> str:
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}/mcp"

    @property
    def requests(self) -> list[dict[str, Any]]:
        return self._server.requests  # type: ignore[attr-defined]

    @property
    def methods(self) -> list[str]:
        return [request["method"] for request in self.requests]

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=2)

    def clear_requests(self) -> None:
        self.requests.clear()


class _RealMCPRequestHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        content_length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(content_length).decode("utf-8"))
        self.server.requests.append(body)  # type: ignore[attr-defined]
        method = body.get("method")
        if method == "tools/list":
            response = {
                "jsonrpc": "2.0",
                "id": body.get("id"),
                "result": {
                    "tools": [
                        {
                            "name": "real.lookup_order",
                            "description": "Look up a real order through an MCP HTTP server.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {"order_id": {"type": "string"}},
                                "required": ["order_id"],
                                "additionalProperties": True,
                            },
                            "annotations": {"readOnlyHint": True},
                        }
                    ]
                },
            }
        elif method == "tools/call":
            arguments = body.get("params", {}).get("arguments", {})
            response = {
                "jsonrpc": "2.0",
                "id": body.get("id"),
                "result": {
                    "content": [{"type": "text", "text": "order ready"}],
                    "structuredContent": {
                        "order_id": arguments.get("order_id"),
                        "status": "ready_for_review",
                        "source": "real_mcp_http",
                    },
                },
            }
        else:
            response = {
                "jsonrpc": "2.0",
                "id": body.get("id"),
                "error": {"code": -32601, "message": f"Unknown method: {method}"},
            }
        payload = json.dumps(response).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, _format: str, *_args: Any) -> None:
        return None


if __name__ == "__main__":
    unittest.main()
