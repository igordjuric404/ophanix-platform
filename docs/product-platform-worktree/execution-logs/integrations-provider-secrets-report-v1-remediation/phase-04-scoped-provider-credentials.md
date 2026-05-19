# Execution Log: Phase 4 - Scoped Provider Credentials

## 1. Phase Overview

| Phase | Goal | Status | Related Findings | Key Checklist Items |
|---|---|---|---|---|
| Phase 1: Secret Governance And Redaction | Redact secret refs by default, gate visibility with a dedicated permission, reject unsafe in-memory production secret providers, and audit secret access. | Done | F-INT-003 | Verify current behavior; add secret-read permission; redact responses; audit secret access; production provider guard; tests; report update. |
| Phase 2: Delegated OAuth Lifecycle | Add OAuth app/session/consent/token-reference lifecycle support and SDK authorization challenge helpers. | Done | F-INT-002 | OAuth app/session/consent models; start/callback/revoke flows; token vault refs only; SDK helpers; tests; report update. |
| Phase 3: User Delegated Tool Execution And Approvals | Bind Tool Gateway calls to delegated user/provider account context, return pending authorization, support approval-required decisions, and audit the binding. | Done | F-INT-004 | Extend principal/decision models; pending auth and approval-required results; reuse approval queue concepts; runtime audit; tests; report update. |
| Phase 4: Scoped Provider Credentials | Scope credentials to environment, delegated subject, provider account, scopes, expiry, rotation, revocation, and allowed tool bindings. | Done | F-INT-001 | Credential migration; repository/API filters; execution selection rejection for expired/revoked/wrong scope; tests; report update. |

## 2. Current Phase Checklist

- [x] Re-read selected audit report, provider secrets plan, previous phase logs, and this execution log before coding.
- [x] Verify F-INT-001 against provider credential migrations, models, repository, and API routes.
- [x] Add environment scope to provider credentials with a safe legacy migration path.
- [x] Add delegated subject, provider account, credential type, scopes, expiry, rotation, revocation metadata, and allowed tool bindings.
- [x] Enforce environment scope in create/list/get/test and any credential selection used by Tool Gateway.
- [x] Reject expired/revoked credentials for tool execution and health/test selection where applicable.
- [x] Redact sensitive credential metadata for broad readers.
- [x] Add cross-environment credential access denial test.
- [x] Add expired/revoked credential tool-call rejection test.
- [x] Add credential response redaction test.
- [x] Run focused provider-secret and Tool Gateway tests.
- [x] Update selected audit report remediation status for F-INT-001.
- [x] Update execution index and this log.

## 3. Implementation Notes

Implemented F-INT-001 by making provider credentials environment-scoped and lifecycle-aware.

Verification:

- F-INT-001 was verified against current code. `0036_provider_credentials.up.sql` had no `environment_id`, delegated subject/account, credential type, scopes, expiry, rotation, revocation, or allowed-tool metadata. `IntegrationRegistryRepository.list_provider_credentials`, `get_provider_credential`, and `mark_provider_credential_used` filtered by organization only. `test_integration_provider_credential` retrieved the secret and ran health validation without status, expiry, or revocation checks. Framework instance config accepted `credential_id` without validating the credential was selectable in the request environment.

Files created:

- `packages/product-platform/src/product_platform/db/migrations/0077_provider_credential_scopes.up.sql`
- `packages/product-platform/src/product_platform/db/migrations/0077_provider_credential_scopes.down.sql`
- `packages/product-platform/tests/test_provider_credentials_scope_phase4.py`
- `docs/product-platform-worktree/execution-logs/integrations-provider-secrets-report-v1-remediation/phase-04-scoped-provider-credentials.md`

Files modified:

- `packages/product-platform/src/product_platform/api/app.py`
- `packages/product-platform/src/product_platform/integrations/models.py`
- `packages/product-platform/src/product_platform/integrations/repository.py`
- `packages/product-platform/frontend/src/api/integrations.ts`
- `packages/product-platform/tests/test_db_phase1.py`
- `docs/audits/features/integrations-provider-secrets/report-v1`
- `docs/product-platform-worktree/execution-logs/integrations-provider-secrets-report-v1-remediation/00-execution-index.md`

Key functions, classes, modules, routes, schemas, workers, or components changed:

- `ProviderCredentialCreateRequest` and `ProviderCredentialResponse`
- `IntegrationRegistryRepository.create_provider_credential`, `list_provider_credentials`, `get_provider_credential`, `mark_provider_credential_used`, `require_provider_credential_selectable`, `create_instance`, and `patch_instance`
- `provider_credential_response`
- Provider credential create/list/test and framework instance create/patch routes in `api/app.py`
- Frontend `ProviderCredential` TypeScript interface

Behavior added or changed:

- Provider credentials persist `environment_id`, `subject_type`, `subject_id`, `provider_account_id`, `credential_type`, `scopes_json`, `expires_at`, `rotation_status`, `revoked_at`, `revoked_by`, `revoked_reason`, `allowed_tool_ids_json`, and `updated_at`.
- Migration `0077` backfills legacy credentials into the oldest environment for their organization, then enforces non-null `environment_id`.
- Provider credential create/list/get/test paths are scoped by organization and environment.
- Expired, revoked, disabled, missing-scope, and disallowed-tool credentials are rejected before secret retrieval or framework connector selection.
- Broad credential list readers receive redacted `secret_ref`, `subject_id`, and `provider_account_id`; privileged secret readers can request sensitive metadata through the existing `include_secret_ref=true` permission gate.

Important implementation decisions:

- Existing org-wide credentials are not left global. The migration maps each legacy credential to the organization's oldest environment as a conservative compatibility path.
- Empty `allowed_tool_ids` means no tool restriction for legacy and simple API-key use cases; a non-empty list is enforced for connector selection.
- Health checks enforce status, expiry, revocation, and environment scope before retrieving secrets, but do not require allowed-tool membership.

## 4. Commands Run

| Command | Exit Code | Result | Relevant Output Summary |
|---|---:|---|---|
| `sed -n '1,470p' docs/audits/features/integrations-provider-secrets/report-v1` | 0 | Passed | Re-read the selected report and confirmed only F-INT-001 remained pending. |
| `sed -n '1,280p' docs/product-platform-worktree/implementation-plans/05-ecosystem-operations/03-integrations/02-provider-secrets-health-checks.md` | 0 | Passed | Re-read provider secrets plan. |
| `sed -n '1,220p' docs/product-platform-worktree/execution-logs/integrations-provider-secrets-report-v1-remediation/00-execution-index.md` | 0 | Passed | Re-read current durable index. |
| `sed -n '1,220p' docs/product-platform-worktree/execution-logs/integrations-provider-secrets-report-v1-remediation/phase-04-scoped-provider-credentials.md` | 0 | Passed | Re-read this phase log before coding. |
| `sed -n '1,220p' packages/product-platform/src/product_platform/db/migrations/0036_provider_credentials.up.sql` | 0 | Passed | Verified original provider credential table was organization-scoped. |
| `sed -n '1,260p' packages/product-platform/src/product_platform/integrations/models.py` | 0 | Passed | Verified provider credential API models lacked scoped metadata. |
| `sed -n '1,260p' packages/product-platform/src/product_platform/integrations/repository.py` | 0 | Passed | Verified provider credential repository filtered by organization only. |
| `sed -n '12640,13060p' packages/product-platform/src/product_platform/api/app.py` | 0 | Passed | Verified provider credential create/list/test handlers did not enforce scoped selection. |
| `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_provider_credentials_scope_phase4.py' -v` | 1 | Failed as expected | New regression tests failed with missing `environment_id`, missing `subject_id`, and expired credential health returning `201` instead of `409`. |
| `PYTHONPATH=src python3 -m compileall -q src/product_platform/integrations src/product_platform/api/app.py src/product_platform/db` | 0 | Passed | Scoped credential implementation compiled successfully. |
| `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_provider_credentials_scope_phase4.py' -v` | 1 | Failed | Two tests passed; environment-scope test hit `403 Environment access is denied` before credential scope logic. |
| `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_provider_credentials_scope_phase4.py' -v` | 1 | Failed | Environment-scope test still hit `403`; principal environment ids were not enough because the in-memory tenant store did not know `env_second`. |
| `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_provider_credentials_scope_phase4.py' -v` | 0 | Passed | Ran 3 tests; all passed after adding `env_second` to the test tenant store. |
| `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_db_phase1.py' -v` | 0 | Passed | Ran 5 tests; migration count, schema, and rollback coverage passed for 0077. |
| `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_provider_secrets_health*.py' -v` | 0 | Passed | Ran 21 tests; existing provider secret and health behavior still passed. |
| `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_framework_connector_registry*.py' -v` | 0 | Passed | Ran 10 tests; framework connector registry compatibility passed. |
| `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_integrations_oauth_lifecycle_phase2.py' -v` | 0 | Passed | Ran 3 tests; OAuth lifecycle remained green. |
| `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_delegated_execution_phase3.py' -v` | 0 | Passed | Ran 2 tests; delegated execution evidence remained green. |
| `npm run typecheck` from `packages/product-platform/frontend` | 0 | Passed | TypeScript frontend typecheck passed with the expanded `ProviderCredential` shape. |
| `npm test -- --runInBand` from `packages/product-platform/frontend` | 1 | Failed | Invalid command option; Vitest does not support Jest's `--runInBand`. |
| `npm test` from `packages/product-platform/frontend` | 1 | Failed | RBAC contract test found frontend permission constants missing backend `secrets:read`. |
| `npm test` from `packages/product-platform/frontend` | 0 | Passed | Ran 122 tests after adding `secrets:read` to frontend RBAC constants. |
| `npm run lint` from `packages/product-platform/frontend` | 0 | Passed | ESLint passed. |
| `npm run build` from `packages/product-platform/frontend` | 0 | Passed | Vite build passed with chunk-size warning. |
| `python3 -m mypy` from `packages/product-platform` | 0 | Passed | Mypy passed for configured backend files. |
| `python3 -m mypy` from `../ophanix-python-sdk` | 0 | Passed | Mypy passed for SDK. |
| `python3 -m ruff check src/product_platform/api/app.py src/product_platform/integrations tests/test_provider_credentials_scope_phase4.py tests/test_db_phase1.py` | 0 | Passed | Ruff passed on changed backend areas. |
| `python3 -m build` from `packages/product-platform` | 0 | Passed | Product platform sdist and wheel built. |
| `python3 -m build` from `../ophanix-python-sdk` | 0 | Passed | SDK sdist and wheel built. |
| `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_*.py' -v` | 0 | Passed | Ran 335 Tool Gateway tests in 270.479s; OK. |

## 5. Observed Output

Initial failing regression:

- `test_provider_credential_environment_scope_enforced` errored with `KeyError: 'environment_id'`.
- `test_sensitive_provider_credential_metadata_is_redacted_for_broad_readers` errored with `KeyError: 'subject_id'`.
- `test_expired_and_revoked_credentials_cannot_be_selected` failed because expired credential health returned `201` and ran provider validation.

Post-implementation validation:

- Phase 4 regression suite passed 3 tests.
- Migration suite passed 5 tests.
- Existing provider secret/health suite passed 21 tests.
- Framework connector registry suite passed 10 tests.
- OAuth lifecycle suite passed 3 tests.
- Delegated Tool Gateway execution suite passed 2 tests.
- Frontend typecheck, lint, tests, and build passed.
- Backend and SDK mypy passed.
- Backend focused ruff passed.
- Backend and SDK package builds passed.
- Broad Tool Gateway suite passed 335 tests.

## 6. Issues Encountered and Fixes

Issue 1:

- What failed: The first Phase 4 regression run failed with missing `environment_id`, missing `subject_id`, and an expired credential health test returning success.
- Why it failed: Provider credential schema and serializers lacked scoped metadata, and health selection did not enforce expiry/revocation.
- How it was fixed: Added migration `0077`, expanded models/responses, added environment-scoped repository lookup, and added `require_provider_credential_selectable`.
- Verified by: `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_provider_credentials_scope_phase4.py' -v` passed.

Issue 2:

- What failed: The environment scope test initially returned `403 Environment access is denied`.
- Why it failed: The test database contained `env_second`, but the in-memory `TenantStore` used by middleware did not.
- How it was fixed: Added `env_second` to the test `TenantStore` and logged the test user into both `env_default` and `env_second`.
- Verified by: `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_provider_credentials_scope_phase4.py' -v` passed.

Issue 3:

- What failed: Final `npm test` failed because frontend RBAC constants did not include backend permission `secrets:read`.
- Why it failed: Phase 1 added backend permission `Permission.SECRETS_READ`, but the frontend RBAC contract constants had not been updated.
- How it was fixed: Added `SECRETS_READ` to `packages/product-platform/frontend/src/lib/rbac.ts` and granted it to `Security Admin`.
- Verified by: `npm test`, `npm run lint`, and `npm run typecheck` passed.

## 7. Deviations From Plan

None.

## 8. Remaining Work for Next Phase

No later phase. Final validation is complete.

## 9. Phase Completion Criteria

1. All related findings are fixed or explicitly blocked - done, F-INT-001 fixed.
2. All acceptance criteria are satisfied - done.
3. Relevant tests are added or updated - done.
4. Relevant tests pass - done.
5. Type checks pass where applicable - done.
6. Lint passes where applicable - done.
7. Build passes where applicable - done.
8. The audit report is updated - done.
9. The execution log is updated - done.
10. The execution index is updated - done.
