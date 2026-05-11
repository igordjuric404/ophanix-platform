from __future__ import annotations

import asyncio
import time
import unittest
from typing import Any
from urllib.parse import parse_qs

import httpx

from product_platform.tool_gateway.sdk import (
    AsyncOphanixToolGatewayClient,
    GatewayCompatibility,
    OphanixToolGatewayClient,
    StaticTokenProvider,
    ToolGatewayClientConfig,
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


class ToolGatewaySdkPhase3Tests(unittest.TestCase):
    def test_list_tools_maps_response_to_typed_definitions(self) -> None:
        seen: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["path"] = request.url.path
            seen["query"] = request.url.query.decode()
            seen["authorization"] = request.headers["authorization"]
            return httpx.Response(200, json=[TOOL_FIXTURE])

        client = _client(handler)

        with self.assertWarns(DeprecationWarning):
            tools = client.list_tools(status="active", limit=25, offset=5)

        self.assertEqual(seen["path"], "/api/v1/gateway/tools")
        self.assertEqual(seen["query"], "limit=25&offset=5")
        self.assertEqual(seen["authorization"], "Bearer sdk-token")
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0].id, "tool_claims_lookup")
        self.assertEqual(tools[0].name, "claims.lookup")
        self.assertEqual(tools[0].display_name, "Claims Lookup")
        self.assertEqual(tools[0].required_scope, "claims.lookup:read")
        self.assertEqual(tools[0].input_schema_json, {"type": "object"})
        self.assertEqual(tools[0].raw["id"], "tool_claims_lookup")

    def test_list_tools_supports_owner_team_filter(self) -> None:
        seen: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["query"] = request.url.query.decode()
            return httpx.Response(200, json=[TOOL_FIXTURE])

        client = _client(handler)

        client.list_tools(owner_team="Claims", limit=25)

        self.assertEqual(seen["query"], "owner_team=Claims&limit=25&offset=0")

    def test_list_tools_rejects_non_active_status_filter(self) -> None:
        client = _client(lambda _request: httpx.Response(200, json=[]))

        with self.assertWarns(DeprecationWarning):
            with self.assertRaisesRegex(ValueError, "active callable tools"):
                client.list_tools(status="draft")

    def test_list_tools_rejects_limit_above_gateway_maximum(self) -> None:
        client = _client(lambda _request: httpx.Response(200, json=[]))

        with self.assertRaisesRegex(ValueError, "less than or equal to 200"):
            client.list_tools(limit=201)

    def test_list_tools_rejects_non_integer_limit(self) -> None:
        client = _client(lambda _request: httpx.Response(200, json=[]))

        with self.assertRaisesRegex(ValueError, "limit must be an integer"):
            client.list_tools(limit=True)  # type: ignore[arg-type]

    def test_list_tools_rejects_malformed_items(self) -> None:
        client = _client(lambda _request: httpx.Response(200, json=["not-a-tool"]))

        with self.assertRaises(ToolGatewayError) as raised:
            client.list_tools()

        self.assertEqual(raised.exception.code, "invalid_response")

    def test_list_tools_rejects_missing_required_tool_fields(self) -> None:
        client = _client(lambda _request: httpx.Response(200, json=[{"id": "tool_missing"}]))

        with self.assertRaises(ToolGatewayError) as raised:
            client.list_tools()

        self.assertEqual(raised.exception.code, "invalid_response")
        self.assertIn("name", raised.exception.message)

    def test_list_tools_rejects_non_object_schema_fields(self) -> None:
        client = _client(
            lambda _request: httpx.Response(
                200,
                json=[{**TOOL_FIXTURE, "input_schema_json": ["not", "an", "object"]}],
            )
        )

        with self.assertRaises(ToolGatewayError) as raised:
            client.list_tools()

        self.assertEqual(raised.exception.code, "invalid_response")
        self.assertIn("input_schema_json", raised.exception.message)

    def test_list_tools_rejects_non_string_description(self) -> None:
        client = _client(
            lambda _request: httpx.Response(
                200,
                json=[{**TOOL_FIXTURE, "description": {"not": "a string"}}],
            )
        )

        with self.assertRaises(ToolGatewayError) as raised:
            client.list_tools()

        self.assertEqual(raised.exception.code, "invalid_response")
        self.assertIn("description", raised.exception.message)

    def test_tool_definition_raw_mapping_is_immutable(self) -> None:
        client = _client(lambda _request: httpx.Response(200, json=[TOOL_FIXTURE]))

        tool = client.list_tools()[0]

        with self.assertRaises(TypeError):
            tool.raw["id"] = "mutated"  # type: ignore[index]

    def test_get_tool_returns_matching_tool_by_name(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=[TOOL_FIXTURE])

        client = _client(handler)

        tool = client.get_tool("claims.lookup")

        self.assertEqual(tool.id, "tool_claims_lookup")
        self.assertEqual(tool.name, "claims.lookup")

    def test_get_tool_paginates_until_matching_tool_is_found(self) -> None:
        seen_offsets: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            query = parse_qs(request.url.query.decode())
            offset = query["offset"][0]
            seen_offsets.append(offset)
            if offset == "0":
                return httpx.Response(
                    200,
                    json=[
                        {
                            **TOOL_FIXTURE,
                            "id": f"tool_other_{index}",
                            "name": f"claims.other_{index}",
                        }
                        for index in range(200)
                    ],
                )
            return httpx.Response(200, json=[TOOL_FIXTURE])

        client = _client(handler)

        tool = client.get_tool("claims.lookup")

        self.assertEqual(tool.id, "tool_claims_lookup")
        self.assertEqual(seen_offsets, ["0", "200"])

    def test_list_all_tools_paginates_until_final_page(self) -> None:
        seen_offsets: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            query = parse_qs(request.url.query.decode())
            offset = query["offset"][0]
            seen_offsets.append(offset)
            if offset == "0":
                return httpx.Response(
                    200,
                    json=[
                        {
                            **TOOL_FIXTURE,
                            "id": f"tool_other_{index}",
                            "name": f"claims.other_{index}",
                        }
                        for index in range(2)
                    ],
                )
            return httpx.Response(200, json=[TOOL_FIXTURE])

        client = _client(handler)

        tools = client.list_all_tools(page_size=2)

        self.assertEqual([tool.id for tool in tools], [
            "tool_other_0",
            "tool_other_1",
            "tool_claims_lookup",
        ])
        self.assertEqual(seen_offsets, ["0", "2"])

    def test_list_all_tools_rejects_non_integer_page_size(self) -> None:
        client = _client(lambda _request: httpx.Response(200, json=[]))

        with self.assertRaisesRegex(ValueError, "page_size must be an integer"):
            client.list_all_tools(page_size=True)  # type: ignore[arg-type]

    def test_get_tool_handles_not_found(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=[])

        client = _client(handler)

        with self.assertRaises(ToolGatewayError) as raised:
            client.get_tool("claims.lookup")

        self.assertEqual(raised.exception.status_code, 404)
        self.assertEqual(raised.exception.code, "tool_not_visible")
        self.assertIn("claims.lookup", raised.exception.message)

    def test_check_compatibility_reads_capabilities_endpoint(self) -> None:
        seen: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["path"] = request.url.path
            return httpx.Response(
                200,
                json={
                    "gateway_contract_version": "tool-gateway.v1",
                    "min_sdk_version": "0.1.0",
                    "sdk_package": "ophanix-tool-gateway-sdk",
                },
            )

        client = _client(handler)

        compatibility = client.check_compatibility()

        self.assertIsInstance(compatibility, GatewayCompatibility)
        self.assertEqual(seen["path"], "/api/v1/gateway/capabilities")
        self.assertTrue(compatibility.compatible)

    def test_client_from_config_uses_reusable_sdk_configuration(self) -> None:
        config = ToolGatewayClientConfig(timeout_seconds=3.0, cache_tools=True)

        client = OphanixToolGatewayClient.from_config(
            base_url="https://gateway.example.test",
            token_provider=StaticTokenProvider("sdk-token"),
            config=config,
            http_client=httpx.Client(
                transport=httpx.MockTransport(lambda _request: httpx.Response(200, json=[]))
            ),
        )

        self.assertEqual(client.timeout_seconds, 3.0)
        self.assertTrue(client.cache_tools)

    def test_cache_is_disabled_by_default(self) -> None:
        calls = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(200, json=[{**TOOL_FIXTURE, "id": f"tool_{calls}"}])

        client = _client(handler)

        first = client.list_tools()
        second = client.list_tools()

        self.assertEqual(calls, 2)
        self.assertEqual(first[0].id, "tool_1")
        self.assertEqual(second[0].id, "tool_2")

    def test_cache_is_used_only_when_explicitly_configured(self) -> None:
        calls = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(200, json=[{**TOOL_FIXTURE, "id": f"tool_{calls}"}])

        client = _client(handler, cache_tools=True)

        first = client.list_tools()
        second = client.list_tools()

        self.assertEqual(calls, 1)
        self.assertEqual(first[0].id, "tool_1")
        self.assertEqual(second[0].id, "tool_1")

    def test_cached_tool_definitions_do_not_share_mutable_schema_state(self) -> None:
        calls = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(200, json=[TOOL_FIXTURE])

        client = _client(handler, cache_tools=True)

        first = client.list_tools()[0]
        first.input_schema_json["mutated"] = True
        second = client.list_tools()[0]

        self.assertEqual(calls, 1)
        self.assertEqual(second.input_schema_json, {"type": "object"})

    def test_cache_entries_are_bounded(self) -> None:
        seen_queries: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen_queries.append(request.url.query.decode())
            return httpx.Response(200, json=[TOOL_FIXTURE])

        client = _client(handler, cache_tools=True, max_cache_entries=1)

        client.list_tools(owner_team="Claims")
        client.list_tools(owner_team="Fraud")
        client.list_tools(owner_team="Claims")

        self.assertEqual(len(seen_queries), 3)

    def test_cache_entries_expire_after_configured_ttl(self) -> None:
        calls = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(200, json=[{**TOOL_FIXTURE, "id": f"tool_{calls}"}])

        client = _client(handler, cache_tools=True, cache_ttl_seconds=0.001)

        first = client.list_tools()
        time.sleep(0.01)
        second = client.list_tools()

        self.assertEqual(calls, 2)
        self.assertEqual(first[0].id, "tool_1")
        self.assertEqual(second[0].id, "tool_2")

    def test_cache_is_partitioned_by_current_token(self) -> None:
        provider = CountingTokenProvider()
        authorizations: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            authorizations.append(request.headers["authorization"])
            return httpx.Response(
                200,
                json=[
                    {
                        **TOOL_FIXTURE,
                        "id": f"tool_{len(authorizations)}",
                    }
                ],
            )

        client = _client(handler, cache_tools=True, token_provider=provider)

        first = client.list_tools()
        second = client.list_tools()

        self.assertEqual(provider.calls, 2)
        self.assertEqual(authorizations, ["Bearer sdk-token-1", "Bearer sdk-token-2"])
        self.assertEqual(first[0].id, "tool_1")
        self.assertEqual(second[0].id, "tool_2")

    def test_get_tool_cache_is_partitioned_by_current_token(self) -> None:
        provider = CountingTokenProvider()
        authorizations: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            authorizations.append(request.headers["authorization"])
            return httpx.Response(
                200,
                json=[
                    {
                        **TOOL_FIXTURE,
                        "id": f"tool_{len(authorizations)}",
                    }
                ],
            )

        client = _client(handler, cache_tools=True, token_provider=provider)

        first = client.get_tool("claims.lookup")
        second = client.get_tool("claims.lookup")

        self.assertEqual(provider.calls, 2)
        self.assertEqual(authorizations, ["Bearer sdk-token-1", "Bearer sdk-token-2"])
        self.assertEqual(first.id, "tool_1")
        self.assertEqual(second.id, "tool_2")

    def test_list_all_tools_uses_one_credential_context_across_pages(self) -> None:
        provider = CountingTokenProvider()
        authorizations: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            authorizations.append(request.headers["authorization"])
            query = parse_qs(request.url.query.decode())
            offset = query["offset"][0]
            if offset == "0":
                return httpx.Response(
                    200,
                    json=[
                        {**TOOL_FIXTURE, "id": "tool_1", "name": "claims.lookup_1"},
                        {**TOOL_FIXTURE, "id": "tool_2", "name": "claims.lookup_2"},
                    ],
                )
            return httpx.Response(200, json=[{**TOOL_FIXTURE, "id": "tool_3"}])

        client = _client(handler, token_provider=provider)

        tools = client.list_all_tools(page_size=2)

        self.assertEqual(provider.calls, 1)
        self.assertEqual(authorizations, ["Bearer sdk-token-1", "Bearer sdk-token-1"])
        self.assertEqual([tool.id for tool in tools], ["tool_1", "tool_2", "tool_3"])

    def test_clear_tool_cache_forces_fresh_discovery(self) -> None:
        calls = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(200, json=[{**TOOL_FIXTURE, "id": f"tool_{calls}"}])

        client = _client(handler, cache_tools=True)

        first = client.list_tools()
        client.clear_tool_cache()
        second = client.list_tools()

        self.assertEqual(calls, 2)
        self.assertEqual(first[0].id, "tool_1")
        self.assertEqual(second[0].id, "tool_2")

    def test_list_tools_retries_transient_discovery_failures(self) -> None:
        calls = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            if calls == 1:
                return httpx.Response(503, json={"error": {"message": "temporary outage"}})
            return httpx.Response(200, json=[TOOL_FIXTURE])

        client = _client(handler, discovery_max_retries=1)

        tools = client.list_tools()

        self.assertEqual(calls, 2)
        self.assertEqual(tools[0].name, "claims.lookup")

    def test_list_tools_respects_retry_after_with_sleep_cap(self) -> None:
        calls = 0
        delays: list[float] = []

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            if calls == 1:
                return httpx.Response(
                    429,
                    headers={"Retry-After": "10"},
                    json={"error": {"message": "rate limited"}},
                )
            return httpx.Response(200, json=[TOOL_FIXTURE])

        client = _client(
            handler,
            discovery_max_retries=1,
            discovery_retry_max_sleep_seconds=2,
        )
        client._sleep = delays.append  # type: ignore[method-assign]

        tools = client.list_tools()

        self.assertEqual(calls, 2)
        self.assertEqual(delays, [2])
        self.assertEqual(tools[0].name, "claims.lookup")

    def test_list_tools_does_not_retry_non_retryable_discovery_failures(self) -> None:
        calls = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(403, json={"error": {"code": "denied", "message": "denied"}})

        client = _client(handler, discovery_max_retries=2)

        with self.assertRaises(ToolGatewayError) as raised:
            client.list_tools()

        self.assertEqual(calls, 1)
        self.assertEqual(raised.exception.status_code, 403)

    def test_async_list_all_tools_paginates_until_final_page(self) -> None:
        asyncio.run(self._async_list_all_tools_paginates_until_final_page())

    async def _async_list_all_tools_paginates_until_final_page(self) -> None:
        seen_offsets: list[str] = []

        async def handler(request: httpx.Request) -> httpx.Response:
            query = parse_qs(request.url.query.decode())
            offset = query["offset"][0]
            seen_offsets.append(offset)
            if offset == "0":
                return httpx.Response(
                    200,
                    json=[
                        {
                            **TOOL_FIXTURE,
                            "id": f"tool_other_{index}",
                            "name": f"claims.other_{index}",
                        }
                        for index in range(2)
                    ],
                )
            return httpx.Response(200, json=[TOOL_FIXTURE])

        transport = httpx.MockTransport(handler)
        async with AsyncOphanixToolGatewayClient(
            base_url="https://gateway.example.test",
            token_provider=StaticTokenProvider("sdk-token"),
            http_client=httpx.AsyncClient(transport=transport),
            discovery_retry_jitter_ratio=0,
        ) as client:
            tools = await client.list_all_tools(page_size=2)

        self.assertEqual([tool.id for tool in tools], [
            "tool_other_0",
            "tool_other_1",
            "tool_claims_lookup",
        ])
        self.assertEqual(seen_offsets, ["0", "2"])

    def test_async_get_tool_cache_is_partitioned_by_current_token(self) -> None:
        asyncio.run(self._async_get_tool_cache_is_partitioned_by_current_token())

    async def _async_get_tool_cache_is_partitioned_by_current_token(self) -> None:
        provider = AsyncCountingTokenProvider()
        authorizations: list[str] = []

        async def handler(request: httpx.Request) -> httpx.Response:
            authorizations.append(request.headers["authorization"])
            return httpx.Response(
                200,
                json=[
                    {
                        **TOOL_FIXTURE,
                        "id": f"tool_{len(authorizations)}",
                    }
                ],
            )

        transport = httpx.MockTransport(handler)
        async with AsyncOphanixToolGatewayClient(
            base_url="https://gateway.example.test",
            token_provider=provider,
            http_client=httpx.AsyncClient(transport=transport),
            cache_tools=True,
            discovery_retry_jitter_ratio=0,
        ) as client:
            first = await client.get_tool("claims.lookup")
            second = await client.get_tool("claims.lookup")

        self.assertEqual(provider.calls, 2)
        self.assertEqual(authorizations, ["Bearer async-sdk-token-1", "Bearer async-sdk-token-2"])
        self.assertEqual(first.id, "tool_1")
        self.assertEqual(second.id, "tool_2")


def _client(
    handler: httpx.MockTransport,
    *,
    cache_tools: bool = False,
    cache_ttl_seconds: float = 300,
    max_cache_entries: int = 256,
    discovery_max_retries: int = 0,
    discovery_retry_max_sleep_seconds: float = 5,
    token_provider: Any | None = None,
) -> OphanixToolGatewayClient:
    transport = httpx.MockTransport(handler)
    return OphanixToolGatewayClient(
        base_url="https://gateway.example.test",
        token_provider=token_provider or StaticTokenProvider("sdk-token"),
        http_client=httpx.Client(transport=transport),
        cache_tools=cache_tools,
        cache_ttl_seconds=cache_ttl_seconds,
        max_cache_entries=max_cache_entries,
        discovery_max_retries=discovery_max_retries,
        discovery_retry_backoff_seconds=0,
        discovery_retry_max_sleep_seconds=discovery_retry_max_sleep_seconds,
        discovery_retry_jitter_ratio=0,
    )


if __name__ == "__main__":
    unittest.main()
