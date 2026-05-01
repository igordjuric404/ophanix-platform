CREATE TABLE IF NOT EXISTS mcp_scan_runs (
    id TEXT PRIMARY KEY,
    server_id TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    summary_json TEXT NOT NULL,
    error_message TEXT,
    FOREIGN KEY (server_id) REFERENCES mcp_servers(id)
);

CREATE INDEX IF NOT EXISTS idx_mcp_scan_runs_server_started
    ON mcp_scan_runs (server_id, started_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_mcp_scan_runs_status_started
    ON mcp_scan_runs (status, started_at DESC, id DESC);

CREATE TABLE IF NOT EXISTS mcp_findings (
    id TEXT PRIMARY KEY,
    scan_run_id TEXT NOT NULL,
    tool_id TEXT NOT NULL,
    tool_version_id TEXT,
    finding_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    recommendation TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (scan_run_id) REFERENCES mcp_scan_runs(id),
    FOREIGN KEY (tool_id) REFERENCES mcp_tools(id),
    FOREIGN KEY (tool_version_id) REFERENCES mcp_tool_versions(id)
);

CREATE INDEX IF NOT EXISTS idx_mcp_findings_scan
    ON mcp_findings (scan_run_id, severity, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_mcp_findings_tool_status
    ON mcp_findings (tool_id, status, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_mcp_findings_status_severity
    ON mcp_findings (status, severity, created_at DESC, id DESC);

CREATE TABLE IF NOT EXISTS mcp_scan_baselines (
    id TEXT PRIMARY KEY,
    server_id TEXT NOT NULL,
    tool_id TEXT NOT NULL,
    schema_hash TEXT NOT NULL,
    accepted_by TEXT NOT NULL,
    accepted_at TEXT NOT NULL,
    reason TEXT NOT NULL,
    FOREIGN KEY (server_id) REFERENCES mcp_servers(id),
    FOREIGN KEY (tool_id) REFERENCES mcp_tools(id)
);

CREATE INDEX IF NOT EXISTS idx_mcp_scan_baselines_tool_hash
    ON mcp_scan_baselines (tool_id, schema_hash);

