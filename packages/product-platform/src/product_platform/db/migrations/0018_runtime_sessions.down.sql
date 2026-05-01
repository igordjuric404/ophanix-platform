DROP INDEX IF EXISTS idx_runtime_actions_decision_created;
DROP INDEX IF EXISTS idx_runtime_actions_session_created;
DROP TABLE IF EXISTS runtime_actions;
DROP INDEX IF EXISTS idx_runtime_sessions_state_started;
DROP INDEX IF EXISTS idx_runtime_sessions_agent_started;
DROP INDEX IF EXISTS idx_runtime_sessions_scope_started;
DROP TABLE IF EXISTS runtime_sessions;
DELETE FROM schema_migrations WHERE version = '0018';
