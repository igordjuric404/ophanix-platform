"""Dependency health registry for readiness checks."""

from __future__ import annotations

import socket
from collections.abc import Callable
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from product_platform.api.settings import Settings
from product_platform.api.models import DependencyStatus
from product_platform.db.migrator import (
    connect_database,
    database_backend_from_url,
    is_supported_database_url,
)
from product_platform.db.postgres import DatabaseError

DependencyCheck = Callable[[], DependencyStatus]
SettingsProbe = Callable[[Settings], DependencyStatus]


@dataclass(frozen=True)
class RegisteredDependency:
    """Named dependency health check."""

    name: str
    required: bool
    check: DependencyCheck


@dataclass(frozen=True)
class ReadinessProbes:
    """Optional adapter hooks for deterministic readiness checks."""

    database: SettingsProbe | None = None
    redis: SettingsProbe | None = None
    object_storage: SettingsProbe | None = None
    secret_manager: SettingsProbe | None = None
    worker: SettingsProbe | None = None


class DependencyRegistry:
    """Collects dependency health checks and readiness decisions."""

    def __init__(self) -> None:
        self._dependencies: dict[str, RegisteredDependency] = {}

    def register(self, name: str, check: DependencyCheck, *, required: bool = True) -> None:
        self._dependencies[name] = RegisteredDependency(name=name, required=required, check=check)

    def check_all(self) -> list[DependencyStatus]:
        statuses: list[DependencyStatus] = []
        for dependency in self._dependencies.values():
            try:
                status = dependency.check()
            except Exception as exc:
                status = DependencyStatus(
                    name=dependency.name,
                    status="unhealthy",
                    required=dependency.required,
                    message=f"{exc.__class__.__name__}: {exc}",
                )
            statuses.append(
                DependencyStatus(
                    name=status.name or dependency.name,
                    status=status.status,
                    required=dependency.required,
                    message=status.message,
                )
            )
        return statuses

    def readiness_status(self) -> tuple[bool, list[DependencyStatus]]:
        statuses = self.check_all()
        ready = all(
            dependency.status == "healthy"
            for dependency in statuses
            if dependency.required
        )
        return ready, statuses


def static_dependency(
    name: str,
    *,
    status: str = "healthy",
    required: bool = False,
    message: str | None = "Placeholder dependency check.",
) -> DependencyCheck:
    """Create a deterministic dependency check."""

    def check() -> DependencyStatus:
        return DependencyStatus(name=name, status=status, required=required, message=message)

    return check


def create_default_dependency_registry(
    settings: Settings | None = None,
    probes: ReadinessProbes | None = None,
) -> DependencyRegistry:
    """Create dependency checks for the product shell."""

    registry = DependencyRegistry()
    resolved_probes = probes or ReadinessProbes()
    if settings is not None and settings.deployment_mode == "cloud":
        registry.register(
            "database",
            _probe_dependency(
                "database",
                settings,
                resolved_probes.database or _probe_database,
            ),
            required=True,
        )
        registry.register(
            "redis",
            _probe_dependency(
                "redis",
                settings,
                resolved_probes.redis or _probe_redis,
            ),
            required=True,
        )
        registry.register(
            "object_storage",
            _probe_dependency(
                "object_storage",
                settings,
                resolved_probes.object_storage or _probe_object_storage,
            ),
            required=True,
        )
        registry.register(
            "secret_manager",
            _probe_dependency(
                "secret_manager",
                settings,
                resolved_probes.secret_manager or _probe_secret_manager,
            ),
            required=True,
        )
        registry.register(
            "worker",
            _probe_dependency("worker", settings, resolved_probes.worker or _probe_worker),
            required=True,
        )
        return registry
    resolved_settings = settings or Settings()
    local_dependencies: tuple[tuple[str, SettingsProbe, bool], ...] = (
        ("database", resolved_probes.database or _probe_database, True),
        ("redis", resolved_probes.redis or _probe_local_redis, False),
        ("worker", resolved_probes.worker or _probe_worker, True),
        ("event_store", _probe_event_store, True),
        ("model_provider", _probe_model_provider, False),
    )
    for name, probe, required in local_dependencies:
        registry.register(
            name,
            _with_forced_failure(
                name,
                resolved_settings,
                _probe_dependency(name, resolved_settings, probe),
            ),
            required=required,
        )
    return registry


def _configured_dependency(
    name: str,
    configured: bool,
    healthy_message: str,
    unhealthy_message: str,
) -> DependencyCheck:
    def check() -> DependencyStatus:
        return DependencyStatus(
            name=name,
            status="healthy" if configured else "unhealthy",
            required=True,
            message=healthy_message if configured else unhealthy_message,
        )

    return check


def _probe_dependency(name: str, settings: Settings, probe: SettingsProbe) -> DependencyCheck:
    def check() -> DependencyStatus:
        status = probe(settings)
        return DependencyStatus(
            name=status.name or name,
            status=status.status,
            required=True,
            message=status.message,
        )

    return check


def _with_forced_failure(
    name: str,
    settings: Settings,
    check: DependencyCheck,
) -> DependencyCheck:
    break_names = {value.lower() for value in settings.system_dependency_breaks}

    def wrapped() -> DependencyStatus:
        if name.lower() in break_names or "*" in break_names:
            return DependencyStatus(
                name=name,
                status="unhealthy",
                message=(
                    f"{name} was intentionally broken via "
                    "OPHANIX_SYSTEM_DEPENDENCY_BREAKS for local verification."
                ),
            )
        return check()

    return wrapped


def _probe_database(settings: Settings) -> DependencyStatus:
    if not is_supported_database_url(settings.database_url):
        return DependencyStatus(
            name="database",
            status="unhealthy",
            required=True,
            message="OPHANIX_DATABASE_URL must be a postgresql:// URL.",
        )
    backend = database_backend_from_url(settings.database_url)
    try:
        connection = connect_database(settings.database_url)
        try:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM schema_migrations"
            ).fetchone()
        finally:
            connection.close()
    except DatabaseError as exc:
        return DependencyStatus(
            name="database",
            status="unhealthy",
            required=True,
            message=f"{backend} database is not ready or migrations are missing: {exc}",
        )
    return DependencyStatus(
        name="database",
        status="healthy",
        required=True,
        message=f"{backend} database is reachable with {row['count']} applied migrations.",
    )


def _probe_redis(settings: Settings) -> DependencyStatus:
    if not settings.redis_url:
        return DependencyStatus(
            name="redis",
            status="unhealthy",
            required=True,
            message="OPHANIX_REDIS_URL is required in cloud mode.",
        )
    parsed = urlparse(settings.redis_url)
    if parsed.scheme not in {"redis", "rediss"} or not parsed.hostname:
        return DependencyStatus(
            name="redis",
            status="unhealthy",
            required=True,
            message="OPHANIX_REDIS_URL must be a redis:// or rediss:// URL.",
        )
    port = parsed.port or 6379
    try:
        with socket.create_connection((parsed.hostname, port), timeout=0.5):
            pass
    except OSError as exc:
        return DependencyStatus(
            name="redis",
            status="unhealthy",
            required=True,
            message=f"Redis endpoint is not reachable: {exc}",
        )
    return DependencyStatus(
        name="redis",
        status="healthy",
        required=True,
        message="Redis endpoint accepted a TCP connection.",
    )


def _probe_local_redis(settings: Settings) -> DependencyStatus:
    if not settings.redis_url:
        return DependencyStatus(
            name="redis",
            status="not_configured",
            required=False,
            message="OPHANIX_REDIS_URL is not configured for this local run.",
        )
    status = _probe_redis(settings)
    return DependencyStatus(
        name="redis",
        status=status.status,
        required=False,
        message=status.message,
    )


def _probe_object_storage(settings: Settings) -> DependencyStatus:
    if not settings.object_storage_bucket:
        return DependencyStatus(
            name="object_storage",
            status="unhealthy",
            required=True,
            message="OPHANIX_OBJECT_STORAGE_BUCKET is required in cloud mode.",
        )
    if not settings.object_storage_endpoint:
        return DependencyStatus(
            name="object_storage",
            status="unchecked",
            required=True,
            message="Object storage bucket is configured, but no endpoint was provided for a reachability probe.",
        )
    parsed = urlparse(settings.object_storage_endpoint)
    if parsed.scheme == "file":
        return _probe_file_path("object_storage", parsed.path, "Object storage path is readable.")
    if parsed.scheme not in {"http", "https"}:
        return DependencyStatus(
            name="object_storage",
            status="unchecked",
            required=True,
            message="Object storage endpoint scheme has no built-in readiness probe.",
        )
    request = Request(settings.object_storage_endpoint, method="HEAD")
    try:
        with urlopen(request, timeout=1):
            pass
    except HTTPError as exc:
        if exc.code < 500:
            return DependencyStatus(
                name="object_storage",
                status="healthy",
                required=True,
                message=f"Object storage endpoint responded with HTTP {exc.code}.",
            )
        return DependencyStatus(
            name="object_storage",
            status="unhealthy",
            required=True,
            message=f"Object storage endpoint returned HTTP {exc.code}.",
        )
    except (OSError, URLError) as exc:
        return DependencyStatus(
            name="object_storage",
            status="unhealthy",
            required=True,
            message=f"Object storage endpoint is not reachable: {exc}",
        )
    return DependencyStatus(
        name="object_storage",
        status="healthy",
        required=True,
        message="Object storage endpoint responded to a HEAD probe.",
    )


def _probe_secret_manager(settings: Settings) -> DependencyStatus:
    if not settings.secret_manager_ref:
        return DependencyStatus(
            name="secret_manager",
            status="unhealthy",
            required=True,
            message="OPHANIX_SECRET_MANAGER_REF is required in cloud mode.",
        )
    parsed = urlparse(settings.secret_manager_ref)
    if parsed.scheme == "file":
        return _probe_file_path("secret_manager", parsed.path, "Secret manager reference is readable.")
    return DependencyStatus(
        name="secret_manager",
        status="unchecked",
        required=True,
        message="Secret manager reference is configured, but no probe adapter is available for this provider.",
    )


def _probe_worker(settings: Settings) -> DependencyStatus:
    return DependencyStatus(
        name="worker",
        status="healthy",
        required=True,
        message="Worker readiness is covered by the worker no-op smoke command.",
    )


def _probe_event_store(settings: Settings) -> DependencyStatus:
    try:
        connection = connect_database(settings.database_url)
        try:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM audit_events"
            ).fetchone()
        finally:
            connection.close()
    except DatabaseError as exc:
        return DependencyStatus(
            name="event_store",
            status="unhealthy",
            required=True,
            message=f"Audit event store is not ready: {exc}",
        )
    return DependencyStatus(
        name="event_store",
        status="healthy",
        required=True,
        message=f"Audit event store is ready with {row['count']} stored events.",
    )


def _probe_model_provider(settings: Settings) -> DependencyStatus:
    try:
        connection = connect_database(settings.database_url)
        try:
            row = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM provider_credentials
                WHERE provider_type = ? AND status = ?
                """,
                ("model_provider", "active"),
            ).fetchone()
        finally:
            connection.close()
    except DatabaseError as exc:
        return DependencyStatus(
            name="model_provider",
            status="not_configured",
            required=False,
            message=f"Model provider credential store is not ready: {exc}",
        )
    count = int(row["count"])
    if count == 0:
        return DependencyStatus(
            name="model_provider",
            status="not_configured",
            required=False,
            message="No active model provider credential is configured.",
        )
    return DependencyStatus(
        name="model_provider",
        status="healthy",
        required=False,
        message=f"{count} active model provider credential(s) configured.",
    )


def _probe_file_path(name: str, path: str, healthy_message: str) -> DependencyStatus:
    if not path:
        return DependencyStatus(
            name=name,
            status="unhealthy",
            required=True,
            message=f"{name} file path is empty.",
        )
    try:
        with open(path, "rb"):
            pass
    except OSError as exc:
        return DependencyStatus(
            name=name,
            status="unhealthy",
            required=True,
            message=f"{name} file path is not readable: {exc}",
        )
    return DependencyStatus(
        name=name,
        status="healthy",
        required=True,
        message=healthy_message,
    )
