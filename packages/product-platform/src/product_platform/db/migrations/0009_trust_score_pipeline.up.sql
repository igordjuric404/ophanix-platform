CREATE TABLE IF NOT EXISTS trust_scores (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    environment_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    score INTEGER NOT NULL CHECK (score >= 0 AND score <= 1000),
    tier TEXT NOT NULL,
    dimensions_json TEXT NOT NULL,
    calculated_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (environment_id) REFERENCES environments(id),
    FOREIGN KEY (agent_id) REFERENCES agents(id),
    UNIQUE (organization_id, environment_id, agent_id)
);

CREATE INDEX IF NOT EXISTS idx_trust_scores_org_env_score
    ON trust_scores (organization_id, environment_id, score DESC, agent_id);

CREATE TABLE IF NOT EXISTS trust_events (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    environment_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    source_event_id TEXT,
    dimension TEXT NOT NULL,
    delta INTEGER NOT NULL,
    reason TEXT NOT NULL,
    score_before INTEGER NOT NULL CHECK (score_before >= 0 AND score_before <= 1000),
    score_after INTEGER NOT NULL CHECK (score_after >= 0 AND score_after <= 1000),
    created_at TEXT NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (environment_id) REFERENCES environments(id),
    FOREIGN KEY (agent_id) REFERENCES agents(id),
    FOREIGN KEY (source_event_id) REFERENCES audit_events(id),
    UNIQUE (organization_id, environment_id, source_event_id, agent_id, dimension)
);

CREATE INDEX IF NOT EXISTS idx_trust_events_agent_created
    ON trust_events (organization_id, environment_id, agent_id, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_trust_events_source
    ON trust_events (organization_id, source_event_id);

CREATE TABLE IF NOT EXISTS trust_rules (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    dimension TEXT NOT NULL,
    delta INTEGER NOT NULL,
    min_delta INTEGER NOT NULL,
    max_delta INTEGER NOT NULL,
    enabled INTEGER NOT NULL,
    config_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    UNIQUE (organization_id, event_type)
);

CREATE INDEX IF NOT EXISTS idx_trust_rules_org_enabled
    ON trust_rules (organization_id, enabled, event_type);

CREATE TABLE IF NOT EXISTS trust_recalculation_runs (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    environment_id TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    summary_json TEXT NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (environment_id) REFERENCES environments(id)
);

CREATE INDEX IF NOT EXISTS idx_trust_recalculation_runs_org_env_started
    ON trust_recalculation_runs (organization_id, environment_id, started_at DESC, id DESC);
