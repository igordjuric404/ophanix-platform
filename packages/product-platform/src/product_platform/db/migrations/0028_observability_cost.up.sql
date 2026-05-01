CREATE TABLE IF NOT EXISTS cost_budgets (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    environment_id TEXT NOT NULL REFERENCES environments(id) ON DELETE CASCADE,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    period TEXT NOT NULL,
    amount_limit REAL NOT NULL,
    used_amount REAL NOT NULL DEFAULT 0,
    action_on_breach TEXT NOT NULL,
    breach_action TEXT NOT NULL DEFAULT 'none',
    status TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cost_budgets_scope_status
    ON cost_budgets (organization_id, environment_id, status, updated_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_cost_budgets_target_period
    ON cost_budgets (organization_id, environment_id, target_type, target_id, period);

CREATE TABLE IF NOT EXISTS cost_events (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    environment_id TEXT NOT NULL REFERENCES environments(id) ON DELETE CASCADE,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    amount REAL NOT NULL,
    units REAL NOT NULL,
    correlation_id TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cost_events_scope_created
    ON cost_events (organization_id, environment_id, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_cost_events_target_created
    ON cost_events (organization_id, environment_id, target_type, target_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_cost_events_provider_model
    ON cost_events (organization_id, environment_id, provider, model);
