DROP INDEX IF EXISTS idx_kill_switch_events_target;
DROP INDEX IF EXISTS idx_kill_switch_events_tenant_created;
DROP TABLE IF EXISTS kill_switch_events;

DROP INDEX IF EXISTS idx_sandbox_decisions_profile_created;
DROP TABLE IF EXISTS sandbox_decisions;

DROP INDEX IF EXISTS idx_sandbox_profiles_tenant_status;
DROP TABLE IF EXISTS sandbox_profiles;

DELETE FROM schema_migrations WHERE version = '0022';
