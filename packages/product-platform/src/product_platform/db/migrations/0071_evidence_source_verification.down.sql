DROP TABLE IF EXISTS compliance_recompute_runs;

ALTER TABLE evidence_items
DROP COLUMN IF EXISTS chain_proof_json;

ALTER TABLE evidence_items
DROP COLUMN IF EXISTS artifact_checksum;

ALTER TABLE evidence_items
DROP COLUMN IF EXISTS policy_version_id;

ALTER TABLE evidence_items
DROP COLUMN IF EXISTS policy_id;

ALTER TABLE evidence_items
DROP COLUMN IF EXISTS tool_id;

ALTER TABLE evidence_items
DROP COLUMN IF EXISTS run_id;

ALTER TABLE evidence_items
DROP COLUMN IF EXISTS trace_id;

ALTER TABLE evidence_items
DROP COLUMN IF EXISTS source_manifest_json;

ALTER TABLE evidence_items
DROP COLUMN IF EXISTS predicate_snapshot_json;

ALTER TABLE evidence_items
DROP COLUMN IF EXISTS control_mapping_version;

ALTER TABLE evidence_items
DROP COLUMN IF EXISTS control_mapping_id;

ALTER TABLE evidence_items
DROP COLUMN IF EXISTS source_event_created_at;

ALTER TABLE evidence_items
DROP COLUMN IF EXISTS source_event_hash_algorithm;

ALTER TABLE evidence_items
DROP COLUMN IF EXISTS source_event_previous_hash;

ALTER TABLE evidence_items
DROP COLUMN IF EXISTS source_event_hash;

ALTER TABLE control_mappings
DROP COLUMN IF EXISTS mapping_version;
