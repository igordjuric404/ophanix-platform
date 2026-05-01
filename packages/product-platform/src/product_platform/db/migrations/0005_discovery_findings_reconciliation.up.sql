CREATE TABLE IF NOT EXISTS discovery_findings (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    environment_id TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    detected_name TEXT NOT NULL,
    agent_type TEXT NOT NULL,
    source TEXT,
    owner_hint TEXT,
    registry_agent_id TEXT,
    status TEXT NOT NULL,
    risk_score REAL NOT NULL,
    risk_level TEXT NOT NULL,
    risk_factors_json TEXT NOT NULL,
    did TEXT,
    endpoint_url TEXT,
    merge_keys_json TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (environment_id) REFERENCES environments(id),
    FOREIGN KEY (registry_agent_id) REFERENCES agents(id),
    UNIQUE (organization_id, environment_id, fingerprint)
);

CREATE INDEX IF NOT EXISTS idx_discovery_findings_org_env_status
    ON discovery_findings (organization_id, environment_id, status, risk_level);

CREATE TABLE IF NOT EXISTS discovery_evidence (
    id TEXT PRIMARY KEY,
    finding_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    evidence_type TEXT NOT NULL,
    evidence_value TEXT NOT NULL,
    confidence REAL NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (finding_id) REFERENCES discovery_findings(id),
    FOREIGN KEY (run_id) REFERENCES discovery_runs(id)
);

CREATE INDEX IF NOT EXISTS idx_discovery_evidence_finding
    ON discovery_evidence (finding_id, created_at);

CREATE TABLE IF NOT EXISTS discovery_suppressions (
    id TEXT PRIMARY KEY,
    finding_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    expires_at TEXT,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (finding_id) REFERENCES discovery_findings(id)
);

CREATE INDEX IF NOT EXISTS idx_discovery_suppressions_finding
    ON discovery_suppressions (finding_id, created_at);

CREATE TABLE IF NOT EXISTS reconciliation_actions (
    id TEXT PRIMARY KEY,
    finding_id TEXT NOT NULL,
    action_type TEXT NOT NULL,
    status TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (finding_id) REFERENCES discovery_findings(id)
);

CREATE INDEX IF NOT EXISTS idx_reconciliation_actions_finding
    ON reconciliation_actions (finding_id, created_at);
