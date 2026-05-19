ALTER TABLE audit_exports
DROP COLUMN IF EXISTS chain_proof_json;

ALTER TABLE audit_exports
DROP COLUMN IF EXISTS completeness_reason;

ALTER TABLE audit_exports
DROP COLUMN IF EXISTS complete;

ALTER TABLE audit_exports
DROP COLUMN IF EXISTS event_count;
