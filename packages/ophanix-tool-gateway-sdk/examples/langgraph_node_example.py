from __future__ import annotations

from typing import Any, TypedDict

from ophanix_tool_gateway import EnvironmentTokenProvider, OphanixToolGatewayClient


class ClaimState(TypedDict, total=False):
    claim_id: str
    claim_status: str
    gateway_request_id: str


def claims_lookup_node(state: ClaimState) -> ClaimState:
    """Framework-style node function that can be adapted into a graph runtime."""

    claim_id = state["claim_id"]
    with OphanixToolGatewayClient(
        base_url="https://gateway.example.com",
        token_provider=EnvironmentTokenProvider(),
    ) as client:
        result = client.call_tool(
            "claims.lookup",
            {"claim_id": claim_id},
            correlation_id=f"claim:{claim_id}",
            idempotency_key=f"claims.lookup:{claim_id}",
        )

    body = _result_body(result.result)
    return {
        **state,
        "claim_status": str(body.get("claim_status", "unknown")),
        "gateway_request_id": result.request_id,
    }


def _result_body(result: Any) -> dict[str, Any]:
    if isinstance(result, dict) and isinstance(result.get("body"), dict):
        return result["body"]
    if isinstance(result, dict):
        return result
    return {}
