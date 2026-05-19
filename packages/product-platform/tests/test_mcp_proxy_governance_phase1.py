from __future__ import annotations

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.mcp.discovery import select_mcp_tool_discovery_adapter
from product_platform.policies.bindings import PolicyBindingRepository
from product_platform.policies.models import (
    PolicyBindingCreateRequest,
    PolicyCreateRequest,
    PolicyVersionCreateRequest,
)
from product_platform.policies.repository import PolicyRepository


DENY_POLICY_BODY = """version: "1.0"
name: real-mcp-deny
rules:
  - name: deny_real_lookup
    condition:
      field: tool_name
      operator: eq
      value: real.lookup_order
    action: deny
    message: Bound policy blocked real lookup.
defaults:
  action: allow
"""


APPROVAL_POLICY_BODY = """version: "1.0"
name: real-mcp-approval
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


class MCPProxyGovernancePhase1Tests(unittest.TestCase):
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
            "X-Correlation-ID": "corr-real-mcp",
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
                "Real MCP proxy governance test agent",
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

    def _bind_policy(self, tool_id: str, body_text: str, name: str) -> tuple[str, str]:
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
                    priority=100,
                ),
                actor_id="user_admin",
            )
        return policy["id"], version["id"]

    def test_real_mcp_tools_list_and_call_are_mediated(self) -> None:
        server, tool = self._create_real_server_and_discover()
        self.assertIn("tools/list", self.mcp_server.methods)
        self.mcp_server.clear_requests()

        response = self.client.post(
            "/api/v1/mcp/proxy/call",
            headers=self._headers(),
            json={
                "source_agent_id": "agent_high",
                "server_id": server["id"],
                "tool_id": tool["id"],
                "params": {"order_id": "ORD-REAL-1"},
            },
        )

        self.assertEqual(response.status_code, 201, response.text)
        payload = response.json()
        self.assertEqual(payload["decision"], "allowed")
        self.assertEqual(payload["response"]["structuredContent"]["source"], "real_mcp_http")
        self.assertEqual(payload["upstream_request"]["method"], "tools/call")
        self.assertEqual(payload["upstream_response_metadata"]["jsonrpc"], "2.0")
        self.assertEqual(self.mcp_server.methods, ["tools/call"])

    def test_demo_adapter_is_rejected_in_production(self) -> None:
        with self.assertRaisesRegex(ValueError, "Demo MCP adapter cannot be selected in production"):
            select_mcp_tool_discovery_adapter(
                {
                    "id": "mcpsrv_demo",
                    "name": "Demo Claims MCP",
                    "endpoint_url": "https://mcp.claims.local/rpc?adapter=demo",
                },
                environment="production",
            )

    def test_bound_deny_policy_blocks_before_upstream_execution(self) -> None:
        server, tool = self._create_real_server_and_discover()
        _policy_id, version_id = self._bind_policy(tool["id"], DENY_POLICY_BODY, "Real MCP Deny")
        self.mcp_server.clear_requests()

        response = self.client.post(
            "/api/v1/mcp/proxy/call",
            headers=self._headers(),
            json={
                "source_agent_id": "agent_high",
                "server_id": server["id"],
                "tool_id": tool["id"],
                "params": {"order_id": "ORD-DENY-1"},
            },
        )

        self.assertEqual(response.status_code, 201, response.text)
        payload = response.json()
        self.assertEqual(payload["decision"], "denied")
        self.assertEqual(payload["gateway_stage"], "policy_enforcement")
        self.assertEqual(payload["matched_policy_version_id"], version_id)
        self.assertEqual(payload["policy_input"]["tool_name"], "real.lookup_order")
        self.assertIn("Bound policy blocked real lookup", payload["reason"])
        self.assertEqual(self.mcp_server.methods, [])

    def test_bound_approval_policy_creates_pending_approval_before_execution(self) -> None:
        server, tool = self._create_real_server_and_discover()
        _policy_id, version_id = self._bind_policy(
            tool["id"],
            APPROVAL_POLICY_BODY,
            "Real MCP Approval",
        )
        self.mcp_server.clear_requests()

        response = self.client.post(
            "/api/v1/mcp/proxy/call",
            headers=self._headers(),
            json={
                "source_agent_id": "agent_high",
                "server_id": server["id"],
                "tool_id": tool["id"],
                "params": {"order_id": "ORD-APPROVE-1"},
            },
        )

        self.assertEqual(response.status_code, 201, response.text)
        payload = response.json()
        self.assertEqual(payload["decision"], "escalated")
        self.assertEqual(payload["gateway_stage"], "policy_approval")
        self.assertEqual(payload["matched_policy_version_id"], version_id)
        self.assertEqual(payload["policy_action"], "require_approval")
        self.assertIsNone(payload["response"])
        self.assertEqual(self.mcp_server.methods, [])

        approvals = self.client.get("/api/v1/mcp/approvals?status=pending", headers=self._headers())
        self.assertEqual(approvals.status_code, 200)
        self.assertEqual(approvals.json()[0]["tool_call_id"], payload["id"])


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
    def methods(self) -> list[str]:
        return [request["method"] for request in self._server.requests]  # type: ignore[attr-defined]

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=2)

    def clear_requests(self) -> None:
        self._server.requests.clear()  # type: ignore[attr-defined]


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
                                "additionalProperties": False,
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
