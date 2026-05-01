"""Lightweight local demo MCP and sample agent services."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.request import urlopen


DEMO_MCP_TOOLS = [
    {
        "name": "refund.lookup",
        "description": "Look up refund eligibility for a demo customer.",
    },
    {
        "name": "refund.issue",
        "description": "Issue a governed demo refund.",
    },
]


def create_demo_http_server(
    *,
    service_type: str,
    host: str,
    port: int,
    agent_id: str | None = None,
) -> ThreadingHTTPServer:
    """Create a local HTTP server for demo compose services."""

    class DemoHandler(BaseHTTPRequestHandler):
        server_version = "OphanixDemoService/0.1"

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/health":
                self._write_json(_health_payload(service_type, agent_id=agent_id))
                return
            if service_type == "mcp" and self.path == "/tools":
                self._write_json({"tools": DEMO_MCP_TOOLS})
                return
            if service_type == "agent" and self.path == "/heartbeat":
                self._write_json(_agent_heartbeat_payload(agent_id))
                return
            self.send_error(404, "Not found")

        def do_POST(self) -> None:  # noqa: N802
            if service_type == "agent" and self.path == "/heartbeat":
                self._write_json(_agent_heartbeat_payload(agent_id))
                return
            self.send_error(404, "Not found")

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _write_json(self, payload: dict[str, Any], status: int = 200) -> None:
            body = json.dumps(payload, sort_keys=True).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return ThreadingHTTPServer((host, port), DemoHandler)


def run_demo_http_service(
    *,
    service_type: str,
    host: str,
    port: int,
    agent_id: str | None = None,
) -> None:
    """Run a blocking local demo HTTP service."""

    server = create_demo_http_server(
        service_type=service_type,
        host=host,
        port=port,
        agent_id=agent_id,
    )
    try:
        server.serve_forever()
    finally:
        server.server_close()


def check_demo_http_health(url: str) -> dict[str, Any]:
    """Fetch and validate a demo service health endpoint."""

    with urlopen(url, timeout=3) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if payload.get("status") != "healthy":
        raise RuntimeError(f"Demo service health check failed: {payload}")
    return payload


def _health_payload(service_type: str, *, agent_id: str | None = None) -> dict[str, Any]:
    payload = {
        "status": "healthy",
        "service": service_type,
    }
    if agent_id is not None:
        payload["agent_id"] = agent_id
    if service_type == "mcp":
        payload["tools"] = [tool["name"] for tool in DEMO_MCP_TOOLS]
    return payload


def _agent_heartbeat_payload(agent_id: str | None) -> dict[str, Any]:
    return {
        "status": "active",
        "agent_id": agent_id or "agent_demo_unknown",
        "heartbeat": "accepted",
    }
