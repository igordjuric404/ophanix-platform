"""MCP security scan adapters and finding normalization."""

from __future__ import annotations

import sys
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class MCPScanFindingCandidate:
    """A scanner finding normalized for product persistence."""

    tool_id: str
    tool_version_id: str | None
    finding_type: str
    severity: str
    title: str
    description: str
    evidence: dict[str, Any]
    recommendation: str


@dataclass(frozen=True)
class MCPScannerAdapterResult:
    """Normalized result from scanning product MCP tools."""

    tools_scanned: int
    tools_flagged: int
    findings: list[MCPScanFindingCandidate]


class MCPScannerAdapter:
    """Wrap Agent OS `MCPSecurityScanner` for product tool records."""

    def __init__(self, scanner: Any | None = None) -> None:
        self.scanner = scanner if scanner is not None else _create_agent_os_scanner()

    def scan_tools(self, tools: list[dict[str, Any]]) -> MCPScannerAdapterResult:
        """Scan product tool dictionaries and return normalized findings."""

        findings: list[MCPScanFindingCandidate] = []
        flagged_tool_ids: set[str] = set()
        for tool in tools:
            schema = _tool_schema(tool)
            definition = _tool_definition(tool)
            server_name = str(tool.get("server_name") or tool.get("server_id") or "unknown")
            threats = self.scanner.scan_tool(
                str(tool.get("name") or "unknown"),
                str(tool.get("description") or ""),
                schema,
                server_name,
            )
            for threat in threats:
                flagged_tool_ids.add(str(tool.get("id") or "unknown"))
                findings.append(_finding_from_threat(tool, definition, threat))
        return MCPScannerAdapterResult(
            tools_scanned=len(tools),
            tools_flagged=len(flagged_tool_ids),
            findings=findings,
        )


def _finding_from_threat(
    tool: dict[str, Any],
    definition: dict[str, Any],
    threat: Any,
) -> MCPScanFindingCandidate:
    threat_type = _enum_value(threat.threat_type)
    severity = _enum_value(threat.severity)
    details = dict(getattr(threat, "details", {}) or {})
    evidence = {
        "tool_name": getattr(threat, "tool_name", tool.get("name")),
        "server_name": getattr(threat, "server_name", tool.get("server_name")),
        "matched_pattern": getattr(threat, "matched_pattern", None),
        "details": details,
        "definition": definition,
    }
    return MCPScanFindingCandidate(
        tool_id=str(tool.get("id") or ""),
        tool_version_id=tool.get("current_version_id"),
        finding_type=threat_type,
        severity=severity,
        title=_title_for_threat(threat_type),
        description=str(getattr(threat, "message", "")),
        evidence=evidence,
        recommendation=_recommendation_for_threat(threat_type),
    )


def _tool_schema(tool: dict[str, Any]) -> dict[str, Any] | None:
    current_version = tool.get("current_version") or {}
    schema = current_version.get("schema") or current_version.get("input_schema")
    if isinstance(schema, dict):
        return schema
    definition = _tool_definition(tool)
    definition_schema = definition.get("inputSchema") or definition.get("schema")
    return definition_schema if isinstance(definition_schema, dict) else None


def _tool_definition(tool: dict[str, Any]) -> dict[str, Any]:
    current_version = tool.get("current_version") or {}
    definition = current_version.get("definition")
    return definition if isinstance(definition, dict) else {}


def _enum_value(value: Any) -> str:
    enum_value = getattr(value, "value", value)
    return str(enum_value)


def _title_for_threat(threat_type: str) -> str:
    titles = {
        "tool_poisoning": "Tool poisoning risk",
        "rug_pull": "Tool definition rug pull",
        "cross_server_attack": "Cross-server tool collision",
        "confused_deputy": "Confused deputy risk",
        "hidden_instruction": "Hidden instruction detected",
        "description_injection": "Prompt injection in tool metadata",
    }
    return titles.get(threat_type, "MCP security finding")


def _recommendation_for_threat(threat_type: str) -> str:
    recommendations = {
        "tool_poisoning": "Tighten the tool schema and remove instruction-bearing defaults or hidden fields.",
        "rug_pull": "Review the schema and description change before re-approving the tool.",
        "cross_server_attack": "Confirm the server owner and rename or scope colliding tool names.",
        "confused_deputy": "Require scoped authorization and explicit user approval for delegated access.",
        "hidden_instruction": "Remove hidden instructions, invisible characters, comments, or encoded payloads.",
        "description_injection": "Rewrite the description as neutral tool metadata without model instructions.",
    }
    return recommendations.get(threat_type, "Review the MCP tool definition before use.")


def _create_agent_os_scanner() -> Any:
    MCPSecurityScanner = _load_agent_os_scanner_class()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return MCPSecurityScanner()


def _load_agent_os_scanner_class() -> Any:
    try:
        from agent_os.mcp_security import MCPSecurityScanner

        return MCPSecurityScanner
    except ModuleNotFoundError:
        agent_os_src = Path(__file__).resolve().parents[4] / "agent-os" / "src"
        if agent_os_src.exists():
            sys.path.insert(0, str(agent_os_src))
            from agent_os.mcp_security import MCPSecurityScanner

            return MCPSecurityScanner
        raise

