CREATE TABLE IF NOT EXISTS trust_cards (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    environment_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    issuer TEXT NOT NULL,
    card_json TEXT NOT NULL,
    signature TEXT NOT NULL,
    status TEXT NOT NULL,
    valid_from TEXT NOT NULL,
    valid_until TEXT NOT NULL,
    issued_at TEXT NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (environment_id) REFERENCES environments(id),
    FOREIGN KEY (agent_id) REFERENCES agents(id)
);

CREATE INDEX IF NOT EXISTS idx_trust_cards_agent_status
    ON trust_cards (organization_id, environment_id, agent_id, status, issued_at DESC);

CREATE TABLE IF NOT EXISTS trust_card_revocations (
    id TEXT PRIMARY KEY,
    trust_card_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    revoked_by TEXT NOT NULL,
    revoked_at TEXT NOT NULL,
    FOREIGN KEY (trust_card_id) REFERENCES trust_cards(id)
);

CREATE INDEX IF NOT EXISTS idx_trust_card_revocations_card
    ON trust_card_revocations (trust_card_id, revoked_at DESC);
