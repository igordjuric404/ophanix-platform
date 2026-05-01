CREATE TABLE IF NOT EXISTS sagas (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    environment_id TEXT NOT NULL,
    runtime_session_id TEXT,
    name TEXT NOT NULL,
    status TEXT NOT NULL,
    created_by TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    correlation_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (environment_id) REFERENCES environments(id),
    FOREIGN KEY (runtime_session_id) REFERENCES runtime_sessions(id)
);

CREATE INDEX IF NOT EXISTS idx_sagas_scope_created
    ON sagas (organization_id, environment_id, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_sagas_status_created
    ON sagas (organization_id, environment_id, status, created_at DESC, id DESC);

CREATE TABLE IF NOT EXISTS saga_steps (
    id TEXT PRIMARY KEY,
    saga_id TEXT NOT NULL,
    step_order INTEGER NOT NULL CHECK (step_order >= 1),
    name TEXT NOT NULL,
    action_name TEXT NOT NULL,
    target_agent_id TEXT NOT NULL,
    required_capability TEXT,
    timeout_seconds INTEGER NOT NULL CHECK (timeout_seconds >= 1),
    retry_count INTEGER NOT NULL CHECK (retry_count >= 0),
    compensation_action TEXT,
    status TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (saga_id) REFERENCES sagas(id),
    FOREIGN KEY (target_agent_id) REFERENCES agents(id),
    UNIQUE (saga_id, step_order)
);

CREATE INDEX IF NOT EXISTS idx_saga_steps_saga_order
    ON saga_steps (saga_id, step_order ASC);

CREATE INDEX IF NOT EXISTS idx_saga_steps_status
    ON saga_steps (saga_id, status, step_order ASC);

CREATE TABLE IF NOT EXISTS saga_events (
    id TEXT PRIMARY KEY,
    saga_id TEXT NOT NULL,
    step_id TEXT,
    event_type TEXT NOT NULL,
    message TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (saga_id) REFERENCES sagas(id),
    FOREIGN KEY (step_id) REFERENCES saga_steps(id)
);

CREATE INDEX IF NOT EXISTS idx_saga_events_saga_created
    ON saga_events (saga_id, created_at ASC, id ASC);

CREATE INDEX IF NOT EXISTS idx_saga_events_type_created
    ON saga_events (event_type, created_at DESC, id DESC);
