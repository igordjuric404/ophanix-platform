DROP INDEX IF EXISTS idx_runtime_ring_decisions_result_created;
DROP INDEX IF EXISTS idx_runtime_ring_decisions_action;
DROP TABLE IF EXISTS runtime_ring_decisions;
DELETE FROM schema_migrations WHERE version = '0019';
