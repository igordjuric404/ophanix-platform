ALTER TABLE agent_identities
ADD COLUMN IF NOT EXISTS proof_type TEXT NOT NULL DEFAULT 'agentmesh-local';

ALTER TABLE agent_identities
ADD COLUMN IF NOT EXISTS issuer TEXT NOT NULL DEFAULT 'local-agentmesh';

ALTER TABLE agent_identities
ADD COLUMN IF NOT EXISTS audience TEXT;

ALTER TABLE agent_identities
ADD COLUMN IF NOT EXISTS subject TEXT;

ALTER TABLE agent_identities
ADD COLUMN IF NOT EXISTS environment_binding TEXT;

ALTER TABLE agent_identities
ADD COLUMN IF NOT EXISTS trusted_root_id TEXT NOT NULL DEFAULT 'local-agentmesh';

ALTER TABLE agent_identities
ADD COLUMN IF NOT EXISTS trusted_root_version TEXT NOT NULL DEFAULT 'v1';

ALTER TABLE agent_identities
ADD COLUMN IF NOT EXISTS key_reference TEXT;

ALTER TABLE agent_identities
ADD COLUMN IF NOT EXISTS certificate_chain_json TEXT NOT NULL DEFAULT '[]';

ALTER TABLE agent_identities
ADD COLUMN IF NOT EXISTS proof_metadata_json TEXT NOT NULL DEFAULT '{}';

ALTER TABLE agent_identities
ADD COLUMN IF NOT EXISTS verified_at TEXT;

ALTER TABLE agent_identities
ADD COLUMN IF NOT EXISTS rotated_at TEXT;

ALTER TABLE agent_identities
ADD COLUMN IF NOT EXISTS revoked_at TEXT;

ALTER TABLE agent_identities
ADD COLUMN IF NOT EXISTS rotation_count INTEGER NOT NULL DEFAULT 0;

UPDATE agent_identities
SET audience = COALESCE(
        audience,
        (
            SELECT a.environment_id
            FROM agents a
            WHERE a.id = agent_identities.agent_id
            LIMIT 1
        )
    ),
    environment_binding = COALESCE(
        environment_binding,
        (
            SELECT a.organization_id || ':' || a.environment_id
            FROM agents a
            WHERE a.id = agent_identities.agent_id
            LIMIT 1
        )
    ),
    verified_at = COALESCE(verified_at, created_at);

CREATE INDEX IF NOT EXISTS idx_agent_identities_trust_root_status
    ON agent_identities (trusted_root_id, issuer, identity_status);
