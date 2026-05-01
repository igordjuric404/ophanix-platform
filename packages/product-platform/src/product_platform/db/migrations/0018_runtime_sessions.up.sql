CREATE TABLE IF NOT EXISTS runtime_sessions (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    environment_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    state TEXT NOT NULL,
    ring INTEGER NOT NULL CHECK (ring >= 0 AND ring <= 3),
    sponsor_user_id TEXT,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    metadata_json TEXT NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (environment_id) REFERENCES environments(id),
    FOREIGN KEY (agent_id) REFERENCES agents(id)
);

CREATE INDEX IF NOT EXISTS idx_runtime_sessions_scope_started
    ON runtime_sessions (organization_id, environment_id, started_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_runtime_sessions_agent_started
    ON runtime_sessions (organization_id, environment_id, agent_id, started_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_runtime_sessions_state_started
    ON runtime_sessions (organization_id, environment_id, state, started_at DESC, id DESC);

CREATE TABLE IF NOT EXISTS runtime_actions (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    action_name TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    required_ring INTEGER CHECK (required_ring IS NULL OR (required_ring >= 0 AND required_ring <= 3)),
    decision TEXT NOT NULL,
    reason TEXT NOT NULL,
    latency_ms INTEGER NOT NULL CHECK (latency_ms >= 0),
    correlation_id TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES runtime_sessions(id)
);

CREATE INDEX IF NOT EXISTS idx_runtime_actions_session_created
    ON runtime_actions (session_id, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_runtime_actions_decision_created
    ON runtime_actions (decision, created_at DESC, id DESC);
