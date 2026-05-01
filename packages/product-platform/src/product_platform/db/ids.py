"""ID generation conventions."""

from __future__ import annotations

from uuid import uuid4


def generate_id(prefix: str) -> str:
    """Generate a stable product ID shape: `<prefix>_<32 lowercase hex>`."""

    normalized = prefix.strip().lower().replace("-", "_")
    if not normalized or not normalized.replace("_", "").isalnum():
        raise ValueError("ID prefix must be alphanumeric with optional underscores or hyphens.")
    return f"{normalized}_{uuid4().hex}"

