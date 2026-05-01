CREATE TABLE IF NOT EXISTS compliance_reports (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    environment_id TEXT NOT NULL,
    framework_id TEXT NOT NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL,
    date_from TEXT NOT NULL,
    date_to TEXT NOT NULL,
    generated_by TEXT,
    artifact_uri TEXT,
    summary_json TEXT NOT NULL,
    rendered_markdown TEXT,
    rendered_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    generated_at TEXT,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (environment_id) REFERENCES environments(id),
    FOREIGN KEY (framework_id) REFERENCES control_frameworks(id)
);

CREATE TABLE IF NOT EXISTS report_evidence_items (
    report_id TEXT NOT NULL,
    evidence_item_id TEXT NOT NULL,
    PRIMARY KEY (report_id, evidence_item_id),
    FOREIGN KEY (report_id) REFERENCES compliance_reports(id),
    FOREIGN KEY (evidence_item_id) REFERENCES evidence_items(id)
);

CREATE TABLE IF NOT EXISTS report_attestations (
    id TEXT PRIMARY KEY,
    report_id TEXT NOT NULL,
    attested_by TEXT NOT NULL,
    statement TEXT NOT NULL,
    signature_ref TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (report_id) REFERENCES compliance_reports(id)
);

CREATE INDEX IF NOT EXISTS idx_compliance_reports_scope
    ON compliance_reports (organization_id, environment_id, status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_report_attestations_report
    ON report_attestations (report_id, created_at DESC);
