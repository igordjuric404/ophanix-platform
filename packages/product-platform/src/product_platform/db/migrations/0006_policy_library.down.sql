DROP INDEX IF EXISTS idx_policy_imports_org_created;
DROP TABLE IF EXISTS policy_imports;
DROP INDEX IF EXISTS idx_policy_versions_policy_created;
DROP INDEX IF EXISTS idx_policy_versions_one_active;
DROP TABLE IF EXISTS policy_versions;
DROP INDEX IF EXISTS idx_policies_org_status_scope;
DROP INDEX IF EXISTS idx_policies_org_slug_active;
DROP TABLE IF EXISTS policies;
DELETE FROM schema_migrations WHERE version = '0006';
