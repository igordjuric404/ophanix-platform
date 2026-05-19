ALTER TABLE slo_measurements ADD COLUMN source TEXT NOT NULL DEFAULT 'manual';
ALTER TABLE slo_measurements ADD COLUMN source_resource_type TEXT;
ALTER TABLE slo_measurements ADD COLUMN source_resource_id TEXT;
ALTER TABLE slo_measurements ADD COLUMN trace_id TEXT;

CREATE INDEX IF NOT EXISTS idx_slo_measurements_source
    ON slo_measurements (source, source_resource_type, source_resource_id);

CREATE INDEX IF NOT EXISTS idx_slo_measurements_trace
    ON slo_measurements (trace_id, measured_at DESC, id DESC);

ALTER TABLE cost_events ADD COLUMN source TEXT NOT NULL DEFAULT 'manual';
ALTER TABLE cost_events ADD COLUMN source_resource_type TEXT;
ALTER TABLE cost_events ADD COLUMN source_resource_id TEXT;
ALTER TABLE cost_events ADD COLUMN trace_id TEXT;

CREATE INDEX IF NOT EXISTS idx_cost_events_source
    ON cost_events (organization_id, environment_id, source, source_resource_type, source_resource_id);

CREATE INDEX IF NOT EXISTS idx_cost_events_trace
    ON cost_events (organization_id, environment_id, trace_id, created_at DESC, id DESC);

ALTER TABLE incidents ADD COLUMN source TEXT NOT NULL DEFAULT 'manual';
ALTER TABLE incidents ADD COLUMN source_resource_type TEXT;
ALTER TABLE incidents ADD COLUMN source_resource_id TEXT;
ALTER TABLE incidents ADD COLUMN trace_id TEXT;

CREATE INDEX IF NOT EXISTS idx_incidents_source
    ON incidents (organization_id, environment_id, source, source_resource_type, source_resource_id);

CREATE INDEX IF NOT EXISTS idx_incidents_trace
    ON incidents (organization_id, environment_id, trace_id, started_at DESC, id DESC);
