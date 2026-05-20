ALTER TABLE plugin_signing_keys ADD COLUMN key_type TEXT NOT NULL DEFAULT 'ed25519';
ALTER TABLE plugin_signing_keys ADD COLUMN trusted_root_id TEXT;
ALTER TABLE plugin_signing_keys ADD COLUMN public_key_fingerprint TEXT;
ALTER TABLE plugin_signing_keys ADD COLUMN metadata_json TEXT NOT NULL DEFAULT '{}';

CREATE INDEX IF NOT EXISTS idx_plugin_signing_keys_org_fingerprint
    ON plugin_signing_keys (organization_id, public_key_fingerprint);

CREATE INDEX IF NOT EXISTS idx_plugin_signing_keys_trusted_root
    ON plugin_signing_keys (organization_id, trusted_root_id);
