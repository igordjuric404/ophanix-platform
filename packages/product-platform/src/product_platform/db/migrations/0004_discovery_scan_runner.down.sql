DROP INDEX IF EXISTS idx_discovery_raw_findings_run;
DROP TABLE IF EXISTS discovery_raw_findings;
DROP INDEX IF EXISTS idx_discovery_runs_target_created;
DROP TABLE IF EXISTS discovery_runs;
DROP INDEX IF EXISTS idx_discovery_targets_org_env;
DROP TABLE IF EXISTS discovery_targets;
DROP TABLE IF EXISTS discovery_scanners;
DELETE FROM schema_migrations WHERE version = '0004';
