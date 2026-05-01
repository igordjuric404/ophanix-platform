CREATE TABLE IF NOT EXISTS policies (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    name TEXT NOT NULL,
    slug TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    scope TEXT NOT NULL,
    owner_user_id TEXT NOT NULL,
    status TEXT NOT NULL,
    tags_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT,
    FOREIGN KEY (organization_id) REFERENCES organizations(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_policies_org_slug_active
    ON policies (organization_id, slug)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_policies_org_status_scope
    ON policies (organization_id, status, scope, name);

CREATE TABLE IF NOT EXISTS policy_versions (
    id TEXT PRIMARY KEY,
    policy_id TEXT NOT NULL,
    version_number INTEGER NOT NULL,
    body_format TEXT NOT NULL,
    body_text TEXT NOT NULL,
    backend TEXT NOT NULL,
    checksum TEXT NOT NULL,
    status TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    activated_at TEXT,
    archived_at TEXT,
    FOREIGN KEY (policy_id) REFERENCES policies(id),
    UNIQUE (policy_id, version_number)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_policy_versions_one_active
    ON policy_versions (policy_id)
    WHERE status = 'active';

CREATE INDEX IF NOT EXISTS idx_policy_versions_policy_created
    ON policy_versions (policy_id, version_number DESC, created_at DESC);

CREATE TABLE IF NOT EXISTS policy_imports (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_path TEXT,
    status TEXT NOT NULL,
    summary_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id)
);

CREATE INDEX IF NOT EXISTS idx_policy_imports_org_created
    ON policy_imports (organization_id, created_at DESC);
