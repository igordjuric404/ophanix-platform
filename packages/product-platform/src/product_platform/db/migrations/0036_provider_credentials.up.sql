CREATE TABLE IF NOT EXISTS provider_credentials (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    provider_type TEXT NOT NULL,
    secret_ref TEXT NOT NULL,
    status TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_used_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_provider_credentials_org_type_status
    ON provider_credentials (organization_id, provider_type, status, created_at DESC, id DESC);

CREATE UNIQUE INDEX IF NOT EXISTS idx_provider_credentials_org_secret_ref
    ON provider_credentials (organization_id, secret_ref);
