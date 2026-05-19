DROP INDEX IF EXISTS idx_mcp_approvals_release_idempotency;
DROP INDEX IF EXISTS idx_mcp_approvals_status_expires;

ALTER TABLE mcp_approvals
DROP COLUMN IF EXISTS release_error;

ALTER TABLE mcp_approvals
DROP COLUMN IF EXISTS release_idempotency_key;

ALTER TABLE mcp_approvals
DROP COLUMN IF EXISTS released_at;

ALTER TABLE mcp_approvals
DROP COLUMN IF EXISTS release_status;

ALTER TABLE mcp_approvals
DROP COLUMN IF EXISTS policy_snapshot_json;

ALTER TABLE mcp_approvals
DROP COLUMN IF EXISTS replay_token_hash;

ALTER TABLE mcp_approvals
DROP COLUMN IF EXISTS expires_at;

ALTER TABLE mcp_approvals
DROP COLUMN IF EXISTS payload_hash;

ALTER TABLE mcp_approvals
DROP COLUMN IF EXISTS original_params_json;

DELETE FROM schema_migrations WHERE version = '0079';
