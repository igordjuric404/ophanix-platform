CREATE TABLE IF NOT EXISTS plugin_reviews (
    id TEXT PRIMARY KEY,
    plugin_version_id TEXT NOT NULL REFERENCES plugin_versions(id) ON DELETE CASCADE,
    status TEXT NOT NULL,
    reviewer_id TEXT,
    findings_json TEXT NOT NULL DEFAULT '[]',
    decision_reason TEXT,
    created_at TEXT NOT NULL,
    decided_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_plugin_reviews_version_created
    ON plugin_reviews (plugin_version_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_plugin_reviews_status
    ON plugin_reviews (status, created_at DESC);

CREATE TABLE IF NOT EXISTS plugin_signing_keys (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    public_key TEXT NOT NULL,
    status TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    revoked_at TEXT,
    UNIQUE (organization_id, name)
);

CREATE INDEX IF NOT EXISTS idx_plugin_signing_keys_org_status
    ON plugin_signing_keys (organization_id, status);

CREATE TABLE IF NOT EXISTS plugin_quality_assessments (
    id TEXT PRIMARY KEY,
    plugin_version_id TEXT NOT NULL REFERENCES plugin_versions(id) ON DELETE CASCADE,
    score REAL NOT NULL,
    dimensions_json TEXT NOT NULL DEFAULT '{}',
    findings_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_plugin_quality_assessments_version_created
    ON plugin_quality_assessments (plugin_version_id, created_at DESC);

CREATE TABLE IF NOT EXISTS plugin_trust_events (
    id TEXT PRIMARY KEY,
    plugin_version_id TEXT NOT NULL REFERENCES plugin_versions(id) ON DELETE CASCADE,
    source_event_id TEXT,
    delta INTEGER NOT NULL,
    reason TEXT NOT NULL,
    score_before INTEGER NOT NULL,
    score_after INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_plugin_trust_events_version_created
    ON plugin_trust_events (plugin_version_id, created_at DESC);
