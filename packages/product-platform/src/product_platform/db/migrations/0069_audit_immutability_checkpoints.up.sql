CREATE TABLE IF NOT EXISTS audit_hash_checkpoints (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    environment_id TEXT,
    start_event_id TEXT,
    end_event_id TEXT,
    event_count INTEGER NOT NULL,
    first_hash TEXT,
    last_hash TEXT,
    algorithm TEXT NOT NULL,
    scope_json TEXT NOT NULL,
    proof_json TEXT NOT NULL,
    signature TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (environment_id) REFERENCES environments(id)
);

CREATE INDEX IF NOT EXISTS idx_audit_hash_checkpoints_scope_created
    ON audit_hash_checkpoints (organization_id, environment_id, created_at DESC, id DESC);

CREATE OR REPLACE FUNCTION prevent_audit_trail_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS '
BEGIN
    RAISE EXCEPTION ''audit trail is append-only: %% on %% is not allowed'', TG_OP, TG_TABLE_NAME
        USING ERRCODE = ''integrity_constraint_violation'';
END;
';

DROP TRIGGER IF EXISTS trg_audit_events_append_only ON audit_events;
CREATE TRIGGER trg_audit_events_append_only
BEFORE UPDATE OR DELETE ON audit_events
FOR EACH ROW EXECUTE FUNCTION prevent_audit_trail_mutation();

DROP TRIGGER IF EXISTS trg_audit_event_hashes_append_only ON audit_event_hashes;
CREATE TRIGGER trg_audit_event_hashes_append_only
BEFORE UPDATE OR DELETE ON audit_event_hashes
FOR EACH ROW EXECUTE FUNCTION prevent_audit_trail_mutation();

DROP TRIGGER IF EXISTS trg_audit_hash_checkpoints_append_only ON audit_hash_checkpoints;
CREATE TRIGGER trg_audit_hash_checkpoints_append_only
BEFORE UPDATE OR DELETE ON audit_hash_checkpoints
FOR EACH ROW EXECUTE FUNCTION prevent_audit_trail_mutation();
