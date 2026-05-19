ALTER TABLE mcp_tool_calls ADD COLUMN policy_binding_id TEXT;
ALTER TABLE mcp_tool_calls ADD COLUMN policy_action TEXT;
ALTER TABLE mcp_tool_calls ADD COLUMN policy_reason TEXT;
ALTER TABLE mcp_tool_calls ADD COLUMN policy_matched_rule TEXT;
ALTER TABLE mcp_tool_calls ADD COLUMN policy_input_json TEXT;
ALTER TABLE mcp_tool_calls ADD COLUMN upstream_request_json TEXT;
ALTER TABLE mcp_tool_calls ADD COLUMN upstream_response_metadata_json TEXT;

CREATE INDEX IF NOT EXISTS idx_mcp_tool_calls_policy_binding
    ON mcp_tool_calls (organization_id, environment_id, policy_binding_id, created_at DESC, id DESC);
