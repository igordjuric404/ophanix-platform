DROP INDEX IF EXISTS idx_background_jobs_operation_identity;
DROP INDEX IF EXISTS idx_background_jobs_idempotency_key;

ALTER TABLE background_jobs DROP COLUMN IF EXISTS idempotency_payload_hash;
ALTER TABLE background_jobs DROP COLUMN IF EXISTS operation_id;
ALTER TABLE background_jobs DROP COLUMN IF EXISTS operation_type;
ALTER TABLE background_jobs DROP COLUMN IF EXISTS idempotency_key;

DELETE FROM schema_migrations WHERE version = '0094';
