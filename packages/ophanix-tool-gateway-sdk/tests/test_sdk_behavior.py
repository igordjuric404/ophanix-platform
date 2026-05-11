from __future__ import annotations

import unittest
from collections.abc import Callable

import httpx

from ophanix_tool_gateway import (
    OphanixToolGatewayClient,
    StaticTokenProvider,
    ToolDeniedError,
    ToolGatewayError,
)


TOOL_FIXTURE = {
    "id": "tool_claims_lookup",
    "name": "claims.lookup",
    "display_name": "Claims Lookup",
    "description": "Lookup claim state.",
    "owner_team": "Claims",
    "status": "active",
    "required_scope": "claims.lookup:read",
    "input_schema_json": {"type": "object"},
    "output_schema_json": {"type": "object"},
}


class StandaloneSdkBehaviorTests(unittest.TestCase):
    def test_call_tool_returns_typed_result(self) -> None:
        client = _client(
            lambda _request: httpx.Response(
                200,
                json={
                    "request_id": "req-sdk",
                    "correlation_id": "corr-sdk",
                    "tool_name": "claims.lookup",
                    "reason_code": "allowed",
                    "result": {"status": "succeeded"},
                    "error": None,
                },
            )
        )

        result = client.call_tool("claims.lookup", {"claim_id": "claim_123"})

        self.assertEqual(result.request_id, "req-sdk")
        self.assertEqual(result.result, {"status": "succeeded"})

    def test_list_tools_returns_isolated_schema_copies_from_cache(self) -> None:
        calls = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(200, json=[TOOL_FIXTURE])

        client = _client(handler, cache_tools=True)

        first = client.list_tools()[0]
        self.assertIsNotNone(first.input_schema_json)
        assert first.input_schema_json is not None
        first.input_schema_json["mutated"] = True
        second = client.list_tools()[0]

        self.assertEqual(calls, 1)
        self.assertEqual(second.input_schema_json, {"type": "object"})

    def test_top_level_gateway_error_code_is_preserved(self) -> None:
        client = _client(
            lambda _request: httpx.Response(
                500,
                json={"code": "GATEWAY_UNAVAILABLE", "message": "Gateway down."},
            )
        )

        with self.assertRaises(ToolGatewayError) as raised:
            client.call_tool("claims.lookup", {"claim_id": "claim_123"})

        self.assertEqual(raised.exception.code, "GATEWAY_UNAVAILABLE")

    def test_retry_after_header_is_exposed_on_gateway_errors(self) -> None:
        client = _client(
            lambda _request: httpx.Response(
                429,
                json={"code": "RATE_LIMITED", "message": "Retry later."},
                headers={"Retry-After": "5"},
            )
        )

        with self.assertRaises(ToolGatewayError) as raised:
            client.call_tool("claims.lookup", {"claim_id": "claim_123"})

        self.assertEqual(raised.exception.retry_after_seconds, 5.0)

    def test_generic_403_remains_gateway_error(self) -> None:
        client = _client(
            lambda _request: httpx.Response(
                403,
                json={"error": {"code": "forbidden", "message": "Proxy denied."}},
            )
        )

        with self.assertRaises(ToolGatewayError) as raised:
            client.call_tool("claims.lookup", {"claim_id": "claim_123"})

        self.assertNotIsInstance(raised.exception, ToolDeniedError)
        self.assertEqual(raised.exception.code, "forbidden")

    def test_structured_policy_403_raises_denied_error(self) -> None:
        client = _client(
            lambda _request: httpx.Response(
                403,
                json={
                    "request_id": "req-denied",
                    "correlation_id": "corr-denied",
                    "tool_name": "claims.lookup",
                    "decision": {"decision": "deny"},
                    "reason_code": "permission_missing",
                    "error": {"code": "permission_missing"},
                },
            )
        )

        with self.assertRaises(ToolDeniedError) as raised:
            client.call_tool("claims.lookup", {"claim_id": "claim_123"})

        self.assertEqual(raised.exception.reason_code, "permission_missing")

    def test_list_all_tools_enforces_max_total(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            offset = int(request.url.params.get("offset", "0"))
            tool = {**TOOL_FIXTURE, "id": f"tool_{offset}", "name": f"claims.lookup.{offset}"}
            return httpx.Response(200, json=[tool])

        client = _client(handler)

        with self.assertRaises(ToolGatewayError) as raised:
            client.list_all_tools(page_size=1, max_total=1)

        self.assertEqual(raised.exception.code, "tool_discovery_too_large")

    def test_streaming_response_cap_blocks_body_without_content_length(self) -> None:
        client = _client(
            lambda _request: httpx.Response(
                200,
                content=b"x" * 11,
                headers={"content-type": "application/json"},
            ),
        )
        client.max_response_bytes = 10

        with self.assertRaises(ToolGatewayError) as raised:
            client.call_tool("claims.lookup", {"claim_id": "claim_123"})

        self.assertEqual(raised.exception.code, "response_too_large")

    def test_list_tools_status_argument_warns_as_deprecated(self) -> None:
        client = _client(lambda _request: httpx.Response(200, json=[]))

        with self.assertWarns(DeprecationWarning):
            self.assertEqual(client.list_tools(status="active"), [])


def _client(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    cache_tools: bool = False,
) -> OphanixToolGatewayClient:
    return OphanixToolGatewayClient(
        base_url="https://gateway.example.test",
        token_provider=StaticTokenProvider("sdk-token"),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        cache_tools=cache_tools,
    )


if __name__ == "__main__":
    unittest.main()
