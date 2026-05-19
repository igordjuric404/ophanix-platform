CREATE INDEX IF NOT EXISTS idx_audit_events_org_env_created
    ON audit_events (organization_id, environment_id, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_audit_events_org_env_type_created
    ON audit_events (organization_id, environment_id, event_type, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_tool_invocation_idempotency_status_updated
    ON tool_invocation_idempotency_records (status, updated_at);
