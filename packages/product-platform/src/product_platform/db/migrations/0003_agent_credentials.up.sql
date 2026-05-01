CREATE TABLE IF NOT EXISTS credential_issuers (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    name TEXT NOT NULL,
    issuer_type TEXT NOT NULL,
    config_json TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    UNIQUE (organization_id, name)
);

CREATE TABLE IF NOT EXISTS agent_credentials (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    credential_type TEXT NOT NULL,
    token_hash TEXT NOT NULL,
    issuer TEXT NOT NULL,
    status TEXT NOT NULL,
    issued_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    revoked_at TEXT,
    last_used_at TEXT,
    metadata_json TEXT NOT NULL,
    FOREIGN KEY (agent_id) REFERENCES agents(id),
    UNIQUE (token_hash)
);

CREATE INDEX IF NOT EXISTS idx_agent_credentials_agent_status
    ON agent_credentials (agent_id, status, expires_at);

CREATE INDEX IF NOT EXISTS idx_agent_credentials_status_expiry
    ON agent_credentials (status, expires_at);

CREATE TABLE IF NOT EXISTS credential_scopes (
    id TEXT PRIMARY KEY,
    credential_id TEXT NOT NULL,
    scope TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id TEXT,
    FOREIGN KEY (credential_id) REFERENCES agent_credentials(id),
    UNIQUE (credential_id, scope, resource_type, resource_id)
);

CREATE INDEX IF NOT EXISTS idx_credential_scopes_credential
    ON credential_scopes (credential_id);

CREATE TABLE IF NOT EXISTS credential_rotations (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    previous_credential_id TEXT NOT NULL,
    new_credential_id TEXT,
    reason TEXT NOT NULL,
    status TEXT NOT NULL,
    requested_by TEXT NOT NULL,
    completed_at TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (agent_id) REFERENCES agents(id),
    FOREIGN KEY (previous_credential_id) REFERENCES agent_credentials(id),
    FOREIGN KEY (new_credential_id) REFERENCES agent_credentials(id)
);

CREATE INDEX IF NOT EXISTS idx_credential_rotations_agent_created
    ON credential_rotations (agent_id, created_at, id);
