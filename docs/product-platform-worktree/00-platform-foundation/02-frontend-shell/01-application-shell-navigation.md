# Application Shell And Navigation

## Feature Scope

Build the frontend application shell: authenticated layout, top navigation, side navigation, environment selector, global search placeholder, notification center placeholder, and route scaffolding for all product areas.

## Existing Repo Assets To Reuse

- Dashboard information architecture from `docs/product-platform-plan/04-dashboard-specification.md`.
- Existing Streamlit dashboards only as content references, not frontend implementation patterns.

## Out Of Scope

- Implementing feature-specific pages.
- Visual redesign of product concepts.

## Data Model

No feature tables. Uses auth, organization, and environment APIs.

## API Surface

Consume:

- `GET /api/v1/auth/me`
- `GET /api/v1/organizations`
- `GET /api/v1/environments`
- `GET /api/v1/system/dependencies`
- `GET /version`

## UI Surface

Routes to scaffold:

- `/overview`
- `/agents`
- `/policies`
- `/trust`
- `/mcp`
- `/mesh`
- `/runtime`
- `/discovery`
- `/marketplace`
- `/compliance`
- `/observability`
- `/integrations`
- `/workflows`
- `/demo-lab`
- `/settings`

## Implementation Phases

### Phase 1: Frontend Project Shell

Steps:

1. Create or select the frontend application location.
2. Add routing.
3. Add base layout with header, side navigation, and content area.
4. Add placeholder pages for all top-level routes.

Tests:

- Component test renders shell.
- Route test verifies every top-level route renders placeholder.
- Lint/type check passes.

### Phase 2: Auth And Environment Context

Steps:

1. Fetch current user on app load.
2. Fetch organizations and environments.
3. Store selected organization and environment in app state.
4. Send environment selection on API requests.

Tests:

- Component test shows selected environment.
- API client test includes environment header.
- Route guard test redirects unauthenticated users.

### Phase 3: System Status And Notifications Placeholder

Steps:

1. Fetch `/system/dependencies`.
2. Show global status indicator.
3. Add notification center shell with empty state.
4. Add status tooltip with API version and dependency health.

Tests:

- Component test renders healthy status.
- Component test renders degraded status.
- API error state displays non-blocking warning.

### Phase 4: Navigation Permissions

Steps:

1. Use current user roles to hide or disable restricted sections.
2. Show access-denied page for unauthorized routes.
3. Keep direct URL access protected by API authorization.

Tests:

- Component test Viewer sees read-only sections.
- Component test Policy Admin sees policy pages.
- Route test unauthorized route shows access denied.

## Overall Validation

- User can log in, select environment, navigate all product sections, and see system health.
- No feature page needs to reinvent layout, auth context, or API client setup.

## Dependencies

- Product API shell.
- Auth, RBAC, and tenancy APIs.

## Definition Of Done

- Frontend has stable routes and layout for the full product.
- Every future page can be implemented inside this shell.
