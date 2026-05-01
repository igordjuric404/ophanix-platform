DROP INDEX IF EXISTS idx_protocol_bridge_health_checks_bridge_checked;
DROP TABLE IF EXISTS protocol_bridge_health_checks;
DROP INDEX IF EXISTS idx_protocol_bridge_routes_protocols;
DROP INDEX IF EXISTS idx_protocol_bridge_routes_bridge;
DROP TABLE IF EXISTS protocol_bridge_routes;
DROP INDEX IF EXISTS idx_protocol_bridges_scope_type_status;
DROP INDEX IF EXISTS idx_protocol_bridges_scope_created;
DROP TABLE IF EXISTS protocol_bridges;
DELETE FROM schema_migrations WHERE version = '0013';
