ALTER TABLE background_jobs ADD COLUMN IF NOT EXISTS retry_backoff_seconds INTEGER NOT NULL DEFAULT 0;
ALTER TABLE background_jobs ADD COLUMN IF NOT EXISTS next_retry_at TEXT;
ALTER TABLE background_jobs ADD COLUMN IF NOT EXISTS dead_lettered_at TEXT;
ALTER TABLE background_jobs ADD COLUMN IF NOT EXISTS dead_letter_reason TEXT;

CREATE INDEX IF NOT EXISTS idx_background_jobs_retry_schedule
    ON background_jobs (status, next_retry_at, scheduled_at);

CREATE INDEX IF NOT EXISTS idx_background_jobs_dead_lettered
    ON background_jobs (status, dead_lettered_at DESC);
