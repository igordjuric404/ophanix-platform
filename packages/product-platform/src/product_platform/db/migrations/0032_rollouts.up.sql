CREATE TABLE IF NOT EXISTS rollouts (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    environment_id TEXT NOT NULL REFERENCES environments(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    strategy TEXT NOT NULL,
    status TEXT NOT NULL,
    current_stage INTEGER NOT NULL,
    config_json TEXT NOT NULL DEFAULT '{}',
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_rollouts_scope_status
    ON rollouts (organization_id, environment_id, status, updated_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_rollouts_target
    ON rollouts (organization_id, environment_id, target_type, target_id);

CREATE TABLE IF NOT EXISTS rollout_events (
    id TEXT PRIMARY KEY,
    rollout_id TEXT NOT NULL REFERENCES rollouts(id) ON DELETE CASCADE,
    stage INTEGER NOT NULL,
    decision TEXT NOT NULL,
    metrics_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_rollout_events_rollout_created
    ON rollout_events (rollout_id, created_at DESC, id DESC);
