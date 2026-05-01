DROP INDEX IF EXISTS idx_plugin_policy_results_result;
DROP INDEX IF EXISTS idx_plugin_policy_results_version_created;
DROP TABLE IF EXISTS plugin_policy_results;

DELETE FROM schema_migrations WHERE version = '0024';
