# Auth, RBAC, And Tenancy

## Feature Scope

Add product authentication, role-based authorization, organization scoping, and environment scoping to the control plane. This feature makes every future dashboard and API route safe to expose to multiple users.

## Existing Repo Assets To Reuse

- Local WebSocket token security concepts from `packages/agent-os-vscode/SECURITY.md` for development-only local tokens.
- Agent identity primitives are not user auth. Do not reuse agent credentials as human user credentials.

## Out Of Scope

- Agent workload identity. Covered under agent registry and credential plans.
- External SCIM provisioning. Later enterprise feature.

## Data Model

Tables:

- `organizations`: id, name, slug, created_at.
- `environments`: id, organization_id, name, slug, type, created_at.
- `users`: id, email, display_name, status, created_at.
- `organization_memberships`: organization_id, user_id, role, status.
- `api_keys`: id, organization_id, name, hashed_secret, scopes, expires_at, last_used_at, revoked_at.
- `auth_sessions`: id, user_id, organization_id, expires_at, created_at.

Roles:

- Viewer.
- Operator.
- Policy Admin.
- Security Admin.
- Compliance Admin.
- Platform Admin.

## API Surface

Implement:

- `POST /api/v1/auth/dev-login`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me`
- `GET /api/v1/organizations`
- `GET /api/v1/environments`
- `POST /api/v1/api-keys`
- `GET /api/v1/api-keys`
- `DELETE /api/v1/api-keys/{id}`

Feature routes must declare required permissions.

## UI Surface

Settings pages:

- Users.
- Roles.
- Organizations.
- Environments.
- API Keys.

Global header:

- Organization selector.
- Environment selector.
- User menu.

## Implementation Phases

### Phase 1: Development Auth

Steps:

1. Add local development login with configured allowlist emails.
2. Create signed session cookie or bearer token.
3. Add current-user dependency.
4. Protect all `/api/v1` routes except health/version.

Tests:

- API test verifies unauthenticated request is rejected.
- API test verifies dev login returns current user.
- API test verifies current user is available in route dependencies.

### Phase 2: RBAC Enforcement

Steps:

1. Define permission constants for major resource groups.
2. Map roles to permissions.
3. Add route dependency for permission checks.
4. Add audit event hook for denied admin actions.

Tests:

- Unit test role-to-permission matrix.
- API test verifies Viewer cannot create a policy.
- API test verifies Policy Admin can create a policy placeholder route.

### Phase 3: Organization And Environment Scoping

Steps:

1. Add organization and environment tables.
2. Add request context fields for selected organization and environment.
3. Require every product query to scope by organization and environment where applicable.
4. Add header or query convention for environment selection.

Tests:

- API test verifies user cannot access another organization.
- API test verifies environment id is required for environment-scoped resources.
- Unit test query helpers always include organization id.

### Phase 4: API Keys

Steps:

1. Add API key creation with one-time secret display.
2. Store only hashed key material.
3. Support scoped API keys for agents, integrations, and CI workflows.
4. Record last used time.

Tests:

- Unit test API key hash verification.
- API test verifies revoked key is rejected.
- API test verifies scope-limited key cannot access forbidden route.

## Overall Validation

- A Platform Admin can create an environment and API key.
- A Viewer can inspect but not mutate resources.
- All feature routes fail closed when no authenticated principal is present.

## Dependencies

- Product API shell.
- PostgreSQL schema migration support.
- Secure random token generation.

## Definition Of Done

- Every route has a clear auth story.
- Every product resource is organization-scoped.
- Environment-scoped resources cannot leak across environments.
- API keys are usable for agents and automation without storing raw secrets.
