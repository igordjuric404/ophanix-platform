CREATE TABLE IF NOT EXISTS demo_reset_runs (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    environment_id TEXT NOT NULL,
    status TEXT NOT NULL,
    requested_by TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    summary_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (environment_id) REFERENCES environments(id)
);

CREATE INDEX IF NOT EXISTS idx_demo_reset_runs_org_env_started
ON demo_reset_runs (organization_id, environment_id, started_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_demo_reset_runs_org_env_status
ON demo_reset_runs (organization_id, environment_id, status, started_at DESC);
