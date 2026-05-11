"""Compatibility exports for the standalone Tool Gateway SDK package."""

from __future__ import annotations

from ophanix_tool_gateway.sdk import (
    AsyncOphanixToolGatewayClient,
    AsyncTokenProvider,
    EnvironmentTokenProvider,
    GatewayCompatibility,
    OphanixToolGatewayClient,
    SDK_VERSION,
    StaticTokenProvider,
    TokenProvider,
    ToolCallResult,
    ToolGatewayClientConfig,
    ToolAuthenticationError,
    ToolDefinition,
    ToolDeniedError,
    ToolGatewayError,
    ToolGatewayValidationError,
)

__version__ = SDK_VERSION

__all__ = [
    "__version__",
    "AsyncOphanixToolGatewayClient",
    "AsyncTokenProvider",
    "EnvironmentTokenProvider",
    "GatewayCompatibility",
    "OphanixToolGatewayClient",
    "StaticTokenProvider",
    "TokenProvider",
    "ToolCallResult",
    "ToolGatewayClientConfig",
    "ToolAuthenticationError",
    "ToolDefinition",
    "ToolDeniedError",
    "ToolGatewayError",
    "ToolGatewayValidationError",
]
