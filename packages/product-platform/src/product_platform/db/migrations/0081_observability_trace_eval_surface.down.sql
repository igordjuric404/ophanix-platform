DROP INDEX IF EXISTS idx_observability_trace_feedback_trace_created;
DROP TABLE IF EXISTS observability_trace_feedback;

DROP INDEX IF EXISTS idx_observability_trace_annotations_trace_created;
DROP TABLE IF EXISTS observability_trace_annotations;

DROP INDEX IF EXISTS idx_observability_eval_results_dataset_created;
DROP INDEX IF EXISTS idx_observability_eval_results_trace_created;
DROP TABLE IF EXISTS observability_eval_results;

DROP INDEX IF EXISTS idx_observability_spans_trace_start;
DROP TABLE IF EXISTS observability_spans;

DROP INDEX IF EXISTS idx_observability_traces_agent_updated;
DROP INDEX IF EXISTS idx_observability_traces_scope_updated;
DROP TABLE IF EXISTS observability_traces;

DELETE FROM schema_migrations WHERE version = '0081';
