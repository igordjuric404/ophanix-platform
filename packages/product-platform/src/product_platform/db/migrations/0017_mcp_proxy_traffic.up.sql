CREATE TABLE IF NOT EXISTS mcp_tool_calls (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    environment_id TEXT NOT NULL,
    server_id TEXT NOT NULL,
    tool_id TEXT NOT NULL,
    source_agent_id TEXT NOT NULL,
    params_summary_json TEXT NOT NULL,
    decision TEXT NOT NULL,
    reason TEXT NOT NULL,
    matched_policy_id TEXT,
    matched_policy_version_id TEXT,
    trust_threshold_id TEXT,
    trust_score INTEGER,
    gateway_stage TEXT,
    response_json TEXT,
    sanitizer_action TEXT,
    latency_ms INTEGER NOT NULL,
    correlation_id TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (environment_id) REFERENCES environments(id),
    FOREIGN KEY (server_id) REFERENCES mcp_servers(id),
    FOREIGN KEY (tool_id) REFERENCES mcp_tools(id),
    FOREIGN KEY (source_agent_id) REFERENCES agents(id)
);

CREATE INDEX IF NOT EXISTS idx_mcp_tool_calls_org_env_created
    ON mcp_tool_calls (organization_id, environment_id, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_mcp_tool_calls_decision_created
    ON mcp_tool_calls (organization_id, environment_id, decision, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_mcp_tool_calls_tool_created
    ON mcp_tool_calls (tool_id, created_at DESC, id DESC);

CREATE TABLE IF NOT EXISTS mcp_approvals (
    id TEXT PRIMARY KEY,
    tool_call_id TEXT NOT NULL,
    status TEXT NOT NULL,
    requested_by_agent_id TEXT NOT NULL,
    approved_by_user_id TEXT,
    decision_reason TEXT,
    requested_at TEXT NOT NULL,
    decided_at TEXT,
    FOREIGN KEY (tool_call_id) REFERENCES mcp_tool_calls(id),
    FOREIGN KEY (requested_by_agent_id) REFERENCES agents(id)
);

CREATE INDEX IF NOT EXISTS idx_mcp_approvals_status_requested
    ON mcp_approvals (status, requested_at DESC, id DESC);

CREATE TABLE IF NOT EXISTS mcp_rate_limits (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    environment_id TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    window_seconds INTEGER NOT NULL,
    max_calls INTEGER NOT NULL,
    enabled INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (environment_id) REFERENCES environments(id)
);

CREATE INDEX IF NOT EXISTS idx_mcp_rate_limits_target
    ON mcp_rate_limits (organization_id, environment_id, target_type, target_id, enabled);
