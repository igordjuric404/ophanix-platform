DROP INDEX IF EXISTS idx_mcp_rate_limits_target;
DROP TABLE IF EXISTS mcp_rate_limits;
DROP INDEX IF EXISTS idx_mcp_approvals_status_requested;
DROP TABLE IF EXISTS mcp_approvals;
DROP INDEX IF EXISTS idx_mcp_tool_calls_tool_created;
DROP INDEX IF EXISTS idx_mcp_tool_calls_decision_created;
DROP INDEX IF EXISTS idx_mcp_tool_calls_org_env_created;
DROP TABLE IF EXISTS mcp_tool_calls;
DELETE FROM schema_migrations WHERE version = '0017';
