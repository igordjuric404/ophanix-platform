DROP INDEX IF EXISTS idx_chaos_runs_status_started;
DROP INDEX IF EXISTS idx_chaos_runs_experiment_started;
DROP TABLE IF EXISTS chaos_runs;

DELETE FROM schema_migrations WHERE version = '0031';
