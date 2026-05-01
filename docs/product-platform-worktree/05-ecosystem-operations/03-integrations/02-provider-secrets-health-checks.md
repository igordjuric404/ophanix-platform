# Provider Secrets And Health Checks

## Feature Scope

Manage external provider credentials and run health checks for model providers, framework connectors, MCP servers, identity providers, observability providers, and secret stores.

## Existing Repo Assets To Reuse

- Existing framework integrations.
- Agent SRE observability integrations.
- MCP server registry.

## Out Of Scope

- Building a full secret manager. MVP should integrate with one or use encrypted local demo storage.
- Human SSO implementation. Auth plan covers product users.

## Data Model

Tables:

- `provider_credentials`: id, organization_id, name, provider_type, secret_ref, status, created_by, created_at, last_used_at.
- `integration_health_checks`: id, organization_id, environment_id, target_type, target_id, status, latency_ms, message, details_json, checked_at.

## API Surface

Implement:

- `POST /api/v1/integrations/provider-credentials`
- `GET /api/v1/integrations/provider-credentials`
- `POST /api/v1/integrations/provider-credentials/{id}/test`
- `POST /api/v1/integrations/health-checks`
- `GET /api/v1/integrations/health-checks`
- `GET /api/v1/integrations/health-checks/latest`

## UI Surface

Integrations -> Model Providers.

Integrations -> Secret Stores.

Integrations -> Observability Providers.

Integrations -> Connector Health.

## Implementation Phases

### Phase 1: Secret Reference Model

Steps:

1. Add provider credential table.
2. Define secret provider interface with demo local implementation.
3. Store only `secret_ref`, never raw secret.
4. Add create/list API with masked display.

Tests:

- API test creates credential and masks value.
- Security test raw secret is not stored.
- Unit test demo secret provider can retrieve by ref.

### Phase 2: Provider Tests

Steps:

1. Add test adapter per provider type.
2. For model provider, run minimal model/list or configured no-op validation.
3. For MCP server, call server health/discovery.
4. For observability provider, validate endpoint/token.

Tests:

- Unit test model provider health success with mocked adapter.
- Unit test invalid secret returns failed health.
- API test credential test stores health check.

### Phase 3: Scheduled Health Checks

Steps:

1. Add health check job.
2. Schedule checks per integration instance.
3. Store status, latency, and details.
4. Emit audit or incident event on repeated failure.

Tests:

- Integration test scheduled health job records result.
- Unit test repeated failure triggers event.
- API test latest health check returns newest result.

### Phase 4: UI

Steps:

1. Build credentials list with masked status.
2. Build add credential form.
3. Build health check table.
4. Add provider-specific setup instructions.

Tests:

- Component test credential value is never displayed.
- Component test test-credential action renders result.
- Component test failed health check shows remediation message.

## Overall Validation

- Add model provider key.
- Run health check.
- Link credential to framework connector.
- Confirm health appears in Integrations and Demo Lab prerequisites.

## Dependencies

- Auth/RBAC.
- Background worker.
- Event pipeline.
- Secret provider.

## Definition Of Done

- External dependencies are configured and validated through the product without exposing secrets.
