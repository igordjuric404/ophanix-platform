"""Time helpers for database records."""

from __future__ import annotations

from datetime import datetime, timezone


def utc_now_iso() -> str:
    """Return a timezone-aware UTC timestamp string."""

    return datetime.now(timezone.utc).isoformat()

