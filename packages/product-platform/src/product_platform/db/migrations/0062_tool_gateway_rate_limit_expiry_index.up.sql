CREATE INDEX IF NOT EXISTS idx_tool_gateway_rate_limit_windows_started
    ON tool_gateway_rate_limit_windows (window_started_at_epoch);
