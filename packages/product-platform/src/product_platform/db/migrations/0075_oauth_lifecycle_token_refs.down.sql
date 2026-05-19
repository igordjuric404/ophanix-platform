DROP INDEX IF EXISTS idx_tool_delegated_authorizations_token_expiry;

ALTER TABLE tool_delegated_authorizations
DROP COLUMN IF EXISTS revoked_reason;

ALTER TABLE tool_delegated_authorizations
DROP COLUMN IF EXISTS revoked_at;

ALTER TABLE tool_delegated_authorizations
DROP COLUMN IF EXISTS last_refreshed_at;

ALTER TABLE tool_delegated_authorizations
DROP COLUMN IF EXISTS token_expires_at;

ALTER TABLE tool_delegated_authorizations
DROP COLUMN IF EXISTS refresh_token_ref;

ALTER TABLE tool_delegated_authorizations
DROP COLUMN IF EXISTS access_token_ref;

DROP INDEX IF EXISTS idx_tool_oauth_authorization_sessions_app;

ALTER TABLE tool_oauth_authorization_sessions
DROP COLUMN IF EXISTS completed_at;

ALTER TABLE tool_oauth_authorization_sessions
DROP COLUMN IF EXISTS delegated_authorization_id;

ALTER TABLE tool_oauth_authorization_sessions
DROP COLUMN IF EXISTS oauth_app_id;

DROP INDEX IF EXISTS idx_tool_oauth_provider_apps_status;
DROP INDEX IF EXISTS idx_tool_oauth_provider_apps_active_provider;
DROP TABLE IF EXISTS tool_oauth_provider_apps;
