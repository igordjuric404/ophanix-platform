ALTER TABLE artifacts ADD COLUMN IF NOT EXISTS digest_algorithm TEXT NOT NULL DEFAULT 'sha256';
ALTER TABLE artifacts ADD COLUMN IF NOT EXISTS retention_policy TEXT NOT NULL DEFAULT 'standard';
ALTER TABLE artifacts ADD COLUMN IF NOT EXISTS redaction_classification TEXT NOT NULL DEFAULT 'internal';
ALTER TABLE artifacts ADD COLUMN IF NOT EXISTS provenance_json TEXT NOT NULL DEFAULT '{}';

ALTER TABLE artifact_attestations ADD COLUMN IF NOT EXISTS artifact_checksum TEXT;
ALTER TABLE artifact_attestations ADD COLUMN IF NOT EXISTS digest_algorithm TEXT NOT NULL DEFAULT 'sha256';
ALTER TABLE artifact_attestations ADD COLUMN IF NOT EXISTS signer_user_id TEXT;

CREATE INDEX IF NOT EXISTS idx_artifact_links_artifact_target
    ON artifact_links (artifact_id, target_type, target_id);

CREATE INDEX IF NOT EXISTS idx_artifact_links_runtime_targets
    ON artifact_links (target_type, target_id, artifact_id)
    WHERE target_type IN (
        'runtime_session',
        'runtime_action',
        'tool_runtime_action',
        'mcp_tool_call',
        'observability_trace',
        'observability_span',
        'observability_eval_result'
    );
