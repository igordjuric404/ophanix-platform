CREATE TABLE IF NOT EXISTS tool_definitions (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    environment_id TEXT NOT NULL,
    name TEXT NOT NULL,
    display_name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    owner_team TEXT NOT NULL,
    status TEXT NOT NULL,
    required_scope TEXT NOT NULL,
    input_schema_json TEXT,
    output_schema_json TEXT,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (environment_id) REFERENCES environments(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_tool_definitions_org_env_name_open
    ON tool_definitions (organization_id, environment_id, lower(name))
    WHERE status IN ('draft', 'active', 'disabled');

CREATE INDEX IF NOT EXISTS idx_tool_definitions_org_env_status
    ON tool_definitions (organization_id, environment_id, status, updated_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_tool_definitions_org_env_owner
    ON tool_definitions (organization_id, environment_id, owner_team, updated_at DESC, id DESC);

CREATE TABLE IF NOT EXISTS tool_definition_versions (
    id TEXT PRIMARY KEY,
    tool_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    input_schema_json TEXT,
    output_schema_json TEXT,
    required_scope TEXT NOT NULL,
    change_summary TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (tool_id) REFERENCES tool_definitions(id) ON DELETE CASCADE,
    UNIQUE (tool_id, version)
);

CREATE INDEX IF NOT EXISTS idx_tool_definition_versions_tool_version
    ON tool_definition_versions (tool_id, version DESC, id DESC);
