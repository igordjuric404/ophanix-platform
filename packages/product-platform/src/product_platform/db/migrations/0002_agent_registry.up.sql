CREATE TABLE IF NOT EXISTS agents (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    environment_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    framework TEXT NOT NULL,
    runtime_type TEXT NOT NULL,
    endpoint_url TEXT,
    owner_user_id TEXT NOT NULL,
    sponsor_user_id TEXT NOT NULL,
    status TEXT NOT NULL,
    trust_score REAL,
    trust_tier TEXT,
    credential_status TEXT,
    credential_expires_at TEXT,
    last_heartbeat_at TEXT,
    decommissioned_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (environment_id) REFERENCES environments(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_agents_org_env_name_active
    ON agents (organization_id, environment_id, lower(name))
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_agents_org_env_status
    ON agents (organization_id, environment_id, status, name);

CREATE TABLE IF NOT EXISTS agent_identities (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    did TEXT NOT NULL,
    public_key_fingerprint TEXT NOT NULL,
    key_type TEXT NOT NULL,
    identity_status TEXT NOT NULL,
    bootstrap_material_json TEXT,
    bootstrap_retrieved_at TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (agent_id) REFERENCES agents(id),
    UNIQUE (agent_id),
    UNIQUE (did)
);

CREATE TABLE IF NOT EXISTS agent_capabilities (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    capability_name TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    status TEXT NOT NULL,
    requested_by TEXT NOT NULL,
    approved_by TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (agent_id) REFERENCES agents(id),
    UNIQUE (agent_id, capability_name, resource_type)
);

CREATE TABLE IF NOT EXISTS agent_protocols (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    protocol TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    status TEXT NOT NULL,
    FOREIGN KEY (agent_id) REFERENCES agents(id),
    UNIQUE (agent_id, protocol, endpoint)
);

CREATE TABLE IF NOT EXISTS agent_policy_selections (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    policy_id TEXT NOT NULL,
    selection_type TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (agent_id) REFERENCES agents(id),
    UNIQUE (agent_id, policy_id, selection_type)
);

CREATE TABLE IF NOT EXISTS agent_lifecycle_events (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    previous_state TEXT,
    next_state TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    reason TEXT,
    metadata_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (agent_id) REFERENCES agents(id)
);

CREATE INDEX IF NOT EXISTS idx_agent_lifecycle_events_agent_created
    ON agent_lifecycle_events (agent_id, created_at, id);

CREATE TABLE IF NOT EXISTS agent_heartbeats (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    status TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    FOREIGN KEY (agent_id) REFERENCES agents(id)
);

CREATE INDEX IF NOT EXISTS idx_agent_heartbeats_agent_observed
    ON agent_heartbeats (agent_id, observed_at DESC);

