CREATE TABLE IF NOT EXISTS policy_evaluations (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    environment_id TEXT NOT NULL,
    policy_id TEXT,
    policy_version_id TEXT,
    binding_id TEXT,
    binding_mode TEXT,
    agent_id TEXT,
    target_type TEXT,
    target_id TEXT,
    action TEXT NOT NULL,
    resource_type TEXT,
    resource_id TEXT,
    context_json TEXT NOT NULL,
    decision TEXT NOT NULL,
    policy_action TEXT NOT NULL,
    matched_rule TEXT,
    reason TEXT NOT NULL,
    latency_ms REAL NOT NULL,
    mode TEXT NOT NULL,
    correlation_id TEXT,
    backend TEXT NOT NULL,
    error INTEGER NOT NULL DEFAULT 0,
    audit_preview_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (environment_id) REFERENCES environments(id),
    FOREIGN KEY (policy_id) REFERENCES policies(id),
    FOREIGN KEY (policy_version_id) REFERENCES policy_versions(id),
    FOREIGN KEY (binding_id) REFERENCES policy_bindings(id)
);

CREATE INDEX IF NOT EXISTS idx_policy_evaluations_org_env_created
    ON policy_evaluations (organization_id, environment_id, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_policy_evaluations_filters
    ON policy_evaluations (
        organization_id,
        environment_id,
        decision,
        mode,
        agent_id,
        action,
        policy_id,
        correlation_id
    );
