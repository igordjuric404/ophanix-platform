DROP INDEX IF EXISTS idx_slo_measurements_status;
DROP INDEX IF EXISTS idx_slo_measurements_slo_measured;
DROP TABLE IF EXISTS slo_measurements;

DROP INDEX IF EXISTS idx_slo_objectives_target;
DROP INDEX IF EXISTS idx_slo_objectives_scope_status;
DROP TABLE IF EXISTS slo_objectives;

DELETE FROM schema_migrations WHERE version = '0027';
