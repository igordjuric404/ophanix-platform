DROP INDEX IF EXISTS idx_plugin_installations_target_agent;
DROP INDEX IF EXISTS idx_plugin_installations_version;
DROP INDEX IF EXISTS idx_plugin_installations_environment_status;
DROP TABLE IF EXISTS plugin_installations;

DELETE FROM schema_migrations WHERE version = '0025';
