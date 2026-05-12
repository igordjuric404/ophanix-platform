ALTER TABLE tool_upstream_targets
    DROP COLUMN IF EXISTS auth_config_json;

ALTER TABLE tool_upstream_targets
    DROP COLUMN IF EXISTS query_parameter_allowlist_json;
