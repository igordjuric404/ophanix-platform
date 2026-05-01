CREATE TABLE IF NOT EXISTS mcp_servers (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    environment_id TEXT NOT NULL,
    name TEXT NOT NULL,
    endpoint_url TEXT NOT NULL,
    owner_user_id TEXT NOT NULL,
    auth_type TEXT NOT NULL,
    status TEXT NOT NULL,
    policy_pack_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_discovered_at TEXT,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (environment_id) REFERENCES environments(id),
    FOREIGN KEY (owner_user_id) REFERENCES users(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_mcp_servers_scope_name_active
    ON mcp_servers (organization_id, environment_id, lower(name));

CREATE INDEX IF NOT EXISTS idx_mcp_servers_scope_status
    ON mcp_servers (organization_id, environment_id, status, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_mcp_servers_owner
    ON mcp_servers (organization_id, owner_user_id, created_at DESC, id DESC);

