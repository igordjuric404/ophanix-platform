ALTER TABLE plugin_policy_results ADD COLUMN policy_input_json TEXT NOT NULL DEFAULT '{}';

ALTER TABLE plugin_installations ADD COLUMN policy_result_id TEXT REFERENCES plugin_policy_results(id) ON DELETE SET NULL;
ALTER TABLE plugin_installations ADD COLUMN review_id TEXT REFERENCES plugin_reviews(id) ON DELETE SET NULL;
ALTER TABLE plugin_installations ADD COLUMN artifact_evidence_id TEXT REFERENCES plugin_artifact_evidence(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_plugin_installations_policy_result
    ON plugin_installations (policy_result_id);

CREATE INDEX IF NOT EXISTS idx_plugin_installations_review
    ON plugin_installations (review_id);

CREATE INDEX IF NOT EXISTS idx_plugin_installations_artifact_evidence
    ON plugin_installations (artifact_evidence_id);
