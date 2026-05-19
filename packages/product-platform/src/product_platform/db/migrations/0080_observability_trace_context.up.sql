ALTER TABLE runtime_sessions ADD COLUMN trace_id TEXT;
ALTER TABLE runtime_sessions ADD COLUMN span_id TEXT;
ALTER TABLE runtime_sessions ADD COLUMN parent_span_id TEXT;
ALTER TABLE runtime_sessions ADD COLUMN traceparent TEXT;
ALTER TABLE runtime_sessions ADD COLUMN tracestate TEXT;
ALTER TABLE runtime_sessions ADD COLUMN baggage TEXT;

ALTER TABLE runtime_actions ADD COLUMN trace_id TEXT;
ALTER TABLE runtime_actions ADD COLUMN span_id TEXT;
ALTER TABLE runtime_actions ADD COLUMN parent_span_id TEXT;
ALTER TABLE runtime_actions ADD COLUMN traceparent TEXT;
ALTER TABLE runtime_actions ADD COLUMN tracestate TEXT;
ALTER TABLE runtime_actions ADD COLUMN baggage TEXT;

ALTER TABLE tool_runtime_actions ADD COLUMN trace_id TEXT;
ALTER TABLE tool_runtime_actions ADD COLUMN span_id TEXT;
ALTER TABLE tool_runtime_actions ADD COLUMN parent_span_id TEXT;
ALTER TABLE tool_runtime_actions ADD COLUMN traceparent TEXT;
ALTER TABLE tool_runtime_actions ADD COLUMN tracestate TEXT;
ALTER TABLE tool_runtime_actions ADD COLUMN baggage TEXT;

ALTER TABLE mcp_tool_calls ADD COLUMN trace_id TEXT;
ALTER TABLE mcp_tool_calls ADD COLUMN span_id TEXT;
ALTER TABLE mcp_tool_calls ADD COLUMN parent_span_id TEXT;
ALTER TABLE mcp_tool_calls ADD COLUMN traceparent TEXT;
ALTER TABLE mcp_tool_calls ADD COLUMN tracestate TEXT;
ALTER TABLE mcp_tool_calls ADD COLUMN baggage TEXT;

ALTER TABLE background_jobs ADD COLUMN trace_id TEXT;
ALTER TABLE background_jobs ADD COLUMN span_id TEXT;
ALTER TABLE background_jobs ADD COLUMN parent_span_id TEXT;
ALTER TABLE background_jobs ADD COLUMN traceparent TEXT;
ALTER TABLE background_jobs ADD COLUMN tracestate TEXT;
ALTER TABLE background_jobs ADD COLUMN baggage TEXT;

CREATE INDEX IF NOT EXISTS idx_runtime_sessions_trace_created
    ON runtime_sessions (trace_id, started_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_runtime_actions_trace_created
    ON runtime_actions (trace_id, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_tool_runtime_actions_trace_created
    ON tool_runtime_actions (trace_id, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_mcp_tool_calls_trace_created
    ON mcp_tool_calls (trace_id, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_background_jobs_trace_created
    ON background_jobs (trace_id, created_at DESC, id DESC);
