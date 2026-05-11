"""Shared API response models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DependencyStatus(BaseModel):
    """Health state for a downstream dependency."""

    name: str
    status: str
    required: bool = True
    message: str | None = None


class HealthStatus(BaseModel):
    """Service health payload."""

    status: str
    version: str
    dependencies: list[DependencyStatus] = Field(default_factory=list)
    uptime_seconds: float


class VersionInfo(BaseModel):
    """Version and build metadata."""

    app: str
    version: str
    build_sha: str
    build_time: str
    environment: str


class RequestContext(BaseModel):
    """Per-request metadata shared across handlers and logs."""

    request_id: str
    correlation_id: str
    server_request_id: str | None = None
    organization_id: str | None = None
    environment_id: str | None = None
    user_id: str | None = None
    actor_type: str | None = None


class PublicConfig(BaseModel):
    """Configuration safe for frontend consumption."""

    app_name: str
    environment: str
    api_base_path: str
    docs_url: str | None
    cors_origins: list[str]
    features: dict[str, bool]


class ApiError(BaseModel):
    """Standard API error shape used by later phases."""

    code: str
    message: str
    request_id: str
    details: dict[str, Any] = Field(default_factory=dict)
