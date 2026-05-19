DROP INDEX IF EXISTS idx_background_jobs_trace_created;
DROP INDEX IF EXISTS idx_mcp_tool_calls_trace_created;
DROP INDEX IF EXISTS idx_tool_runtime_actions_trace_created;
DROP INDEX IF EXISTS idx_runtime_actions_trace_created;
DROP INDEX IF EXISTS idx_runtime_sessions_trace_created;

ALTER TABLE background_jobs DROP COLUMN IF EXISTS baggage;
ALTER TABLE background_jobs DROP COLUMN IF EXISTS tracestate;
ALTER TABLE background_jobs DROP COLUMN IF EXISTS traceparent;
ALTER TABLE background_jobs DROP COLUMN IF EXISTS parent_span_id;
ALTER TABLE background_jobs DROP COLUMN IF EXISTS span_id;
ALTER TABLE background_jobs DROP COLUMN IF EXISTS trace_id;

ALTER TABLE mcp_tool_calls DROP COLUMN IF EXISTS baggage;
ALTER TABLE mcp_tool_calls DROP COLUMN IF EXISTS tracestate;
ALTER TABLE mcp_tool_calls DROP COLUMN IF EXISTS traceparent;
ALTER TABLE mcp_tool_calls DROP COLUMN IF EXISTS parent_span_id;
ALTER TABLE mcp_tool_calls DROP COLUMN IF EXISTS span_id;
ALTER TABLE mcp_tool_calls DROP COLUMN IF EXISTS trace_id;

ALTER TABLE tool_runtime_actions DROP COLUMN IF EXISTS baggage;
ALTER TABLE tool_runtime_actions DROP COLUMN IF EXISTS tracestate;
ALTER TABLE tool_runtime_actions DROP COLUMN IF EXISTS traceparent;
ALTER TABLE tool_runtime_actions DROP COLUMN IF EXISTS parent_span_id;
ALTER TABLE tool_runtime_actions DROP COLUMN IF EXISTS span_id;
ALTER TABLE tool_runtime_actions DROP COLUMN IF EXISTS trace_id;

ALTER TABLE runtime_actions DROP COLUMN IF EXISTS baggage;
ALTER TABLE runtime_actions DROP COLUMN IF EXISTS tracestate;
ALTER TABLE runtime_actions DROP COLUMN IF EXISTS traceparent;
ALTER TABLE runtime_actions DROP COLUMN IF EXISTS parent_span_id;
ALTER TABLE runtime_actions DROP COLUMN IF EXISTS span_id;
ALTER TABLE runtime_actions DROP COLUMN IF EXISTS trace_id;

ALTER TABLE runtime_sessions DROP COLUMN IF EXISTS baggage;
ALTER TABLE runtime_sessions DROP COLUMN IF EXISTS tracestate;
ALTER TABLE runtime_sessions DROP COLUMN IF EXISTS traceparent;
ALTER TABLE runtime_sessions DROP COLUMN IF EXISTS parent_span_id;
ALTER TABLE runtime_sessions DROP COLUMN IF EXISTS span_id;
ALTER TABLE runtime_sessions DROP COLUMN IF EXISTS trace_id;

DELETE FROM schema_migrations WHERE version = '0080';
