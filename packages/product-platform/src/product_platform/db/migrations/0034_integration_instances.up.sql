CREATE TABLE IF NOT EXISTS integration_instances (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    environment_id TEXT NOT NULL REFERENCES environments(id) ON DELETE CASCADE,
    integration_id TEXT NOT NULL REFERENCES integrations(id) ON DELETE RESTRICT,
    name TEXT NOT NULL,
    config_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_integration_instances_scope_status
    ON integration_instances (organization_id, environment_id, status, updated_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_integration_instances_integration
    ON integration_instances (integration_id, organization_id, environment_id);
