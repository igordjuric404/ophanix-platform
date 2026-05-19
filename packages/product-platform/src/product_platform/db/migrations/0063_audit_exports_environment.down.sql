DROP INDEX IF EXISTS idx_audit_exports_org_env_created;

ALTER TABLE audit_exports
DROP CONSTRAINT IF EXISTS fk_audit_exports_environment;

ALTER TABLE audit_exports
DROP COLUMN IF EXISTS environment_id;
