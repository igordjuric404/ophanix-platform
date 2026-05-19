CREATE TABLE IF NOT EXISTS tool_oauth_provider_apps (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    environment_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    client_id TEXT NOT NULL,
    authorization_url TEXT NOT NULL,
    token_url TEXT NOT NULL,
    redirect_url TEXT NOT NULL,
    scopes_json TEXT NOT NULL,
    client_secret_ref TEXT,
    status TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (environment_id) REFERENCES environments(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_tool_oauth_provider_apps_active_provider
    ON tool_oauth_provider_apps (organization_id, environment_id, provider)
    WHERE status = 'active';

CREATE INDEX IF NOT EXISTS idx_tool_oauth_provider_apps_status
    ON tool_oauth_provider_apps (organization_id, environment_id, status, updated_at DESC);

ALTER TABLE tool_oauth_authorization_sessions
ADD COLUMN IF NOT EXISTS oauth_app_id TEXT;

ALTER TABLE tool_oauth_authorization_sessions
ADD COLUMN IF NOT EXISTS delegated_authorization_id TEXT;

ALTER TABLE tool_oauth_authorization_sessions
ADD COLUMN IF NOT EXISTS completed_at TEXT;

CREATE INDEX IF NOT EXISTS idx_tool_oauth_authorization_sessions_app
    ON tool_oauth_authorization_sessions (organization_id, environment_id, oauth_app_id)
    WHERE oauth_app_id IS NOT NULL;

ALTER TABLE tool_delegated_authorizations
ADD COLUMN IF NOT EXISTS access_token_ref TEXT;

ALTER TABLE tool_delegated_authorizations
ADD COLUMN IF NOT EXISTS refresh_token_ref TEXT;

ALTER TABLE tool_delegated_authorizations
ADD COLUMN IF NOT EXISTS token_expires_at TEXT;

ALTER TABLE tool_delegated_authorizations
ADD COLUMN IF NOT EXISTS last_refreshed_at TEXT;

ALTER TABLE tool_delegated_authorizations
ADD COLUMN IF NOT EXISTS revoked_at TEXT;

ALTER TABLE tool_delegated_authorizations
ADD COLUMN IF NOT EXISTS revoked_reason TEXT;

CREATE INDEX IF NOT EXISTS idx_tool_delegated_authorizations_token_expiry
    ON tool_delegated_authorizations (organization_id, environment_id, status, token_expires_at);
