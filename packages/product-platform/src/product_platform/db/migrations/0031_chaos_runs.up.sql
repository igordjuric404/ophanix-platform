CREATE TABLE IF NOT EXISTS chaos_runs (
    id TEXT PRIMARY KEY,
    experiment_id TEXT NOT NULL REFERENCES chaos_experiments(id) ON DELETE CASCADE,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    result_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_chaos_runs_experiment_started
    ON chaos_runs (experiment_id, started_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_chaos_runs_status_started
    ON chaos_runs (status, started_at DESC);
