CREATE TABLE IF NOT EXISTS incidents (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    environment_id TEXT NOT NULL REFERENCES environments(id) ON DELETE CASCADE,
    severity TEXT NOT NULL,
    status TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    owner_user_id TEXT,
    correlation_id TEXT,
    source_event_id TEXT,
    resolution_note TEXT,
    started_at TEXT NOT NULL,
    acknowledged_at TEXT,
    resolved_at TEXT,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_incidents_scope_status
    ON incidents (organization_id, environment_id, status, started_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_incidents_correlation
    ON incidents (organization_id, environment_id, correlation_id);

CREATE INDEX IF NOT EXISTS idx_incidents_source_event
    ON incidents (organization_id, environment_id, source_event_id);
