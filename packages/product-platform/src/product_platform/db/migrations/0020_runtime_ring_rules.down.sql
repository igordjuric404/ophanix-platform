DROP INDEX IF EXISTS idx_runtime_ring_rules_pattern;
DROP INDEX IF EXISTS idx_runtime_ring_rules_scope_enabled;
DROP TABLE IF EXISTS runtime_ring_rules;
DELETE FROM schema_migrations WHERE version = '0020';
