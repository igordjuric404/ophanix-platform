DROP INDEX IF EXISTS idx_tool_runtime_actions_authorization_session;

ALTER TABLE tool_runtime_actions
DROP COLUMN IF EXISTS authorization_session_id;

ALTER TABLE tool_runtime_actions
DROP COLUMN IF EXISTS approval_state;

ALTER TABLE tool_runtime_actions
DROP COLUMN IF EXISTS provider_account_id;

ALTER TABLE tool_runtime_actions
DROP COLUMN IF EXISTS delegated_user_id;

DROP INDEX IF EXISTS idx_tool_policy_decisions_authorization_session;

ALTER TABLE tool_policy_decisions
DROP COLUMN IF EXISTS authorization_session_id;

ALTER TABLE tool_policy_decisions
DROP COLUMN IF EXISTS approval_state;

ALTER TABLE tool_policy_decisions
DROP COLUMN IF EXISTS provider_account_id;

ALTER TABLE tool_policy_decisions
DROP COLUMN IF EXISTS delegated_user_id;

DROP INDEX IF EXISTS idx_tool_oauth_authorization_sessions_lookup;
DROP TABLE IF EXISTS tool_oauth_authorization_sessions;

DROP INDEX IF EXISTS idx_tool_delegated_authorizations_lookup;
DROP TABLE IF EXISTS tool_delegated_authorizations;

DROP INDEX IF EXISTS idx_tool_delegation_requirements_status;
DROP INDEX IF EXISTS idx_tool_delegation_requirements_active_tool;
DROP TABLE IF EXISTS tool_delegation_requirements;
