DROP INDEX IF EXISTS idx_mcp_scan_baselines_tool_hash;
DROP TABLE IF EXISTS mcp_scan_baselines;
DROP INDEX IF EXISTS idx_mcp_findings_status_severity;
DROP INDEX IF EXISTS idx_mcp_findings_tool_status;
DROP INDEX IF EXISTS idx_mcp_findings_scan;
DROP TABLE IF EXISTS mcp_findings;
DROP INDEX IF EXISTS idx_mcp_scan_runs_status_started;
DROP INDEX IF EXISTS idx_mcp_scan_runs_server_started;
DROP TABLE IF EXISTS mcp_scan_runs;
DELETE FROM schema_migrations WHERE version = '0016';

