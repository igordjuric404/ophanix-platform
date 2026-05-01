CREATE TABLE IF NOT EXISTS runtime_ring_decisions (
    id TEXT PRIMARY KEY,
    runtime_action_id TEXT NOT NULL,
    agent_trust_score INTEGER NOT NULL CHECK (agent_trust_score >= 0 AND agent_trust_score <= 1000),
    required_ring INTEGER NOT NULL CHECK (required_ring >= 0 AND required_ring <= 3),
    assigned_ring INTEGER NOT NULL CHECK (assigned_ring >= 0 AND assigned_ring <= 3),
    result TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (runtime_action_id) REFERENCES runtime_actions(id)
);

CREATE INDEX IF NOT EXISTS idx_runtime_ring_decisions_action
    ON runtime_ring_decisions (runtime_action_id);

CREATE INDEX IF NOT EXISTS idx_runtime_ring_decisions_result_created
    ON runtime_ring_decisions (result, created_at DESC, id DESC);
