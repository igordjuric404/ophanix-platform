ALTER TABLE workflow_runs ADD COLUMN workflow_definition_id TEXT;
ALTER TABLE workflow_runs ADD COLUMN inputs_json TEXT;
ALTER TABLE workflow_runs ADD COLUMN started_by TEXT;
ALTER TABLE workflow_runs ADD COLUMN started_at TEXT;
ALTER TABLE workflow_runs ADD COLUMN finished_at TEXT;
ALTER TABLE workflow_runs ADD COLUMN exit_code INTEGER;
ALTER TABLE workflow_runs ADD COLUMN summary_json TEXT;

UPDATE workflow_runs
SET workflow_definition_id = COALESCE(workflow_definition_id, workflow_type),
    inputs_json = COALESCE(inputs_json, payload_json),
    summary_json = COALESCE(summary_json, '{}');

CREATE TABLE IF NOT EXISTS workflow_logs (
    id TEXT PRIMARY KEY,
    workflow_run_id TEXT NOT NULL,
    stream TEXT NOT NULL,
    line_number INTEGER NOT NULL,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (workflow_run_id) REFERENCES workflow_runs(id)
);

CREATE INDEX IF NOT EXISTS idx_workflow_runs_org_env_status
    ON workflow_runs (organization_id, environment_id, status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_workflow_logs_run_line
    ON workflow_logs (workflow_run_id, line_number);
