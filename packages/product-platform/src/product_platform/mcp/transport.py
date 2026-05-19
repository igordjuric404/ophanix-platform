"""MCP transport helpers for Product Platform mediation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx

MCP_PROTOCOL_VERSION = "2025-11-25"


class MCPTransportError(ValueError):
    """Raised when an MCP transport request fails or returns an invalid response."""


@dataclass(frozen=True)
class MCPJSONRPCResponse:
    """Normalized JSON-RPC response from an MCP transport."""

    result: dict[str, Any] | list[Any] | str | int | float | bool | None
    metadata: dict[str, Any]


class MCPStreamableHTTPClient:
    """Small synchronous client for MCP Streamable HTTP JSON-RPC requests."""

    def __init__(self, *, timeout_seconds: float = 5.0, http_client: httpx.Client | None = None) -> None:
        self.timeout_seconds = timeout_seconds
        self.http_client = http_client

    def request(
        self,
        endpoint_url: str,
        method: str,
        *,
        params: dict[str, Any] | None = None,
        request_id: str,
    ) -> MCPJSONRPCResponse:
        """Send one JSON-RPC request to an MCP Streamable HTTP endpoint."""

        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
        }
        if params is not None:
            payload["params"] = params
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "MCP-Protocol-Version": MCP_PROTOCOL_VERSION,
        }
        client = self.http_client or httpx.Client()
        close_client = self.http_client is None
        try:
            response = client.post(
                endpoint_url,
                json=payload,
                headers=headers,
                timeout=self.timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise MCPTransportError(f"MCP HTTP transport failed: {exc}") from exc
        finally:
            if close_client:
                client.close()

        response_bytes = len(response.content)
        if response.status_code >= 400:
            raise MCPTransportError(f"MCP HTTP transport returned status {response.status_code}.")
        body = _decode_jsonrpc_response(response)
        if not isinstance(body, dict):
            raise MCPTransportError("MCP JSON-RPC response must be an object.")
        if body.get("jsonrpc") != "2.0":
            raise MCPTransportError("MCP JSON-RPC response must include jsonrpc='2.0'.")
        if "error" in body and body["error"] is not None:
            error = body["error"]
            message = error.get("message") if isinstance(error, dict) else str(error)
            raise MCPTransportError(f"MCP JSON-RPC error: {message}")
        result = body.get("result")
        metadata = {
            "jsonrpc": body.get("jsonrpc"),
            "id": body.get("id"),
            "http_status": response.status_code,
            "content_type": response.headers.get("content-type"),
            "response_bytes": response_bytes,
            "result_type": type(result).__name__,
            "result_keys": sorted(result.keys()) if isinstance(result, dict) else [],
            "is_error": bool(result.get("isError")) if isinstance(result, dict) else False,
        }
        return MCPJSONRPCResponse(result=result, metadata=metadata)


def _decode_jsonrpc_response(response: httpx.Response) -> Any:
    content_type = response.headers.get("content-type", "").lower()
    if "text/event-stream" in content_type:
        return _decode_sse_json(response.text)
    return response.json()


def _decode_sse_json(text: str) -> Any:
    data_lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("data:"):
            data = line[len("data:") :].strip()
            if data == "[DONE]":
                break
            data_lines.append(data)
            if data:
                break
    if not data_lines:
        raise MCPTransportError("MCP SSE response did not contain a JSON data event.")
    return json.loads("\n".join(data_lines))

