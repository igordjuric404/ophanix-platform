DROP INDEX IF EXISTS idx_saga_activity_results_key;
DROP INDEX IF EXISTS idx_saga_activity_results_step_mode;
DROP INDEX IF EXISTS idx_saga_activity_results_saga_created;
DROP TABLE IF EXISTS saga_activity_results;
DELETE FROM schema_migrations WHERE version = '0088';
