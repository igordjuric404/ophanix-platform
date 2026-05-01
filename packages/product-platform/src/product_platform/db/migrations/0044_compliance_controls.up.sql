CREATE TABLE IF NOT EXISTS control_frameworks (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    description TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (organization_id, name, version),
    FOREIGN KEY (organization_id) REFERENCES organizations(id)
);

CREATE TABLE IF NOT EXISTS controls (
    id TEXT PRIMARY KEY,
    framework_id TEXT NOT NULL,
    control_code TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    required_evidence_types_json TEXT NOT NULL,
    owner_user_id TEXT,
    UNIQUE (framework_id, control_code),
    FOREIGN KEY (framework_id) REFERENCES control_frameworks(id)
);

CREATE TABLE IF NOT EXISTS control_mappings (
    id TEXT PRIMARY KEY,
    control_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    source_component TEXT,
    predicate_json TEXT NOT NULL,
    evidence_type TEXT NOT NULL,
    UNIQUE (control_id, event_type, source_component, evidence_type),
    FOREIGN KEY (control_id) REFERENCES controls(id)
);

CREATE TABLE IF NOT EXISTS evidence_items (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    environment_id TEXT NOT NULL,
    control_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    freshness_at TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (organization_id, environment_id, control_id, source_type, source_id),
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (environment_id) REFERENCES environments(id),
    FOREIGN KEY (control_id) REFERENCES controls(id)
);

CREATE INDEX IF NOT EXISTS idx_controls_framework
    ON controls (framework_id, control_code);

CREATE INDEX IF NOT EXISTS idx_control_mappings_event
    ON control_mappings (event_type, source_component);

CREATE INDEX IF NOT EXISTS idx_evidence_items_scope
    ON evidence_items (organization_id, environment_id, status, freshness_at DESC);
