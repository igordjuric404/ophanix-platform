CREATE TABLE IF NOT EXISTS saga_checkpoints (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    environment_id TEXT NOT NULL,
    saga_id TEXT NOT NULL,
    step_id TEXT NOT NULL,
    runtime_session_id TEXT,
    checkpoint_key TEXT NOT NULL UNIQUE,
    mode TEXT NOT NULL CHECK (mode IN ('execute', 'compensation')),
    schema_version TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'valid' CHECK (status IN ('valid', 'invalidated')),
    payload_json TEXT NOT NULL DEFAULT '{}',
    policy_snapshot_json TEXT NOT NULL DEFAULT '{}',
    tool_calls_json TEXT NOT NULL DEFAULT '[]',
    error_json TEXT NOT NULL DEFAULT '{}',
    payload_hash TEXT NOT NULL,
    hash_algorithm TEXT NOT NULL DEFAULT 'sha256',
    restored_at TEXT,
    invalidated_reason TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (saga_id) REFERENCES sagas(id),
    FOREIGN KEY (step_id) REFERENCES saga_steps(id),
    UNIQUE (saga_id, step_id, mode)
);

CREATE INDEX IF NOT EXISTS idx_saga_checkpoints_tenant_created
    ON saga_checkpoints (organization_id, environment_id, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_saga_checkpoints_saga_created
    ON saga_checkpoints (saga_id, created_at ASC, id ASC);

CREATE INDEX IF NOT EXISTS idx_saga_checkpoints_step_mode
    ON saga_checkpoints (step_id, mode);
