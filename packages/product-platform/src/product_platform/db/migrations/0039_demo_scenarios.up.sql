CREATE TABLE IF NOT EXISTS demo_scenarios (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    environment_id TEXT NOT NULL,
    name TEXT NOT NULL,
    slug TEXT NOT NULL,
    description TEXT NOT NULL,
    value_proof TEXT NOT NULL,
    status TEXT NOT NULL,
    required_services_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (environment_id) REFERENCES environments(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_demo_scenarios_org_env_slug
ON demo_scenarios (organization_id, environment_id, slug);

CREATE INDEX IF NOT EXISTS idx_demo_scenarios_org_env_status
ON demo_scenarios (organization_id, environment_id, status);

CREATE TABLE IF NOT EXISTS demo_steps (
    id TEXT PRIMARY KEY,
    scenario_id TEXT NOT NULL,
    step_order INTEGER NOT NULL,
    title TEXT NOT NULL,
    expected_result TEXT NOT NULL,
    action_type TEXT NOT NULL,
    action_config_json TEXT NOT NULL,
    proof_links_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (scenario_id) REFERENCES demo_scenarios(id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_demo_steps_scenario_order
ON demo_steps (scenario_id, step_order);
