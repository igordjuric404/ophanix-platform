"""Durable operational state for Tool Gateway runtime safeguards."""

from __future__ import annotations

import hashlib
import math
import time
from dataclasses import dataclass
from typing import Any

from product_platform.db.connection import Database
from product_platform.db.postgres import Connection
from product_platform.db.time import utc_now_iso
from product_platform.tool_gateway.invocation import ToolExecutionError


@dataclass(frozen=True)
class ToolGatewayRateLimitResult:
    """Result of a Tool Gateway rate-limit check."""

    limited: bool
    retry_after_seconds: int


def tool_gateway_rate_limit_result(
    connection: Connection,
    *,
    key: str,
    overflow_key: str,
    max_requests: int,
    window_seconds: int,
    max_keys: int,
    now_epoch: float | None = None,
) -> ToolGatewayRateLimitResult:
    """Apply a fixed-window rate limit using shared database state.

    The table stores only a SHA-256 hash of the request bucket, never raw
    Authorization header material. When the key-space cap is reached, new keys
    are folded into a per-client overflow bucket instead of creating unbounded
    rows.
    """

    if max_requests <= 0 or window_seconds <= 0:
        return ToolGatewayRateLimitResult(limited=False, retry_after_seconds=0)
    now = float(time.time() if now_epoch is None else now_epoch)
    cutoff = now - float(window_seconds)
    connection.execute(
        "DELETE FROM tool_gateway_rate_limit_windows WHERE window_started_at_epoch <= ?",
        (cutoff,),
    )
    effective_key = key
    key_hash = _rate_limit_key_hash(effective_key)
    existing = _rate_limit_window(connection, key_hash)
    if existing is None and max_keys > 0:
        count_row = connection.execute(
            "SELECT COUNT(*) AS count FROM tool_gateway_rate_limit_windows",
        ).fetchone()
        if int(count_row["count"] if count_row is not None else 0) >= max_keys:
            effective_key = overflow_key
            key_hash = _rate_limit_key_hash(effective_key)
            existing = _rate_limit_window(connection, key_hash)
    row = connection.execute(
        """
        INSERT INTO tool_gateway_rate_limit_windows (
            key_hash, window_started_at_epoch, request_count, updated_at
        )
        VALUES (?, ?, ?, ?)
        ON CONFLICT (key_hash) DO UPDATE SET
            window_started_at_epoch = CASE
                WHEN tool_gateway_rate_limit_windows.window_started_at_epoch <= ?
                    THEN EXCLUDED.window_started_at_epoch
                ELSE tool_gateway_rate_limit_windows.window_started_at_epoch
            END,
            request_count = CASE
                WHEN tool_gateway_rate_limit_windows.window_started_at_epoch <= ?
                    THEN 1
                ELSE tool_gateway_rate_limit_windows.request_count + 1
            END,
            updated_at = EXCLUDED.updated_at
        RETURNING window_started_at_epoch, request_count
        """,
        (key_hash, now, 1, utc_now_iso(), cutoff, cutoff),
    ).fetchone()
    window_started_at = float(row["window_started_at_epoch"] if row is not None else now)
    request_count = int(row["request_count"] if row is not None else 1)
    retry_after = max(1, int(math.ceil(window_seconds - (now - window_started_at))))
    return ToolGatewayRateLimitResult(
        limited=request_count > max_requests,
        retry_after_seconds=retry_after,
    )


class DatabaseToolGatewayCircuitBreaker:
    """Database-backed circuit breaker shared across app instances."""

    def __init__(
        self,
        database: Database,
        *,
        failure_threshold: int = 5,
        cooldown_seconds: float = 30.0,
        clock: Any | None = None,
    ) -> None:
        if failure_threshold <= 0:
            raise ValueError("failure_threshold must be greater than zero.")
        if cooldown_seconds <= 0:
            raise ValueError("cooldown_seconds must be greater than zero.")
        self.database = database
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self._clock = clock or time.time

    def before_call(self, target_id: str) -> None:
        """Raise when the target circuit is open."""

        now = float(self._clock())
        with self.database.transaction() as connection:
            row = _circuit_breaker_row(connection, target_id)
            if row is None:
                return
            opened_until = float(row["opened_until_epoch"])
            if opened_until > now:
                raise ToolExecutionError(
                    code="upstream_circuit_open",
                    message="Configured upstream target is temporarily unavailable.",
                    status_code=503,
                )
            if opened_until:
                connection.execute(
                    """
                    UPDATE tool_gateway_circuit_breaker_state
                    SET failure_count = 0, opened_until_epoch = 0, updated_at = ?
                    WHERE target_id = ?
                    """,
                    (utc_now_iso(), target_id),
                )

    def record_success(self, target_id: str) -> None:
        """Reset the target circuit after a successful call."""

        with self.database.transaction() as connection:
            connection.execute(
                "DELETE FROM tool_gateway_circuit_breaker_state WHERE target_id = ?",
                (target_id,),
            )

    def record_failure(self, target_id: str) -> None:
        """Count a target failure and open the circuit when the threshold is reached."""

        now = float(self._clock())
        with self.database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO tool_gateway_circuit_breaker_state (
                    target_id, failure_count, opened_until_epoch, updated_at
                )
                VALUES (?, 1, ?, ?)
                ON CONFLICT (target_id) DO UPDATE SET
                    failure_count = CASE
                        WHEN tool_gateway_circuit_breaker_state.opened_until_epoch > ?
                            THEN tool_gateway_circuit_breaker_state.failure_count
                        ELSE tool_gateway_circuit_breaker_state.failure_count + 1
                    END,
                    opened_until_epoch = CASE
                        WHEN tool_gateway_circuit_breaker_state.opened_until_epoch > ?
                            THEN tool_gateway_circuit_breaker_state.opened_until_epoch
                        WHEN tool_gateway_circuit_breaker_state.failure_count + 1 >= ?
                            THEN ?
                        ELSE 0
                    END,
                    updated_at = EXCLUDED.updated_at
                """,
                (
                    target_id,
                    now + self.cooldown_seconds if self.failure_threshold <= 1 else 0.0,
                    utc_now_iso(),
                    now,
                    now,
                    self.failure_threshold,
                    now + self.cooldown_seconds,
                ),
            )


def _rate_limit_key_hash(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _rate_limit_window(connection: Connection, key_hash: str) -> Any | None:
    return connection.execute(
        """
        SELECT key_hash, window_started_at_epoch, request_count
        FROM tool_gateway_rate_limit_windows
        WHERE key_hash = ?
        """,
        (key_hash,),
    ).fetchone()


def _circuit_breaker_row(connection: Connection, target_id: str) -> Any | None:
    return connection.execute(
        """
        SELECT target_id, failure_count, opened_until_epoch
        FROM tool_gateway_circuit_breaker_state
        WHERE target_id = ?
        """,
        (target_id,),
    ).fetchone()
