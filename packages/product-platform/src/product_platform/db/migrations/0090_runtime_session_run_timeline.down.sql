DROP INDEX IF EXISTS idx_runtime_run_steps_runtime_action;
DROP INDEX IF EXISTS idx_runtime_run_steps_session_order;
DROP INDEX IF EXISTS idx_runtime_run_steps_run_order;
DROP TABLE IF EXISTS runtime_run_steps;

DROP INDEX IF EXISTS idx_runtime_runs_thread_started;
DROP INDEX IF EXISTS idx_runtime_runs_scope_started;
DROP INDEX IF EXISTS idx_runtime_runs_session_started;
DROP TABLE IF EXISTS runtime_runs;

ALTER TABLE runtime_sessions DROP COLUMN IF EXISTS thread_id;
ALTER TABLE runtime_sessions DROP COLUMN IF EXISTS memory_scope;
ALTER TABLE runtime_sessions DROP COLUMN IF EXISTS created_by_user_id;
