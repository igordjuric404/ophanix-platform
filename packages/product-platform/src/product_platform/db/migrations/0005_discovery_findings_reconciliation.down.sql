DROP INDEX IF EXISTS idx_reconciliation_actions_finding;
DROP TABLE IF EXISTS reconciliation_actions;
DROP INDEX IF EXISTS idx_discovery_suppressions_finding;
DROP TABLE IF EXISTS discovery_suppressions;
DROP INDEX IF EXISTS idx_discovery_evidence_finding;
DROP TABLE IF EXISTS discovery_evidence;
DROP INDEX IF EXISTS idx_discovery_findings_org_env_status;
DROP TABLE IF EXISTS discovery_findings;
DELETE FROM schema_migrations WHERE version = '0005';
