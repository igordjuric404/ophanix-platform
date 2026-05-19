DROP INDEX IF EXISTS idx_provider_credentials_expiry;
DROP INDEX IF EXISTS idx_provider_credentials_subject;
DROP INDEX IF EXISTS idx_provider_credentials_org_env_secret_ref;
DROP INDEX IF EXISTS idx_provider_credentials_org_env_type_status;

CREATE INDEX IF NOT EXISTS idx_provider_credentials_org_type_status
    ON provider_credentials (organization_id, provider_type, status, created_at DESC, id DESC);

CREATE UNIQUE INDEX IF NOT EXISTS idx_provider_credentials_org_secret_ref
    ON provider_credentials (organization_id, secret_ref);

ALTER TABLE provider_credentials
DROP COLUMN IF EXISTS updated_at;

ALTER TABLE provider_credentials
DROP COLUMN IF EXISTS allowed_tool_ids_json;

ALTER TABLE provider_credentials
DROP COLUMN IF EXISTS revoked_reason;

ALTER TABLE provider_credentials
DROP COLUMN IF EXISTS revoked_by;

ALTER TABLE provider_credentials
DROP COLUMN IF EXISTS revoked_at;

ALTER TABLE provider_credentials
DROP COLUMN IF EXISTS rotation_status;

ALTER TABLE provider_credentials
DROP COLUMN IF EXISTS expires_at;

ALTER TABLE provider_credentials
DROP COLUMN IF EXISTS scopes_json;

ALTER TABLE provider_credentials
DROP COLUMN IF EXISTS credential_type;

ALTER TABLE provider_credentials
DROP COLUMN IF EXISTS provider_account_id;

ALTER TABLE provider_credentials
DROP COLUMN IF EXISTS subject_id;

ALTER TABLE provider_credentials
DROP COLUMN IF EXISTS subject_type;

ALTER TABLE provider_credentials
DROP COLUMN IF EXISTS environment_id;
