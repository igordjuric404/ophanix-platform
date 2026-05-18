"""Runtime settings for the product API."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

DEFAULT_POSTGRES_URL = "postgresql://ophanix:ophanix-local@127.0.0.1:5432/ophanix_product"


def _csv_env(name: str, default: str) -> list[str]:
    raw = os.environ.get(name, default)
    return [value.strip() for value in raw.split(",") if value.strip()]


def _dev_login_allowed_emails() -> list[str]:
    values = _csv_env("OPHANIX_DEV_LOGIN_ALLOWED_EMAILS", "admin@example.com")
    if "admin@example.com" not in {value.lower() for value in values}:
        values.insert(0, "admin@example.com")
    return values


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _environment_is_local() -> bool:
    return os.environ.get("OPHANIX_ENVIRONMENT", "development").strip().lower() in {
        "development",
        "dev",
        "local",
        "local-demo",
        "test",
    }


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return int(raw.strip())


@dataclass(frozen=True)
class Settings:
    """Settings loaded from environment variables.

    This intentionally avoids `pydantic-settings` because it is not available in
    the current workspace, while still keeping a typed configuration object.
    """

    app_name: str = field(default_factory=lambda: os.environ.get("OPHANIX_APP_NAME", "Ophanix Product Platform"))
    environment: str = field(default_factory=lambda: os.environ.get("OPHANIX_ENVIRONMENT", "development"))
    build_sha: str = field(default_factory=lambda: os.environ.get("OPHANIX_BUILD_SHA", "local"))
    build_time: str = field(default_factory=lambda: os.environ.get("OPHANIX_BUILD_TIME", "local"))
    api_base_path: str = "/api/v1"
    default_organization_id: str = field(
        default_factory=lambda: os.environ.get("OPHANIX_DEFAULT_ORGANIZATION_ID", "org_default")
    )
    database_url: str = field(
        default_factory=lambda: os.environ.get("OPHANIX_DATABASE_URL", DEFAULT_POSTGRES_URL)
    )
    database_max_pool_size: int = field(
        default_factory=lambda: _int_env("OPHANIX_DATABASE_MAX_POOL_SIZE", 5)
    )
    dev_login_allowed_emails: list[str] = field(
        default_factory=_dev_login_allowed_emails
    )
    session_secret: str = field(default_factory=lambda: os.environ.get("OPHANIX_SESSION_SECRET", "dev-secret-change-me"))
    session_ttl_seconds: int = field(
        default_factory=lambda: int(os.environ.get("OPHANIX_SESSION_TTL_SECONDS", "28800"))
    )
    cors_origins: list[str] = field(
        default_factory=lambda: _csv_env(
            "CORS_ALLOWED_ORIGINS",
            "http://localhost:3000,http://localhost:5173,http://localhost:8080",
        )
    )
    enable_api_docs: bool | None = field(
        default_factory=lambda: (
            _bool_env("OPHANIX_ENABLE_API_DOCS")
            if os.environ.get("OPHANIX_ENABLE_API_DOCS") is not None
            else None
        )
    )
    enable_dev_login: bool | None = field(
        default_factory=lambda: (
            _bool_env("OPHANIX_ENABLE_DEV_LOGIN")
            if os.environ.get("OPHANIX_ENABLE_DEV_LOGIN") is not None
            else None
        )
    )
    enable_production_chaos: bool = field(
        default_factory=lambda: _bool_env("OPHANIX_ENABLE_PRODUCTION_CHAOS", False)
    )
    deployment_mode: str = field(default_factory=lambda: os.environ.get("OPHANIX_DEPLOYMENT_MODE", "local"))
    redis_url: str | None = field(default_factory=lambda: os.environ.get("OPHANIX_REDIS_URL"))
    object_storage_bucket: str | None = field(
        default_factory=lambda: os.environ.get("OPHANIX_OBJECT_STORAGE_BUCKET")
    )
    object_storage_endpoint: str | None = field(
        default_factory=lambda: os.environ.get("OPHANIX_OBJECT_STORAGE_ENDPOINT")
    )
    artifact_storage_path: str = field(
        default_factory=lambda: os.environ.get("OPHANIX_ARTIFACT_STORAGE_PATH", "/tmp/ophanix-product-artifacts")
    )
    artifact_max_bytes: int = field(
        default_factory=lambda: _int_env("OPHANIX_ARTIFACT_MAX_BYTES", 25_000_000)
    )
    api_max_body_bytes: int = field(
        default_factory=lambda: _int_env("OPHANIX_API_MAX_BODY_BYTES", 35_000_000)
    )
    secret_manager_ref: str | None = field(
        default_factory=lambda: os.environ.get("OPHANIX_SECRET_MANAGER_REF")
    )
    gateway_token_hash_pepper: str | None = field(
        default_factory=lambda: os.environ.get("OPHANIX_GATEWAY_TOKEN_HASH_PEPPER")
    )
    api_key_hash_pepper: str | None = field(
        default_factory=lambda: os.environ.get("OPHANIX_API_KEY_HASH_PEPPER")
    )
    idp_issuer_url: str | None = field(default_factory=lambda: os.environ.get("OPHANIX_IDP_ISSUER_URL"))
    idp_audience: str | None = field(default_factory=lambda: os.environ.get("OPHANIX_IDP_AUDIENCE"))
    tls_certificate_ref: str | None = field(default_factory=lambda: os.environ.get("OPHANIX_TLS_CERTIFICATE_REF"))
    internal_cidrs: list[str] = field(
        default_factory=lambda: _csv_env("OPHANIX_INTERNAL_CIDRS", "10.0.0.0/8")
    )
    system_dependency_breaks: list[str] = field(
        default_factory=lambda: _csv_env("OPHANIX_SYSTEM_DEPENDENCY_BREAKS", "")
    )
    tool_gateway_max_body_bytes: int = field(
        default_factory=lambda: _int_env("OPHANIX_TOOL_GATEWAY_MAX_BODY_BYTES", 1_000_000)
    )
    tool_gateway_rate_limit_window_seconds: int = field(
        default_factory=lambda: _int_env("OPHANIX_TOOL_GATEWAY_RATE_LIMIT_WINDOW_SECONDS", 60)
    )
    tool_gateway_rate_limit_max_requests: int = field(
        default_factory=lambda: _int_env("OPHANIX_TOOL_GATEWAY_RATE_LIMIT_MAX_REQUESTS", 600)
    )
    tool_gateway_rate_limit_max_keys: int = field(
        default_factory=lambda: _int_env("OPHANIX_TOOL_GATEWAY_RATE_LIMIT_MAX_KEYS", 10_000)
    )
    tool_gateway_max_upstream_response_bytes: int = field(
        default_factory=lambda: _int_env("OPHANIX_TOOL_GATEWAY_MAX_UPSTREAM_RESPONSE_BYTES", 1_000_000)
    )
    tool_gateway_circuit_breaker_failure_threshold: int = field(
        default_factory=lambda: _int_env("OPHANIX_TOOL_GATEWAY_CIRCUIT_BREAKER_FAILURE_THRESHOLD", 5)
    )
    tool_gateway_circuit_breaker_cooldown_seconds: int = field(
        default_factory=lambda: _int_env("OPHANIX_TOOL_GATEWAY_CIRCUIT_BREAKER_COOLDOWN_SECONDS", 30)
    )
    tool_gateway_idempotency_in_progress_ttl_seconds: int = field(
        default_factory=lambda: _int_env(
            "OPHANIX_TOOL_GATEWAY_IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS",
            600,
        )
    )
    tool_gateway_idempotency_replay_retention_seconds: int = field(
        default_factory=lambda: _int_env(
            "OPHANIX_TOOL_GATEWAY_IDEMPOTENCY_REPLAY_RETENTION_SECONDS",
            7 * 24 * 60 * 60,
        )
    )
    tool_gateway_upstream_host_allowlist: list[str] = field(
        default_factory=lambda: _csv_env("OPHANIX_TOOL_GATEWAY_UPSTREAM_HOST_ALLOWLIST", "")
    )


def load_settings() -> Settings:
    """Load settings from the current process environment."""

    return Settings()
