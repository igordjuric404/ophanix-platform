DROP INDEX IF EXISTS idx_agent_identities_trust_root_status;

ALTER TABLE agent_identities
DROP COLUMN IF EXISTS rotation_count;

ALTER TABLE agent_identities
DROP COLUMN IF EXISTS revoked_at;

ALTER TABLE agent_identities
DROP COLUMN IF EXISTS rotated_at;

ALTER TABLE agent_identities
DROP COLUMN IF EXISTS verified_at;

ALTER TABLE agent_identities
DROP COLUMN IF EXISTS proof_metadata_json;

ALTER TABLE agent_identities
DROP COLUMN IF EXISTS certificate_chain_json;

ALTER TABLE agent_identities
DROP COLUMN IF EXISTS key_reference;

ALTER TABLE agent_identities
DROP COLUMN IF EXISTS trusted_root_version;

ALTER TABLE agent_identities
DROP COLUMN IF EXISTS trusted_root_id;

ALTER TABLE agent_identities
DROP COLUMN IF EXISTS environment_binding;

ALTER TABLE agent_identities
DROP COLUMN IF EXISTS subject;

ALTER TABLE agent_identities
DROP COLUMN IF EXISTS audience;

ALTER TABLE agent_identities
DROP COLUMN IF EXISTS issuer;

ALTER TABLE agent_identities
DROP COLUMN IF EXISTS proof_type;
