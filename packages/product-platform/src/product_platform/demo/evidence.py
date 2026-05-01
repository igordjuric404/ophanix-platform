"""Evidence link generation for Demo Lab runs."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from product_platform.demo.models import (
    DemoEvidenceLink,
    DemoProofChecklistItem,
    DemoScenarioStepResponse,
)


AREA_RESOURCE_KEYS: dict[str, tuple[str, str]] = {
    "Agents": ("agent_id", "agent_ids"),
    "Policies": ("policy_slug", "policy_slugs"),
    "MCP": ("mcp_server_id", "mcp_server_id"),
    "Mesh": ("message_id", "mesh_message_id"),
    "Runtime": ("runtime_ref", "saga_id"),
    "Trust": ("agent_id", "agent_id"),
    "Discovery": ("finding_id", "finding_id"),
    "Compliance": ("report_id", "report_id"),
    "Observability": ("report_id", "report_id"),
}


def build_evidence_links(
    step: DemoScenarioStepResponse,
    result: dict[str, Any],
) -> list[DemoEvidenceLink]:
    """Build concrete dashboard links for a step result."""

    resource_ids = result.get("resource_ids") if isinstance(result.get("resource_ids"), dict) else {}
    correlation_id = _optional_str(result.get("correlation_id"))
    links: list[DemoEvidenceLink] = []
    for proof in step.proof_links:
        query: dict[str, str] = {}
        resource_id = _resource_for_area(proof.area, resource_ids, proof.resource_hint)
        param_name = AREA_RESOURCE_KEYS.get(proof.area, ("resource_id", "resource_id"))[0]
        if resource_id:
            query[param_name] = resource_id
        if correlation_id:
            query["correlation_id"] = correlation_id
        links.append(
            DemoEvidenceLink(
                area=proof.area,
                label=proof.label,
                route=_route_with_query(proof.route, query),
                resource_id=resource_id,
                correlation_id=correlation_id,
            )
        )
    return links


def build_proof_checklist(
    step: DemoScenarioStepResponse,
    *,
    step_status: str,
    result: dict[str, Any],
) -> list[DemoProofChecklistItem]:
    """Build proof checklist rows for one step run."""

    actual_result = _optional_str(result.get("actual_result"))
    status = {
        "succeeded": "completed",
        "failed": "failed",
        "canceled": "canceled",
    }.get(step_status, "pending")
    return [
        DemoProofChecklistItem(
            area=link.area,
            label=link.label,
            status=status,
            route=link.route,
            expected_result=step.expected_result,
            actual_result=actual_result,
        )
        for link in build_evidence_links(step, result)
    ]


def _resource_for_area(
    area: str,
    resource_ids: dict[str, Any],
    fallback: str | None,
) -> str | None:
    _, resource_key = AREA_RESOURCE_KEYS.get(area, ("resource_id", "resource_id"))
    value = resource_ids.get(resource_key)
    if isinstance(value, list):
        return _optional_str(value[0]) if value else fallback
    if value is None and area == "Runtime":
        value = resource_ids.get("approval_id")
    if value is None and area == "MCP":
        value = resource_ids.get("tool_names")
        if isinstance(value, list):
            return _optional_str(value[0]) if value else fallback
    return _optional_str(value) or fallback


def _route_with_query(route: str, query: dict[str, str]) -> str:
    if not query:
        return route
    separator = "&" if "?" in route else "?"
    return f"{route}{separator}{urlencode(query)}"


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
