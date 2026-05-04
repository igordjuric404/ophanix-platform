# Policy Library And Versioning

## Feature Scope

Build the persistent policy library with version history, import/export, metadata, status, ownership, and rollback. This feature makes policy files manageable from the product instead of scattered YAML in examples and packages.

## Existing Repo Assets To Reuse

- Policy schema from `packages/agent-os/src/agent_os/policies/schema.py`.
- Example policies from `packages/agent-os/examples/policies` and `packages/agent-mesh/examples/policies`.
- Shared policy schema from `packages/agent-os/src/agent_os/policies/shared.py`.

## Out Of Scope

- Policy editor UI. Covered separately.
- Runtime evaluation. Covered by simulator and evaluation feed.
- Binding policies to resources. Covered by bindings plan.

## Data Model

Tables:

- `policies`: id, organization_id, name, slug, description, scope, owner_user_id, status, tags_json, created_at, updated_at.
- `policy_versions`: id, policy_id, version_number, body_format, body_text, backend, checksum, created_by, created_at, activated_at, archived_at.
- `policy_imports`: id, organization_id, source_type, source_path, status, summary_json, created_at.

## API Surface

Implement:

- `POST /api/v1/policies`
- `GET /api/v1/policies`
- `GET /api/v1/policies/{id}`
- `POST /api/v1/policies/{id}/versions`
- `GET /api/v1/policies/{id}/versions`
- `POST /api/v1/policies/{id}/versions/{version_id}/activate`
- `POST /api/v1/policies/{id}/versions/{version_id}/rollback`
- `POST /api/v1/policies/import`
- `GET /api/v1/policies/{id}/export`

## UI Surface

Policies -> Library:

- Policy table.
- Version drawer.
- Import dialog.
- Export action.
- Activate and rollback actions.

## Implementation Phases

### Phase 1: Policy Persistence

Steps:

1. Create policy and version tables.
2. Add repository methods for create, list, get, and create version.
3. Store immutable policy version body.
4. Calculate checksum for version body.

Tests:

- Integration test creates policy.
- Integration test creates multiple versions.
- Unit test checksum changes when body changes.
- API test list is scoped by organization.

### Phase 2: Import Existing YAML Policies

Steps:

1. Add import endpoint that accepts uploaded body or known repo path.
2. Parse YAML/JSON through existing schema loader.
3. Create policy and initial version.
4. Return import summary including warnings.

Tests:

- API test imports valid YAML.
- API test invalid YAML returns validation error.
- Integration test imported policy version body matches source.

### Phase 3: Activation And Rollback

Steps:

1. Allow one active version per policy.
2. Add activation audit event.
3. Add rollback action that activates a previous version.
4. Prevent activating archived versions.

Tests:

- Integration test activating version deactivates prior active version.
- API test rollback activates previous version.
- API test archived version cannot be activated.
- Integration test activation emits audit event.

### Phase 4: Library UI

Steps:

1. Build policy table with filters for scope, owner, backend, status, tag.
2. Build version history drawer.
3. Add import dialog.
4. Add activate, rollback, archive, export actions.

Tests:

- Component test table renders policy rows.
- Component test import dialog submits body.
- Component test version drawer shows active version.

## Overall Validation

- Import existing example policy.
- Create a second version.
- Activate it.
- Roll back to the first version.
- Confirm all events appear in Audit Explorer.

## Dependencies

- Database schema.
- Event pipeline.
- Auth/RBAC.

## Definition Of Done

- Policies are centrally stored, versioned, importable, exportable, and auditable.
