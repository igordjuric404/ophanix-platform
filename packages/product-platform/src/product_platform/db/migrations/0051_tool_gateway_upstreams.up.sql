CREATE TABLE IF NOT EXISTS tool_upstream_targets (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    environment_id TEXT NOT NULL,
    tool_id TEXT NOT NULL,
    base_url TEXT NOT NULL,
    path_template TEXT NOT NULL,
    method TEXT NOT NULL,
    auth_mode TEXT NOT NULL,
    timeout_ms INTEGER NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (environment_id) REFERENCES environments(id),
    FOREIGN KEY (tool_id) REFERENCES tool_definitions(id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_tool_upstream_targets_tool_active
    ON tool_upstream_targets (organization_id, environment_id, tool_id)
    WHERE status IN ('configured', 'healthy', 'degraded', 'unhealthy');

CREATE INDEX IF NOT EXISTS idx_tool_upstream_targets_org_env_status
    ON tool_upstream_targets (organization_id, environment_id, status, updated_at DESC, id DESC);

CREATE TABLE IF NOT EXISTS tool_upstream_health_checks (
    id TEXT PRIMARY KEY,
    target_id TEXT NOT NULL,
    health_url TEXT NOT NULL,
    expected_status INTEGER NOT NULL,
    interval_seconds INTEGER NOT NULL,
    last_status TEXT,
    last_checked_at TEXT,
    last_error TEXT,
    enabled INTEGER NOT NULL,
    FOREIGN KEY (target_id) REFERENCES tool_upstream_targets(id) ON DELETE CASCADE,
    UNIQUE (target_id)
);

CREATE INDEX IF NOT EXISTS idx_tool_upstream_health_checks_target
    ON tool_upstream_health_checks (target_id);
