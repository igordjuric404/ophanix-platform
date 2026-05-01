"""Mesh topology aggregation."""

from __future__ import annotations

import time
from collections.abc import Iterable, Mapping
from typing import Any

from product_platform.db.time import utc_now_iso
from product_platform.mesh.models import (
    MeshTopologyEdge,
    MeshTopologyNode,
    MeshTopologyResponse,
)
from product_platform.mesh.repository import MeshRepository


DENIED_DECISIONS = {"deny", "denied", "blocked"}
TOPOLOGY_CACHE_TTL_SECONDS = 5
_TOPOLOGY_CACHE: dict[tuple[int, str, str, str | None, str | None], tuple[float, MeshTopologyResponse]] = {}


class MeshTopologyService:
    """Build and cache topology responses from persisted mesh messages."""

    def __init__(self, repository: MeshRepository) -> None:
        self.repository = repository

    def get_topology(
        self,
        *,
        start_time: str | None = None,
        end_time: str | None = None,
    ) -> MeshTopologyResponse:
        key = (
            id(self.repository.connection),
            self.repository.organization_id,
            self.repository.environment_id,
            start_time,
            end_time,
        )
        cached = _TOPOLOGY_CACHE.get(key)
        now = time.monotonic()
        if cached is not None and cached[0] > now:
            return cached[1].model_copy(update={"cached": True})
        rows = self.repository.list_messages(
            start_time=start_time,
            end_time=end_time,
            limit=1000,
        )
        topology = aggregate_mesh_topology(rows)
        _TOPOLOGY_CACHE[key] = (now + TOPOLOGY_CACHE_TTL_SECONDS, topology)
        return topology


def aggregate_mesh_topology(messages: Iterable[Mapping[str, Any]]) -> MeshTopologyResponse:
    """Aggregate message rows into graph nodes and edges."""

    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[tuple[str, str, str], dict[str, Any]] = {}
    count = 0
    for message in messages:
        count += 1
        source_id = _value(message, "source_agent_id")
        target_id = _value(message, "target_agent_id")
        protocol = _value(message, "protocol")
        decision = str(_value(message, "decision")).lower()
        latency = int(_value(message, "latency_ms") or 0)
        _touch_node(
            nodes,
            source_id,
            name=_value(message, "source_agent_name"),
            status=_value(message, "source_agent_status"),
            trust_tier=_value(message, "source_trust_tier"),
        )
        _touch_node(
            nodes,
            target_id,
            name=_value(message, "target_agent_name"),
            status=_value(message, "target_agent_status"),
            trust_tier=_value(message, "target_trust_tier"),
        )
        nodes[source_id]["message_count"] += 1
        nodes[target_id]["message_count"] += 1
        edge_key = (source_id, target_id, protocol)
        edge = edges.setdefault(
            edge_key,
            {
                "source_agent_id": source_id,
                "target_agent_id": target_id,
                "protocol": protocol,
                "volume": 0,
                "denied_count": 0,
                "latency_total": 0,
            },
        )
        edge["volume"] += 1
        edge["latency_total"] += latency
        if decision in DENIED_DECISIONS:
            edge["denied_count"] += 1
    return MeshTopologyResponse(
        nodes=[
            MeshTopologyNode(**node)
            for node in sorted(nodes.values(), key=lambda item: item["agent_id"])
        ],
        edges=[
            MeshTopologyEdge(
                source_agent_id=edge["source_agent_id"],
                target_agent_id=edge["target_agent_id"],
                protocol=edge["protocol"],
                volume=edge["volume"],
                denied_count=edge["denied_count"],
                deny_rate=edge["denied_count"] / edge["volume"] if edge["volume"] else 0,
                average_latency_ms=edge["latency_total"] / edge["volume"] if edge["volume"] else 0,
            )
            for edge in sorted(edges.values(), key=lambda item: (item["source_agent_id"], item["target_agent_id"], item["protocol"]))
        ],
        message_count=count,
        generated_at=utc_now_iso(),
        cached=False,
    )


def _touch_node(
    nodes: dict[str, dict[str, Any]],
    agent_id: str,
    *,
    name: str | None,
    status: str | None,
    trust_tier: str | None,
) -> None:
    nodes.setdefault(
        agent_id,
        {
            "agent_id": agent_id,
            "name": name,
            "status": status,
            "trust_tier": trust_tier,
            "message_count": 0,
        },
    )


def _value(message: Mapping[str, Any], key: str) -> Any:
    return message[key]
