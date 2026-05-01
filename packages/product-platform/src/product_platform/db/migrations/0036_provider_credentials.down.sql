DROP INDEX IF EXISTS idx_provider_credentials_org_secret_ref;
DROP INDEX IF EXISTS idx_provider_credentials_org_type_status;
DROP TABLE IF EXISTS provider_credentials;

DELETE FROM schema_migrations WHERE version = '0036';
