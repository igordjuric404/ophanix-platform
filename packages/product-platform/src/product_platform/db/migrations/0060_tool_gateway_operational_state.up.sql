CREATE TABLE IF NOT EXISTS tool_gateway_rate_limit_windows (
    key_hash TEXT PRIMARY KEY,
    window_started_at_epoch DOUBLE PRECISION NOT NULL,
    request_count INTEGER NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tool_gateway_rate_limit_windows_updated
    ON tool_gateway_rate_limit_windows (updated_at);

CREATE TABLE IF NOT EXISTS tool_gateway_circuit_breaker_state (
    target_id TEXT PRIMARY KEY,
    failure_count INTEGER NOT NULL,
    opened_until_epoch DOUBLE PRECISION NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tool_gateway_circuit_breaker_state_opened
    ON tool_gateway_circuit_breaker_state (opened_until_epoch);
