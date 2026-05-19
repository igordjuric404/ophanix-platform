DROP INDEX IF EXISTS idx_tool_runtime_actions_delegated_authorization;

ALTER TABLE tool_runtime_actions
DROP COLUMN IF EXISTS delegated_authorization_id;

DROP INDEX IF EXISTS idx_tool_policy_decisions_delegated_authorization;

DROP INDEX IF EXISTS idx_tool_policy_decisions_credential;

ALTER TABLE tool_policy_decisions
DROP COLUMN IF EXISTS delegated_authorization_id;

ALTER TABLE tool_policy_decisions
DROP COLUMN IF EXISTS credential_id;
