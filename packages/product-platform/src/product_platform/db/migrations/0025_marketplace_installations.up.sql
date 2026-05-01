CREATE TABLE IF NOT EXISTS plugin_installations (
    id TEXT PRIMARY KEY,
    plugin_version_id TEXT NOT NULL REFERENCES plugin_versions(id) ON DELETE CASCADE,
    environment_id TEXT NOT NULL REFERENCES environments(id) ON DELETE CASCADE,
    target_agent_id TEXT REFERENCES agents(id) ON DELETE SET NULL,
    status TEXT NOT NULL,
    installed_by TEXT NOT NULL,
    installed_at TEXT NOT NULL,
    uninstalled_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_plugin_installations_environment_status
    ON plugin_installations (environment_id, status, installed_at DESC);

CREATE INDEX IF NOT EXISTS idx_plugin_installations_version
    ON plugin_installations (plugin_version_id);

CREATE INDEX IF NOT EXISTS idx_plugin_installations_target_agent
    ON plugin_installations (target_agent_id);
