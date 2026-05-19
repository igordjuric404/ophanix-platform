"""W3C trace-context parsing and serialization helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import uuid4

TRACEPARENT_PATTERN = re.compile(
    r"^(?P<version>[0-9a-f]{2})-"
    r"(?P<trace_id>[0-9a-f]{32})-"
    r"(?P<span_id>[0-9a-f]{16})-"
    r"(?P<trace_flags>[0-9a-f]{2})$"
)
MAX_TRACESTATE_LENGTH = 512
MAX_BAGGAGE_LENGTH = 2048


@dataclass(frozen=True)
class TraceContext:
    """Normalized trace context for one server-side request span."""

    trace_id: str
    span_id: str
    parent_span_id: str | None
    traceparent: str
    tracestate: str | None = None
    baggage: str | None = None


def build_request_trace_context(
    *,
    traceparent: str | None,
    tracestate: str | None = None,
    baggage: str | None = None,
) -> TraceContext:
    """Build a server span context from inbound W3C trace headers."""

    parsed = parse_traceparent(traceparent)
    if parsed is None:
        trace_id = _new_trace_id()
        parent_span_id = None
        trace_flags = "01"
    else:
        trace_id, parent_span_id, trace_flags = parsed
    span_id = _new_span_id()
    normalized_traceparent = serialize_traceparent(
        trace_id=trace_id,
        span_id=span_id,
        trace_flags=trace_flags,
    )
    return TraceContext(
        trace_id=trace_id,
        span_id=span_id,
        parent_span_id=parent_span_id,
        traceparent=normalized_traceparent,
        tracestate=sanitize_tracestate(tracestate),
        baggage=sanitize_baggage(baggage),
    )


def parse_traceparent(value: str | None) -> tuple[str, str, str] | None:
    """Return trace ID, parent span ID, and flags from a W3C traceparent header."""

    if value is None:
        return None
    match = TRACEPARENT_PATTERN.fullmatch(value.strip())
    if match is None or match.group("version") != "00":
        return None
    trace_id = match.group("trace_id")
    span_id = match.group("span_id")
    trace_flags = match.group("trace_flags")
    if trace_id == "0" * 32 or span_id == "0" * 16:
        return None
    return trace_id, span_id, trace_flags


def serialize_traceparent(
    *,
    trace_id: str,
    span_id: str,
    trace_flags: str = "01",
) -> str:
    """Serialize a W3C traceparent header for the current span."""

    return f"00-{trace_id}-{span_id}-{trace_flags}"


def sanitize_tracestate(value: str | None) -> str | None:
    """Normalize a tracestate header value for persistence and propagation."""

    return _sanitize_header_value(value, max_length=MAX_TRACESTATE_LENGTH)


def sanitize_baggage(value: str | None) -> str | None:
    """Normalize a baggage header value for persistence and propagation."""

    return _sanitize_header_value(value, max_length=MAX_BAGGAGE_LENGTH)


def _sanitize_header_value(value: str | None, *, max_length: int) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped or len(stripped) > max_length:
        return None
    if any(ord(character) < 32 or ord(character) == 127 for character in stripped):
        return None
    return stripped


def _new_trace_id() -> str:
    return uuid4().hex


def _new_span_id() -> str:
    return uuid4().hex[:16]
