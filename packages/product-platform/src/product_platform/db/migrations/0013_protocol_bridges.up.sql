CREATE TABLE IF NOT EXISTS protocol_bridges (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    environment_id TEXT NOT NULL,
    name TEXT NOT NULL,
    bridge_type TEXT NOT NULL,
    status TEXT NOT NULL,
    config_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (environment_id) REFERENCES environments(id)
);

CREATE INDEX IF NOT EXISTS idx_protocol_bridges_scope_created
    ON protocol_bridges (organization_id, environment_id, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_protocol_bridges_scope_type_status
    ON protocol_bridges (organization_id, environment_id, bridge_type, status);

CREATE TABLE IF NOT EXISTS protocol_bridge_routes (
    id TEXT PRIMARY KEY,
    bridge_id TEXT NOT NULL,
    source_protocol TEXT NOT NULL,
    target_protocol TEXT NOT NULL,
    source_agent_id TEXT,
    target_agent_id TEXT,
    policy_binding_id TEXT,
    enabled INTEGER NOT NULL CHECK (enabled IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (bridge_id) REFERENCES protocol_bridges(id),
    FOREIGN KEY (source_agent_id) REFERENCES agents(id),
    FOREIGN KEY (target_agent_id) REFERENCES agents(id),
    FOREIGN KEY (policy_binding_id) REFERENCES policy_bindings(id)
);

CREATE INDEX IF NOT EXISTS idx_protocol_bridge_routes_bridge
    ON protocol_bridge_routes (bridge_id, enabled, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_protocol_bridge_routes_protocols
    ON protocol_bridge_routes (source_protocol, target_protocol, enabled);

CREATE TABLE IF NOT EXISTS protocol_bridge_health_checks (
    id TEXT PRIMARY KEY,
    bridge_id TEXT NOT NULL,
    status TEXT NOT NULL,
    latency_ms INTEGER NOT NULL CHECK (latency_ms >= 0),
    message TEXT NOT NULL,
    checked_at TEXT NOT NULL,
    FOREIGN KEY (bridge_id) REFERENCES protocol_bridges(id)
);

CREATE INDEX IF NOT EXISTS idx_protocol_bridge_health_checks_bridge_checked
    ON protocol_bridge_health_checks (bridge_id, checked_at DESC, id DESC);
