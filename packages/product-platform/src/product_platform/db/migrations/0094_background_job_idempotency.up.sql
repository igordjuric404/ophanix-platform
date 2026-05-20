ALTER TABLE background_jobs ADD COLUMN IF NOT EXISTS idempotency_key TEXT;
ALTER TABLE background_jobs ADD COLUMN IF NOT EXISTS operation_type TEXT;
ALTER TABLE background_jobs ADD COLUMN IF NOT EXISTS operation_id TEXT;
ALTER TABLE background_jobs ADD COLUMN IF NOT EXISTS idempotency_payload_hash TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS idx_background_jobs_idempotency_key
    ON background_jobs (organization_id, environment_id, job_type, idempotency_key)
    WHERE idempotency_key IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_background_jobs_operation_identity
    ON background_jobs (organization_id, environment_id, job_type, operation_type, operation_id)
    WHERE operation_type IS NOT NULL AND operation_id IS NOT NULL;
