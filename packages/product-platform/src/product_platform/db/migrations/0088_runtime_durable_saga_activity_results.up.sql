CREATE TABLE IF NOT EXISTS saga_activity_results (
    id TEXT PRIMARY KEY,
    saga_id TEXT NOT NULL,
    step_id TEXT NOT NULL,
    activity_key TEXT NOT NULL,
    action_name TEXT NOT NULL,
    mode TEXT NOT NULL CHECK (mode IN ('execute', 'compensation')),
    status TEXT NOT NULL CHECK (status IN ('started', 'succeeded', 'failed')),
    attempt_count INTEGER NOT NULL DEFAULT 1 CHECK (attempt_count >= 1),
    result_json TEXT NOT NULL,
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (saga_id) REFERENCES sagas(id),
    FOREIGN KEY (step_id) REFERENCES saga_steps(id),
    UNIQUE (saga_id, step_id, mode)
);

CREATE INDEX IF NOT EXISTS idx_saga_activity_results_saga_created
    ON saga_activity_results (saga_id, created_at ASC, id ASC);

CREATE INDEX IF NOT EXISTS idx_saga_activity_results_step_mode
    ON saga_activity_results (step_id, mode);

CREATE INDEX IF NOT EXISTS idx_saga_activity_results_key
    ON saga_activity_results (activity_key);
