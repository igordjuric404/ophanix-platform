CREATE TABLE IF NOT EXISTS agent_tool_permissions (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    environment_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    tool_id TEXT NOT NULL,
    scope TEXT NOT NULL,
    status TEXT NOT NULL,
    granted_by TEXT NOT NULL,
    granted_reason TEXT NOT NULL DEFAULT '',
    granted_at TEXT NOT NULL,
    revoked_by TEXT,
    revoked_reason TEXT,
    revoked_at TEXT,
    expires_at TEXT,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (environment_id) REFERENCES environments(id),
    FOREIGN KEY (agent_id) REFERENCES agents(id),
    FOREIGN KEY (tool_id) REFERENCES tool_definitions(id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_agent_tool_permissions_active_pair
    ON agent_tool_permissions (organization_id, environment_id, agent_id, tool_id)
    WHERE status IN ('active', 'paused');

CREATE INDEX IF NOT EXISTS idx_agent_tool_permissions_agent_status
    ON agent_tool_permissions (organization_id, environment_id, agent_id, status, granted_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_agent_tool_permissions_tool_status
    ON agent_tool_permissions (organization_id, environment_id, tool_id, status, granted_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_agent_tool_permissions_expiry
    ON agent_tool_permissions (organization_id, environment_id, status, expires_at)
    WHERE expires_at IS NOT NULL;

CREATE TABLE IF NOT EXISTS agent_tool_permission_history (
    id TEXT PRIMARY KEY,
    permission_id TEXT NOT NULL,
    action TEXT NOT NULL,
    actor_user_id TEXT NOT NULL,
    reason TEXT,
    previous_status TEXT,
    new_status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (permission_id) REFERENCES agent_tool_permissions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_agent_tool_permission_history_permission_created
    ON agent_tool_permission_history (permission_id, created_at DESC, id DESC);
