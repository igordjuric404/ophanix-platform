"""Secret-provider adapters used by provider credential APIs."""

from __future__ import annotations

import os
import re
from typing import Protocol

from product_platform.db.ids import generate_id

DEFAULT_ENV_SECRET_PREFIX = "OPHANIX_SECRET_"
ENV_SECRET_MANAGER_REFS = {"env", "environment"}
ENV_SECRET_NAME_PATTERN = re.compile(r"^[A-Z_][A-Z0-9_]{0,255}$")
ENV_SECRET_PREFIX_PATTERN = re.compile(r"^[A-Z_][A-Z0-9_]{0,127}$")
SECRET_REF_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,256}$")


class SecretProvider(Protocol):
    """Store and retrieve secrets by opaque reference."""

    def store(self, secret_value: str) -> str:
        """Store a secret and return an opaque reference."""

    def retrieve(self, secret_ref: str) -> str | None:
        """Retrieve a secret value by reference."""


class DemoLocalSecretProvider:
    """In-memory local secret provider for deterministic tests and demos."""

    def __init__(self) -> None:
        self._secrets: dict[str, str] = {}

    def store(self, secret_value: str) -> str:
        secret_ref = generate_id("secref")
        self._secrets[secret_ref] = secret_value
        return secret_ref

    def retrieve(self, secret_ref: str) -> str | None:
        return self._secrets.get(secret_ref)


class EnvironmentSecretProvider:
    """Read-only provider backed by environment-injected secrets.

    This adapter is intended for production container platforms where the
    orchestrator or managed secret store injects secrets as environment
    variables. It never stores new secret values at runtime.
    """

    def __init__(self, *, prefix: str = DEFAULT_ENV_SECRET_PREFIX) -> None:
        normalized_prefix = prefix.strip().upper()
        if not ENV_SECRET_PREFIX_PATTERN.fullmatch(normalized_prefix):
            raise ValueError("environment secret prefix must be an uppercase environment-variable prefix.")
        self.prefix = normalized_prefix

    def store(self, secret_value: str) -> str:
        raise RuntimeError("EnvironmentSecretProvider is read-only; create secrets in the external secret manager.")

    def retrieve(self, secret_ref: str) -> str | None:
        env_name = self._env_name_for_ref(secret_ref)
        return os.environ.get(env_name)

    def _env_name_for_ref(self, secret_ref: str) -> str:
        stripped = secret_ref.strip()
        if not SECRET_REF_PATTERN.fullmatch(stripped):
            raise ValueError("secret_ref contains unsupported characters.")
        if stripped.startswith("env:"):
            env_name = stripped[4:].strip().upper()
            if not ENV_SECRET_NAME_PATTERN.fullmatch(env_name):
                raise ValueError("env: secret_ref must contain a valid environment variable name.")
            if not env_name.startswith(self.prefix):
                raise ValueError("env: secret_ref must use the configured environment secret prefix.")
            return env_name
        normalized = re.sub(r"[^A-Za-z0-9]", "_", stripped).upper()
        return f"{self.prefix}{normalized}"

    def validate_reference(self, secret_ref: str) -> str:
        """Validate a caller-provided reference and return the environment variable it resolves to."""

        return self._env_name_for_ref(secret_ref)


DEFAULT_SECRET_PROVIDER = DemoLocalSecretProvider()


def is_demo_secret_provider(provider: object) -> bool:
    """Return whether the configured provider is the local in-memory demo provider."""

    return isinstance(provider, DemoLocalSecretProvider)


def is_supported_secret_manager_ref(secret_manager_ref: str | None) -> bool:
    """Return whether the current code can build the referenced provider."""

    if secret_manager_ref is None:
        return False
    normalized = secret_manager_ref.strip().lower()
    return normalized in ENV_SECRET_MANAGER_REFS or normalized.startswith("env:")


def validate_secret_reference_for_provider(secret_ref: str, provider: SecretProvider) -> None:
    """Reject secret references that the configured provider cannot safely resolve."""

    if isinstance(provider, EnvironmentSecretProvider):
        provider.validate_reference(secret_ref)


def build_secret_provider(secret_manager_ref: str | None, *, environment: str) -> SecretProvider:
    """Build the configured secret provider.

    Local/test environments default to the deterministic in-memory provider.
    Non-local deployments must choose an implemented provider explicitly.
    """

    normalized_environment = environment.strip().lower()
    local_environment = normalized_environment in {"development", "dev", "local", "test"}
    if secret_manager_ref is None or not secret_manager_ref.strip():
        if local_environment:
            return DEFAULT_SECRET_PROVIDER
        raise ValueError("OPHANIX_SECRET_MANAGER_REF must be set to a supported provider outside local/test.")
    normalized_ref = secret_manager_ref.strip()
    normalized_lower = normalized_ref.lower()
    if normalized_lower in {"demo", "local"}:
        if local_environment:
            return DEFAULT_SECRET_PROVIDER
        raise ValueError("The demo secret provider is not allowed outside local/test environments.")
    if normalized_lower in ENV_SECRET_MANAGER_REFS:
        return EnvironmentSecretProvider()
    if normalized_lower.startswith("env:"):
        prefix = normalized_ref.split(":", 1)[1].strip() or DEFAULT_ENV_SECRET_PREFIX
        return EnvironmentSecretProvider(prefix=prefix)
    raise ValueError(
        "Unsupported OPHANIX_SECRET_MANAGER_REF. Supported values are 'env' "
        "or 'env:<ENV_VAR_PREFIX>'."
    )
