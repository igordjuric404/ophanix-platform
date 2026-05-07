CREATE TABLE IF NOT EXISTS tool_response_policies (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    environment_id TEXT NOT NULL,
    tool_id TEXT NOT NULL,
    max_response_bytes INTEGER NOT NULL,
    redaction_rules_json TEXT NOT NULL,
    expose_to_agent INTEGER NOT NULL,
    store_full_response INTEGER NOT NULL,
    strict_output_validation INTEGER NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (environment_id) REFERENCES environments(id),
    FOREIGN KEY (tool_id) REFERENCES tool_definitions(id) ON DELETE CASCADE,
    UNIQUE (tool_id)
);

CREATE INDEX IF NOT EXISTS idx_tool_response_policies_org_env_status
    ON tool_response_policies (organization_id, environment_id, status, updated_at DESC, id DESC);
