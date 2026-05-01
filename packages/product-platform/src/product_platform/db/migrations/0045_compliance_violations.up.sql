CREATE TABLE IF NOT EXISTS compliance_violations (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    environment_id TEXT NOT NULL,
    control_id TEXT NOT NULL,
    agent_id TEXT,
    severity TEXT NOT NULL,
    status TEXT NOT NULL,
    reason TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_event_id TEXT,
    acknowledged_by TEXT,
    acknowledged_at TEXT,
    resolved_by TEXT,
    resolved_at TEXT,
    resolution_reason TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (organization_id, environment_id, control_id, source_type, source_id),
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (environment_id) REFERENCES environments(id),
    FOREIGN KEY (control_id) REFERENCES controls(id),
    FOREIGN KEY (source_event_id) REFERENCES audit_events(id)
);

CREATE INDEX IF NOT EXISTS idx_compliance_violations_scope
    ON compliance_violations (organization_id, environment_id, status, severity, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_compliance_violations_control
    ON compliance_violations (control_id, status);
