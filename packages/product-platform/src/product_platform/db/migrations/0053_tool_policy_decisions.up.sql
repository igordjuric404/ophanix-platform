CREATE TABLE IF NOT EXISTS tool_policy_decisions (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    environment_id TEXT NOT NULL,
    agent_id TEXT,
    tool_id TEXT,
    permission_id TEXT,
    decision TEXT NOT NULL,
    reason_code TEXT NOT NULL,
    reason_message TEXT NOT NULL,
    matched_policy_id TEXT,
    request_id TEXT NOT NULL,
    correlation_id TEXT,
    payload_summary_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (environment_id) REFERENCES environments(id),
    FOREIGN KEY (agent_id) REFERENCES agents(id),
    FOREIGN KEY (tool_id) REFERENCES tool_definitions(id),
    FOREIGN KEY (permission_id) REFERENCES agent_tool_permissions(id)
);

CREATE INDEX IF NOT EXISTS idx_tool_policy_decisions_org_env_created
    ON tool_policy_decisions (organization_id, environment_id, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_tool_policy_decisions_agent_created
    ON tool_policy_decisions (organization_id, environment_id, agent_id, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_tool_policy_decisions_tool_created
    ON tool_policy_decisions (organization_id, environment_id, tool_id, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_tool_policy_decisions_decision_reason
    ON tool_policy_decisions (organization_id, environment_id, decision, reason_code, created_at DESC, id DESC);
