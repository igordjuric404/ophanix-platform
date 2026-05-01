CREATE TABLE IF NOT EXISTS chaos_experiments (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    environment_id TEXT NOT NULL REFERENCES environments(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    fault_type TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    blast_radius_json TEXT NOT NULL DEFAULT '{}',
    guardrails_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chaos_experiments_scope_status
    ON chaos_experiments (organization_id, environment_id, status, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_chaos_experiments_target
    ON chaos_experiments (organization_id, environment_id, target_type, target_id);
