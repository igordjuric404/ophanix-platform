CREATE TABLE IF NOT EXISTS tool_invocation_idempotency_records (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    environment_id TEXT NOT NULL,
    credential_id TEXT NOT NULL,
    tool_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    request_id TEXT NOT NULL,
    correlation_id TEXT,
    status TEXT NOT NULL,
    response_status_code INTEGER,
    response_body_json TEXT,
    error_code TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (environment_id) REFERENCES environments(id),
    FOREIGN KEY (credential_id) REFERENCES agent_credentials(id),
    FOREIGN KEY (tool_id) REFERENCES tool_definitions(id),
    UNIQUE (
        organization_id,
        environment_id,
        credential_id,
        tool_id,
        idempotency_key
    )
);

CREATE INDEX IF NOT EXISTS idx_tool_invocation_idempotency_lookup
    ON tool_invocation_idempotency_records (
        organization_id,
        environment_id,
        credential_id,
        tool_id,
        idempotency_key
    );

CREATE INDEX IF NOT EXISTS idx_tool_invocation_idempotency_created
    ON tool_invocation_idempotency_records (
        organization_id,
        environment_id,
        created_at DESC,
        id DESC
    );
