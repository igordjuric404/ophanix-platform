DROP INDEX IF EXISTS idx_chaos_experiments_target;
DROP INDEX IF EXISTS idx_chaos_experiments_scope_status;
DROP TABLE IF EXISTS chaos_experiments;

DELETE FROM schema_migrations WHERE version = '0030';
