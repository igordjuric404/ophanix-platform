DROP INDEX IF EXISTS idx_plugin_trust_events_version_created;
DROP TABLE IF EXISTS plugin_trust_events;

DROP INDEX IF EXISTS idx_plugin_quality_assessments_version_created;
DROP TABLE IF EXISTS plugin_quality_assessments;

DROP INDEX IF EXISTS idx_plugin_signing_keys_org_status;
DROP TABLE IF EXISTS plugin_signing_keys;

DROP INDEX IF EXISTS idx_plugin_reviews_status;
DROP INDEX IF EXISTS idx_plugin_reviews_version_created;
DROP TABLE IF EXISTS plugin_reviews;

DELETE FROM schema_migrations WHERE version = '0026';
