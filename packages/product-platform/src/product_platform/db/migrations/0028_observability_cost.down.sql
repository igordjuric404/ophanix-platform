DROP INDEX IF EXISTS idx_cost_events_provider_model;
DROP INDEX IF EXISTS idx_cost_events_target_created;
DROP INDEX IF EXISTS idx_cost_events_scope_created;
DROP TABLE IF EXISTS cost_events;

DROP INDEX IF EXISTS idx_cost_budgets_target_period;
DROP INDEX IF EXISTS idx_cost_budgets_scope_status;
DROP TABLE IF EXISTS cost_budgets;

DELETE FROM schema_migrations WHERE version = '0028';
