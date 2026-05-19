CREATE TABLE IF NOT EXISTS observability_traces (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    environment_id TEXT NOT NULL,
    trace_id TEXT NOT NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL,
    agent_id TEXT,
    runtime_session_id TEXT,
    correlation_id TEXT,
    metadata_json TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    created_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (organization_id, environment_id, trace_id),
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (environment_id) REFERENCES environments(id),
    FOREIGN KEY (agent_id) REFERENCES agents(id),
    FOREIGN KEY (runtime_session_id) REFERENCES runtime_sessions(id)
);

CREATE INDEX IF NOT EXISTS idx_observability_traces_scope_updated
    ON observability_traces (organization_id, environment_id, updated_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_observability_traces_agent_updated
    ON observability_traces (organization_id, environment_id, agent_id, updated_at DESC, id DESC);

CREATE TABLE IF NOT EXISTS observability_spans (
    id TEXT PRIMARY KEY,
    trace_record_id TEXT NOT NULL,
    organization_id TEXT NOT NULL,
    environment_id TEXT NOT NULL,
    trace_id TEXT NOT NULL,
    span_id TEXT NOT NULL,
    parent_span_id TEXT,
    span_kind TEXT NOT NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT,
    latency_ms INTEGER,
    resource_type TEXT,
    resource_id TEXT,
    attributes_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (organization_id, environment_id, trace_id, span_id),
    FOREIGN KEY (trace_record_id) REFERENCES observability_traces(id) ON DELETE CASCADE,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (environment_id) REFERENCES environments(id)
);

CREATE INDEX IF NOT EXISTS idx_observability_spans_trace_start
    ON observability_spans (organization_id, environment_id, trace_id, start_time ASC, id ASC);

CREATE TABLE IF NOT EXISTS observability_eval_results (
    id TEXT PRIMARY KEY,
    trace_record_id TEXT,
    organization_id TEXT NOT NULL,
    environment_id TEXT NOT NULL,
    trace_id TEXT NOT NULL,
    span_id TEXT,
    dataset_id TEXT,
    dataset_name TEXT,
    evaluator_name TEXT NOT NULL,
    score REAL,
    label TEXT,
    passed INTEGER,
    feedback_json TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    created_by TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (trace_record_id) REFERENCES observability_traces(id) ON DELETE SET NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (environment_id) REFERENCES environments(id)
);

CREATE INDEX IF NOT EXISTS idx_observability_eval_results_trace_created
    ON observability_eval_results (organization_id, environment_id, trace_id, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_observability_eval_results_dataset_created
    ON observability_eval_results (organization_id, environment_id, dataset_id, created_at DESC, id DESC);

CREATE TABLE IF NOT EXISTS observability_trace_annotations (
    id TEXT PRIMARY KEY,
    trace_record_id TEXT,
    organization_id TEXT NOT NULL,
    environment_id TEXT NOT NULL,
    trace_id TEXT NOT NULL,
    span_id TEXT,
    annotation_type TEXT NOT NULL,
    body_json TEXT NOT NULL,
    created_by TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (trace_record_id) REFERENCES observability_traces(id) ON DELETE SET NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (environment_id) REFERENCES environments(id)
);

CREATE INDEX IF NOT EXISTS idx_observability_trace_annotations_trace_created
    ON observability_trace_annotations (organization_id, environment_id, trace_id, created_at DESC, id DESC);

CREATE TABLE IF NOT EXISTS observability_trace_feedback (
    id TEXT PRIMARY KEY,
    trace_record_id TEXT,
    organization_id TEXT NOT NULL,
    environment_id TEXT NOT NULL,
    trace_id TEXT NOT NULL,
    span_id TEXT,
    rating TEXT NOT NULL,
    body_json TEXT NOT NULL,
    created_by TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (trace_record_id) REFERENCES observability_traces(id) ON DELETE SET NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (environment_id) REFERENCES environments(id)
);

CREATE INDEX IF NOT EXISTS idx_observability_trace_feedback_trace_created
    ON observability_trace_feedback (organization_id, environment_id, trace_id, created_at DESC, id DESC);
