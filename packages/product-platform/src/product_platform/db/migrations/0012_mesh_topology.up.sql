CREATE TABLE IF NOT EXISTS mesh_messages (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    environment_id TEXT NOT NULL,
    source_agent_id TEXT NOT NULL,
    target_agent_id TEXT NOT NULL,
    protocol TEXT NOT NULL,
    action TEXT NOT NULL,
    decision TEXT NOT NULL,
    latency_ms INTEGER NOT NULL CHECK (latency_ms >= 0),
    correlation_id TEXT,
    payload_summary_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (environment_id) REFERENCES environments(id),
    FOREIGN KEY (source_agent_id) REFERENCES agents(id),
    FOREIGN KEY (target_agent_id) REFERENCES agents(id)
);

CREATE INDEX IF NOT EXISTS idx_mesh_messages_scope_created
    ON mesh_messages (organization_id, environment_id, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_mesh_messages_source_created
    ON mesh_messages (organization_id, environment_id, source_agent_id, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_mesh_messages_target_created
    ON mesh_messages (organization_id, environment_id, target_agent_id, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_mesh_messages_protocol_decision
    ON mesh_messages (organization_id, environment_id, protocol, decision, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_mesh_messages_correlation
    ON mesh_messages (organization_id, environment_id, correlation_id);

CREATE TABLE IF NOT EXISTS mesh_handoffs (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    environment_id TEXT NOT NULL,
    source_agent_id TEXT NOT NULL,
    target_agent_id TEXT NOT NULL,
    task_type TEXT NOT NULL,
    required_capabilities_json TEXT NOT NULL,
    trust_result TEXT NOT NULL,
    policy_result TEXT NOT NULL,
    status TEXT NOT NULL,
    reason TEXT NOT NULL,
    correlation_id TEXT,
    metadata_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (environment_id) REFERENCES environments(id),
    FOREIGN KEY (source_agent_id) REFERENCES agents(id),
    FOREIGN KEY (target_agent_id) REFERENCES agents(id)
);

CREATE INDEX IF NOT EXISTS idx_mesh_handoffs_scope_created
    ON mesh_handoffs (organization_id, environment_id, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_mesh_handoffs_source_created
    ON mesh_handoffs (organization_id, environment_id, source_agent_id, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_mesh_handoffs_status_created
    ON mesh_handoffs (organization_id, environment_id, status, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_mesh_handoffs_correlation
    ON mesh_handoffs (organization_id, environment_id, correlation_id);

CREATE TABLE IF NOT EXISTS mesh_topology_snapshots (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    environment_id TEXT NOT NULL,
    time_bucket TEXT NOT NULL,
    nodes_json TEXT NOT NULL,
    edges_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (environment_id) REFERENCES environments(id),
    UNIQUE (organization_id, environment_id, time_bucket)
);

CREATE INDEX IF NOT EXISTS idx_mesh_topology_snapshots_scope_bucket
    ON mesh_topology_snapshots (organization_id, environment_id, time_bucket DESC);
