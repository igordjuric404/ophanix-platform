DROP INDEX IF EXISTS idx_api_keys_rotation_to;

DROP INDEX IF EXISTS idx_api_keys_rotation_from;

ALTER TABLE api_keys
DROP COLUMN IF EXISTS rotated_to_key_id;

ALTER TABLE api_keys
DROP COLUMN IF EXISTS rotated_from_key_id;

ALTER TABLE api_keys
DROP COLUMN IF EXISTS revoked_reason;

ALTER TABLE api_keys
DROP COLUMN IF EXISTS revoked_by;

ALTER TABLE api_keys
DROP COLUMN IF EXISTS created_by;
