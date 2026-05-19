ALTER TABLE mcp_approvals ADD COLUMN original_params_json TEXT;
ALTER TABLE mcp_approvals ADD COLUMN payload_hash TEXT;
ALTER TABLE mcp_approvals ADD COLUMN expires_at TEXT;
ALTER TABLE mcp_approvals ADD COLUMN replay_token_hash TEXT;
ALTER TABLE mcp_approvals ADD COLUMN policy_snapshot_json TEXT;
ALTER TABLE mcp_approvals ADD COLUMN release_status TEXT;
ALTER TABLE mcp_approvals ADD COLUMN released_at TEXT;
ALTER TABLE mcp_approvals ADD COLUMN release_idempotency_key TEXT;
ALTER TABLE mcp_approvals ADD COLUMN release_error TEXT;

CREATE INDEX IF NOT EXISTS idx_mcp_approvals_status_expires
    ON mcp_approvals (status, expires_at, requested_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_mcp_approvals_release_idempotency
    ON mcp_approvals (tool_call_id, release_idempotency_key);
