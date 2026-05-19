ALTER TABLE audit_exports
ADD COLUMN IF NOT EXISTS environment_id TEXT;

UPDATE audit_exports
SET environment_id = (
    SELECT e.id
    FROM environments e
    WHERE e.organization_id = audit_exports.organization_id
    ORDER BY e.created_at ASC, e.id ASC
    LIMIT 1
)
WHERE environment_id IS NULL;

ALTER TABLE audit_exports
ALTER COLUMN environment_id SET NOT NULL;

ALTER TABLE audit_exports
ADD CONSTRAINT fk_audit_exports_environment
FOREIGN KEY (environment_id) REFERENCES environments(id);

CREATE INDEX IF NOT EXISTS idx_audit_exports_org_env_created
    ON audit_exports (organization_id, environment_id, created_at DESC, id DESC);
