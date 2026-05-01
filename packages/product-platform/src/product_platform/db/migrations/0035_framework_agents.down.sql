DROP INDEX IF EXISTS idx_framework_agents_agent;
DROP INDEX IF EXISTS idx_framework_agents_instance;
DROP TABLE IF EXISTS framework_agents;

DELETE FROM schema_migrations WHERE version = '0035';
