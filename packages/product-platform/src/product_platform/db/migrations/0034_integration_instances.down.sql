DROP INDEX IF EXISTS idx_integration_instances_integration;
DROP INDEX IF EXISTS idx_integration_instances_scope_status;
DROP TABLE IF EXISTS integration_instances;

DELETE FROM schema_migrations WHERE version = '0034';
