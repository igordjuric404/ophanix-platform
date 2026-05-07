from __future__ import annotations

import unittest
from typing import Any

import httpx

from product_platform.tool_gateway.sdk import (
    OphanixToolGatewayClient,
    StaticTokenProvider,
    ToolGatewayError,
)


TOOL_FIXTURE = {
    "id": "tool_claims_lookup",
    "organization_id": "org_demo",
    "environment_id": "env_demo",
    "name": "claims.lookup",
    "display_name": "Claims Lookup",
    "description": "Lookup claim state.",
    "owner_team": "Claims",
    "status": "active",
    "required_scope": "claims.lookup:read",
    "input_schema_json": {"type": "object"},
    "output_schema_json": {"type": "object"},
    "created_by": "user_demo",
    "created_at": "2026-05-01T00:00:00+00:00",
    "updated_at": "2026-05-01T00:00:00+00:00",
    "latest_version": {"id": "toolver_claims_lookup", "version": 1},
    "versions": [],
}


class ToolGatewaySdkPhase3Tests(unittest.TestCase):
    def test_list_tools_maps_response_to_typed_definitions(self) -> None:
        seen: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["path"] = request.url.path
            seen["query"] = request.url.query.decode()
            seen["authorization"] = request.headers["authorization"]
            return httpx.Response(200, json=[TOOL_FIXTURE])

        client = _client(handler)

        tools = client.list_tools(status="active", limit=25, offset=5)

        self.assertEqual(seen["path"], "/api/v1/tools")
        self.assertEqual(seen["query"], "status=active&limit=25&offset=5")
        self.assertEqual(seen["authorization"], "Bearer sdk-token")
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0].id, "tool_claims_lookup")
        self.assertEqual(tools[0].name, "claims.lookup")
        self.assertEqual(tools[0].display_name, "Claims Lookup")
        self.assertEqual(tools[0].required_scope, "claims.lookup:read")
        self.assertEqual(tools[0].input_schema_json, {"type": "object"})
        self.assertEqual(tools[0].latest_version, {"id": "toolver_claims_lookup", "version": 1})
        self.assertEqual(tools[0].raw["organization_id"], "org_demo")

    def test_get_tool_returns_matching_tool_by_name(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=[TOOL_FIXTURE])

        client = _client(handler)

        tool = client.get_tool("claims.lookup")

        self.assertEqual(tool.id, "tool_claims_lookup")
        self.assertEqual(tool.name, "claims.lookup")

    def test_get_tool_handles_not_found(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=[])

        client = _client(handler)

        with self.assertRaises(ToolGatewayError) as raised:
            client.get_tool("claims.lookup")

        self.assertEqual(raised.exception.status_code, 404)
        self.assertEqual(raised.exception.code, "tool_not_found")
        self.assertIn("claims.lookup", raised.exception.message)

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


def _client(
    handler: httpx.MockTransport,
    *,
    cache_tools: bool = False,
) -> OphanixToolGatewayClient:
    transport = httpx.MockTransport(handler)
    return OphanixToolGatewayClient(
        base_url="https://gateway.example.test",
        token_provider=StaticTokenProvider("sdk-token"),
        http_client=httpx.Client(transport=transport),
        cache_tools=cache_tools,
    )


if __name__ == "__main__":
    unittest.main()
