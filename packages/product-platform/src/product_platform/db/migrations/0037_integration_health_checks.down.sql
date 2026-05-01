DROP INDEX IF EXISTS idx_integration_health_scope_status;
DROP INDEX IF EXISTS idx_integration_health_scope_target_checked;
DROP TABLE IF EXISTS integration_health_checks;

DELETE FROM schema_migrations WHERE version = '0037';
