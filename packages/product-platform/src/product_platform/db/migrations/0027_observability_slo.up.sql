CREATE TABLE IF NOT EXISTS slo_objectives (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    environment_id TEXT NOT NULL REFERENCES environments(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    sli TEXT NOT NULL,
    target_value REAL NOT NULL,
    "window" TEXT NOT NULL,
    status TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_slo_objectives_scope_status
    ON slo_objectives (organization_id, environment_id, status, updated_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_slo_objectives_target
    ON slo_objectives (organization_id, environment_id, target_type, target_id);

CREATE TABLE IF NOT EXISTS slo_measurements (
    id TEXT PRIMARY KEY,
    slo_id TEXT NOT NULL REFERENCES slo_objectives(id) ON DELETE CASCADE,
    value REAL NOT NULL,
    good_events INTEGER NOT NULL,
    total_events INTEGER NOT NULL,
    error_budget_remaining REAL NOT NULL,
    burn_rate REAL NOT NULL,
    status TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    measured_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_slo_measurements_slo_measured
    ON slo_measurements (slo_id, measured_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_slo_measurements_status
    ON slo_measurements (status, measured_at DESC);
