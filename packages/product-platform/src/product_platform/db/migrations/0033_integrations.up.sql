CREATE TABLE IF NOT EXISTS integrations (
    id TEXT PRIMARY KEY,
    integration_type TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    status TEXT NOT NULL,
    supported_versions_json TEXT NOT NULL DEFAULT '[]',
    setup_doc_url TEXT,
    example_path TEXT,
    setup_snippet TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_integrations_type_id
    ON integrations (integration_type, id);

CREATE INDEX IF NOT EXISTS idx_integrations_type_status
    ON integrations (integration_type, status, name);
