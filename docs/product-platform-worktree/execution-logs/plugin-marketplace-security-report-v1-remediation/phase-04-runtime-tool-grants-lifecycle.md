# Execution Log: Phase 4 - Runtime Tool Grants Lifecycle

## 1. Phase Overview

| Phase | Goal | Status | Related Findings | Key Checklist Items |
|---|---|---|---|---|
| Phase 1: Signature Trust Roots | Replace demo/manifest-declared signature trust with trusted-root verification and fail-closed policy decisions. | Done | F-PLG-002 | Trusted Ed25519 roots; canonical signature verification; key revocation; regression tests. |
| Phase 2: Artifact Provenance Scan Gates | Require package provenance, SBOM, license, vulnerability, and malware scan evidence before install. | Done | F-PLG-003 | Artifact evidence persistence; scan gate evaluation; digest binding; audit event; regression tests. |
| Phase 3: Fail-Closed Install Policy | Enforce explicit marketplace policy and review approval before installation. | Done | F-PLG-001 | Fresh explicit allow policy; signature/artifact/review gates; blocked install audit; install evidence IDs. |
| Phase 4: Runtime Tool Grants Lifecycle | Materialize tool-level runtime grants from installed plugins and revoke them on lifecycle changes. | Done | F-PLG-004 | Runtime grant table; Tool Gateway permission materialization; install/uninstall/disable audit and revocation; runtime denial tests. |
| Phase 5: Marketplace UI Policy Contract | Align frontend policy states and install UI with backend `allow`/`deny` contract. | Done | F-PLG-005 | Normalize enums; show blocking gates; update Vitest coverage. |

## 2. Current Phase Checklist

- [x] Re-read selected audit report finding F-PLG-004.
- [x] Inspect tool gateway permission schemas, repository methods, and runtime invocation enforcement.
- [x] Define minimal marketplace install to tool-grant mapping from plugin permissions/capabilities.
- [x] Persist plugin-originated tool grants bound to organization, environment, and optional agent.
- [x] Apply grants on install only after policy allow.
- [x] Revoke or disable grants on uninstall.
- [x] Ensure runtime tool invocation evaluates plugin-originated grants through Tool Gateway permission enforcement.
- [x] Audit grant creation, denial, and revocation with correlation context.
- [x] Add regression test `test_plugin_install_generates_runtime_tool_policy`.
- [x] Add integration tests for install grants, uninstall revocation, disabled-plugin revocation, and unauthorized tool use rejection.
- [x] Run focused backend tool-gateway/marketplace tests.
- [x] Fix failures and re-run focused backend tool-gateway/marketplace tests.
- [x] Update selected audit report remediation block for F-PLG-004.
- [x] Update this execution log and execution index.

## 3. Implementation Notes

Files created:
- `packages/product-platform/src/product_platform/db/migrations/0087_marketplace_runtime_tool_grants.up.sql`
- `packages/product-platform/src/product_platform/db/migrations/0087_marketplace_runtime_tool_grants.down.sql`
- `packages/product-platform/tests/test_plugin_marketplace_security_phase4.py`

Files modified:
- `packages/product-platform/src/product_platform/marketplace/repository.py`
- `packages/product-platform/src/product_platform/api/app.py`
- `packages/product-platform/tests/test_db_phase1.py`
- `docs/audits/features/plugin-marketplace-security/report-v1`
- `docs/product-platform-worktree/execution-logs/plugin-marketplace-security-report-v1-remediation/00-execution-index.md`

Key changes:
- Added `plugin_runtime_tool_grants` to persist plugin install, version, organization, environment, agent, Tool Gateway tool, scope, manifest capability/permission/risk class, linked `agent_tool_permission_id`, ownership, status, and metadata.
- Marketplace install now extracts manifest `tool_grants`, `runtime_tools`, or `tools` entries and requires each tool to be declared in signed plugin capabilities before creating a runtime grant.
- Target-agent installs with runtime tool grants create Tool Gateway `agent_tool_permissions`; Tool Gateway runtime decisions then allow only the installed plugin tools with matching credential scopes and deny tools not granted by the plugin install.
- Marketplace uninstall revokes marketplace-owned `agent_tool_permissions` and marks runtime grant rows revoked.
- Re-importing an existing plugin with status `disabled` disables active installations and revokes marketplace-owned runtime grants.
- FastAPI emits `marketplace.plugin.runtime_grants.created` and `marketplace.plugin.runtime_grants.revoked` audit events with correlation IDs and grant evidence.

Important decisions:
- Runtime grants are materialized through existing Tool Gateway enforcement instead of creating a parallel runtime policy engine.
- Manifest tool grant names must be present in signed `capabilities`; unsigned nested `tools` values cannot authorize tools outside signed capabilities.
- Environment-level installs without a target agent do not create Tool Gateway permissions. If a manifest declares runtime tool grants, target-agent install is required so runtime enforcement has a concrete agent principal.

## 4. Commands Run

| Command | Exit Code | Result | Relevant Output Summary |
|---|---:|---|---|
| `python3 -m compileall -q src/product_platform/marketplace src/product_platform/tool_gateway tests/test_plugin_marketplace_security_phase4.py` | 0 | Passed | Red-test file and affected packages compiled before implementation. |
| `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_plugin_marketplace_security_phase4.py' -v` | 1 | Failed as expected | Red test failed with `relation "plugin_runtime_tool_grants" does not exist`. |
| `python3 -m compileall -q src/product_platform/marketplace src/product_platform/api/app.py tests/test_plugin_marketplace_security_phase4.py tests/test_db_phase1.py` | 0 | Passed | Runtime grant implementation, API, Phase 4 test, and DB test compiled. |
| `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_plugin_marketplace_security_phase4.py' -v` | 0 | Passed | Passed 2 tests for install grant creation, runtime allow/deny, uninstall revocation, disabled-plugin revocation, and audit events. |
| `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_plugin_marketplace_security_phase*.py' -v` | 0 | Passed | Passed 11 marketplace security tests across Phases 1-4. |
| `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_marketplace_catalog_phase*.py' -v` | 0 | Passed | Passed 11 marketplace catalog tests. |
| `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_marketplace_catalog_overall.py' -v` | 0 | Passed | Passed 1 overall marketplace install test. |
| `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_plugin_review_signing_trust*.py' -v` | 0 | Passed | Passed 14 review/signing/trust tests. |
| `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_permissions_phase*.py' -v` | 0 | Passed | Passed 16 Tool Gateway permission tests. |
| `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_decision_phase1.py' -v` | 0 | Passed | Passed 3 Tool Gateway decision tests. |
| `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tool_gateway_invocation_phase1.py' -v` | 0 | Passed | Passed 3 Tool Gateway invocation tests. |
| `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_db_phase1.py' -v` | 0 | Passed | Passed 5 database migration tests, including apply and rollback coverage for `0087`. |

## 5. Observed Output

- The red test initially failed because `plugin_runtime_tool_grants` did not exist.
- After implementation, installing a plugin with signed capability `claims.lookup` created one runtime grant and one active Tool Gateway permission for `claims.lookup`.
- Runtime decision for `claims.lookup` returned `allow`; runtime decision for undeclared `claims.issue_refund` returned `deny`.
- Uninstall revoked the runtime grant and marketplace-owned Tool Gateway permission, and subsequent runtime decision for `claims.lookup` returned `deny`.
- Re-importing the same plugin with status `disabled` disabled the active installation, revoked runtime grant rows, revoked marketplace-owned Tool Gateway permissions, emitted a grant revocation audit event, and denied subsequent runtime calls.
- Broader marketplace, Tool Gateway, review/signing/trust, and migration suites passed.

## 6. Issues Encountered and Fixes

Issue: Phase 4 red test failed with `relation "plugin_runtime_tool_grants" does not exist`.

Why it failed: Marketplace install had no persisted runtime grant model and did not create Tool Gateway permissions.

Fix: Added migration `0087`, runtime grant extraction/materialization in `MarketplaceCatalogRepository`, audit events in FastAPI, and revocation paths on uninstall and plugin disable.

Verified by: `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_plugin_marketplace_security_phase4.py' -v` passed 2 tests.

## 7. Deviations From Plan

None.

## 8. Remaining Work for Next Phase

Phase 5 will align the frontend policy-result contract with backend `allow` and add UI/contract tests.

## 9. Phase Completion Criteria

1. All related findings are fixed or explicitly blocked: Done for F-PLG-004.
2. All acceptance criteria are satisfied: Done; install creates approved tool grants, unapproved tools are denied, and uninstall/disable revokes access.
3. Relevant tests are added or updated: Done.
4. Relevant tests pass: Done.
5. Type checks pass where applicable: Compile checks pass; broader type check deferred to final validation.
6. Lint passes where applicable: Deferred to final validation.
7. Build passes where applicable: Deferred to final validation.
8. The audit report is updated: Done.
9. The execution log is updated: Done.
10. The execution index is updated: Done.
