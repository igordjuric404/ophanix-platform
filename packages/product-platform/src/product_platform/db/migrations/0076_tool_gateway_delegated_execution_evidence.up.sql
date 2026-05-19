ALTER TABLE tool_policy_decisions
ADD COLUMN IF NOT EXISTS credential_id TEXT;

ALTER TABLE tool_policy_decisions
ADD COLUMN IF NOT EXISTS delegated_authorization_id TEXT;

CREATE INDEX IF NOT EXISTS idx_tool_policy_decisions_credential
    ON tool_policy_decisions (organization_id, environment_id, credential_id, created_at DESC)
    WHERE credential_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_tool_policy_decisions_delegated_authorization
    ON tool_policy_decisions (organization_id, environment_id, delegated_authorization_id, created_at DESC)
    WHERE delegated_authorization_id IS NOT NULL;

ALTER TABLE tool_runtime_actions
ADD COLUMN IF NOT EXISTS delegated_authorization_id TEXT;

CREATE INDEX IF NOT EXISTS idx_tool_runtime_actions_delegated_authorization
    ON tool_runtime_actions (organization_id, environment_id, delegated_authorization_id, created_at DESC)
    WHERE delegated_authorization_id IS NOT NULL;
