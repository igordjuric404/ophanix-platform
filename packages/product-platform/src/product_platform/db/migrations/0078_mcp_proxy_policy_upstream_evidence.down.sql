DROP INDEX IF EXISTS idx_mcp_tool_calls_policy_binding;

ALTER TABLE mcp_tool_calls
DROP COLUMN IF EXISTS upstream_response_metadata_json;

ALTER TABLE mcp_tool_calls
DROP COLUMN IF EXISTS upstream_request_json;

ALTER TABLE mcp_tool_calls
DROP COLUMN IF EXISTS policy_input_json;

ALTER TABLE mcp_tool_calls
DROP COLUMN IF EXISTS policy_matched_rule;

ALTER TABLE mcp_tool_calls
DROP COLUMN IF EXISTS policy_reason;

ALTER TABLE mcp_tool_calls
DROP COLUMN IF EXISTS policy_action;

ALTER TABLE mcp_tool_calls
DROP COLUMN IF EXISTS policy_binding_id;

DELETE FROM schema_migrations WHERE version = '0078';
