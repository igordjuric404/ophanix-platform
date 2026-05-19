ALTER TABLE control_mappings
ADD COLUMN IF NOT EXISTS mapping_version TEXT NOT NULL DEFAULT 'v1';

ALTER TABLE evidence_items
ADD COLUMN IF NOT EXISTS source_event_hash TEXT;

ALTER TABLE evidence_items
ADD COLUMN IF NOT EXISTS source_event_previous_hash TEXT;

ALTER TABLE evidence_items
ADD COLUMN IF NOT EXISTS source_event_hash_algorithm TEXT;

ALTER TABLE evidence_items
ADD COLUMN IF NOT EXISTS source_event_created_at TEXT;

ALTER TABLE evidence_items
ADD COLUMN IF NOT EXISTS control_mapping_id TEXT;

ALTER TABLE evidence_items
ADD COLUMN IF NOT EXISTS control_mapping_version TEXT NOT NULL DEFAULT 'v1';

ALTER TABLE evidence_items
ADD COLUMN IF NOT EXISTS predicate_snapshot_json TEXT NOT NULL DEFAULT '{}';

ALTER TABLE evidence_items
ADD COLUMN IF NOT EXISTS source_manifest_json TEXT NOT NULL DEFAULT '{}';

ALTER TABLE evidence_items
ADD COLUMN IF NOT EXISTS trace_id TEXT;

ALTER TABLE evidence_items
ADD COLUMN IF NOT EXISTS run_id TEXT;

ALTER TABLE evidence_items
ADD COLUMN IF NOT EXISTS tool_id TEXT;

ALTER TABLE evidence_items
ADD COLUMN IF NOT EXISTS policy_id TEXT;

ALTER TABLE evidence_items
ADD COLUMN IF NOT EXISTS policy_version_id TEXT;

ALTER TABLE evidence_items
ADD COLUMN IF NOT EXISTS artifact_checksum TEXT;

ALTER TABLE evidence_items
ADD COLUMN IF NOT EXISTS chain_proof_json TEXT NOT NULL DEFAULT '{}';

CREATE TABLE IF NOT EXISTS compliance_recompute_runs (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    environment_id TEXT NOT NULL,
    status TEXT NOT NULL,
    scanned_event_count INTEGER NOT NULL,
    evidence_count INTEGER NOT NULL,
    refreshed_count INTEGER NOT NULL,
    runtime_action_count INTEGER NOT NULL DEFAULT 0,
    complete INTEGER NOT NULL,
    cursor_json TEXT NOT NULL,
    source_range_json TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (environment_id) REFERENCES environments(id)
);

CREATE INDEX IF NOT EXISTS idx_compliance_recompute_runs_scope_created
    ON compliance_recompute_runs (organization_id, environment_id, completed_at DESC, id DESC);
