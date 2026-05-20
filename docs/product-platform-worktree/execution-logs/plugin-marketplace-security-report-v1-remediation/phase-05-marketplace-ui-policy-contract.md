# Execution Log: Phase 5 - Marketplace UI Policy Contract

## 1. Phase Overview

| Phase | Goal | Status | Related Findings | Key Checklist Items |
|---|---|---|---|---|
| Phase 1: Signature Trust Roots | Replace demo/manifest-declared signature trust with trusted-root verification and fail-closed policy decisions. | Done | F-PLG-002 | Inspect signing schema; add trusted-root metadata; verify canonical signatures against active keys; reject forgeable/demo signatures; audit key lifecycle; regression tests. |
| Phase 2: Artifact Provenance Scan Gates | Require package provenance, SBOM, license, vulnerability, and malware scan evidence before install. | Done | F-PLG-003 | Add scan/provenance persistence; validate manifest artifacts; enforce install gates; audit findings; regression tests. |
| Phase 3: Fail-Closed Install Policy | Enforce explicit marketplace policy and review approval before installation. | Done | F-PLG-001 | Remove default-open policy behavior; require policy evidence; enforce approval/signature/scans; audit deny reasons; regression tests. |
| Phase 4: Runtime Tool Grants Lifecycle | Materialize tool-level runtime grants from installed plugins and revoke them on lifecycle changes. | Done | F-PLG-004 | Map permissions to tool gateway grants; enforce at runtime; revoke on uninstall; audit lifecycle; integration tests. |
| Phase 5: Marketplace UI Policy Contract | Align frontend policy states and install UI with backend `allow`/`deny` contract. | Done | F-PLG-005 | Normalize enums; show blocking gates; update Vitest coverage. |

## 2. Current Phase Checklist

- [x] Re-read selected audit report finding F-PLG-005.
- [x] Verify frontend policy result rendering and fixtures.
- [x] Replace `allowed` assumptions with backend `allow` or normalize explicitly at the API boundary.
- [x] Ensure install controls are disabled or clearly blocked for deny/missing gate states.
- [x] Render signature, review, artifact, runtime grant, and policy gate failures coherently.
- [x] Add regression test `test_marketplace_ui_accepts_allow_policy_result`.
- [x] Run focused frontend marketplace tests.
- [x] Fix failures and re-run focused frontend marketplace tests.
- [x] Run frontend typecheck/lint where applicable.
- [x] Update selected audit report remediation block for F-PLG-005.
- [x] Update this execution log and execution index.

## 3. Implementation Notes

Files modified:
- `packages/product-platform/frontend/src/api/marketplace.ts`
- `packages/product-platform/frontend/src/features/marketplace/MarketplacePage.tsx`
- `packages/product-platform/frontend/src/features/marketplace/MarketplacePage.test.tsx`
- `docs/audits/features/plugin-marketplace-security/report-v1`
- `docs/product-platform-worktree/execution-logs/plugin-marketplace-security-report-v1-remediation/phase-05-marketplace-ui-policy-contract.md`
- `docs/product-platform-worktree/execution-logs/plugin-marketplace-security-report-v1-remediation/00-execution-index.md`

Key changes:
- Added `policy_input` to the frontend `PluginPolicyResult` API type so Phase 3 policy evidence is available in Marketplace UI code.
- Added `marketplacePolicyDecision` to normalize legacy `allowed` values and backend `allow` values to the backend policy contract.
- Added `marketplacePolicyAllowsInstall` to enable installation only when the policy result belongs to the selected version, the decision is `allow`, and signature plus artifact-evidence policy gates were included in the policy check.
- Added a `Require Artifact Evidence` policy checkbox and included `require_artifact_evidence` in `marketplacePolicyPayloadFromValues`.
- Added an Artifact gate to `InstallGates` and rendered backend `allow` as `pass`.
- Updated MarketplacePage tests to use backend-style `allow` policy results, include `policy_input`, check artifact evidence during policy actions, and cover `test_marketplace_ui_accepts_allow_policy_result`.

Important implementation decisions:
- The UI accepts `allow` as the canonical backend decision and tolerates legacy `allowed` only through normalization.
- The install button remains fail-closed when the latest policy result is missing, belongs to a different selected version, is not `allow`, or lacks signature/artifact-evidence policy evidence.

## 4. Commands Run

| Command | Exit Code | Result | Relevant Output Summary |
|---|---:|---|---|
| Startup inspection commands listed in `00-execution-index.md` | 0 | Passed | Verified frontend marketplace test fixture uses `result: "allowed"` while backend policy evaluator returns `allow`. |
| `rg -n "F-PLG-005\|allowed\|allow\|policy_input\|require_signature\|check-policy\|InstallGates\|marketplacePolicyPayloadFromValues" docs/audits/features/plugin-marketplace-security/report-v1 packages/product-platform/frontend/src/features/marketplace/MarketplacePage.tsx packages/product-platform/frontend/src/features/marketplace/MarketplacePage.test.tsx packages/product-platform/frontend/src/api/marketplace.ts` | 0 | Passed | Located stale `allowed` UI checks in `MarketplacePage.tsx` and backend-style `allow` fixture coverage in the test file. |
| `sed -n '1,220p' packages/product-platform/frontend/src/api/marketplace.ts` | 0 | Passed | Confirmed `PluginPolicyResult` did not type `policy_input` before the fix. |
| `sed -n '500,940p' packages/product-platform/frontend/src/features/marketplace/MarketplacePage.tsx` | 0 | Passed | Confirmed install enablement and gate rendering compared against `allowed`. |
| `sed -n '1,260p' packages/product-platform/frontend/src/features/marketplace/MarketplacePage.test.tsx` | 0 | Passed | Reviewed MarketplacePage test workflow and policy fixture. |
| `cat packages/product-platform/frontend/package.json` | 0 | Passed | Confirmed frontend scripts: `test`, `typecheck`, `lint`, and `build`. |
| `sed -n '260,430p' packages/product-platform/frontend/src/features/marketplace/MarketplacePage.test.tsx` | 0 | Passed | Reviewed marketplace fetch mock and policy endpoint responses. |
| `sed -n '1040,1095p' packages/product-platform/frontend/src/features/marketplace/MarketplacePage.tsx` | 0 | Passed | Reviewed marketplace policy payload mapping. |
| `sed -n '220,360p' packages/product-platform/frontend/src/api/marketplace.ts` | 0 | Passed | Reviewed marketplace hooks and mutation query invalidation. |
| `npm test -- --run src/features/marketplace/MarketplacePage.test.tsx` | 1 | Failed as expected | Red run passed 3 tests and failed 2 workflow tests because backend-style `allow` did not enable installation. |
| `npm test -- --run src/features/marketplace/MarketplacePage.test.tsx` | 0 | Passed | Passed 6 tests after UI normalization and artifact gate changes. |
| `npm run typecheck` | 0 | Passed | TypeScript completed without errors. |
| `npm run lint` | 0 | Passed | ESLint completed without findings. |
| `npm run build` | 0 | Passed | Vite build succeeded; emitted a non-failing chunk-size warning for `dist/assets/index-CgnPVV47.js`. |

## 5. Observed Output

- Red focused Vitest run failed exactly on the audited behavior: after a successful policy check with backend `allow`, the UI did not create an installation because the Install button remained disabled by the stale `allowed` comparison.
- Green focused Vitest run passed 6 tests after remediation.
- Typecheck and lint passed without findings.
- Build passed with a non-failing Vite warning: `Some chunks are larger than 500 kB after minification`.

## 6. Issues Encountered and Fixes

1. What failed: MarketplacePage workflow tests could not find `Plugin installation created` after a policy check returned backend-style `allow`.
   Why it failed: `InstallPanel` and `InstallGates` compared `policyResult.result` with `allowed`.
   How it was fixed: Added `marketplacePolicyDecision`, updated install enablement and gate rendering to use canonical `allow`, and added a regression test with backend `allow`.
   Verified by: `npm test -- --run src/features/marketplace/MarketplacePage.test.tsx` passed 6 tests.

## 7. Deviations From Plan

None.

## 8. Remaining Work for Next Phase

No later phase. Final validation is complete; see `00-execution-index.md` for the full final validation command table.

## 9. Phase Completion Criteria

A phase is complete only when:

1. All related findings are fixed or explicitly blocked
2. All acceptance criteria are satisfied
3. Relevant tests are added or updated
4. Relevant tests pass
5. Type checks pass where applicable
6. Lint passes where applicable
7. Build passes where applicable
8. The audit report is updated
9. The execution log is updated
10. The execution index is updated
