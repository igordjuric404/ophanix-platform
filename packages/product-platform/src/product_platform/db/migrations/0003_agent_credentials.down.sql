DROP INDEX IF EXISTS idx_credential_rotations_agent_created;
DROP TABLE IF EXISTS credential_rotations;
DROP INDEX IF EXISTS idx_credential_scopes_credential;
DROP TABLE IF EXISTS credential_scopes;
DROP INDEX IF EXISTS idx_agent_credentials_status_expiry;
DROP INDEX IF EXISTS idx_agent_credentials_agent_status;
DROP TABLE IF EXISTS agent_credentials;
DROP TABLE IF EXISTS credential_issuers;
DELETE FROM schema_migrations WHERE version = '0003';
