DROP INDEX IF EXISTS idx_plugin_installations_artifact_evidence;
DROP INDEX IF EXISTS idx_plugin_installations_review;
DROP INDEX IF EXISTS idx_plugin_installations_policy_result;

ALTER TABLE plugin_installations DROP COLUMN IF EXISTS artifact_evidence_id;
ALTER TABLE plugin_installations DROP COLUMN IF EXISTS review_id;
ALTER TABLE plugin_installations DROP COLUMN IF EXISTS policy_result_id;

ALTER TABLE plugin_policy_results DROP COLUMN IF EXISTS policy_input_json;
