CREATE TABLE IF NOT EXISTS plugin_policy_results (
    id TEXT PRIMARY KEY,
    plugin_version_id TEXT NOT NULL REFERENCES plugin_versions(id) ON DELETE CASCADE,
    result TEXT NOT NULL,
    findings_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_plugin_policy_results_version_created
    ON plugin_policy_results (plugin_version_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_plugin_policy_results_result
    ON plugin_policy_results (result);
