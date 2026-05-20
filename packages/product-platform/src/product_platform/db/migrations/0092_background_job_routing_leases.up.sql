ALTER TABLE background_jobs ADD COLUMN IF NOT EXISTS queue_name TEXT NOT NULL DEFAULT 'default';
ALTER TABLE background_jobs ADD COLUMN IF NOT EXISTS priority INTEGER NOT NULL DEFAULT 0;
ALTER TABLE background_jobs ADD COLUMN IF NOT EXISTS lease_until TEXT;
ALTER TABLE background_jobs ADD COLUMN IF NOT EXISTS claimed_by TEXT;
ALTER TABLE background_jobs ADD COLUMN IF NOT EXISTS heartbeat_at TEXT;
ALTER TABLE background_jobs ADD COLUMN IF NOT EXISTS concurrency_key TEXT;

CREATE INDEX IF NOT EXISTS idx_background_jobs_claim_queue
    ON background_jobs (
        status,
        queue_name,
        priority DESC,
        scheduled_at ASC,
        created_at ASC,
        id ASC
    );

CREATE INDEX IF NOT EXISTS idx_background_jobs_lease_recovery
    ON background_jobs (status, lease_until, queue_name);

CREATE INDEX IF NOT EXISTS idx_background_jobs_worker_heartbeat
    ON background_jobs (claimed_by, heartbeat_at DESC);
