CREATE TABLE IF NOT EXISTS framework_agents (
    id TEXT PRIMARY KEY,
    integration_instance_id TEXT NOT NULL REFERENCES integration_instances(id) ON DELETE CASCADE,
    agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    framework_agent_ref TEXT NOT NULL,
    sdk_version TEXT NOT NULL,
    telemetry_status TEXT NOT NULL,
    policy_coverage_status TEXT NOT NULL,
    linked_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (integration_instance_id, agent_id)
);

CREATE INDEX IF NOT EXISTS idx_framework_agents_instance
    ON framework_agents (integration_instance_id, linked_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_framework_agents_agent
    ON framework_agents (agent_id, integration_instance_id);
