DROP INDEX IF EXISTS idx_background_jobs_dead_lettered;
DROP INDEX IF EXISTS idx_background_jobs_retry_schedule;

ALTER TABLE background_jobs DROP COLUMN IF EXISTS dead_letter_reason;
ALTER TABLE background_jobs DROP COLUMN IF EXISTS dead_lettered_at;
ALTER TABLE background_jobs DROP COLUMN IF EXISTS next_retry_at;
ALTER TABLE background_jobs DROP COLUMN IF EXISTS retry_backoff_seconds;

DELETE FROM schema_migrations WHERE version = '0093';
