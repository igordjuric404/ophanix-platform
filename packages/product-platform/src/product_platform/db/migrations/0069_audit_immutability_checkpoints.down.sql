DROP TRIGGER IF EXISTS trg_audit_hash_checkpoints_append_only ON audit_hash_checkpoints;
DROP TRIGGER IF EXISTS trg_audit_event_hashes_append_only ON audit_event_hashes;
DROP TRIGGER IF EXISTS trg_audit_events_append_only ON audit_events;
DROP FUNCTION IF EXISTS prevent_audit_trail_mutation();
DROP TABLE IF EXISTS audit_hash_checkpoints;
