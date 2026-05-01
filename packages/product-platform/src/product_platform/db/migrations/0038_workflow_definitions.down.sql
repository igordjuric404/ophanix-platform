DROP INDEX IF EXISTS idx_workflow_definitions_org_enabled;
DROP INDEX IF EXISTS idx_workflow_definitions_org_command;
DROP TABLE IF EXISTS workflow_definitions;

DELETE FROM schema_migrations WHERE version = '0038';
