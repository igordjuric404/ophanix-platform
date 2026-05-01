"""Deterministic sample plugin manifests for demos and tests."""

from __future__ import annotations

from typing import Any


def sample_plugin_manifests() -> list[dict[str, Any]]:
    """Return two stable sample manifests used by marketplace validation."""

    return [
        {
            "name": "support-triage-assistant",
            "version": "1.0.0",
            "description": "Routes support requests to governed support agents.",
            "author": "Ophanix Labs",
            "plugin_type": "agent",
            "capabilities": ["tickets:read", "tickets:route"],
            "permissions": ["agent.invoke", "audit.write"],
            "package_ref": "local://plugins/support-triage-assistant/1.0.0",
            "signature": "demo-signature",
        },
        {
            "name": "unsigned-data-exporter",
            "version": "0.9.0",
            "description": "Demo exporter used to verify unsigned install blocking.",
            "author": "Example Integrations",
            "plugin_type": "integration",
            "capabilities": ["data:export"],
            "permissions": ["storage.write"],
            "package_ref": "local://plugins/unsigned-data-exporter/0.9.0",
        },
    ]
