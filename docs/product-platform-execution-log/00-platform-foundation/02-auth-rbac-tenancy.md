# Auth, RBAC, And Tenancy Execution Log

Source plan: `docs/product-platform-worktree/00-platform-foundation/01-control-plane-api/02-auth-rbac-tenancy.md`

## Phase Overview

| Phase | Goal | Status | Biggest Checklist Items |
| --- | --- | --- | --- |
| Phase 1: Development Auth | Add allowlisted dev login, signed session token/cookie, current-user dependency, and fail-closed `/api/v1` protection. | Done | Login; token/cookie; auth dependency; protected routes; tests. |
| Phase 2: RBAC Enforcement | Define permissions, map roles, enforce permissions on routes, and audit denied admin actions. | Done | Permission constants; role matrix; permission dependency; denial audit hook; tests. |
| Phase 3: Organization And Environment Scoping | Add org/environment records, request context selection, and scoped query helpers. | Done | Tenant tables; context fields; org isolation; environment header convention; tests. |
| Phase 4: API Keys | Add scoped API keys with one-time secret display, hashing, revocation, last-used tracking, and scope enforcement. | Done | Key generation; hash/verify; scope checks; revoked handling; tests. |

## Detailed Checklist - Phase 1: Development Auth

- [x] Review Product API Shell log and current code before starting.
- [x] Add development auth settings for allowlisted emails and token signing secret.
- [x] Add auth models for users, sessions, roles, and principals.
- [x] Implement `POST /api/v1/auth/dev-login`.
- [x] Implement `POST /api/v1/auth/logout`.
- [x] Implement `GET /api/v1/auth/me`.
- [x] Add dependency that rejects unauthenticated `/api/v1` requests except explicitly public system/auth endpoints.
- [x] Add unit/API tests for unauthenticated rejection, login response, and dependency user availability.

## Detailed Checklist - Phase 2: RBAC Enforcement

- [x] Define permission constants for major resource groups.
- [x] Map Viewer, Operator, Policy Admin, Security Admin, Compliance Admin, and Platform Admin roles to permissions.
- [x] Add route dependency for permission checks.
- [x] Add audit event hook for denied admin actions.
- [x] Add unit test role-to-permission matrix.
- [x] Add API test verifying Viewer cannot create a policy.
- [x] Add API test verifying Policy Admin can create a policy placeholder route.
- [x] Run focused tests and inspect output.
- [x] Fix any failures and re-run until passing.

## Detailed Checklist - Phase 3: Organization And Environment Scoping

- [x] Add organization and environment models/store.
- [x] Add request context fields for selected organization and environment.
- [x] Require every product query to scope by organization and environment where applicable.
- [x] Add header convention for organization/environment selection.
- [x] Implement `GET /api/v1/organizations`.
- [x] Implement `GET /api/v1/environments`.
- [x] Add API test verifying user cannot access another organization.
- [x] Add API test verifying environment id is required for environment-scoped resources.
- [x] Add unit test query helpers always include organization id.
- [x] Run focused tests and inspect output.
- [x] Fix any failures and re-run until passing.

## Detailed Checklist - Phase 4: API Keys

- [x] Add API key creation with one-time secret display.
- [x] Store only hashed key material.
- [x] Support scoped API keys for agents, integrations, and CI workflows.
- [x] Record last used time.
- [x] Implement `POST /api/v1/api-keys`.
- [x] Implement `GET /api/v1/api-keys`.
- [x] Implement `DELETE /api/v1/api-keys/{id}`.
- [x] Add unit test API key hash verification.
- [x] Add API test verifying revoked key is rejected.
- [x] Add API test verifying scope-limited key cannot access forbidden route.
- [x] Run focused tests and inspect output.
- [x] Fix any failures and re-run until passing.

## Overall Validation Checklist

- [x] A Platform Admin can create an environment and API key.
- [x] A Viewer can inspect but not mutate resources.
- [x] All feature routes fail closed when no authenticated principal is present.
- [x] Every product resource is organization-scoped in the current in-memory implementation.
- [x] Environment-scoped resources require `X-Environment-ID`.
- [x] API keys are usable for automation without storing raw secrets.

## Activity Log

- 2026-04-30: Created initial execution log from implementation plan. Not started.
- 2026-04-30: Product API Shell completed and validated. Starting Auth/RBAC/Tenancy Phase 1 after reviewing prior logs and plan.
- 2026-04-30: Implemented Auth/RBAC/Tenancy Phase 1 development auth.
  - Added auth settings, HMAC-signed bearer/cookie sessions, allowlisted dev login, logout, `auth/me`, current-user dependency, and fail-closed `/api/v1` middleware.
  - Adjusted protected system endpoint tests to authenticate after `/api/v1` became fail-closed.
  - Issues fixed: missing `AuthResponse` import; request ID fallback for auth middleware responses; protected endpoint tests without auth.
  - Verified with `PYTHONPATH=src python3 -m unittest discover -s tests -v`; result: 18 tests passed.
  - Next: Phase 2 RBAC enforcement.
- 2026-04-30: Implemented Auth/RBAC/Tenancy Phase 2 RBAC enforcement.
  - Added permission constants, role-permission matrix, `require_permission`, denied admin action audit hook, and `/api/v1/policies` placeholder route requiring `policy:write`.
  - Added dev-login role selection for local/test users with role validation.
  - Verified with `PYTHONPATH=src python3 -m unittest discover -s tests -v`; result: 22 tests passed.
  - Next: Phase 3 organization and environment scoping.
- 2026-04-30: Implemented Auth/RBAC/Tenancy Phase 3 organization and environment scoping.
  - Added in-memory `TenantStore`, organization/environment models, selected org/env request validation, scoped org/env list routes, environment-required placeholder policy creation, and `apply_organization_scope`.
  - Verified user cannot access another org, env-scoped resources require `X-Environment-ID`, and query helpers force organization scope.
  - Verified with `PYTHONPATH=src python3 -m unittest discover -s tests -v`; result: 27 tests passed.
  - Next: Phase 4 API keys.
- 2026-04-30: Implemented Auth/RBAC/Tenancy Phase 4 API keys and overall validation.
  - Added one-time API key creation, PBKDF2-hashed secret storage, bearer API key auth, scope-based permission checks, revocation, last-used tracking, and API key list/delete routes.
  - Added `POST /api/v1/environments` for overall validation and Platform Admin tenant management.
  - Issue fixed: API key principal email initially used a `.local` reserved domain, causing Pydantic email validation errors; changed to `keys.ophanix.ai`.
  - Verified with `PYTHONPATH=src python3 -m unittest discover -s tests -v`; result: 34 tests passed.
  - Auth/RBAC/Tenancy is complete; next feature is Canonical Database Schema.
