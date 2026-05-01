DROP INDEX IF EXISTS idx_demo_reset_runs_org_env_status;
DROP INDEX IF EXISTS idx_demo_reset_runs_org_env_started;
DROP TABLE IF EXISTS demo_reset_runs;

DELETE FROM schema_migrations WHERE version = '0041';
