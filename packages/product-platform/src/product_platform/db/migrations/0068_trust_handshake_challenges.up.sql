CREATE TABLE IF NOT EXISTS handshake_challenges (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    environment_id TEXT NOT NULL,
    source_agent_id TEXT NOT NULL,
    source_did TEXT NOT NULL,
    target_agent_id TEXT NOT NULL,
    target_did TEXT NOT NULL,
    purpose TEXT NOT NULL,
    threshold_type TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    audience TEXT NOT NULL,
    nonce TEXT NOT NULL,
    contract_version TEXT NOT NULL,
    issued_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    consumed_at TEXT,
    consumed_by_handshake_event_id TEXT,
    metadata_json TEXT NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (environment_id) REFERENCES environments(id),
    FOREIGN KEY (source_agent_id) REFERENCES agents(id),
    FOREIGN KEY (target_agent_id) REFERENCES agents(id),
    FOREIGN KEY (consumed_by_handshake_event_id) REFERENCES handshake_events(id),
    UNIQUE (organization_id, environment_id, nonce)
);

CREATE INDEX IF NOT EXISTS idx_handshake_challenges_source_created
    ON handshake_challenges (organization_id, environment_id, source_agent_id, issued_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_handshake_challenges_target_created
    ON handshake_challenges (organization_id, environment_id, target_agent_id, issued_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_handshake_challenges_consumed
    ON handshake_challenges (organization_id, environment_id, consumed_at, expires_at);
