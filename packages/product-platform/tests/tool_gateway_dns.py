from __future__ import annotations

import socket
from unittest.mock import patch


def patch_public_dns_resolution():
    """Keep synthetic upstream host tests independent from ambient DNS."""

    return patch(
        "product_platform.tool_gateway.models.socket.getaddrinfo",
        return_value=[
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                6,
                "",
                ("93.184.216.34", 443),
            )
        ],
    )
