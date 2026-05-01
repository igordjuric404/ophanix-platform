CREATE TABLE IF NOT EXISTS demo_runs (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    environment_id TEXT NOT NULL,
    scenario_id TEXT NOT NULL,
    status TEXT NOT NULL,
    started_by TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    summary_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (environment_id) REFERENCES environments(id),
    FOREIGN KEY (scenario_id) REFERENCES demo_scenarios(id)
);

CREATE INDEX IF NOT EXISTS idx_demo_runs_org_env_status
ON demo_runs (organization_id, environment_id, status, started_at);

CREATE INDEX IF NOT EXISTS idx_demo_runs_scenario
ON demo_runs (scenario_id, started_at);

CREATE TABLE IF NOT EXISTS demo_step_runs (
    id TEXT PRIMARY KEY,
    demo_run_id TEXT NOT NULL,
    demo_step_id TEXT NOT NULL,
    status TEXT NOT NULL,
    result_json TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (demo_run_id) REFERENCES demo_runs(id) ON DELETE CASCADE,
    FOREIGN KEY (demo_step_id) REFERENCES demo_steps(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_demo_step_runs_run_step
ON demo_step_runs (demo_run_id, demo_step_id);

CREATE INDEX IF NOT EXISTS idx_demo_step_runs_run_status
ON demo_step_runs (demo_run_id, status);
