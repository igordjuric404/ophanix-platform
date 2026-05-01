CREATE TABLE IF NOT EXISTS artifact_attestations (
    id TEXT PRIMARY KEY,
    artifact_id TEXT NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
    attested_by TEXT NOT NULL,
    statement TEXT NOT NULL,
    signature_ref TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_artifact_attestations_artifact
    ON artifact_attestations(artifact_id, created_at DESC);
