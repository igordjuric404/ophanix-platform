DROP INDEX IF EXISTS idx_saga_activity_attempts_status;
DROP INDEX IF EXISTS idx_saga_activity_attempts_worker_job;
DROP INDEX IF EXISTS idx_saga_activity_attempts_idempotency;
DROP INDEX IF EXISTS idx_saga_activity_attempts_activity;
DROP TABLE IF EXISTS saga_activity_attempts;

DROP INDEX IF EXISTS idx_saga_activity_results_repair_status;
DROP INDEX IF EXISTS idx_saga_activity_results_worker_job;
DROP INDEX IF EXISTS idx_saga_activity_results_idempotency;

ALTER TABLE saga_activity_results DROP COLUMN IF EXISTS repair_reason;
ALTER TABLE saga_activity_results DROP COLUMN IF EXISTS repair_status;
ALTER TABLE saga_activity_results DROP COLUMN IF EXISTS side_effect_completed_at;
ALTER TABLE saga_activity_results DROP COLUMN IF EXISTS side_effect_started_at;
ALTER TABLE saga_activity_results DROP COLUMN IF EXISTS lease_expires_at;
ALTER TABLE saga_activity_results DROP COLUMN IF EXISTS lease_owner;
ALTER TABLE saga_activity_results DROP COLUMN IF EXISTS worker_job_id;
ALTER TABLE saga_activity_results DROP COLUMN IF EXISTS external_operation_id;
ALTER TABLE saga_activity_results DROP COLUMN IF EXISTS idempotency_key;
