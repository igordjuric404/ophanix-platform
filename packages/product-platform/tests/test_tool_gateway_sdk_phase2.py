from __future__ import annotations

import json
import unittest
from typing import Any

import httpx

from product_platform.tool_gateway.sdk import (
    OphanixToolGatewayClient,
    StaticTokenProvider,
    ToolDeniedError,
    ToolGatewayError,
)


class CountingTokenProvider:
    def __init__(self) -> None:
        self.calls = 0

    def get_token(self) -> str:
        self.calls += 1
        return f"sdk-token-{self.calls}"


class ToolGatewaySdkPhase2Tests(unittest.TestCase):
    def test_successful_call_returns_typed_result(self) -> None:
        seen: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["method"] = request.method
            seen["path"] = request.url.path
            seen["authorization"] = request.headers["authorization"]
            seen["body"] = json.loads(request.content.decode())
            return httpx.Response(
                200,
                json={
                    "request_id": "req-sdk-1",
                    "correlation_id": "corr-sdk-1",
                    "tool_name": "claims.lookup",
                    "reason_code": "allowed",
                    "decision": {"id": "decision_1", "decision": "allow"},
                    "result": {
                        "status": "succeeded",
                        "body": {"claim_id": "claim_123", "status": "open"},
                    },
                    "error": None,
                },
            )

        client = _client(handler)

        result = client.call_tool("claims.lookup", {"claim_id": "claim_123"})

        self.assertEqual(result.request_id, "req-sdk-1")
        self.assertEqual(result.correlation_id, "corr-sdk-1")
        self.assertEqual(result.tool_name, "claims.lookup")
        self.assertEqual(result.reason_code, "allowed")
        self.assertEqual(result.decision, {"id": "decision_1", "decision": "allow"})
        self.assertEqual(result.result["body"]["status"], "open")
        self.assertEqual(seen["method"], "POST")
        self.assertEqual(seen["path"], "/api/v1/tools/claims.lookup/invoke")
        self.assertEqual(seen["authorization"], "Bearer sdk-token")
        self.assertEqual(seen["body"], {"payload": {"claim_id": "claim_123"}})

    def test_denied_response_raises_typed_error(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                403,
                json={
                    "request_id": "req-denied",
                    "correlation_id": "corr-denied",
                    "tool_name": "claims.lookup",
                    "reason_code": "permission_missing",
                    "result": None,
                    "error": {
                        "code": "permission_missing",
                        "message": "Agent is not permitted to call this tool.",
                    },
                },
            )

        client = _client(handler)

        with self.assertRaises(ToolDeniedError) as raised:
            client.call_tool("claims.lookup", {"claim_id": "claim_123"})

        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(raised.exception.reason_code, "permission_missing")
        self.assertEqual(raised.exception.request_id, "req-denied")
        self.assertEqual(raised.exception.correlation_id, "corr-denied")
        self.assertIn("not permitted", raised.exception.message)

    def test_token_provider_is_called_for_each_request(self) -> None:
        provider = CountingTokenProvider()
        authorizations: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            authorizations.append(request.headers["authorization"])
            return httpx.Response(
                200,
                json={
                    "request_id": f"req-{len(authorizations)}",
                    "correlation_id": f"corr-{len(authorizations)}",
                    "tool_name": "claims.lookup",
                    "reason_code": "allowed",
                    "result": {"status": "succeeded"},
                    "error": None,
                },
            )

        client = _client(handler, token_provider=provider)

        client.call_tool("claims.lookup", {"claim_id": "claim_123"})
        client.call_tool("claims.lookup", {"claim_id": "claim_456"})

        self.assertEqual(provider.calls, 2)
        self.assertEqual(authorizations, ["Bearer sdk-token-1", "Bearer sdk-token-2"])

    def test_correlation_id_is_sent_in_header_and_body(self) -> None:
        seen: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["correlation_header"] = request.headers["x-correlation-id"]
            seen["body"] = json.loads(request.content.decode())
            return httpx.Response(
                200,
                json={
                    "request_id": "req-corr",
                    "correlation_id": "corr-client",
                    "tool_name": "claims.lookup",
                    "reason_code": "allowed",
                    "result": {"status": "succeeded"},
                    "error": None,
                },
            )

        client = _client(handler)

        client.call_tool("claims.lookup", {"claim_id": "claim_123"}, correlation_id="corr-client")

        self.assertEqual(seen["correlation_header"], "corr-client")
        self.assertEqual(
            seen["body"],
            {"payload": {"claim_id": "claim_123"}, "correlation_id": "corr-client"},
        )

    def test_gateway_failure_raises_typed_error(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                502,
                json={
                    "request_id": "req-upstream",
                    "correlation_id": "corr-upstream",
                    "tool_name": "claims.lookup",
                    "reason_code": "allowed",
                    "result": None,
                    "error": {
                        "code": "upstream_timeout",
                        "message": "Upstream request timed out.",
                    },
                },
            )

        client = _client(handler)

        with self.assertRaises(ToolGatewayError) as raised:
            client.call_tool("claims.lookup", {"claim_id": "claim_123"})

        self.assertEqual(raised.exception.status_code, 502)
        self.assertEqual(raised.exception.code, "upstream_timeout")
        self.assertEqual(raised.exception.request_id, "req-upstream")
        self.assertIn("timed out", raised.exception.message)

    def test_transport_failure_raises_typed_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused", request=request)

        client = _client(handler)

        with self.assertRaises(ToolGatewayError) as raised:
            client.call_tool("claims.lookup", {"claim_id": "claim_123"})

        self.assertEqual(raised.exception.code, "transport_error")
        self.assertIn("connection refused", raised.exception.message)


def _client(
    handler: httpx.MockTransport,
    *,
    token_provider: Any | None = None,
) -> OphanixToolGatewayClient:
    transport = httpx.MockTransport(handler)
    return OphanixToolGatewayClient(
        base_url="https://gateway.example.test",
        token_provider=token_provider or StaticTokenProvider("sdk-token"),
        http_client=httpx.Client(transport=transport),
    )


if __name__ == "__main__":
    unittest.main()
