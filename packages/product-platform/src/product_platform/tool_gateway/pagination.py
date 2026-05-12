"""Signed cursor helpers for Tool Gateway discovery pagination."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class GatewayToolCursor:
    """Decoded cursor state for snapshot discovery scans."""

    snapshot_before: str
    last_updated_at: str | None
    last_id: str | None
    owner_team: str | None


def encode_gateway_tool_cursor(cursor: GatewayToolCursor, *, secret: str) -> str:
    """Encode and sign a cursor token."""

    payload = {
        "v": 1,
        "snapshot_before": cursor.snapshot_before,
        "last_updated_at": cursor.last_updated_at,
        "last_id": cursor.last_id,
        "owner_team": cursor.owner_team,
    }
    payload_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    payload_part = _base64url(payload_bytes)
    signature_part = _base64url(
        hmac.new(secret.encode("utf-8"), payload_part.encode("ascii"), hashlib.sha256).digest()
    )
    return f"{payload_part}.{signature_part}"


def decode_gateway_tool_cursor(token: str, *, secret: str) -> GatewayToolCursor:
    """Decode and verify a signed cursor token."""

    try:
        payload_part, signature_part = token.split(".", 1)
    except ValueError as exc:
        raise ValueError("Invalid discovery cursor.") from exc
    expected = _base64url(
        hmac.new(secret.encode("utf-8"), payload_part.encode("ascii"), hashlib.sha256).digest()
    )
    if not hmac.compare_digest(signature_part, expected):
        raise ValueError("Invalid discovery cursor.")
    try:
        payload = json.loads(_base64url_decode(payload_part).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid discovery cursor.") from exc
    if not isinstance(payload, dict) or payload.get("v") != 1:
        raise ValueError("Invalid discovery cursor.")
    snapshot_before = _required_str(payload.get("snapshot_before"))
    last_updated_at = _optional_str(payload.get("last_updated_at"))
    last_id = _optional_str(payload.get("last_id"))
    owner_team = _optional_str(payload.get("owner_team"))
    if (last_updated_at is None) != (last_id is None):
        raise ValueError("Invalid discovery cursor.")
    return GatewayToolCursor(
        snapshot_before=snapshot_before,
        last_updated_at=last_updated_at,
        last_id=last_id,
        owner_team=owner_team,
    )


def _required_str(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Invalid discovery cursor.")
    return value


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Invalid discovery cursor.")
    stripped = value.strip()
    return stripped or None


def _base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _base64url_decode(value: str) -> bytes:
    padding = "=" * ((4 - len(value) % 4) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))
