CREATE TABLE IF NOT EXISTS policy_lint_results (
    id TEXT PRIMARY KEY,
    policy_version_id TEXT NOT NULL,
    severity TEXT NOT NULL,
    code TEXT NOT NULL,
    message TEXT NOT NULL,
    path TEXT NOT NULL,
    line_number INTEGER,
    fatal INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (policy_version_id) REFERENCES policy_versions(id)
);

CREATE INDEX IF NOT EXISTS idx_policy_lint_results_version
    ON policy_lint_results (policy_version_id, severity, created_at);
