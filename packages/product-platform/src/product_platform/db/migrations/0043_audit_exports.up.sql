CREATE TABLE IF NOT EXISTS audit_exports (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    filters_json TEXT NOT NULL,
    format TEXT NOT NULL,
    status TEXT NOT NULL,
    artifact_uri TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id)
);

CREATE INDEX IF NOT EXISTS idx_audit_exports_org_created
    ON audit_exports (organization_id, created_at DESC, id DESC);
