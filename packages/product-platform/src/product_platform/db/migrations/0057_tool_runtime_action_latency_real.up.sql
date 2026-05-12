ALTER TABLE tool_runtime_actions
    ALTER COLUMN latency_ms TYPE DOUBLE PRECISION
    USING latency_ms::double precision;
