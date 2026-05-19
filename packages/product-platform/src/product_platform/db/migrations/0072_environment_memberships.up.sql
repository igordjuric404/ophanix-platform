CREATE TABLE IF NOT EXISTS environment_memberships (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    environment_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    role TEXT NOT NULL,
    status TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'manual',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    expires_at TEXT,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (environment_id) REFERENCES environments(id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE (organization_id, environment_id, user_id, role)
);

CREATE INDEX IF NOT EXISTS idx_environment_memberships_user_status
    ON environment_memberships (organization_id, user_id, status);

CREATE INDEX IF NOT EXISTS idx_environment_memberships_environment_status
    ON environment_memberships (organization_id, environment_id, status);
