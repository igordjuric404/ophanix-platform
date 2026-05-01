CREATE TABLE IF NOT EXISTS mcp_tools (
    id TEXT PRIMARY KEY,
    server_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    current_version_id TEXT,
    risk_level TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (server_id) REFERENCES mcp_servers(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_mcp_tools_server_name
    ON mcp_tools (server_id, name);

CREATE INDEX IF NOT EXISTS idx_mcp_tools_server_status
    ON mcp_tools (server_id, status, created_at DESC, id DESC);

CREATE TABLE IF NOT EXISTS mcp_tool_versions (
    id TEXT PRIMARY KEY,
    tool_id TEXT NOT NULL,
    schema_json TEXT NOT NULL,
    schema_hash TEXT NOT NULL,
    definition_json TEXT NOT NULL,
    discovered_at TEXT NOT NULL,
    scan_status TEXT NOT NULL,
    FOREIGN KEY (tool_id) REFERENCES mcp_tools(id)
);

CREATE INDEX IF NOT EXISTS idx_mcp_tool_versions_tool_discovered
    ON mcp_tool_versions (tool_id, discovered_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_mcp_tool_versions_schema_hash
    ON mcp_tool_versions (schema_hash);

