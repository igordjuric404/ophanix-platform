DROP INDEX IF EXISTS idx_plugin_signing_keys_trusted_root;
DROP INDEX IF EXISTS idx_plugin_signing_keys_org_fingerprint;

ALTER TABLE plugin_signing_keys DROP COLUMN IF EXISTS metadata_json;
ALTER TABLE plugin_signing_keys DROP COLUMN IF EXISTS public_key_fingerprint;
ALTER TABLE plugin_signing_keys DROP COLUMN IF EXISTS trusted_root_id;
ALTER TABLE plugin_signing_keys DROP COLUMN IF EXISTS key_type;
