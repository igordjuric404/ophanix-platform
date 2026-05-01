CREATE TABLE IF NOT EXISTS trust_thresholds (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    environment_id TEXT NOT NULL,
    threshold_type TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    min_score INTEGER NOT NULL CHECK (min_score >= 0 AND min_score <= 1000),
    required_tier TEXT NOT NULL,
    enabled INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (environment_id) REFERENCES environments(id),
    UNIQUE (organization_id, environment_id, threshold_type, target_type, target_id)
);

CREATE INDEX IF NOT EXISTS idx_trust_thresholds_scope_type
    ON trust_thresholds (organization_id, environment_id, threshold_type, enabled, target_type, target_id);

CREATE TABLE IF NOT EXISTS handshake_events (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    environment_id TEXT NOT NULL,
    source_agent_id TEXT NOT NULL,
    target_agent_id TEXT NOT NULL,
    purpose TEXT NOT NULL,
    threshold_type TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    required_score INTEGER NOT NULL CHECK (required_score >= 0 AND required_score <= 1000),
    required_tier TEXT NOT NULL,
    source_score INTEGER NOT NULL CHECK (source_score >= 0 AND source_score <= 1000),
    target_score INTEGER NOT NULL CHECK (target_score >= 0 AND target_score <= 1000),
    result TEXT NOT NULL,
    reason TEXT NOT NULL,
    correlation_id TEXT,
    metadata_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (environment_id) REFERENCES environments(id),
    FOREIGN KEY (source_agent_id) REFERENCES agents(id),
    FOREIGN KEY (target_agent_id) REFERENCES agents(id)
);

CREATE INDEX IF NOT EXISTS idx_handshake_events_source_created
    ON handshake_events (organization_id, environment_id, source_agent_id, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_handshake_events_target_created
    ON handshake_events (organization_id, environment_id, target_agent_id, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_handshake_events_result_created
    ON handshake_events (organization_id, environment_id, result, created_at DESC, id DESC);
