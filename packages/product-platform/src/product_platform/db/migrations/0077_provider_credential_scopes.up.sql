ALTER TABLE provider_credentials
ADD COLUMN IF NOT EXISTS environment_id TEXT;

UPDATE provider_credentials pc
SET environment_id = (
    SELECT e.id
    FROM environments e
    WHERE e.organization_id = pc.organization_id
    ORDER BY e.created_at ASC, e.id ASC
    LIMIT 1
)
WHERE environment_id IS NULL;

ALTER TABLE provider_credentials
ALTER COLUMN environment_id SET NOT NULL;

ALTER TABLE provider_credentials
ADD COLUMN IF NOT EXISTS subject_type TEXT;

UPDATE provider_credentials
SET subject_type = 'organization'
WHERE subject_type IS NULL;

ALTER TABLE provider_credentials
ALTER COLUMN subject_type SET NOT NULL;

ALTER TABLE provider_credentials
ADD COLUMN IF NOT EXISTS subject_id TEXT;

ALTER TABLE provider_credentials
ADD COLUMN IF NOT EXISTS provider_account_id TEXT;

ALTER TABLE provider_credentials
ADD COLUMN IF NOT EXISTS credential_type TEXT;

UPDATE provider_credentials
SET credential_type = 'api_key'
WHERE credential_type IS NULL;

ALTER TABLE provider_credentials
ALTER COLUMN credential_type SET NOT NULL;

ALTER TABLE provider_credentials
ADD COLUMN IF NOT EXISTS scopes_json TEXT;

UPDATE provider_credentials
SET scopes_json = '[]'
WHERE scopes_json IS NULL;

ALTER TABLE provider_credentials
ALTER COLUMN scopes_json SET NOT NULL;

ALTER TABLE provider_credentials
ADD COLUMN IF NOT EXISTS expires_at TEXT;

ALTER TABLE provider_credentials
ADD COLUMN IF NOT EXISTS rotation_status TEXT;

UPDATE provider_credentials
SET rotation_status = 'current'
WHERE rotation_status IS NULL;

ALTER TABLE provider_credentials
ALTER COLUMN rotation_status SET NOT NULL;

ALTER TABLE provider_credentials
ADD COLUMN IF NOT EXISTS revoked_at TEXT;

ALTER TABLE provider_credentials
ADD COLUMN IF NOT EXISTS revoked_by TEXT;

ALTER TABLE provider_credentials
ADD COLUMN IF NOT EXISTS revoked_reason TEXT;

ALTER TABLE provider_credentials
ADD COLUMN IF NOT EXISTS allowed_tool_ids_json TEXT;

UPDATE provider_credentials
SET allowed_tool_ids_json = '[]'
WHERE allowed_tool_ids_json IS NULL;

ALTER TABLE provider_credentials
ALTER COLUMN allowed_tool_ids_json SET NOT NULL;

ALTER TABLE provider_credentials
ADD COLUMN IF NOT EXISTS updated_at TEXT;

UPDATE provider_credentials
SET updated_at = created_at
WHERE updated_at IS NULL;

ALTER TABLE provider_credentials
ALTER COLUMN updated_at SET NOT NULL;

DROP INDEX IF EXISTS idx_provider_credentials_org_secret_ref;
DROP INDEX IF EXISTS idx_provider_credentials_org_type_status;

CREATE INDEX IF NOT EXISTS idx_provider_credentials_org_env_type_status
    ON provider_credentials (organization_id, environment_id, provider_type, status, created_at DESC, id DESC);

CREATE UNIQUE INDEX IF NOT EXISTS idx_provider_credentials_org_env_secret_ref
    ON provider_credentials (organization_id, environment_id, secret_ref);

CREATE INDEX IF NOT EXISTS idx_provider_credentials_subject
    ON provider_credentials (organization_id, environment_id, subject_type, subject_id)
    WHERE subject_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_provider_credentials_expiry
    ON provider_credentials (organization_id, environment_id, status, expires_at)
    WHERE expires_at IS NOT NULL;
