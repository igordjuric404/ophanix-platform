CREATE TABLE IF NOT EXISTS tool_delegation_requirements (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    environment_id TEXT NOT NULL,
    tool_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    required_scopes_json TEXT NOT NULL,
    approval_required INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (environment_id) REFERENCES environments(id),
    FOREIGN KEY (tool_id) REFERENCES tool_definitions(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_tool_delegation_requirements_active_tool
    ON tool_delegation_requirements (organization_id, environment_id, tool_id)
    WHERE status = 'active';

CREATE INDEX IF NOT EXISTS idx_tool_delegation_requirements_status
    ON tool_delegation_requirements (organization_id, environment_id, status, updated_at DESC);

CREATE TABLE IF NOT EXISTS tool_delegated_authorizations (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    environment_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    tool_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    provider_account_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    scopes_json TEXT NOT NULL,
    status TEXT NOT NULL,
    approval_state TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (environment_id) REFERENCES environments(id),
    FOREIGN KEY (agent_id) REFERENCES agents(id),
    FOREIGN KEY (tool_id) REFERENCES tool_definitions(id)
);

CREATE INDEX IF NOT EXISTS idx_tool_delegated_authorizations_lookup
    ON tool_delegated_authorizations (
        organization_id,
        environment_id,
        agent_id,
        tool_id,
        user_id,
        provider_account_id,
        provider,
        status,
        expires_at DESC
    );

CREATE TABLE IF NOT EXISTS tool_oauth_authorization_sessions (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    environment_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    credential_id TEXT NOT NULL,
    tool_id TEXT NOT NULL,
    user_id TEXT,
    provider_account_id TEXT,
    provider TEXT NOT NULL,
    required_scopes_json TEXT NOT NULL,
    status TEXT NOT NULL,
    approval_state TEXT NOT NULL,
    authorization_url TEXT NOT NULL,
    reason_code TEXT NOT NULL,
    expires_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (environment_id) REFERENCES environments(id),
    FOREIGN KEY (agent_id) REFERENCES agents(id),
    FOREIGN KEY (credential_id) REFERENCES agent_credentials(id),
    FOREIGN KEY (tool_id) REFERENCES tool_definitions(id)
);

CREATE INDEX IF NOT EXISTS idx_tool_oauth_authorization_sessions_lookup
    ON tool_oauth_authorization_sessions (
        organization_id,
        environment_id,
        agent_id,
        credential_id,
        id
    );

ALTER TABLE tool_policy_decisions
ADD COLUMN IF NOT EXISTS delegated_user_id TEXT;

ALTER TABLE tool_policy_decisions
ADD COLUMN IF NOT EXISTS provider_account_id TEXT;

ALTER TABLE tool_policy_decisions
ADD COLUMN IF NOT EXISTS approval_state TEXT;

ALTER TABLE tool_policy_decisions
ADD COLUMN IF NOT EXISTS authorization_session_id TEXT;

CREATE INDEX IF NOT EXISTS idx_tool_policy_decisions_authorization_session
    ON tool_policy_decisions (organization_id, environment_id, authorization_session_id)
    WHERE authorization_session_id IS NOT NULL;

ALTER TABLE tool_runtime_actions
ADD COLUMN IF NOT EXISTS delegated_user_id TEXT;

ALTER TABLE tool_runtime_actions
ADD COLUMN IF NOT EXISTS provider_account_id TEXT;

ALTER TABLE tool_runtime_actions
ADD COLUMN IF NOT EXISTS approval_state TEXT;

ALTER TABLE tool_runtime_actions
ADD COLUMN IF NOT EXISTS authorization_session_id TEXT;

CREATE INDEX IF NOT EXISTS idx_tool_runtime_actions_authorization_session
    ON tool_runtime_actions (organization_id, environment_id, authorization_session_id)
    WHERE authorization_session_id IS NOT NULL;
