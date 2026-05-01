CREATE TABLE IF NOT EXISTS policy_bindings (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    environment_id TEXT NOT NULL,
    policy_id TEXT NOT NULL,
    policy_version_id TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    mode TEXT NOT NULL,
    rollout_percentage INTEGER NOT NULL,
    priority INTEGER NOT NULL,
    status TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (environment_id) REFERENCES environments(id),
    FOREIGN KEY (policy_id) REFERENCES policies(id),
    FOREIGN KEY (policy_version_id) REFERENCES policy_versions(id)
);

CREATE INDEX IF NOT EXISTS idx_policy_bindings_org_env_target
    ON policy_bindings (organization_id, environment_id, target_type, target_id, status);

CREATE INDEX IF NOT EXISTS idx_policy_bindings_policy
    ON policy_bindings (organization_id, policy_id, status, priority);

CREATE TABLE IF NOT EXISTS policy_exceptions (
    id TEXT PRIMARY KEY,
    binding_id TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    expires_at TEXT,
    created_by TEXT NOT NULL,
    approved_by TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (binding_id) REFERENCES policy_bindings(id)
);

CREATE INDEX IF NOT EXISTS idx_policy_exceptions_binding
    ON policy_exceptions (binding_id, target_type, target_id, expires_at);

CREATE TABLE IF NOT EXISTS policy_rollout_events (
    id TEXT PRIMARY KEY,
    binding_id TEXT NOT NULL,
    previous_percentage INTEGER NOT NULL,
    next_percentage INTEGER NOT NULL,
    actor_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (binding_id) REFERENCES policy_bindings(id)
);

CREATE INDEX IF NOT EXISTS idx_policy_rollout_events_binding
    ON policy_rollout_events (binding_id, created_at);
