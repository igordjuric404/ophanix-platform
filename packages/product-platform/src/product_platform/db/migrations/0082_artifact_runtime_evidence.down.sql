DROP INDEX IF EXISTS idx_artifact_links_runtime_targets;
DROP INDEX IF EXISTS idx_artifact_links_artifact_target;

ALTER TABLE artifact_attestations DROP COLUMN IF EXISTS signer_user_id;
ALTER TABLE artifact_attestations DROP COLUMN IF EXISTS digest_algorithm;
ALTER TABLE artifact_attestations DROP COLUMN IF EXISTS artifact_checksum;

ALTER TABLE artifacts DROP COLUMN IF EXISTS provenance_json;
ALTER TABLE artifacts DROP COLUMN IF EXISTS redaction_classification;
ALTER TABLE artifacts DROP COLUMN IF EXISTS retention_policy;
ALTER TABLE artifacts DROP COLUMN IF EXISTS digest_algorithm;

DELETE FROM schema_migrations WHERE version = '0082';
