"""Protocol bridge runtime health helpers."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class ProtocolBridgeHealthResult:
    """Result from an honest bridge health probe."""

    status: str
    latency_ms: int
    message: str


class ProtocolBridgeHealthAdapter:
    """Evaluate bridge configuration without claiming full runtime transport health."""

    def check(self, bridge: Mapping[str, Any]) -> ProtocolBridgeHealthResult:
        """Return a deterministic health result for a configured bridge."""

        started = time.monotonic()
        bridge_type = str(_bridge_value(bridge, "bridge_type", "")).lower()
        bridge_status = str(_bridge_value(bridge, "status", "")).lower()
        config = _parse_config_json(_bridge_value(bridge, "config_json", "{}"))
        if bridge_status == "disabled":
            return ProtocolBridgeHealthResult(
                status="disabled",
                latency_ms=_elapsed_ms(started),
                message="Bridge is disabled; runtime check was not attempted.",
            )
        endpoint = str(config.get("endpoint") or config.get("url") or "").strip()
        if bridge_type in {"a2a", "mcp", "custom"} and not endpoint:
            return ProtocolBridgeHealthResult(
                status="error",
                latency_ms=_elapsed_ms(started),
                message=(
                    f"{bridge_type.upper()} bridge config is missing an endpoint; "
                    "runtime protocol capability remains limited."
                ),
            )
        return ProtocolBridgeHealthResult(
            status="limited",
            latency_ms=_elapsed_ms(started),
            message=(
                f"{bridge_type.upper()} bridge configuration is present, but AgentMesh "
                "bridge methods are placeholder/pass-through implementations; "
                "runtime delivery is limited and not reported as healthy."
            ),
        )


def _parse_config_json(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or not value:
        return {}
    parsed = json.loads(value)
    return parsed if isinstance(parsed, dict) else {}


def _bridge_value(bridge: Mapping[str, Any], key: str, default: object) -> object:
    if hasattr(bridge, "get"):
        return bridge.get(key, default)
    try:
        return bridge[key]
    except (KeyError, IndexError):
        return default


def _elapsed_ms(started: float) -> int:
    return max(0, int(round((time.monotonic() - started) * 1000)))
