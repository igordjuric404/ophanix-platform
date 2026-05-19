WITH ranked_environment_installs AS (
    SELECT
        id,
        ROW_NUMBER() OVER (
            PARTITION BY plugin_version_id, environment_id
            ORDER BY installed_at DESC, id DESC
        ) AS row_number
    FROM plugin_installations
    WHERE status = 'installed'
      AND target_agent_id IS NULL
)
UPDATE plugin_installations AS installation
SET status = 'uninstalled',
    uninstalled_at = COALESCE(uninstalled_at, installed_at)
FROM ranked_environment_installs AS ranked
WHERE installation.id = ranked.id
  AND ranked.row_number > 1;

WITH ranked_agent_installs AS (
    SELECT
        id,
        ROW_NUMBER() OVER (
            PARTITION BY plugin_version_id, environment_id, target_agent_id
            ORDER BY installed_at DESC, id DESC
        ) AS row_number
    FROM plugin_installations
    WHERE status = 'installed'
      AND target_agent_id IS NOT NULL
)
UPDATE plugin_installations AS installation
SET status = 'uninstalled',
    uninstalled_at = COALESCE(uninstalled_at, installed_at)
FROM ranked_agent_installs AS ranked
WHERE installation.id = ranked.id
  AND ranked.row_number > 1;

CREATE UNIQUE INDEX IF NOT EXISTS idx_plugin_installations_unique_active_environment
    ON plugin_installations (plugin_version_id, environment_id)
    WHERE status = 'installed' AND target_agent_id IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_plugin_installations_unique_active_agent
    ON plugin_installations (plugin_version_id, environment_id, target_agent_id)
    WHERE status = 'installed' AND target_agent_id IS NOT NULL;
