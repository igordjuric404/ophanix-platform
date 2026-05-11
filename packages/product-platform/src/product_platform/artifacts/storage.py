"""Artifact storage provider implementations."""

from __future__ import annotations

import hashlib
from pathlib import Path


class ArtifactStorageError(ValueError):
    """Raised when artifact storage input is unsafe."""


class LocalArtifactProvider:
    """Filesystem-backed artifact provider with relative-key safety."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def upload(self, key: str, data: bytes) -> str:
        path = self._path_for_key(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return f"local-artifact://{key}"

    def download(self, storage_uri: str) -> bytes:
        key = storage_uri.removeprefix("local-artifact://")
        return self._path_for_key(key).read_bytes()

    def _path_for_key(self, key: str) -> Path:
        normalized = key.strip().lstrip("/")
        path = Path(normalized)
        if not normalized or path.is_absolute() or ".." in path.parts:
            raise ArtifactStorageError("Artifact key must be a safe relative path.")
        resolved = (self.root / path).resolve()
        if self.root not in [resolved, *resolved.parents]:
            raise ArtifactStorageError("Artifact key escapes the artifact root.")
        return resolved


def calculate_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
