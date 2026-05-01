DROP INDEX IF EXISTS idx_rollout_events_rollout_created;
DROP TABLE IF EXISTS rollout_events;

DROP INDEX IF EXISTS idx_rollouts_target;
DROP INDEX IF EXISTS idx_rollouts_scope_status;
DROP TABLE IF EXISTS rollouts;

DELETE FROM schema_migrations WHERE version = '0032';
