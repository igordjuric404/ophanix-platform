"""Product wrapper around the agent-discovery scanner registry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agent_discovery.scanners.base import registry as agent_discovery_registry

# Import modules for registration side effects.
from agent_discovery.scanners import config as _config_scanner  # noqa: F401
from agent_discovery.scanners import github as _github_scanner  # noqa: F401
from agent_discovery.scanners import process as _process_scanner  # noqa: F401

from product_platform.discovery.models import DiscoveryScannerResponse


@dataclass(frozen=True)
class ScannerConfigContract:
    """Product-level metadata for scanner configuration."""

    required: list[str]
    optional: list[str]
    schema: dict[str, Any]


CONFIG_CONTRACTS: dict[str, ScannerConfigContract] = {
    "process": ScannerConfigContract(
        required=[],
        optional=["include_command_line"],
        schema={"type": "object", "properties": {"include_command_line": {"type": "boolean"}}},
    ),
    "config": ScannerConfigContract(
        required=["paths"],
        optional=["max_depth"],
        schema={
            "type": "object",
            "required": ["paths"],
            "properties": {
                "paths": {"type": "array", "items": {"type": "string"}},
                "max_depth": {"type": "integer", "minimum": 1, "default": 10},
            },
        },
    ),
    "github": ScannerConfigContract(
        required=["repos", "org"],
        optional=["token_ref"],
        schema={
            "type": "object",
            "anyOf": [{"required": ["repos"]}, {"required": ["org"]}],
            "properties": {
                "repos": {"type": "array", "items": {"type": "string"}},
                "org": {"type": "string"},
                "token_ref": {"type": "string"},
            },
        },
    ),
}


class DiscoveryScannerRegistry:
    """Lists and validates built-in discovery scanners."""

    def __init__(self, scanner_registry: Any = agent_discovery_registry) -> None:
        self.scanner_registry = scanner_registry

    @classmethod
    def default(cls) -> "DiscoveryScannerRegistry":
        return cls()

    def list_scanners(self) -> list[DiscoveryScannerResponse]:
        scanners: list[DiscoveryScannerResponse] = []
        for scanner_name in self.scanner_registry.list_scanners():
            scanner = self.scanner_registry.get(scanner_name)
            if scanner is None:
                continue
            contract = CONFIG_CONTRACTS.get(
                scanner.name,
                ScannerConfigContract(required=[], optional=[], schema={}),
            )
            scanners.append(
                DiscoveryScannerResponse(
                    id=f"scanner_{scanner.name}",
                    scanner_type=scanner.name,
                    name=_display_name(scanner.name),
                    description=scanner.description,
                    status="available",
                    available=True,
                    required_config=contract.required,
                    optional_config=contract.optional,
                    config_schema=contract.schema,
                )
            )
        return sorted(scanners, key=lambda scanner: scanner.scanner_type)

    def validate_config(self, scanner_type: str, config: dict[str, Any]) -> list[str]:
        scanner = self.scanner_registry.get(scanner_type)
        if scanner is None:
            return [f"Unknown scanner type: {scanner_type}"]
        return scanner.validate_config(**config)


def _display_name(scanner_type: str) -> str:
    return {
        "process": "Process Scanner",
        "config": "Config Scanner",
        "github": "GitHub Scanner",
    }.get(scanner_type, scanner_type.replace("_", " ").title())
