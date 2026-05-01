CREATE TABLE IF NOT EXISTS integration_health_checks (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    environment_id TEXT NOT NULL REFERENCES environments(id) ON DELETE CASCADE,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    status TEXT NOT NULL,
    latency_ms INTEGER NOT NULL,
    message TEXT NOT NULL,
    details_json TEXT NOT NULL DEFAULT '{}',
    checked_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_integration_health_scope_target_checked
    ON integration_health_checks (organization_id, environment_id, target_type, target_id, checked_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_integration_health_scope_status
    ON integration_health_checks (organization_id, environment_id, status, checked_at DESC, id DESC);
