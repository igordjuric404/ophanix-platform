DROP INDEX IF EXISTS idx_incidents_source_event;
DROP INDEX IF EXISTS idx_incidents_correlation;
DROP INDEX IF EXISTS idx_incidents_scope_status;
DROP TABLE IF EXISTS incidents;

DELETE FROM schema_migrations WHERE version = '0029';
