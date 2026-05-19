DROP INDEX IF EXISTS idx_incidents_trace;
DROP INDEX IF EXISTS idx_incidents_source;
DROP INDEX IF EXISTS idx_cost_events_trace;
DROP INDEX IF EXISTS idx_cost_events_source;
DROP INDEX IF EXISTS idx_slo_measurements_trace;
DROP INDEX IF EXISTS idx_slo_measurements_source;

ALTER TABLE incidents DROP COLUMN IF EXISTS trace_id;
ALTER TABLE incidents DROP COLUMN IF EXISTS source_resource_id;
ALTER TABLE incidents DROP COLUMN IF EXISTS source_resource_type;
ALTER TABLE incidents DROP COLUMN IF EXISTS source;

ALTER TABLE cost_events DROP COLUMN IF EXISTS trace_id;
ALTER TABLE cost_events DROP COLUMN IF EXISTS source_resource_id;
ALTER TABLE cost_events DROP COLUMN IF EXISTS source_resource_type;
ALTER TABLE cost_events DROP COLUMN IF EXISTS source;

ALTER TABLE slo_measurements DROP COLUMN IF EXISTS trace_id;
ALTER TABLE slo_measurements DROP COLUMN IF EXISTS source_resource_id;
ALTER TABLE slo_measurements DROP COLUMN IF EXISTS source_resource_type;
ALTER TABLE slo_measurements DROP COLUMN IF EXISTS source;
