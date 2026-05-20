ALTER TABLE saga_activity_results ADD COLUMN IF NOT EXISTS idempotency_key TEXT;
ALTER TABLE saga_activity_results ADD COLUMN IF NOT EXISTS external_operation_id TEXT;
ALTER TABLE saga_activity_results ADD COLUMN IF NOT EXISTS worker_job_id TEXT;
ALTER TABLE saga_activity_results ADD COLUMN IF NOT EXISTS lease_owner TEXT;
ALTER TABLE saga_activity_results ADD COLUMN IF NOT EXISTS lease_expires_at TEXT;
ALTER TABLE saga_activity_results ADD COLUMN IF NOT EXISTS side_effect_started_at TEXT;
ALTER TABLE saga_activity_results ADD COLUMN IF NOT EXISTS side_effect_completed_at TEXT;
ALTER TABLE saga_activity_results ADD COLUMN IF NOT EXISTS repair_status TEXT NOT NULL DEFAULT 'none'
    CHECK (repair_status IN ('none', 'required', 'approved', 'resolved'));
ALTER TABLE saga_activity_results ADD COLUMN IF NOT EXISTS repair_reason TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS idx_saga_activity_results_idempotency
    ON saga_activity_results (saga_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_saga_activity_results_worker_job
    ON saga_activity_results (worker_job_id)
    WHERE worker_job_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_saga_activity_results_repair_status
    ON saga_activity_results (saga_id, repair_status)
    WHERE repair_status <> 'none';

CREATE TABLE IF NOT EXISTS saga_activity_attempts (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    environment_id TEXT NOT NULL,
    saga_id TEXT NOT NULL,
    step_id TEXT NOT NULL,
    activity_result_id TEXT NOT NULL,
    activity_key TEXT NOT NULL,
    mode TEXT NOT NULL CHECK (mode IN ('execute', 'compensation')),
    action_name TEXT NOT NULL,
    attempt_number INTEGER NOT NULL CHECK (attempt_number >= 1),
    idempotency_key TEXT NOT NULL,
    external_operation_id TEXT,
    worker_job_id TEXT,
    status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'succeeded', 'failed', 'manual_repair')),
    lease_owner TEXT,
    lease_expires_at TEXT,
    side_effect_started_at TEXT,
    side_effect_completed_at TEXT,
    error_message TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (saga_id) REFERENCES sagas(id),
    FOREIGN KEY (step_id) REFERENCES saga_steps(id),
    FOREIGN KEY (activity_result_id) REFERENCES saga_activity_results(id),
    FOREIGN KEY (worker_job_id) REFERENCES background_jobs(id),
    UNIQUE (saga_id, step_id, mode, attempt_number)
);

CREATE INDEX IF NOT EXISTS idx_saga_activity_attempts_activity
    ON saga_activity_attempts (activity_result_id, attempt_number ASC);

CREATE INDEX IF NOT EXISTS idx_saga_activity_attempts_idempotency
    ON saga_activity_attempts (saga_id, idempotency_key);

CREATE INDEX IF NOT EXISTS idx_saga_activity_attempts_worker_job
    ON saga_activity_attempts (worker_job_id)
    WHERE worker_job_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_saga_activity_attempts_status
    ON saga_activity_attempts (organization_id, environment_id, status, updated_at DESC, id DESC);
