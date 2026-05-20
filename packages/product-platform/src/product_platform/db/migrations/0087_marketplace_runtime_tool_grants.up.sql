CREATE TABLE IF NOT EXISTS plugin_runtime_tool_grants (
    id TEXT PRIMARY KEY,
    installation_id TEXT NOT NULL REFERENCES plugin_installations(id) ON DELETE CASCADE,
    plugin_version_id TEXT NOT NULL REFERENCES plugin_versions(id) ON DELETE CASCADE,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    environment_id TEXT NOT NULL REFERENCES environments(id) ON DELETE CASCADE,
    agent_id TEXT REFERENCES agents(id) ON DELETE SET NULL,
    tool_id TEXT NOT NULL REFERENCES tool_definitions(id) ON DELETE CASCADE,
    agent_tool_permission_id TEXT REFERENCES agent_tool_permissions(id) ON DELETE SET NULL,
    tool_name TEXT NOT NULL,
    scope TEXT NOT NULL,
    capability TEXT,
    permission TEXT,
    risk_class TEXT,
    status TEXT NOT NULL,
    owns_agent_tool_permission INTEGER NOT NULL DEFAULT 1,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    revoked_by TEXT,
    revoked_reason TEXT,
    revoked_at TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_plugin_runtime_tool_grants_installation
    ON plugin_runtime_tool_grants (installation_id, status, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_plugin_runtime_tool_grants_agent_tool
    ON plugin_runtime_tool_grants (organization_id, environment_id, agent_id, tool_id, status);

CREATE INDEX IF NOT EXISTS idx_plugin_runtime_tool_grants_permission
    ON plugin_runtime_tool_grants (agent_tool_permission_id, status);

CREATE INDEX IF NOT EXISTS idx_plugin_runtime_tool_grants_version
    ON plugin_runtime_tool_grants (plugin_version_id, status);
