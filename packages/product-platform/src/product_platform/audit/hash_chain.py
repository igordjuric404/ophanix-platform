"""Tamper-evident hash chain for audit events."""

from __future__ import annotations

import hashlib
import hmac
import json
from pydantic import BaseModel

from product_platform.audit.events import AuditEventEnvelope

HASH_ALGORITHM = "sha256"
CHECKPOINT_SIGNATURE_ALGORITHM = "hmac-sha256"
DEFAULT_CHECKPOINT_SIGNING_KEY = "ophanix-local-audit-checkpoint-v1"


class AuditVerificationResult(BaseModel):
    """Verification result for one event or a range."""

    valid: bool
    checked_count: int
    failed_event_id: str | None = None
    reason: str | None = None
    checkpoint_id: str | None = None


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


def canonical_checkpoint_signature_input(proof: dict[str, object]) -> str:
    """Return stable JSON used as checkpoint signature input."""

    return json.dumps(proof, sort_keys=True, separators=(",", ":"))


def sign_checkpoint_proof(
    proof: dict[str, object],
    signing_key: str | None = None,
) -> str:
    """Sign a checkpoint proof with a local HMAC key."""

    key = signing_key or DEFAULT_CHECKPOINT_SIGNING_KEY
    return hmac.new(
        key.encode("utf-8"),
        canonical_checkpoint_signature_input(proof).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
