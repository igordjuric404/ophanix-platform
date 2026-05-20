ALTER TABLE runtime_sessions ADD COLUMN IF NOT EXISTS created_by_user_id TEXT;
ALTER TABLE runtime_sessions ADD COLUMN IF NOT EXISTS memory_scope TEXT NOT NULL DEFAULT 'session';
ALTER TABLE runtime_sessions ADD COLUMN IF NOT EXISTS thread_id TEXT;

CREATE TABLE IF NOT EXISTS runtime_runs (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    environment_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    thread_id TEXT NOT NULL,
    run_type TEXT NOT NULL,
    status TEXT NOT NULL,
    source_type TEXT,
    source_id TEXT,
    started_by_user_id TEXT,
    trace_id TEXT,
    span_id TEXT,
    parent_span_id TEXT,
    correlation_id TEXT,
    recovery_state_json TEXT NOT NULL DEFAULT '{}',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    started_at TEXT NOT NULL,
    ended_at TEXT,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES runtime_sessions(id)
);

CREATE INDEX IF NOT EXISTS idx_runtime_runs_session_started
    ON runtime_runs (session_id, started_at ASC, id ASC);

CREATE INDEX IF NOT EXISTS idx_runtime_runs_scope_started
    ON runtime_runs (organization_id, environment_id, started_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_runtime_runs_thread_started
    ON runtime_runs (organization_id, environment_id, thread_id, started_at DESC, id DESC);

CREATE TABLE IF NOT EXISTS runtime_run_steps (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    environment_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    parent_step_id TEXT,
    runtime_action_id TEXT,
    saga_id TEXT,
    saga_step_id TEXT,
    checkpoint_id TEXT,
    policy_decision_id TEXT,
    step_order INTEGER NOT NULL CHECK (step_order >= 1),
    step_type TEXT NOT NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL,
    trace_id TEXT,
    span_id TEXT,
    parent_span_id TEXT,
    correlation_id TEXT,
    artifact_links_json TEXT NOT NULL DEFAULT '[]',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    started_at TEXT NOT NULL,
    ended_at TEXT,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runtime_runs(id),
    FOREIGN KEY (session_id) REFERENCES runtime_sessions(id),
    FOREIGN KEY (runtime_action_id) REFERENCES runtime_actions(id),
    FOREIGN KEY (saga_id) REFERENCES sagas(id),
    FOREIGN KEY (saga_step_id) REFERENCES saga_steps(id),
    FOREIGN KEY (checkpoint_id) REFERENCES saga_checkpoints(id),
    FOREIGN KEY (policy_decision_id) REFERENCES runtime_ring_decisions(id)
);

CREATE INDEX IF NOT EXISTS idx_runtime_run_steps_run_order
    ON runtime_run_steps (run_id, step_order ASC, id ASC);

CREATE INDEX IF NOT EXISTS idx_runtime_run_steps_session_order
    ON runtime_run_steps (session_id, started_at ASC, id ASC);

CREATE INDEX IF NOT EXISTS idx_runtime_run_steps_runtime_action
    ON runtime_run_steps (runtime_action_id);
