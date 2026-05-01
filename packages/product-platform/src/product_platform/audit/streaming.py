"""Server-sent event formatting for audit events."""

from __future__ import annotations

import json

from product_platform.audit.events import AuditEventEnvelope


def format_sse_event(event: AuditEventEnvelope) -> str:
    """Format one audit event as a server-sent event."""

    data = json.dumps(event.model_dump(mode="json"), sort_keys=True)
    return f"id: {event.id}\nevent: audit_event\ndata: {data}\n\n"

