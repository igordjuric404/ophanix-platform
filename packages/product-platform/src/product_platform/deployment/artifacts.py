"""Artifact storage adapters used by deployment smoke tests."""

from __future__ import annotations

from pathlib import Path


class LocalArtifactStore:
    """Filesystem-backed object storage adapter for deterministic tests."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def upload(self, key: str, data: bytes) -> str:
        path = self._path_for_key(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    def download(self, key: str) -> bytes:
        return self._path_for_key(key).read_bytes()

    def _path_for_key(self, key: str) -> Path:
        normalized = key.strip().lstrip("/")
        if not normalized or ".." in Path(normalized).parts:
            raise ValueError("Artifact key must be a relative path.")
        return self.root / normalized
