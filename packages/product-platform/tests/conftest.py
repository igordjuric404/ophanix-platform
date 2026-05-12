from __future__ import annotations

import os
import socket

import pytest


def pytest_configure() -> None:
    """Give model validators a deterministic test environment."""

    os.environ.setdefault("OPHANIX_ENVIRONMENT", "test")


@pytest.fixture(autouse=True)
def _resolve_demo_upstream_hosts(monkeypatch: pytest.MonkeyPatch) -> None:
    """Resolve reserved demo hostnames without enabling unresolved-host bypass."""

    import product_platform.tool_gateway.models as gateway_models

    original_getaddrinfo = gateway_models.socket.getaddrinfo

    def getaddrinfo(host: str, port: object, *args: object, **kwargs: object) -> object:
        normalized = str(host).strip().lower().rstrip(".")
        if normalized.endswith(".internal.example") or normalized.endswith(".example.invalid"):
            return [
                (
                    socket.AF_INET,
                    socket.SOCK_STREAM,
                    6,
                    "",
                    ("93.184.216.34", int(port or 443)),
                )
            ]
        return original_getaddrinfo(host, port, *args, **kwargs)

    monkeypatch.setattr(gateway_models.socket, "getaddrinfo", getaddrinfo)
