DROP INDEX IF EXISTS idx_policy_rollout_events_binding;
DROP TABLE IF EXISTS policy_rollout_events;
DROP INDEX IF EXISTS idx_policy_exceptions_binding;
DROP TABLE IF EXISTS policy_exceptions;
DROP INDEX IF EXISTS idx_policy_bindings_policy;
DROP INDEX IF EXISTS idx_policy_bindings_org_env_target;
DROP TABLE IF EXISTS policy_bindings;
DELETE FROM schema_migrations WHERE version = '0008';
