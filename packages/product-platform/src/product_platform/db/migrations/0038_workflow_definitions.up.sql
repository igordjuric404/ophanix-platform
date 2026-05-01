CREATE TABLE IF NOT EXISTS workflow_definitions (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    name TEXT NOT NULL,
    workflow_type TEXT NOT NULL,
    command_ref TEXT NOT NULL,
    input_schema_json TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_workflow_definitions_org_command
ON workflow_definitions (organization_id, command_ref);

CREATE INDEX IF NOT EXISTS idx_workflow_definitions_org_enabled
ON workflow_definitions (organization_id, enabled, workflow_type);
