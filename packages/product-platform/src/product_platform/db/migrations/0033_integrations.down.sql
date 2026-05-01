DROP INDEX IF EXISTS idx_integrations_type_status;
DROP INDEX IF EXISTS idx_integrations_type_id;
DROP TABLE IF EXISTS integrations;

DELETE FROM schema_migrations WHERE version = '0033';
