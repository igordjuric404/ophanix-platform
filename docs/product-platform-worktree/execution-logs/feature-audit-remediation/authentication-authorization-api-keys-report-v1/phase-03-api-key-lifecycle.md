# Execution Log: Phase 3 - API Key Lifecycle

## 1. Phase Overview

| Phase | Goal | Status | Related Findings | Key Checklist Items |
|---|---|---|---|---|
| Phase 1: Enterprise IdP And Environment RBAC | Add production OIDC/JWKS validation, reject production dev-token auth, map verified claims to roles/environment membership, and enforce human environment access. | Done | F-AUTH-001, F-AUTH-004 | OIDC/JWKS validator; production startup guard; IdP group/role/env claim mapping; human env fail-closed middleware; audited break-glass; frontend env guard; tests/report/logs. |
| Phase 2: User-Delegated Tool Authorization | Bind Tool Gateway calls to delegated user/provider authorization, support pending authorization decisions, audit user-agent-tool binding, and add SDK challenge handling. | Done | F-AUTH-002 | Delegated authorization persistence; pending authorization/approval decisions; runtime audit binding; invocation blocking; SDK challenge/status helpers; tests/report/logs. |
| Phase 3: API Key Lifecycle | Add mandatory expiry policy, atomic rotation, revoke reason/actor evidence, last-use/scope violation audit coverage, and tests. | Done | F-AUTH-003 | Lifecycle metadata migration; default TTL/max TTL enforcement; atomic rotate endpoint; revoke actor/reason evidence; expired/revoked/scope violation audit events; focused regression tests. |

## 2. Current Phase Checklist

- [x] Re-read selected audit report finding F-AUTH-003.
- [x] Verify current API-key hashing, expiry, environment scope, revoke, and last-used behavior.
- [x] Verify current API-key schema gaps for revoke reason/actor and rotation evidence.
- [x] Verify current audit event coverage for create, rotate, revoke, failed use, and scope violation.
- [x] Add migration/model fields for rotation/revoke evidence if missing.
- [x] Require expiry or policy-controlled lifetime for new production keys.
- [x] Add atomic rotate endpoint that creates replacement and revokes old key.
- [x] Record revoke reason, revoked-by actor, created-by actor, last use, and environment.
- [x] Emit audit events for create, rotate, revoke, failed use, expired use, revoked use, and scope violation.
- [x] Add API key rotation integration test.
- [x] Add expired key rejection test.
- [x] Add audit event tests for create/revoke/scope violation.
- [x] Run focused API-key tests.
- [x] Run related backend tests.
- [x] Update selected audit report remediation status for F-AUTH-003.
- [x] Update execution index.

## 3. Implementation Notes

Files created:

- `packages/product-platform/src/product_platform/db/migrations/0074_api_key_lifecycle_metadata.up.sql`
- `packages/product-platform/src/product_platform/db/migrations/0074_api_key_lifecycle_metadata.down.sql`
- `packages/product-platform/tests/test_auth_remediation_phase3.py`

Files modified:

- `packages/product-platform/src/product_platform/api/api_keys.py`
- `packages/product-platform/src/product_platform/api/app.py`
- `packages/product-platform/src/product_platform/api/settings.py`
- `packages/product-platform/tests/test_db_phase1.py`
- `docs/audits/features/authentication-authorization-api-keys/report-v1`
- `docs/product-platform-worktree/execution-logs/feature-audit-remediation/authentication-authorization-api-keys-report-v1/00-execution-index.md`

Key functions, classes, modules, routes, schemas, workers, or components changed:

- Added `ApiKeyRevokeRequest`, `ApiKeyRotateRequest`, `ApiKeyRotationResponse`, and `ApiKeyAuthenticationResult`.
- Extended `ApiKeyResponse` and `ApiKeyRecord` with `created_by`, `revoked_by`, `revoked_reason`, `rotated_from_key_id`, and `rotated_to_key_id`.
- Added `ApiKeyStore.get_key`, `revoke_key`, `rotate_key`, and `authenticate_with_result`; mirrored the same lifecycle behavior in `DatabaseApiKeyStore`.
- Added settings `api_key_default_ttl_seconds` and `api_key_max_ttl_seconds`.
- Added `POST /api/v1/api-keys/{key_id}/rotate`.
- Updated `POST /api/v1/api-keys` to apply expiry policy and persist `created_by`.
- Updated `DELETE /api/v1/api-keys/{key_id}` to persist `revoked_by` and `revoked_reason` while remaining backward-compatible with callers that omit a body.
- Added API-key auth failure audit events for expired/revoked valid keys and environment scope-violation audit events before returning the existing 403.

Behavior added or changed:

- API keys now always receive a policy-controlled expiry if the caller omits `expires_at`.
- API-key expiry is rejected if it is in the past or beyond the configured max TTL.
- Rotation creates a replacement key with a one-time secret, records `rotated_from_key_id`, revokes the previous key with actor/reason metadata, records `rotated_to_key_id`, and emits `admin.api_key.rotated` plus `admin.api_key.revoked`.
- Revoked and expired keys are rejected and audited with safe reason codes, without logging raw secrets.
- Out-of-scope environment use is rejected and audited as `auth.api_key.scope_violation` while preserving existing 403 response behavior.

Important implementation decisions:

- Default TTL uses settings rather than hard-requiring all clients to send `expires_at`, preserving existing API compatibility while satisfying a policy-controlled lifetime.
- Revoke request body is optional for compatibility, but a non-empty stored reason is always written.
- API-key scope violation remains in the tenancy middleware instead of authentication so existing authorization semantics and tests stay stable.
- Audit payloads include key IDs and lifecycle metadata but never raw API-key secrets.

## 4. Commands Run

| Command | Exit Code | Result | Relevant Output Summary |
|---|---:|---|---|
| `pwd && git status --short` | 0 | Passed | Confirmed current repo and pre-Phase-3 worktree state. |
| `sed -n '1,420p' packages/product-platform/src/product_platform/api/api_keys.py` | 0 | Passed | Verified hashing, optional expiry, revoke timestamp only, no rotation route support. |
| `sed -n '1320,1395p' packages/product-platform/src/product_platform/api/app.py && sed -n '1840,1885p' ... && sed -n '4880,5065p' ...` | 0 | Passed | Verified API-key auth middleware, store factory, create/list/revoke routes. |
| `sed -n '1,180p' .../0001_base_schema.up.sql && sed -n '1,120p' .../0064_api_key_environment_scope.up.sql && sed -n '1,80p' .../0064_api_key_environment_scope.down.sql` | 0 | Passed | Verified base API-key table and environment-scope migration. |
| `rg -n "api.key|api_key|api-keys|ApiKey" ...` | 0 | Passed | Located API-key code, tests, and report references. |
| `sed -n '1,95p' packages/product-platform/src/product_platform/api/app.py && sed -n '1348,1425p' ...` | 0 | Passed | Read imports and middleware environment-scope behavior. |
| `sed -n '100,155p' packages/product-platform/src/product_platform/api/settings.py && sed -n '1,230p' tests/test_auth_phase4.py` | 0 | Passed | Verified settings lacked API-key TTL fields and existing API-key tests expected backward compatibility. |
| `sed -n '1528,1665p' packages/product-platform/src/product_platform/api/app.py` | 0 | Passed | Read existing audit helper shape for admin settings and authz events. |
| `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_auth_remediation_phase3.py' -v` | 1 | Failed as expected | New tests initially showed missing default expiry, missing revoke metadata, missing rotation route, and a setup warm-up issue. |
| `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_auth_remediation_phase3.py' -v` | 1 | Failed as expected | After setup warm-up, failures were the product gaps: no expiry policy, no `created_by`, no rotation route, no revoke metadata. |
| `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_auth_remediation_phase3.py' -v` | 0 | Passed | 4 Phase 3 remediation tests passed. |
| `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_auth_phase4.py' -v` | 0 | Passed | 12 existing API-key tests passed. |
| `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_auth_overall.py' -v` | 0 | Passed | 2 auth overall tests passed. |
| `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_db_phase1.py' -v` | 0 | Passed | 5 migration tests passed with `0074_api_key_lifecycle_metadata`. |
| `python3 -m compileall -q src/product_platform/api/api_keys.py src/product_platform/api/app.py src/product_platform/api/settings.py tests/test_auth_remediation_phase3.py tests/test_db_phase1.py` | 0 | Passed | Touched Phase 3 Python files compiled. |
| `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_auth_remediation_phase*.py' -v` | 0 | Passed | 12 selected-report remediation tests passed across all phases. |
| `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_auth_phase*.py' -v` | 0 | Passed | 25 auth phase tests passed. |
| `python3 -m ruff check src/product_platform/api/api_keys.py src/product_platform/api/app.py src/product_platform/api/settings.py tests/test_auth_remediation_phase3.py tests/test_db_phase1.py` | 0 | Passed | Ruff passed for touched Phase 3 backend/test files. |
| `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_api_shell_phase2.py' -v` | 0 | Passed | 8 API shell phase 2 tests passed. |
| `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_api_shell_phase3.py' -v` | 0 | Passed | 8 API shell phase 3 tests passed. |
| `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_mvp_cloud_deployment_phase*.py' -v` | 0 | Passed | 19 MVP cloud deployment smoke tests passed. |
| `python3 -m compileall -q src/product_platform/api src/product_platform/db tests/test_auth_remediation_phase1.py tests/test_auth_remediation_phase2.py tests/test_auth_remediation_phase3.py tests/oidc_test_utils.py` | 0 | Passed | Final selected-report backend compile validation passed. |

## 5. Observed Output

- Initial Phase 3 regression run failed on the expected gaps: `expires_at` was `None`, response metadata lacked `revoked_by`, `DatabaseApiKeyStore.create_key` rejected `created_by`, and `POST /api/v1/api-keys/{key_id}/rotate` returned 404.
- After implementation, focused Phase 3 tests passed:
  - Default expiry and creator metadata are present.
  - Rotation revokes the old key, links replacement metadata, rejects old secret, and keeps replacement secret working.
  - Explicit revoke stores actor and reason.
  - Expired key use and environment scope violations are rejected and audited.
- Existing API-key tests still passed, including no-body revocation and 403 environment-denial behavior.
- Migration apply/rollback validation passed with the new `0074` lifecycle metadata migration.
- Ruff and compile validation passed.

## 6. Issues Encountered and Fixes

1. What failed: Initial Phase 3 test attempted direct database insertion before lazy API database initialization.
   Why it failed: `app.state.database` was `None` until an API-key route initialized the migrated test database.
   How it was fixed: Warmed the API-key route in test setup with `GET /api/v1/api-keys`.
   Verified by: Re-running `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_auth_remediation_phase3.py' -v`.

2. What failed: New tests showed missing expiry policy, lifecycle metadata, rotation route, and denied-use audit behavior.
   Why it failed: F-AUTH-003 was verified as still partially implemented in the current codebase.
   How it was fixed: Added `0074` metadata migration, store lifecycle methods, API-key TTL settings, rotation route, revoke metadata persistence, and denied-use audit events.
   Verified by: Focused Phase 3 test suite, existing auth/API-key tests, migration tests, compile, and Ruff.

## 7. Deviations From Plan

No material deviations. The implementation uses a policy-controlled default TTL instead of requiring every caller to send `expires_at`, preserving backward compatibility with existing API clients while satisfying the mandatory lifetime requirement.

## 8. Remaining Work for Next Phase

None. No later phase is defined for this selected report.

## 9. Phase Completion Criteria

1. All related findings are fixed or explicitly blocked: Done, F-AUTH-003 fixed.
2. All acceptance criteria are satisfied: Done.
3. Relevant tests are added or updated: Done.
4. Relevant tests pass: Done.
5. Type checks pass where applicable: No dedicated type-check command is configured for the backend; Python compile validation passed.
6. Lint passes where applicable: Done.
7. Build passes where applicable: Backend compile validation and deployment smoke tests passed; no separate backend build command is configured.
8. The audit report is updated: Done.
9. The execution log is updated: Done.
10. The execution index is updated: Done.
