DROP INDEX IF EXISTS idx_background_jobs_worker_heartbeat;
DROP INDEX IF EXISTS idx_background_jobs_lease_recovery;
DROP INDEX IF EXISTS idx_background_jobs_claim_queue;

ALTER TABLE background_jobs DROP COLUMN IF EXISTS concurrency_key;
ALTER TABLE background_jobs DROP COLUMN IF EXISTS heartbeat_at;
ALTER TABLE background_jobs DROP COLUMN IF EXISTS claimed_by;
ALTER TABLE background_jobs DROP COLUMN IF EXISTS lease_until;
ALTER TABLE background_jobs DROP COLUMN IF EXISTS priority;
ALTER TABLE background_jobs DROP COLUMN IF EXISTS queue_name;

DELETE FROM schema_migrations WHERE version = '0092';
