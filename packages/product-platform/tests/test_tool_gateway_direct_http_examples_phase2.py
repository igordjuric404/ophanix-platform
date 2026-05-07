from __future__ import annotations

import importlib.util
import json
import re
import unittest
from pathlib import Path
from typing import Any


EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples" / "tool-gateway-direct-http"
README_PATH = EXAMPLES_DIR / "README.md"
PYTHON_EXAMPLE_PATH = EXAMPLES_DIR / "direct_http_requests_example.py"
ALLOWED_SNIPPET_PATH = EXAMPLES_DIR / "expected-allowed-response.json"
DENIED_SNIPPET_PATH = EXAMPLES_DIR / "expected-denied-response.json"


class FakeResponse:
    def __init__(self, status_code: int, body: dict[str, Any]) -> None:
        self.status_code = status_code
        self._body = body
        self.text = json.dumps(body, sort_keys=True)

    def json(self) -> dict[str, Any]:
        return self._body

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class ToolGatewayDirectHttpExamplesPhase2Tests(unittest.TestCase):
    def test_readme_contains_allowed_and_denied_curl_shapes(self) -> None:
        content = README_PATH.read_text()

        self.assertIn("Tool Gateway Direct HTTP Examples", content)
        self.assertRegex(
            content,
            re.compile(r"curl .*\$OPHANIX_BASE_URL/api/v1/tools/claims\.lookup/invoke", re.S),
        )
        self.assertIn("Authorization: Bearer $OPHANIX_TOOL_GATEWAY_ALLOWED_TOKEN", content)
        self.assertIn("Authorization: Bearer $OPHANIX_TOOL_GATEWAY_DENIED_TOKEN", content)
        self.assertIn("X-Correlation-ID: demo-direct-http-allowed", content)
        self.assertIn("X-Correlation-ID: demo-direct-http-denied", content)
        self.assertIn('"payload": {"claim_id": "claim_123"}', content)

    def test_expected_response_snippets_match_gateway_response_model(self) -> None:
        allowed = json.loads(ALLOWED_SNIPPET_PATH.read_text())
        denied = json.loads(DENIED_SNIPPET_PATH.read_text())

        self.assertEqual(allowed["request_id"], "req-demo-direct-http-allowed")
        self.assertEqual(allowed["correlation_id"], "demo-direct-http-allowed")
        self.assertEqual(allowed["tool_name"], "claims.lookup")
        self.assertEqual(allowed["decision"]["decision"], "allow")
        self.assertEqual(allowed["result"]["status"], "succeeded")
        self.assertIsNone(allowed["error"])

        self.assertEqual(denied["request_id"], "req-demo-direct-http-denied")
        self.assertEqual(denied["correlation_id"], "demo-direct-http-denied")
        self.assertEqual(denied["tool_name"], "claims.lookup")
        self.assertEqual(denied["reason_code"], "permission_missing")
        self.assertIsNone(denied["result"])
        self.assertEqual(denied["error"]["code"], "permission_missing")

    def test_python_requests_example_handles_allowed_and_denied_responses(self) -> None:
        module = _load_python_example()
        calls: list[dict[str, Any]] = []

        def fake_post(url: str, *, headers: dict[str, str], json: dict[str, Any], timeout: float):
            calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
            if headers["Authorization"].endswith("denied-token"):
                return FakeResponse(403, json_load(DENIED_SNIPPET_PATH))
            return FakeResponse(200, json_load(ALLOWED_SNIPPET_PATH))

        allowed = module.invoke_tool_direct_http(
            base_url="http://127.0.0.1:8000",
            token="ophanix-local-only-tool-gateway-allowed-token",
            tool_name="claims.lookup",
            payload={"claim_id": "claim_123"},
            correlation_id="demo-direct-http-allowed",
            post=fake_post,
        )

        self.assertEqual(allowed["result"]["body"]["claim_status"], "open")
        self.assertEqual(calls[0]["url"], "http://127.0.0.1:8000/api/v1/tools/claims.lookup/invoke")
        self.assertEqual(calls[0]["headers"]["Authorization"], "Bearer ophanix-local-only-tool-gateway-allowed-token")
        self.assertEqual(calls[0]["headers"]["X-Correlation-ID"], "demo-direct-http-allowed")
        self.assertEqual(
            calls[0]["json"],
            {"payload": {"claim_id": "claim_123"}, "correlation_id": "demo-direct-http-allowed"},
        )

        with self.assertRaises(module.ToolGatewayDirectHttpDenied) as raised:
            module.invoke_tool_direct_http(
                base_url="http://127.0.0.1:8000",
                token="ophanix-local-only-tool-gateway-denied-token",
                tool_name="claims.lookup",
                payload={"claim_id": "claim_123"},
                correlation_id="demo-direct-http-denied",
                post=fake_post,
            )

        self.assertEqual(raised.exception.reason_code, "permission_missing")
        self.assertEqual(raised.exception.response["request_id"], "req-demo-direct-http-denied")


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


def json_load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


if __name__ == "__main__":
    unittest.main()
