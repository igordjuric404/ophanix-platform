WITH ranked_running_runs AS (
    SELECT
        id,
        ROW_NUMBER() OVER (
            PARTITION BY organization_id, environment_id, target_id
            ORDER BY created_at DESC, id DESC
        ) AS duplicate_rank
    FROM discovery_runs
    WHERE status = 'running'
)
UPDATE discovery_runs
SET status = 'skipped',
    finished_at = COALESCE(finished_at, CURRENT_TIMESTAMP::TEXT),
    error_message = COALESCE(
        error_message,
        'Skipped because another discovery scan is already running for this target.'
    ),
    summary_json = '{"overlap": true, "raw_finding_count": 0}',
    updated_at = CURRENT_TIMESTAMP::TEXT
WHERE id IN (
    SELECT id
    FROM ranked_running_runs
    WHERE duplicate_rank > 1
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_discovery_runs_one_running_per_target
    ON discovery_runs (organization_id, environment_id, target_id)
    WHERE status = 'running';
