ALTER TABLE tool_runtime_actions
    ALTER COLUMN latency_ms TYPE INTEGER
    USING latency_ms::integer;
