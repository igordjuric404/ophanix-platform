# Execution Log: Phase 3 - Fail-Closed Install Policy

## 1. Phase Overview

| Phase | Goal | Status | Related Findings | Key Checklist Items |
|---|---|---|---|---|
| Phase 1: Signature Trust Roots | Replace demo/manifest-declared signature trust with trusted-root verification and fail-closed policy decisions. | Done | F-PLG-002 | Trusted Ed25519 roots; canonical signature verification; key revocation; regression tests. |
| Phase 2: Artifact Provenance Scan Gates | Require package provenance, SBOM, license, vulnerability, and malware scan evidence before install. | Done | F-PLG-003 | Artifact evidence persistence; scan gate evaluation; digest binding; audit event; regression tests. |
| Phase 3: Fail-Closed Install Policy | Enforce explicit marketplace policy and review approval before installation. | Done | F-PLG-001 | Remove default-open policy fallback; require fresh allow result; enforce signature/artifact/review gates; audit denial; store install evidence IDs. |
| Phase 4: Runtime Tool Grants Lifecycle | Materialize tool-level runtime grants from installed plugins and revoke them on lifecycle changes. | Done | F-PLG-004 | Map permissions to tool gateway grants; enforce at runtime; revoke on uninstall; audit lifecycle; integration tests. |
| Phase 5: Marketplace UI Policy Contract | Align frontend policy states and install UI with backend `allow`/`deny` contract. | Done | F-PLG-005 | Normalize enums; show blocking gates; update Vitest coverage. |

## 2. Current Phase Checklist

- [x] Re-read selected audit report finding F-PLG-001.
- [x] Verify current install behavior in repository and API tests.
- [x] Define required marketplace install policy defaults from implementation plans and audit report.
- [x] Remove implicit `PluginPolicyCheckRequest()` install fallback that allows default-open installs.
- [x] Require a fresh explicit allow policy result before install.
- [x] Require review approval where manifest declares review requirement.
- [x] Require trusted signature and artifact gate evidence from Phases 1 and 2.
- [x] Add denial audit event for blocked marketplace installation attempts.
- [x] Add regression test `test_marketplace_install_fails_closed_without_policy`.
- [x] Add API tests for missing policy, stale policy, and successful compliant install.
- [x] Run focused backend install-policy tests.
- [x] Fix failures and re-run focused backend install-policy tests.
- [x] Update selected audit report remediation block for F-PLG-001.
- [x] Update this execution log and execution index.

## 3. Implementation Notes

Files created:
- `packages/product-platform/src/product_platform/db/migrations/0086_marketplace_install_policy_evidence.up.sql`
- `packages/product-platform/src/product_platform/db/migrations/0086_marketplace_install_policy_evidence.down.sql`
- `packages/product-platform/tests/test_plugin_marketplace_security_phase3.py`

Files modified:
- `packages/product-platform/src/product_platform/marketplace/models.py`
- `packages/product-platform/src/product_platform/marketplace/repository.py`
- `packages/product-platform/src/product_platform/api/app.py`
- `packages/product-platform/tests/test_db_phase1.py`
- `packages/product-platform/tests/test_plugin_review_signing_trust_overall.py`
- `docs/audits/features/plugin-marketplace-security/report-v1`
- `docs/product-platform-worktree/execution-logs/plugin-marketplace-security-report-v1-remediation/00-execution-index.md`

Key changes:
- `PluginPolicyResultResponse` now includes the policy input used for the result.
- `PluginInstallationResponse` now includes `policy_result_id`, `review_id`, and `artifact_evidence_id`.
- Migration `0086` adds `plugin_policy_results.policy_input_json` and evidence columns on `plugin_installations`.
- `MarketplaceCatalogRepository.check_policy` persists canonical policy input JSON.
- `MarketplaceCatalogRepository.create_installation` no longer creates a default permissive policy result. It now requires a fresh explicit `allow` result, signature and artifact gates in the policy input, review approval when required, passing artifact evidence, and records policy/review/artifact evidence IDs on install.
- FastAPI install route now emits `marketplace.plugin.install_blocked` audit events for blocked installation attempts before returning HTTP 409.
- The overall review/signing/trust integration test now recomputes policy after trust recomputation mutates the version, proving stale policy cannot be reused.

Important decisions:
- Stale policy detection compares latest policy result creation time with `plugin_versions.updated_at`. This intentionally forces policy recomputation after version evidence changes.
- Existing installations can retain nullable evidence columns for migration compatibility, but new installs require evidence before insert.

## 4. Commands Run

| Command | Exit Code | Result | Relevant Output Summary |
|---|---:|---|---|
| Startup inspection commands listed in `00-execution-index.md` | 0 | Passed | Verified previous `create_installation` created an empty default policy result when none existed. |
| `python3 -m compileall -q src/product_platform/marketplace src/product_platform/api/app.py tests/test_plugin_marketplace_security_phase3.py` | 0 | Passed | Marketplace, API, and Phase 3 regression test files compiled. |
| `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_plugin_marketplace_security_phase3.py' -v` | 0 | Passed | Passed 3 tests for missing policy denial, evidence-bound install storage, and stale policy rejection. |
| `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_plugin_marketplace_security_phase*.py' -v` | 0 | Passed | Passed 9 marketplace security tests across Phases 1-3. |
| `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_marketplace_catalog_phase*.py' -v` | 0 | Passed | Passed 11 marketplace catalog policy/install tests. |
| `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_marketplace_catalog_overall.py' -v` | 0 | Passed | Passed 1 overall marketplace install flow test. |
| `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_plugin_review_signing_trust*.py' -v` | 1 | Failed | First run failed 1 overall review/signing/trust test because policy was computed before trust recomputation changed the version, correctly making the policy stale. |
| `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_plugin_review_signing_trust*.py' -v` | 0 | Passed | Passed 14 review/signing/trust tests after updating the overall test to recompute policy immediately before install. |
| `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_db_phase1.py' -v` | 0 | Passed | Passed 5 database migration tests, including apply and rollback coverage for migration `0086`. |

## 5. Observed Output

- Focused Phase 3 tests passed: missing policy returned HTTP 409 and emitted `marketplace.plugin.install_blocked`; compliant install returned HTTP 201 with `policy_result_id` and `artifact_evidence_id`; stale policy returned HTTP 409 with a stale-policy message.
- Broader marketplace catalog and security tests passed after the fail-closed install change.
- Initial review/signing/trust overall test failed with `Plugin policy result is stale and must be recomputed.`, proving the stale guard works when version state changes after policy calculation.
- Database migration tests passed, including rollback.

## 6. Issues Encountered and Fixes

Issue: `test_overall_review_signature_quality_trust_flow` failed after Phase 3 stale-policy enforcement.

Why it failed: The test computed an allow policy result, then called trust recomputation, which updates the plugin version trust tier and `updated_at`. Installation correctly rejected the earlier policy result as stale.

Fix: Updated `packages/product-platform/tests/test_plugin_review_signing_trust_overall.py` to recompute an allow policy result after trust recomputation and before install.

Verified by: `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_plugin_review_signing_trust*.py' -v` passed 14 tests.

## 7. Deviations From Plan

None.

## 8. Remaining Work for Next Phase

Phase 4 will materialize runtime tool grants from approved marketplace installs and revoke them on uninstall/disable/revocation.

## 9. Phase Completion Criteria

1. All related findings are fixed or explicitly blocked: Done for F-PLG-001.
2. All acceptance criteria are satisfied: Done; missing/stale policy blocks install, signature/artifact/review gates are enforced, install rows store evidence IDs.
3. Relevant tests are added or updated: Done.
4. Relevant tests pass: Done.
5. Type checks pass where applicable: Compile checks pass; broader type check deferred to final validation.
6. Lint passes where applicable: Deferred to final validation.
7. Build passes where applicable: Deferred to final validation.
8. The audit report is updated: Done.
9. The execution log is updated: Done.
10. The execution index is updated: Done.
