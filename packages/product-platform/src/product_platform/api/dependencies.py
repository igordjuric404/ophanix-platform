"""Dependency health registry for readiness checks."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from product_platform.api.models import DependencyStatus

DependencyCheck = Callable[[], DependencyStatus]


@dataclass(frozen=True)
class RegisteredDependency:
    """Named dependency health check."""

    name: str
    required: bool
    check: DependencyCheck


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


def create_default_dependency_registry() -> DependencyRegistry:
    """Create placeholder dependency checks for the product shell."""

    registry = DependencyRegistry()
    for name in ("database", "redis", "worker", "event_store", "model_provider"):
        registry.register(name, static_dependency(name, required=False), required=False)
    return registry

