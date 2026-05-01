DROP INDEX IF EXISTS idx_plugin_versions_signature;
DROP INDEX IF EXISTS idx_plugin_versions_plugin_created;
DROP TABLE IF EXISTS plugin_versions;

DROP INDEX IF EXISTS idx_plugins_org_type;
DROP INDEX IF EXISTS idx_plugins_org_status;
DROP TABLE IF EXISTS plugins;

DELETE FROM schema_migrations WHERE version = '0023';
