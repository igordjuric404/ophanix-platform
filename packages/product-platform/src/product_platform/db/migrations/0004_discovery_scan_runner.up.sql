CREATE TABLE IF NOT EXISTS discovery_scanners (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    scanner_type TEXT NOT NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL,
    config_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    UNIQUE (organization_id, scanner_type, name)
);

CREATE TABLE IF NOT EXISTS discovery_targets (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    environment_id TEXT NOT NULL,
    scanner_id TEXT NOT NULL,
    scanner_type TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_value TEXT NOT NULL,
    credentials_ref TEXT,
    schedule_id TEXT,
    enabled INTEGER NOT NULL,
    config_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (environment_id) REFERENCES environments(id)
);

CREATE INDEX IF NOT EXISTS idx_discovery_targets_org_env
    ON discovery_targets (organization_id, environment_id, scanner_type, enabled);

CREATE TABLE IF NOT EXISTS discovery_runs (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    environment_id TEXT NOT NULL,
    scanner_id TEXT NOT NULL,
    scanner_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    error_message TEXT,
    summary_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (environment_id) REFERENCES environments(id),
    FOREIGN KEY (target_id) REFERENCES discovery_targets(id)
);

CREATE INDEX IF NOT EXISTS idx_discovery_runs_target_created
    ON discovery_runs (target_id, created_at DESC, id);

CREATE TABLE IF NOT EXISTS discovery_raw_findings (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    raw_payload_json TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES discovery_runs(id)
);

CREATE INDEX IF NOT EXISTS idx_discovery_raw_findings_run
    ON discovery_raw_findings (run_id, fingerprint);
