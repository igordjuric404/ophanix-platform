DROP INDEX IF EXISTS idx_policy_lint_results_version;
DROP TABLE IF EXISTS policy_lint_results;
DELETE FROM schema_migrations WHERE version = '0007';
