# Ophanix Product Platform Feature Validation Guide

This folder contains beginner-friendly validation instructions for the implemented Ophanix product-platform UI. The guide is grounded in the current repository implementation under `packages/product-platform`, including the product plans in `docs/product-platform-plan`, frontend routes, API handlers, service modules, database migrations, seed data, and automated tests.

Use the files in numeric order when validating a fresh local environment. Feature 1 confirms startup, authentication, tenant selection, and the app shell that every later feature depends on.

## Feature Index

1. [Authentication, App Shell, and Overview](feature-01-authentication-overview.md)
2. [Agent Registry, Lifecycle, and Credentials](feature-02-agent-registry-lifecycle-credentials.md)
3. [Policy Library, Bindings, Simulator, and Evaluation Feed](feature-03-policy-library-bindings-simulator.md)
4. [Trust Scores, Trust Cards, Thresholds, and Handshakes](feature-04-trust-scores-cards-handshakes.md)
5. [MCP Security](feature-05-mcp-security.md)
6. [Agent Mesh](feature-06-agent-mesh.md)
7. [Runtime Control](feature-07-runtime-control.md)
8. [Discovery and Reconciliation](feature-08-discovery-reconciliation.md)
9. [Marketplace Plugins](feature-09-marketplace-plugins.md)
10. [Compliance, Audit, Evidence, Reports, and Attestation](feature-10-compliance-audit-reports.md)

The implemented UI also includes supporting routes for `/observability`, `/integrations`, `/workflows`, `/demo-lab`, and a placeholder `/settings` route. Those routes are referenced from the feature guides when they support validation, but they are not counted as separate features in this guide.

## Repository Surfaces Reviewed

- Product plan docs: `docs/product-platform-plan/README.md`, `01-current-state-assessment.md`, `02-product-platform-gap-analysis.md`, `03-target-platform-architecture.md`, `04-dashboard-specification.md`, `05-end-to-end-demo-scenario.md`, and `06-implementation-dependencies.md`.
- Local demo docs: `packages/product-platform/README.md` and `packages/product-platform/LOCAL_DEMO.md`.
- Frontend route registry and router: `packages/product-platform/frontend/src/lib/routes.ts` and `packages/product-platform/frontend/src/app/router.tsx`.
- Implemented feature pages: `packages/product-platform/frontend/src/features/*`.
- API and auth handlers: `packages/product-platform/src/product_platform/api/app.py`, `auth.py`, and `settings.py`.
- Domain modules: `agents`, `policies`, `trust`, `mcp`, `mesh`, `runtime`, `discovery`, `marketplace`, `compliance`, `audit`, `integrations`, `observability`, `workflows`, and `demo`.
- Database migrations: `packages/product-platform/src/product_platform/db/migrations`.
- Seed data: `packages/product-platform/src/product_platform/db/seed.py`.
- Backend tests: `packages/product-platform/tests/test_*.py`.
- Frontend component and page tests: `packages/product-platform/frontend/src/features/**/*.test.tsx`.

## Local Startup

From the repository root:

```bash
cd packages/product-platform
./start.sh
```

Expected result:

- The frontend starts at `http://127.0.0.1:3000`.
- The API starts at `http://127.0.0.1:8088`.
- The script ensures `admin@example.com` is allowed for development login.
- The script seeds the default organization and environment if they do not already exist.

To run the Docker local demo instead:

```bash
cd packages/product-platform
cp .env.example .env
docker compose --env-file .env -f docker-compose.demo.yml up --build
```

Docker demo URLs:

- Frontend: `http://localhost:3000`
- Product API: `http://localhost:8088`
- Demo MCP server: `http://localhost:8091/health`
- Optional Grafana profile: `http://localhost:3001`
- Optional Prometheus profile: `http://localhost:9090`

## Required Environment

For local validation, these defaults are sufficient:

```text
OPHANIX_DATABASE_URL=postgresql://ophanix:ophanix-local@127.0.0.1:5432/ophanix_product
OPHANIX_DEFAULT_ORGANIZATION_ID=org_default
OPHANIX_DEV_LOGIN_ALLOWED_EMAILS=admin@example.com,demo@example.com
OPHANIX_SESSION_SECRET=replace-with-a-long-local-secret
OPHANIX_SESSION_TTL_SECONDS=28800
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

The seeded demo records are:

- Organization ID: `org_default`
- Organization name: `Ophanix Demo`
- Environment ID: `env_default`
- Environment name: `Development`
- Admin user ID: `user_admin`
- Admin email: `admin@example.com`

The frontend API client sends session cookies and the selected environment. Programmatic checks should include:

```bash
API=http://127.0.0.1:8088
COOKIE=/tmp/ophanix.cookies

curl -s -c "$COOKIE" \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.com","roles":["Platform Admin"]}' \
  "$API/api/v1/auth/dev-login"

curl -s -b "$COOKIE" "$API/api/v1/auth/me"
curl -s -b "$COOKIE" "$API/api/v1/organizations"
curl -s -b "$COOKIE" "$API/api/v1/environments"
```

Most feature examples use these headers:

```bash
-b "$COOKIE" \
-H 'Content-Type: application/json' \
-H 'X-Environment-ID: env_default'
```

## Test Accounts and Roles

Use `admin@example.com` for all beginner validation unless a feature file says otherwise. The login screen exposes these roles:

- `Platform Admin`: full access across implemented routes.
- `Policy Admin`: policy-focused access.
- `Security Admin`: MCP and security-focused access.
- `Compliance Admin`: compliance-focused access.
- `Operator`: operations-focused access.
- `Viewer`: read-oriented access; some nav items render disabled and protected routes show an access denied page.

The implemented auth flow is local development auth:

- UI route: `/login`
- API login: `POST /api/v1/auth/dev-login`
- API session: `GET /api/v1/auth/me`
- API logout: `POST /api/v1/auth/logout`
- Cookie name: `ophanix_session`

## Integration Setup Required: Okta or Other IdP

The repository contains deployment settings for an external identity provider, but the implemented local UI currently signs in through `/api/v1/auth/dev-login`. No complete browser OIDC redirect/callback flow was confirmed in the current frontend code.

For a cloud pilot, configure the IdP using `packages/product-platform/deploy/cloud/security.md`:

1. Create an Okta/OIDC application for the product-platform frontend.
2. Set the callback URL to `https://app.example.com/auth/callback`.
3. Set the logout URL to `https://app.example.com/auth/logout`.
4. Export `OPHANIX_IDP_ISSUER_URL`.
5. Export `OPHANIX_IDP_AUDIENCE`.
6. Set `OPHANIX_SESSION_SECRET` from a real secret manager.
7. Leave `OPHANIX_DEV_LOGIN_ALLOWED_EMAILS` empty to disable development login.
8. Set `CORS_ALLOWED_ORIGINS` to the exact frontend HTTPS origin.

Quick verification before claiming Okta works:

```bash
curl -s "$API/api/v1/system/dependencies" | jq
```

Expected: the identity-provider dependency should not be reported as missing. If the UI still only shows the local `Email` and `Role` form on `/login`, the production OIDC experience still needs implementation or verification.

## Resetting Demo State

For the Docker local demo, use `/demo-lab`:

1. Open `http://localhost:3000/demo-lab`.
2. Find `Environment Reset`.
3. Enter `RESET` in the confirmation field.
4. Click the reset button.

Programmatic reset endpoint:

```bash
curl -s -b "$COOKIE" \
  -H 'Content-Type: application/json' \
  -H 'X-Environment-ID: env_default' \
  -d '{"confirmation":"RESET"}' \
  "$API/api/v1/demo/reset"
```

This reset flow is demo-specific. Use it only when you intentionally want to remove demo-created agents, MCP servers, workflows, audit records, and related demo records.

## Automated Validation Commands

Backend:

```bash
cd packages/product-platform
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Frontend:

```bash
cd packages/product-platform/frontend
npm run validate
npm run test:e2e
```

Focused frontend page tests:

```bash
cd packages/product-platform/frontend
npm test -- AgentsPage.test.tsx
npm test -- PoliciesPage.test.tsx
npm test -- TrustPage.test.tsx
npm test -- McpPage.test.tsx
npm test -- MeshPage.test.tsx
npm test -- RuntimePage.test.tsx
npm test -- DiscoveryPage.test.tsx
npm test -- MarketplacePage.test.tsx
npm test -- CompliancePage.test.tsx
```

The last repository validation record found under `docs/product-platform-worktree/execution-logs/04-refactor-logs/final-validation.md` reports passing frontend validation, Playwright E2E, legacy tests, and 492 backend unit tests on 2026-05-03. Run the commands above again for current local confidence.

## How To Use Each Feature Guide

1. Start the API and frontend.
2. Sign in as `admin@example.com` with `Platform Admin`.
3. Select `Development` in the `Environment` selector if it is not already selected.
4. Follow each feature guide in order.
5. Use the UI checks first, then run the programmatic verification commands.
6. When a guide says "needs verification", do not treat that behavior as proven by the repository.

Unless otherwise stated, expected URLs use the local frontend host `http://127.0.0.1:3000` and the API host `http://127.0.0.1:8088`.
