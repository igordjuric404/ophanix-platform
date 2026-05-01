CREATE TABLE IF NOT EXISTS sandbox_profiles (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    environment_id TEXT NOT NULL REFERENCES environments(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    provider_type TEXT NOT NULL,
    allowed_imports_json TEXT NOT NULL DEFAULT '[]',
    blocked_imports_json TEXT NOT NULL DEFAULT '[]',
    allowed_paths_json TEXT NOT NULL DEFAULT '[]',
    network_policy_json TEXT NOT NULL DEFAULT '{}',
    resource_limits_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (organization_id, environment_id, name)
);

CREATE INDEX IF NOT EXISTS idx_sandbox_profiles_tenant_status
    ON sandbox_profiles (organization_id, environment_id, status);

CREATE TABLE IF NOT EXISTS sandbox_decisions (
    id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL REFERENCES sandbox_profiles(id) ON DELETE CASCADE,
    agent_id TEXT REFERENCES agents(id) ON DELETE SET NULL,
    action_name TEXT,
    decision TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sandbox_decisions_profile_created
    ON sandbox_decisions (profile_id, created_at DESC);

CREATE TABLE IF NOT EXISTS kill_switch_events (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    environment_id TEXT NOT NULL REFERENCES environments(id) ON DELETE CASCADE,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    scope TEXT NOT NULL,
    reason TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_kill_switch_events_tenant_created
    ON kill_switch_events (organization_id, environment_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_kill_switch_events_target
    ON kill_switch_events (target_type, target_id);
