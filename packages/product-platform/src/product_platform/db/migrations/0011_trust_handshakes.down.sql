DROP INDEX IF EXISTS idx_handshake_events_result_created;
DROP INDEX IF EXISTS idx_handshake_events_target_created;
DROP INDEX IF EXISTS idx_handshake_events_source_created;
DROP TABLE IF EXISTS handshake_events;
DROP INDEX IF EXISTS idx_trust_thresholds_scope_type;
DROP TABLE IF EXISTS trust_thresholds;
DELETE FROM schema_migrations WHERE version = '0011';
