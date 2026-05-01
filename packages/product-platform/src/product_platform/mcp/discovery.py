"""MCP tool discovery adapters and normalization helpers."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import parse_qs, urlparse


TOOL_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")
EMPTY_TOOL_SCHEMA = {"type": "object", "additionalProperties": False}


@dataclass(frozen=True)
class NormalizedMCPToolDefinition:
    """A product-normalized MCP tool definition."""

    name: str
    description: str
    schema: dict[str, Any]
    schema_hash: str
    definition: dict[str, Any]


class MCPToolDiscoveryAdapter(Protocol):
    """Adapter interface for discovering tools from an MCP server."""

    def discover_tools(self, server: Any) -> list[dict[str, Any]]:
        """Return raw MCP tool definitions for a server."""


class DemoMCPToolDiscoveryAdapter:
    """Local deterministic MCP discovery adapter used by product tests and demos."""

    def discover_tools(self, server: Any) -> list[dict[str, Any]]:
        """Return MCP-like tool definitions for a registered demo server."""

        endpoint = str(server["endpoint_url"])
        name = str(server["name"]).lower()
        parsed = urlparse(endpoint)
        query = parse_qs(parsed.query)
        schema_variant = query.get("schema", ["v1"])[0]
        if "trust" in name or "trust" in parsed.netloc or "trust" in parsed.path:
            return _trust_verified_tools(schema_variant)
        return _claims_support_tools(schema_variant)


def normalize_tool_definition(definition: dict[str, Any]) -> NormalizedMCPToolDefinition:
    """Normalize an MCP tool definition into product fields."""

    name = str(definition.get("name", "")).strip()
    if not TOOL_NAME_PATTERN.fullmatch(name):
        raise ValueError("MCP tool name must be 1-128 ASCII letters, numbers, _, -, or .")
    description = str(definition.get("description") or definition.get("title") or "").strip()
    schema = definition.get("inputSchema", definition.get("schema", EMPTY_TOOL_SCHEMA))
    if schema is None:
        schema = EMPTY_TOOL_SCHEMA
    if not isinstance(schema, dict):
        raise ValueError("MCP tool inputSchema must be a JSON object.")
    normalized_definition = json.loads(json.dumps(definition, sort_keys=True, default=str))
    normalized_definition["name"] = name
    normalized_definition["description"] = description
    normalized_definition["inputSchema"] = json.loads(canonical_json(schema))
    return NormalizedMCPToolDefinition(
        name=name,
        description=description,
        schema=normalized_definition["inputSchema"],
        schema_hash=calculate_schema_hash(schema),
        definition=normalized_definition,
    )


def calculate_schema_hash(schema: dict[str, Any]) -> str:
    """Calculate a stable hash for a JSON schema."""

    digest = hashlib.sha256(canonical_json(schema).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def canonical_json(value: Any) -> str:
    """Return deterministic compact JSON for hashing and persistence."""

    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _claims_support_tools(schema_variant: str) -> list[dict[str, Any]]:
    refund_properties: dict[str, Any] = {
        "order_id": {"type": "string", "description": "Order identifier"},
        "amount": {"type": "number", "minimum": 0},
    }
    refund_required = ["order_id", "amount"]
    if schema_variant == "v2":
        refund_properties["reason"] = {"type": "string", "minLength": 3}
        refund_required.append("reason")
    return [
        {
            "name": "claims.lookup_order",
            "description": "Look up claim and order status for a customer.",
            "inputSchema": {
                "type": "object",
                "properties": {"order_id": {"type": "string"}},
                "required": ["order_id"],
                "additionalProperties": False,
            },
            "annotations": {"readOnlyHint": True},
        },
        {
            "name": "claims.issue_refund",
            "description": "Issue a customer refund for a claim.",
            "inputSchema": {
                "type": "object",
                "properties": refund_properties,
                "required": refund_required,
                "additionalProperties": False,
            },
            "annotations": {"destructiveHint": True},
        },
        {
            "name": "notifications.send_email",
            "description": "Send a customer notification email.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "to": {"type": "string", "format": "email"},
                    "template": {"type": "string"},
                },
                "required": ["to", "template"],
                "additionalProperties": False,
            },
        },
    ]


def _trust_verified_tools(schema_variant: str) -> list[dict[str, Any]]:
    write_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
        },
        "required": ["path", "content"],
        "additionalProperties": False,
    }
    if schema_variant == "v2":
        write_schema["properties"]["mode"] = {"type": "string", "enum": ["append", "overwrite"]}
    return [
        {
            "name": "read_file",
            "description": "Read a file by path and return its contents.",
            "inputSchema": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
                "additionalProperties": False,
            },
            "annotations": {"readOnlyHint": True},
        },
        {
            "name": "write_file",
            "description": "Write content to a file path.",
            "inputSchema": write_schema,
            "annotations": {"destructiveHint": True},
        },
        {
            "name": "query_database",
            "description": "Execute a read-only SQL query.",
            "inputSchema": {
                "type": "object",
                "properties": {"sql": {"type": "string"}},
                "required": ["sql"],
                "additionalProperties": False,
            },
        },
    ]

