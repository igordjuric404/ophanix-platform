# Plugin Catalog And Installation

## Feature Scope

Create a product marketplace catalog and installation workflow. Users can view plugins, inspect manifests, check policy compatibility, install approved plugins into environments, and uninstall them with audit history.

## Existing Repo Assets To Reuse

- Manifest model from `packages/agent-marketplace/src/agent_marketplace/manifest.py`.
- Registry from `packages/agent-marketplace/src/agent_marketplace/registry.py`.
- Installer from `packages/agent-marketplace/src/agent_marketplace/installer.py`.
- Marketplace policy from `packages/agent-marketplace/src/agent_marketplace/marketplace_policy.py`.

## Out Of Scope

- Publishing and review workflow.
- Signing key management.
- Usage trust scoring.

## Data Model

Tables:

- `plugins`: id, organization_id, name, description, publisher, plugin_type, status, created_at.
- `plugin_versions`: id, plugin_id, version, manifest_json, package_ref, signature_status, quality_score, trust_tier, created_at.
- `plugin_installations`: id, plugin_version_id, environment_id, target_agent_id, status, installed_by, installed_at, uninstalled_at.
- `plugin_policy_results`: id, plugin_version_id, result, findings_json, created_at.

## API Surface

Implement:

- `GET /api/v1/marketplace/plugins`
- `GET /api/v1/marketplace/plugins/{id}`
- `POST /api/v1/marketplace/plugins/import`
- `POST /api/v1/marketplace/plugins/{version_id}/check-policy`
- `POST /api/v1/marketplace/installations`
- `GET /api/v1/marketplace/installations`
- `POST /api/v1/marketplace/installations/{id}/uninstall`

## UI Surface

Marketplace -> Catalog.

Marketplace -> Installed.

Plugin Detail.

## Implementation Phases

### Phase 1: Catalog Persistence

Steps:

1. Create plugin and version tables.
2. Import sample plugin manifests.
3. Validate manifests with existing manifest model.
4. Store manifest JSON and derived summary fields.

Tests:

- API test imports valid manifest.
- API test invalid manifest rejected.
- Integration test catalog list returns imported plugin.

### Phase 2: Policy Compatibility Check

Steps:

1. Wrap marketplace policy evaluator.
2. Check plugin type, required capabilities, signature status, organization restrictions.
3. Store result and findings.
4. Block install when policy result is deny.

Tests:

- Unit test unsigned plugin denied when signature required.
- Unit test allowed plugin passes.
- API test check-policy persists result.

### Phase 3: Installation Workflow

Steps:

1. Add install endpoint requiring target environment and optional target agents.
2. Check policy before install.
3. Call existing installer where possible for local demo.
4. Record install state and emit audit event.
5. Add uninstall endpoint.

Tests:

- API test install allowed plugin.
- API test install denied plugin fails.
- API test uninstall updates status.
- Integration test install emits audit event.

### Phase 4: UI

Steps:

1. Build catalog table.
2. Build plugin detail with manifest, permissions, versions, policy status.
3. Build install wizard.
4. Build installed plugins table.

Tests:

- Component test catalog renders plugin rows.
- Component test install wizard shows required capabilities.
- Component test denied plugin displays policy finding.

## Overall Validation

- Import two sample plugins.
- Install signed allowed plugin.
- Attempt unsigned restricted plugin and verify it is blocked.
- Confirm audit and installed-state UI.

## Dependencies

- Policy bindings/evaluator.
- Agent inventory.
- Event pipeline.

## Definition Of Done

- Marketplace install behavior is governed by policy and visible in product state.
