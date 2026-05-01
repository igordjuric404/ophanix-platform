# Policy Editor And Linting

## Feature Scope

Build the policy editor and lint workflow. Users can edit YAML/JSON/Rego/Cedar bodies, validate them, view lint warnings, save a new version, and understand affected resources.

## Existing Repo Assets To Reuse

- Policy schema loader and validation from Agent OS.
- Policy linter from `packages/agent-compliance/src/agent_compliance/cli/lint_policy.py`.
- OPA/Cedar backend metadata from Agent OS policy backends.

## Out Of Scope

- Full policy impact simulation. Covered by simulator.
- Binding policies to agents/tools. Covered separately.

## Data Model

Uses:

- `policies`.
- `policy_versions`.

Optional:

- `policy_lint_results`: id, policy_version_id, severity, code, message, path, created_at.

## API Surface

Implement:

- `POST /api/v1/policies/lint`
- `POST /api/v1/policies/{id}/versions/draft`
- `POST /api/v1/policies/{id}/versions/{version_id}/lint`
- `GET /api/v1/policies/{id}/versions/{version_id}/lint-results`

## UI Surface

Policies -> Editor:

- Metadata panel.
- Code editor.
- Lint and validation panel.
- Affected resources panel.
- Save as version action.

## Implementation Phases

### Phase 1: Lint Service

Steps:

1. Wrap existing policy linter behind a service function.
2. Accept body text and body format.
3. Return structured lint results with severity, code, message, and path.
4. Normalize schema validation errors into the same result shape.

Tests:

- Unit test valid policy has no errors.
- Unit test missing required field returns error.
- Unit test unknown operator returns warning or error according to linter.

### Phase 2: Editor API

Steps:

1. Add lint endpoint for unsaved body.
2. Add draft-save endpoint that creates a non-active version.
3. Persist lint results for saved versions.
4. Require Policy Admin permission.

Tests:

- API test lint unsaved body.
- API test save draft creates version.
- API test Viewer cannot save draft.
- Integration test lint results are persisted.

### Phase 3: Editor UI

Steps:

1. Add code editor component with format selection.
2. Add metadata form for description, tags, backend, scope.
3. Add lint panel with clickable line/path results.
4. Add save version action.

Tests:

- Component test lint errors render.
- Component test save button disabled when fatal validation errors exist.
- Component test backend selector changes editor hints.

### Phase 4: Affected Resources Panel

Steps:

1. Query existing policy bindings for the selected policy.
2. Show affected agents, MCP tools, runtime actions, and environments.
3. Warn when saving a version would affect active bindings after activation.
4. Link to bindings page.

Tests:

- Component test affected resources list renders.
- API test affected resources are organization-scoped.
- Component test warning appears when active bindings exist.

## Overall Validation

- Open imported policy.
- Introduce a validation error and see lint result.
- Fix it and save a new version.
- Verify version history includes the saved body.

## Dependencies

- Policy library and versioning.
- Auth/RBAC.
- Frontend shell.

## Definition Of Done

- Policy editing is possible without manually changing repo files.
- Lint errors are structured, actionable, and saved with policy versions.
