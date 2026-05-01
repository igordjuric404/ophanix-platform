DROP INDEX IF EXISTS idx_mcp_tool_versions_schema_hash;
DROP INDEX IF EXISTS idx_mcp_tool_versions_tool_discovered;
DROP TABLE IF EXISTS mcp_tool_versions;
DROP INDEX IF EXISTS idx_mcp_tools_server_status;
DROP INDEX IF EXISTS idx_mcp_tools_server_name;
DROP TABLE IF EXISTS mcp_tools;
DELETE FROM schema_migrations WHERE version = '0015';

