DROP INDEX IF EXISTS idx_demo_steps_scenario_order;
DROP TABLE IF EXISTS demo_steps;

DROP INDEX IF EXISTS idx_demo_scenarios_org_env_status;
DROP INDEX IF EXISTS idx_demo_scenarios_org_env_slug;
DROP TABLE IF EXISTS demo_scenarios;

DELETE FROM schema_migrations WHERE version = '0039';
