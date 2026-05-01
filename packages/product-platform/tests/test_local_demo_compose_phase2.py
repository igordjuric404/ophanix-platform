from __future__ import annotations

import json
import subprocess
import threading
import unittest
from pathlib import Path
from urllib.request import Request, urlopen

from product_platform.demo.services import create_demo_http_server, check_demo_http_health


PACKAGE_DIR = Path(__file__).resolve().parents[1]


class LocalDemoComposePhase2Tests(unittest.TestCase):
    def test_mcp_service_health_and_tools_pass(self) -> None:
        server = create_demo_http_server(service_type="mcp", host="127.0.0.1", port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address
            health = check_demo_http_health(f"http://{host}:{port}/health")
            with urlopen(f"http://{host}:{port}/tools", timeout=3) as response:
                tools = json.loads(response.read().decode("utf-8"))
        finally:
            server.shutdown()
            server.server_close()

        self.assertEqual(health["service"], "mcp")
        self.assertEqual(health["status"], "healthy")
        self.assertIn("refund.lookup", {tool["name"] for tool in tools["tools"]})

    def test_sample_agent_heartbeat_passes(self) -> None:
        server = create_demo_http_server(
            service_type="agent",
            host="127.0.0.1",
            port=0,
            agent_id="agent_demo_support",
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address
            health = check_demo_http_health(f"http://{host}:{port}/health")
            request = Request(f"http://{host}:{port}/heartbeat", method="POST", data=b"{}")
            with urlopen(request, timeout=3) as response:
                heartbeat = json.loads(response.read().decode("utf-8"))
        finally:
            server.shutdown()
            server.server_close()

        self.assertEqual(health["agent_id"], "agent_demo_support")
        self.assertEqual(heartbeat["heartbeat"], "accepted")
        self.assertEqual(heartbeat["status"], "active")

    def test_compose_config_validates_optional_demo_profiles(self) -> None:
        result = subprocess.run(
            [
                "docker",
                "compose",
                "--env-file",
                ".env.example",
                "-f",
                "docker-compose.demo.yml",
                "--profile",
                "policy",
                "--profile",
                "observability",
                "config",
            ],
            cwd=PACKAGE_DIR,
            check=True,
            capture_output=True,
            text=True,
        )

        for service in (
            "sample-mcp:",
            "support-agent:",
            "refund-agent:",
            "research-agent:",
            "opa:",
            "otel-collector:",
            "prometheus:",
            "grafana:",
        ):
            self.assertIn(service, result.stdout)


if __name__ == "__main__":
    unittest.main()
