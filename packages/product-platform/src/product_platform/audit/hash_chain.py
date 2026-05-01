"""Tamper-evident hash chain for audit events."""

from __future__ import annotations

import hashlib
import json
from pydantic import BaseModel

from product_platform.audit.events import AuditEventEnvelope

HASH_ALGORITHM = "sha256"


class AuditVerificationResult(BaseModel):
    """Verification result for one event or a range."""

    valid: bool
    checked_count: int
    failed_event_id: str | None = None
    reason: str | None = None


def canonical_event_hash_input(
    event: AuditEventEnvelope,
    previous_hash: str | None,
) -> str:
    """Return stable JSON used as hash input."""

    return json.dumps(
        {
            "event": event.model_dump(mode="json"),
            "previous_hash": previous_hash,
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def calculate_event_hash(event: AuditEventEnvelope, previous_hash: str | None) -> str:
    """Calculate the current hash for an event."""

    return hashlib.sha256(canonical_event_hash_input(event, previous_hash).encode()).hexdigest()

