CREATE TABLE IF NOT EXISTS plugins (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    publisher TEXT NOT NULL,
    plugin_type TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (organization_id, name, publisher)
);

CREATE INDEX IF NOT EXISTS idx_plugins_org_status
    ON plugins (organization_id, status);

CREATE INDEX IF NOT EXISTS idx_plugins_org_type
    ON plugins (organization_id, plugin_type);

CREATE TABLE IF NOT EXISTS plugin_versions (
    id TEXT PRIMARY KEY,
    plugin_id TEXT NOT NULL REFERENCES plugins(id) ON DELETE CASCADE,
    version TEXT NOT NULL,
    manifest_json TEXT NOT NULL,
    package_ref TEXT NOT NULL,
    signature_status TEXT NOT NULL,
    quality_score REAL NOT NULL DEFAULT 0,
    trust_tier TEXT NOT NULL DEFAULT 'unrated',
    required_capabilities_json TEXT NOT NULL DEFAULT '[]',
    permissions_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (plugin_id, version)
);

CREATE INDEX IF NOT EXISTS idx_plugin_versions_plugin_created
    ON plugin_versions (plugin_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_plugin_versions_signature
    ON plugin_versions (signature_status);
