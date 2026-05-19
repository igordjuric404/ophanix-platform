ALTER TABLE api_keys
ADD COLUMN IF NOT EXISTS created_by TEXT;

ALTER TABLE api_keys
ADD COLUMN IF NOT EXISTS revoked_by TEXT;

ALTER TABLE api_keys
ADD COLUMN IF NOT EXISTS revoked_reason TEXT;

ALTER TABLE api_keys
ADD COLUMN IF NOT EXISTS rotated_from_key_id TEXT;

ALTER TABLE api_keys
ADD COLUMN IF NOT EXISTS rotated_to_key_id TEXT;

CREATE INDEX IF NOT EXISTS idx_api_keys_rotation_from
    ON api_keys (organization_id, rotated_from_key_id)
    WHERE rotated_from_key_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_api_keys_rotation_to
    ON api_keys (organization_id, rotated_to_key_id)
    WHERE rotated_to_key_id IS NOT NULL;
