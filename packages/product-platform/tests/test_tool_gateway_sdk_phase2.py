from __future__ import annotations

import asyncio
import json
import math
import unittest
from datetime import datetime
from typing import Any

import httpx

from product_platform.tool_gateway.sdk import (
    AsyncOphanixToolGatewayClient,
    OphanixToolGatewayClient,
    StaticTokenProvider,
    ToolAuthenticationError,
    ToolDeniedError,
    ToolGatewayError,
)


class CountingTokenProvider:
    def __init__(self) -> None:
        self.calls = 0

    def get_token(self) -> str:
        self.calls += 1
        return f"sdk-token-{self.calls}"


class AsyncCountingTokenProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def get_token(self) -> str:
        self.calls += 1
        return f"async-sdk-token-{self.calls}"


class AsyncOnlyTokenProvider:
    async def get_token(self) -> str:
        return "async-only-token"


class ToolGatewaySdkPhase2Tests(unittest.TestCase):
    def test_successful_call_returns_typed_result(self) -> None:
        seen: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["method"] = request.method
            seen["path"] = request.url.path
            seen["authorization"] = request.headers["authorization"]
            seen["user_agent"] = request.headers["user-agent"]
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
        self.assertTrue(seen["user_agent"].startswith("ophanix-tool-gateway-python/"))
        self.assertEqual(seen["body"], {"payload": {"claim_id": "claim_123"}})

    def test_call_tool_rejects_non_string_tool_name(self) -> None:
        client = _client(lambda _request: httpx.Response(200, json={}))

        with self.assertRaisesRegex(ValueError, "tool_name must be a string"):
            client.call_tool(123, {})  # type: ignore[arg-type]

    def test_call_tool_rejects_non_json_serializable_payload(self) -> None:
        client = _client(lambda _request: httpx.Response(200, json={}))

        with self.assertRaisesRegex(ValueError, "payload must be JSON serializable"):
            client.call_tool("claims.lookup", {"created_at": datetime(2026, 5, 1)})

    def test_call_tool_rejects_payload_with_non_string_keys(self) -> None:
        client = _client(lambda _request: httpx.Response(200, json={}))

        with self.assertRaisesRegex(ValueError, "payload keys must be strings"):
            client.call_tool("claims.lookup", {123: "claim_123"})  # type: ignore[dict-item]

    def test_call_tool_rejects_payload_with_non_finite_numbers(self) -> None:
        client = _client(lambda _request: httpx.Response(200, json={}))

        with self.assertRaisesRegex(ValueError, "finite numbers"):
            client.call_tool("claims.lookup", {"score": math.nan})

    def test_call_tool_rejects_non_string_correlation_id(self) -> None:
        client = _client(lambda _request: httpx.Response(200, json={}))

        with self.assertRaisesRegex(ValueError, "optional text values must be strings"):
            client.call_tool("claims.lookup", {}, correlation_id=123)  # type: ignore[arg-type]

    def test_call_tool_rejects_correlation_id_header_control_characters(self) -> None:
        client = _client(lambda _request: httpx.Response(200, json={}))

        with self.assertRaisesRegex(ValueError, "header control characters"):
            client.call_tool("claims.lookup", {}, correlation_id="bad\nid")

    def test_call_tool_rejects_token_header_control_characters(self) -> None:
        client = _client(
            lambda _request: httpx.Response(200, json={}),
            token_provider=StaticTokenProvider("bad\ntoken"),
        )

        with self.assertRaisesRegex(ValueError, "header control characters"):
            client.call_tool("claims.lookup", {})

    def test_sync_client_rejects_async_token_provider(self) -> None:
        client = _client(
            lambda _request: httpx.Response(200, json={}),
            token_provider=AsyncOnlyTokenProvider(),
        )

        with self.assertRaisesRegex(ValueError, "AsyncOphanixToolGatewayClient"):
            client.call_tool("claims.lookup", {})

    def test_successful_http_response_must_have_required_gateway_fields(self) -> None:
        client = _client(lambda _request: httpx.Response(200, json={"result": {"ok": True}}))

        with self.assertRaises(ToolGatewayError) as raised:
            client.call_tool("claims.lookup", {"claim_id": "claim_123"})

        self.assertEqual(raised.exception.code, "invalid_response")
        self.assertIn("request_id", raised.exception.message)

    def test_successful_http_response_must_not_contain_error(self) -> None:
        client = _client(
            lambda _request: httpx.Response(
                200,
                json={
                    "request_id": "req-bad",
                    "correlation_id": "corr-bad",
                    "tool_name": "claims.lookup",
                    "error": {"code": "unexpected", "message": "unexpected"},
                },
            )
        )

        with self.assertRaises(ToolGatewayError) as raised:
            client.call_tool("claims.lookup", {"claim_id": "claim_123"})

        self.assertEqual(raised.exception.code, "invalid_response")

    def test_successful_http_response_rejects_non_object_decision(self) -> None:
        client = _client(
            lambda _request: httpx.Response(
                200,
                json={
                    "request_id": "req-bad-decision",
                    "correlation_id": "corr-bad-decision",
                    "tool_name": "claims.lookup",
                    "decision": ["not", "an", "object"],
                    "result": {"status": "succeeded"},
                    "error": None,
                },
            )
        )

        with self.assertRaises(ToolGatewayError) as raised:
            client.call_tool("claims.lookup", {"claim_id": "claim_123"})

        self.assertEqual(raised.exception.code, "invalid_response")
        self.assertIn("decision", raised.exception.message)

    def test_non_json_success_response_is_invalid_response(self) -> None:
        client = _client(lambda _request: httpx.Response(200, text="ok"))

        with self.assertRaises(ToolGatewayError) as raised:
            client.call_tool("claims.lookup", {"claim_id": "claim_123"})

        self.assertEqual(raised.exception.code, "invalid_response")
        self.assertEqual(
            raised.exception.response_body["error"]["message"],
            "Tool Gateway returned a non-JSON response.",
        )

    def test_error_response_body_redacts_sensitive_fields(self) -> None:
        client = _client(
            lambda _request: httpx.Response(
                500,
                json={
                    "request_id": "req-redacted",
                    "error": {
                        "code": "upstream_error",
                        "message": "Upstream returned an error.",
                        "authorization": "Bearer leaked",
                        "nested": {"api_key": "leaked-api-key"},
                    },
                },
            )
        )

        with self.assertRaises(ToolGatewayError) as raised:
            client.call_tool("claims.lookup", {"claim_id": "claim_123"})

        body = raised.exception.response_body
        self.assertEqual(body["error"]["authorization"], "[redacted]")
        self.assertEqual(body["error"]["nested"]["api_key"], "[redacted]")

    def test_error_response_body_redacts_common_secret_text_shapes(self) -> None:
        client = _client(
            lambda _request: httpx.Response(
                500,
                json={
                    "request_id": "req-redacted-text-shapes",
                    "error": {
                        "code": "upstream_error",
                        "message": (
                            "Authorization: Bearer abc-def.ghi "
                            "client_secret = 'client-secret-value', "
                            'x-api-key: "api-key-value"; '
                            "access_token=access-token-value "
                            "private_key: private-key-value"
                        ),
                        "monkey": "diagnostic-value",
                    },
                },
            )
        )

        with self.assertRaises(ToolGatewayError) as raised:
            client.call_tool("claims.lookup", {"claim_id": "claim_123"})

        body = raised.exception.response_body
        self.assertEqual(
            body["error"]["message"],
            (
                "Authorization: [redacted] "
                "client_secret = [redacted], "
                "x-api-key: [redacted]; "
                "access_token=[redacted] "
                "private_key: [redacted]"
            ),
        )
        self.assertEqual(body["error"]["monkey"], "diagnostic-value")

    def test_error_response_body_redacts_colon_bearing_bearer_tokens(self) -> None:
        client = _client(
            lambda _request: httpx.Response(
                500,
                json={
                    "request_id": "req-redacted-bearer-colon",
                    "error": {
                        "code": "upstream_error",
                        "message": "Authorization: Bearer issuer:subject:signature",
                    },
                },
            )
        )

        with self.assertRaises(ToolGatewayError) as raised:
            client.call_tool("claims.lookup", {"claim_id": "claim_123"})

        message = raised.exception.response_body["error"]["message"]
        self.assertEqual(message, "Authorization: [redacted]")
        self.assertNotIn("issuer:subject:signature", str(raised.exception.response_body))

    def test_error_messages_are_generic_while_response_body_is_sanitized(self) -> None:
        client = _client(
            lambda _request: httpx.Response(
                502,
                json={
                    "request_id": "req-redacted-message",
                    "error": {
                        "code": "upstream_error",
                        "message": "Failed with Bearer leaked-token and token=leaked-token",
                    },
                },
            )
        )

        with self.assertRaises(ToolGatewayError) as raised:
            client.call_tool("claims.lookup", {"claim_id": "claim_123"})

        self.assertEqual(raised.exception.message, "Tool Gateway returned HTTP 502.")
        self.assertEqual(
            raised.exception.response_body["error"]["message"],
            "Failed with Bearer [redacted] and token=[redacted]",
        )

    def test_denied_response_raises_typed_error(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                403,
                json={
                    "request_id": "req-denied",
                    "correlation_id": "corr-denied",
                    "tool_name": "claims.lookup",
                    "decision": {"decision": "deny"},
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

    def test_generic_403_response_is_not_reported_as_policy_denial(self) -> None:
        client = _client(
            lambda _request: httpx.Response(
                403,
                json={"code": "FORBIDDEN", "message": "Forbidden by proxy."},
            )
        )

        with self.assertRaises(ToolGatewayError) as raised:
            client.call_tool("claims.lookup", {"claim_id": "claim_123"})

        self.assertNotIsInstance(raised.exception, ToolDeniedError)
        self.assertEqual(raised.exception.code, "FORBIDDEN")

    def test_gateway_error_extracts_top_level_error_code(self) -> None:
        client = _client(
            lambda _request: httpx.Response(
                500,
                json={"code": "GATEWAY_UNAVAILABLE", "message": "Gateway down."},
            )
        )

        with self.assertRaises(ToolGatewayError) as raised:
            client.call_tool("claims.lookup", {"claim_id": "claim_123"})

        self.assertEqual(raised.exception.code, "GATEWAY_UNAVAILABLE")

    def test_gateway_error_exposes_retry_after_seconds(self) -> None:
        client = _client(
            lambda _request: httpx.Response(
                429,
                json={"code": "RATE_LIMITED", "message": "Retry later."},
                headers={"Retry-After": "7"},
            )
        )

        with self.assertRaises(ToolGatewayError) as raised:
            client.call_tool("claims.lookup", {"claim_id": "claim_123"})

        self.assertEqual(raised.exception.code, "RATE_LIMITED")
        self.assertEqual(raised.exception.retry_after_seconds, 7.0)

    def test_gateway_response_above_configured_size_cap_is_rejected_before_json_parse(self) -> None:
        client = _client(
            lambda _request: httpx.Response(
                200,
                content=b'{"too_large": true}',
                headers={"content-type": "application/json", "content-length": "19"},
            ),
            max_response_bytes=10,
        )

        with self.assertRaises(ToolGatewayError) as raised:
            client.call_tool("claims.lookup", {"claim_id": "claim_123"})

        self.assertEqual(raised.exception.code, "response_too_large")

    def test_call_tool_rejects_cyclic_payload(self) -> None:
        client = _client(lambda _request: httpx.Response(200, json={}))
        payload: dict[str, Any] = {}
        payload["self"] = payload

        with self.assertRaisesRegex(ValueError, "cycles"):
            client.call_tool("claims.lookup", payload)

    def test_authentication_failure_raises_typed_error(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                401,
                json={
                    "request_id": "req-auth",
                    "correlation_id": "corr-auth",
                    "error": {
                        "code": "credential_not_found",
                        "message": "Gateway authentication failed.",
                    },
                },
            )

        client = _client(handler)

        with self.assertRaises(ToolAuthenticationError) as raised:
            client.call_tool("claims.lookup", {"claim_id": "claim_123"})

        self.assertEqual(raised.exception.status_code, 401)
        self.assertEqual(raised.exception.code, "credential_not_found")
        self.assertEqual(raised.exception.request_id, "req-auth")

    def test_successful_response_rejects_non_string_reason_code(self) -> None:
        client = _client(
            lambda _request: httpx.Response(
                200,
                json={
                    "request_id": "req-bad-reason",
                    "correlation_id": "corr-bad-reason",
                    "tool_name": "claims.lookup",
                    "reason_code": 123,
                    "result": {"status": "succeeded"},
                    "error": None,
                },
            )
        )

        with self.assertRaises(ToolGatewayError) as raised:
            client.call_tool("claims.lookup", {"claim_id": "claim_123"})

        self.assertEqual(raised.exception.code, "invalid_response")
        self.assertIn("reason_code", raised.exception.message)

    def test_successful_result_raw_mapping_is_immutable(self) -> None:
        client = _client(
            lambda _request: httpx.Response(
                200,
                json={
                    "request_id": "req-immutable",
                    "correlation_id": "corr-immutable",
                    "tool_name": "claims.lookup",
                    "reason_code": "allowed",
                    "result": {"status": "succeeded"},
                    "error": None,
                },
            )
        )

        result = client.call_tool("claims.lookup", {"claim_id": "claim_123"})

        with self.assertRaises(TypeError):
            result.raw["request_id"] = "mutated"  # type: ignore[index]

    def test_call_tool_rejects_payload_above_configured_size_cap(self) -> None:
        client = OphanixToolGatewayClient(
            base_url="https://gateway.example.test",
            token_provider=StaticTokenProvider("sdk-token"),
            http_client=httpx.Client(transport=httpx.MockTransport(lambda _request: httpx.Response(200))),
            max_payload_bytes=8,
        )

        with self.assertRaisesRegex(ValueError, "payload exceeds max_payload_bytes"):
            client.call_tool("claims.lookup", {"claim_id": "claim_123"})

    def test_non_json_error_response_uses_bounded_sanitized_excerpt(self) -> None:
        secret = "Bearer issuer:subject:signature"
        client = _client(lambda _request: httpx.Response(502, text=f"{secret} " + ("x" * 5000)))

        with self.assertRaises(ToolGatewayError) as raised:
            client.call_tool("claims.lookup", {"claim_id": "claim_123"})

        body_excerpt = raised.exception.response_body["error"]["body_excerpt"]
        self.assertLessEqual(len(body_excerpt), 2048)
        self.assertNotIn(secret, body_excerpt)

    def test_event_hook_receives_safe_metadata_without_payload_or_token(self) -> None:
        events: list[dict[str, Any]] = []

        def hook(event) -> None:
            with self.assertRaises(TypeError):
                event["mutated"] = True
            events.append(dict(event))

        client = OphanixToolGatewayClient(
            base_url="https://gateway.example.test",
            token_provider=StaticTokenProvider("sdk-token"),
            http_client=httpx.Client(
                transport=httpx.MockTransport(
                    lambda _request: httpx.Response(
                        200,
                        json={
                            "request_id": "req-event",
                            "correlation_id": "corr-event",
                            "tool_name": "claims.lookup",
                            "reason_code": "allowed",
                            "result": {"status": "succeeded"},
                            "error": None,
                        },
                    )
                )
            ),
            event_hook=hook,
        )

        client.call_tool("claims.lookup", {"claim_id": "claim_123"})

        self.assertEqual([event["event"] for event in events], ["tool_call.start", "tool_call.success"])
        self.assertNotIn("sdk-token", str(events))
        self.assertNotIn("claim_123", str(events))

    def test_error_event_hook_includes_gateway_request_and_correlation_ids(self) -> None:
        events: list[dict[str, Any]] = []
        client = OphanixToolGatewayClient(
            base_url="https://gateway.example.test",
            token_provider=StaticTokenProvider("sdk-token"),
            http_client=httpx.Client(
                transport=httpx.MockTransport(
                    lambda _request: httpx.Response(
                        502,
                        json={
                            "request_id": "req-error-event",
                            "correlation_id": "corr-error-event",
                            "error": {"code": "upstream_error"},
                        },
                    )
                )
            ),
            event_hook=lambda event: events.append(dict(event)),
        )

        with self.assertRaises(ToolGatewayError):
            client.call_tool("claims.lookup", {"claim_id": "claim_123"})

        error = [event for event in events if event["event"] == "tool_call.error"][0]
        self.assertEqual("req-error-event", error["request_id"])
        self.assertEqual("corr-error-event", error["correlation_id"])

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
        self.assertEqual(raised.exception.message, "Tool Gateway returned HTTP 502.")

    def test_transport_failure_raises_typed_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused", request=request)

        client = _client(handler)

        with self.assertRaises(ToolGatewayError) as raised:
            client.call_tool("claims.lookup", {"claim_id": "claim_123"})

        self.assertEqual(raised.exception.code, "transport_error")
        self.assertEqual(raised.exception.message, "Tool Gateway transport error.")

    def test_async_successful_call_returns_typed_result(self) -> None:
        asyncio.run(self._async_successful_call_returns_typed_result())

    async def _async_successful_call_returns_typed_result(self) -> None:
        provider = AsyncCountingTokenProvider()
        seen: dict[str, Any] = {}

        async def handler(request: httpx.Request) -> httpx.Response:
            seen["authorization"] = request.headers["authorization"]
            seen["body"] = json.loads(request.content.decode())
            return httpx.Response(
                200,
                json={
                    "request_id": "req-async-1",
                    "correlation_id": "corr-async-1",
                    "tool_name": "claims.lookup",
                    "reason_code": "allowed",
                    "result": {"status": "succeeded"},
                    "error": None,
                },
            )

        transport = httpx.MockTransport(handler)
        async with AsyncOphanixToolGatewayClient(
            base_url="https://gateway.example.test",
            token_provider=provider,
            http_client=httpx.AsyncClient(transport=transport),
        ) as client:
            result = await client.call_tool("claims.lookup", {"claim_id": "claim_123"})

        self.assertEqual(result.request_id, "req-async-1")
        self.assertEqual(result.result, {"status": "succeeded"})
        self.assertEqual(seen["authorization"], "Bearer async-sdk-token-1")
        self.assertEqual(seen["body"], {"payload": {"claim_id": "claim_123"}})
        self.assertEqual(provider.calls, 1)


def _client(
    handler: httpx.MockTransport,
    *,
    token_provider: Any | None = None,
    max_response_bytes: int = 1_000_000,
) -> OphanixToolGatewayClient:
    transport = httpx.MockTransport(handler)
    return OphanixToolGatewayClient(
        base_url="https://gateway.example.test",
        token_provider=token_provider or StaticTokenProvider("sdk-token"),
        http_client=httpx.Client(transport=transport),
        max_response_bytes=max_response_bytes,
    )


if __name__ == "__main__":
    unittest.main()
