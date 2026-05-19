ALTER TABLE api_keys
ADD COLUMN IF NOT EXISTS environment_ids_json TEXT NOT NULL DEFAULT '[]';

UPDATE api_keys
SET environment_ids_json = COALESCE(
    (
        SELECT json_build_array(e.id)::text
        FROM environments e
        WHERE e.organization_id = api_keys.organization_id
        ORDER BY e.created_at ASC, e.id ASC
        LIMIT 1
    ),
    '[]'
)
WHERE environment_ids_json = '[]';
