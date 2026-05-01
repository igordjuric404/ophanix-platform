DROP TABLE IF EXISTS agent_heartbeats;
DROP TABLE IF EXISTS agent_lifecycle_events;
DROP TABLE IF EXISTS agent_policy_selections;
DROP TABLE IF EXISTS agent_protocols;
DROP TABLE IF EXISTS agent_capabilities;
DROP TABLE IF EXISTS agent_identities;
DROP INDEX IF EXISTS idx_agents_org_env_status;
DROP INDEX IF EXISTS idx_agents_org_env_name_active;
DROP TABLE IF EXISTS agents;
DELETE FROM schema_migrations WHERE version = '0002';

