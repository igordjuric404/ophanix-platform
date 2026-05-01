"""Demo secret provider used by provider credential APIs."""

from __future__ import annotations

from typing import Protocol

from product_platform.db.ids import generate_id


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


DEFAULT_SECRET_PROVIDER = DemoLocalSecretProvider()
