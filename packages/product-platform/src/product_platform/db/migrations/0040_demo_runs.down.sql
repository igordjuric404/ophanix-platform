DROP INDEX IF EXISTS idx_demo_step_runs_run_status;
DROP INDEX IF EXISTS idx_demo_step_runs_run_step;
DROP TABLE IF EXISTS demo_step_runs;

DROP INDEX IF EXISTS idx_demo_runs_scenario;
DROP INDEX IF EXISTS idx_demo_runs_org_env_status;
DROP TABLE IF EXISTS demo_runs;

DELETE FROM schema_migrations WHERE version = '0040';
