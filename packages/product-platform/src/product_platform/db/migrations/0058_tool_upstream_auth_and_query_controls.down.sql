PRAGMA foreign_keys = OFF;

CREATE TABLE IF NOT EXISTS tool_upstream_targets_0058_down (
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

INSERT INTO tool_upstream_targets_0058_down (
    id, organization_id, environment_id, tool_id, base_url,
    path_template, method, auth_mode, timeout_ms, status,
    created_at, updated_at
)
SELECT
    id, organization_id, environment_id, tool_id, base_url,
    path_template, method, auth_mode, timeout_ms, status,
    created_at, updated_at
FROM tool_upstream_targets;

DROP INDEX IF EXISTS idx_tool_upstream_targets_org_env_status;
DROP INDEX IF EXISTS idx_tool_upstream_targets_tool_active;
DROP TABLE tool_upstream_targets;
ALTER TABLE tool_upstream_targets_0058_down RENAME TO tool_upstream_targets;

CREATE UNIQUE INDEX IF NOT EXISTS idx_tool_upstream_targets_tool_active
    ON tool_upstream_targets (organization_id, environment_id, tool_id)
    WHERE status IN ('configured', 'healthy', 'degraded', 'unhealthy');

CREATE INDEX IF NOT EXISTS idx_tool_upstream_targets_org_env_status
    ON tool_upstream_targets (organization_id, environment_id, status, updated_at DESC, id DESC);

PRAGMA foreign_keys = ON;
