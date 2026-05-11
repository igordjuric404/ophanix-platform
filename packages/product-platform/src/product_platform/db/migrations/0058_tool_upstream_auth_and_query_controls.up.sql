ALTER TABLE tool_upstream_targets
    ADD COLUMN auth_config_json TEXT;

ALTER TABLE tool_upstream_targets
    ADD COLUMN query_parameter_allowlist_json TEXT NOT NULL DEFAULT '[]';
