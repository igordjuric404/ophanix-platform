CREATE TABLE IF NOT EXISTS plugin_artifact_evidence (
    id TEXT PRIMARY KEY,
    plugin_version_id TEXT NOT NULL REFERENCES plugin_versions(id) ON DELETE CASCADE,
    package_ref TEXT NOT NULL,
    artifact_digest TEXT NOT NULL,
    digest_algorithm TEXT NOT NULL DEFAULT 'sha256',
    provenance_json TEXT NOT NULL DEFAULT '{}',
    sbom_json TEXT NOT NULL DEFAULT '{}',
    license_json TEXT NOT NULL DEFAULT '{}',
    vulnerability_scan_json TEXT NOT NULL DEFAULT '{}',
    malware_scan_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL,
    findings_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (plugin_version_id)
);

CREATE INDEX IF NOT EXISTS idx_plugin_artifact_evidence_digest
    ON plugin_artifact_evidence (artifact_digest);

CREATE INDEX IF NOT EXISTS idx_plugin_artifact_evidence_status
    ON plugin_artifact_evidence (status);
