PRAGMA foreign_keys = OFF;

CREATE TABLE IF NOT EXISTS tool_runtime_actions_old_latency (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    environment_id TEXT NOT NULL,
    request_id TEXT NOT NULL,
    correlation_id TEXT,
    agent_id TEXT,
    credential_id TEXT,
    tool_id TEXT,
    permission_id TEXT,
    decision_id TEXT,
    action_status TEXT NOT NULL,
    reason_code TEXT,
    upstream_status_code INTEGER,
    latency_ms INTEGER,
    payload_summary_json TEXT NOT NULL,
    response_summary_json TEXT,
    redaction_applied INTEGER NOT NULL DEFAULT 0,
    error_code TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (environment_id) REFERENCES environments(id),
    FOREIGN KEY (agent_id) REFERENCES agents(id),
    FOREIGN KEY (credential_id) REFERENCES agent_credentials(id),
    FOREIGN KEY (tool_id) REFERENCES tool_definitions(id),
    FOREIGN KEY (permission_id) REFERENCES agent_tool_permissions(id),
    FOREIGN KEY (decision_id) REFERENCES tool_policy_decisions(id)
);

INSERT INTO tool_runtime_actions_old_latency (
    id, organization_id, environment_id, request_id, correlation_id,
    agent_id, credential_id, tool_id, permission_id, decision_id,
    action_status, reason_code, upstream_status_code, latency_ms,
    payload_summary_json, response_summary_json, redaction_applied,
    error_code, created_at, updated_at
)
SELECT
    id, organization_id, environment_id, request_id, correlation_id,
    agent_id, credential_id, tool_id, permission_id, decision_id,
    action_status, reason_code, upstream_status_code, CAST(latency_ms AS INTEGER),
    payload_summary_json, response_summary_json, redaction_applied,
    error_code, created_at, updated_at
FROM tool_runtime_actions;

DROP TABLE tool_runtime_actions;
ALTER TABLE tool_runtime_actions_old_latency RENAME TO tool_runtime_actions;

CREATE INDEX IF NOT EXISTS idx_tool_runtime_actions_org_env_created
    ON tool_runtime_actions (organization_id, environment_id, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_tool_runtime_actions_agent_created
    ON tool_runtime_actions (organization_id, environment_id, agent_id, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_tool_runtime_actions_tool_created
    ON tool_runtime_actions (organization_id, environment_id, tool_id, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_tool_runtime_actions_decision_created
    ON tool_runtime_actions (organization_id, environment_id, decision_id, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_tool_runtime_actions_status_created
    ON tool_runtime_actions (organization_id, environment_id, action_status, created_at DESC, id DESC);

PRAGMA foreign_keys = ON;
