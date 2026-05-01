CREATE TABLE IF NOT EXISTS runtime_ring_rules (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    environment_id TEXT NOT NULL,
    action_pattern TEXT NOT NULL,
    required_ring INTEGER NOT NULL CHECK (required_ring >= 0 AND required_ring <= 3),
    min_trust_score INTEGER NOT NULL CHECK (min_trust_score >= 0 AND min_trust_score <= 1000),
    enabled INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (environment_id) REFERENCES environments(id)
);

CREATE INDEX IF NOT EXISTS idx_runtime_ring_rules_scope_enabled
    ON runtime_ring_rules (organization_id, environment_id, enabled, updated_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_runtime_ring_rules_pattern
    ON runtime_ring_rules (organization_id, environment_id, action_pattern);
