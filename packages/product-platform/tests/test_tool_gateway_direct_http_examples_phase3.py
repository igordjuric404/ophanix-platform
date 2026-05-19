from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import DEMO_ENV_ID, seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.tool_gateway.direct_http_examples import (
    DIRECT_HTTP_ALLOWED_TOKEN,
    DIRECT_HTTP_DENIED_TOKEN,
    seed_tool_gateway_direct_http_fixtures,
)
from tool_gateway_dns import patch_public_dns_resolution


EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples" / "tool-gateway-direct-http"
README_PATH = EXAMPLES_DIR / "README.md"
PYTHON_EXAMPLE_PATH = EXAMPLES_DIR / "direct_http_requests_example.py"


class FakeHTTPResponse:
    def __init__(self, *, status_code: int, body: dict[str, Any]) -> None:
        self.status_code = status_code
        self._body = body
        self.headers = {"content-type": "application/json"}
        self.text = json.dumps(body, sort_keys=True)

    def json(self) -> dict[str, Any]:
        return self._body


class FakeHTTPClient:
    def request(self, method: str, url: str, *, json, headers, timeout: float):
        return FakeHTTPResponse(
            status_code=200,
            body={"claim_id": json["claim_id"], "claim_status": "open"},
        )


class FakeGetResponse:
    status_code = 200

    def __init__(self, body: list[dict[str, Any]]) -> None:
        self._body = body

    def json(self) -> list[dict[str, Any]]:
        return self._body

    def raise_for_status(self) -> None:
        return None


class ToolGatewayDirectHttpExamplesPhase3Tests(unittest.TestCase):
    def setUp(self) -> None:
        dns_patch = patch_public_dns_resolution()
        dns_patch.start()
        self.addCleanup(dns_patch.stop)
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            seed_tool_gateway_direct_http_fixtures(connection)
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
        self.app.state.tool_gateway_http_client = FakeHTTPClient()
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def test_allowed_and_denied_calls_are_found_by_correlation_id(self) -> None:
        allowed_response = self.client.post(
            "/api/v1/tools/claims.lookup/invoke",
            headers={
                "Authorization": f"Bearer {DIRECT_HTTP_ALLOWED_TOKEN}",
                "X-Request-ID": "req-direct-http-smoke-allowed",
                "X-Correlation-ID": "corr-direct-http-smoke-allowed",
            },
            json={
                "payload": {"claim_id": "claim_123"},
                "correlation_id": "corr-direct-http-smoke-allowed",
            },
        )
        denied_response = self.client.post(
            "/api/v1/tools/claims.lookup/invoke",
            headers={
                "Authorization": f"Bearer {DIRECT_HTTP_DENIED_TOKEN}",
                "X-Request-ID": "req-direct-http-smoke-denied",
                "X-Correlation-ID": "corr-direct-http-smoke-denied",
            },
            json={
                "payload": {"claim_id": "claim_456"},
                "correlation_id": "corr-direct-http-smoke-denied",
            },
        )

        self.assertEqual(allowed_response.status_code, 200, allowed_response.text)
        self.assertEqual(denied_response.status_code, 403, denied_response.text)

        allowed_actions = self._runtime_actions("corr-direct-http-smoke-allowed")
        denied_actions = self._runtime_actions("corr-direct-http-smoke-denied")

        self.assertEqual(len(allowed_actions), 1)
        self.assertEqual(allowed_actions[0]["request_id"], allowed_response.json()["request_id"])
        self.assertEqual(allowed_actions[0]["correlation_id"], "corr-direct-http-smoke-allowed")
        self.assertEqual(allowed_actions[0]["action_status"], "completed")

        self.assertEqual(len(denied_actions), 1)
        self.assertEqual(denied_actions[0]["request_id"], denied_response.json()["request_id"])
        self.assertEqual(denied_actions[0]["correlation_id"], "corr-direct-http-smoke-denied")
        self.assertEqual(denied_actions[0]["action_status"], "denied")
        self.assertEqual(denied_actions[0]["reason_code"], "permission_missing")

    def test_readme_contains_audit_verification_query(self) -> None:
        content = README_PATH.read_text()

        self.assertIn("/api/v1/tool-runtime/actions?correlation_id=demo-direct-http-allowed", content)
        self.assertIn("Tool Gateway -> Decisions", content)

    def test_python_example_lists_runtime_actions_by_correlation_id(self) -> None:
        module = _load_python_example()
        calls: list[dict[str, Any]] = []

        def fake_get(url: str, *, headers: dict[str, str], params: dict[str, str], timeout: float):
            calls.append({"url": url, "headers": headers, "params": params, "timeout": timeout})
            return FakeGetResponse(
                [
                    {
                        "request_id": "req-demo-direct-http-allowed",
                        "correlation_id": "demo-direct-http-allowed",
                        "action_status": "completed",
                    }
                ]
            )

        actions = module.list_runtime_actions_by_correlation_id(
            base_url="http://127.0.0.1:8000",
            user_token="operator-user-token",
            correlation_id="demo-direct-http-allowed",
            get=fake_get,
        )

        self.assertEqual(actions[0]["action_status"], "completed")
        self.assertEqual(calls[0]["url"], "http://127.0.0.1:8000/api/v1/tool-runtime/actions")
        self.assertEqual(calls[0]["headers"]["Authorization"], "Bearer operator-user-token")
        self.assertEqual(calls[0]["params"], {"correlation_id": "demo-direct-http-allowed"})

    def _runtime_actions(self, correlation_id: str) -> list[dict[str, Any]]:
        response = self.client.get(
            "/api/v1/tool-runtime/actions",
            headers=self._operator_headers(),
            params={"correlation_id": correlation_id},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def _operator_headers(self) -> dict[str, str]:
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "admin@example.com", "roles": ["Security Admin"]},
        )
        return {
            "Authorization": f"Bearer {login.json()['access_token']}",
            "X-Environment-ID": DEMO_ENV_ID,
        }


def _load_python_example():
    spec = importlib.util.spec_from_file_location(
        "direct_http_requests_example",
        PYTHON_EXAMPLE_PATH,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("Could not load direct HTTP Python example.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    unittest.main()
