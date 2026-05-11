CREATE UNIQUE INDEX IF NOT EXISTS idx_credential_scopes_unique_normalized
    ON credential_scopes (
        credential_id,
        scope,
        resource_type,
        COALESCE(resource_id, '')
    );
