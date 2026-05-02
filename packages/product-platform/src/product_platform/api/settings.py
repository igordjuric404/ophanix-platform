"""Runtime settings for the product API."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


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
        default_factory=lambda: os.environ.get("OPHANIX_DATABASE_URL", "sqlite:///ophanix_product.db")
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
    secret_manager_ref: str | None = field(
        default_factory=lambda: os.environ.get("OPHANIX_SECRET_MANAGER_REF")
    )
    idp_issuer_url: str | None = field(default_factory=lambda: os.environ.get("OPHANIX_IDP_ISSUER_URL"))
    idp_audience: str | None = field(default_factory=lambda: os.environ.get("OPHANIX_IDP_AUDIENCE"))
    tls_certificate_ref: str | None = field(default_factory=lambda: os.environ.get("OPHANIX_TLS_CERTIFICATE_REF"))
    internal_cidrs: list[str] = field(
        default_factory=lambda: _csv_env("OPHANIX_INTERNAL_CIDRS", "10.0.0.0/8")
    )


def load_settings() -> Settings:
    """Load settings from the current process environment."""

    return Settings()
