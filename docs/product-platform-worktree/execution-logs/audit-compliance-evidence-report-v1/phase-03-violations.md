# Execution Log: Phase 3 - Violations

## 1. Phase Overview

| Phase | Goal | Status | Related Findings | Key Checklist Items |
|---|---|---|---|---|
| Phase 1: Audit Explorer Page And Export | Make audit records append-only, export complete verifiable audit data, and surface completeness/integrity metadata. | Done | F-AUD-001, F-AUD-002 | Append-only audit tables; hash checkpoints; export chain proof; complete export pagination; partial export metadata; tests. |
| Phase 2: Control Map And Evidence Recompute | Recompute evidence over complete source histories and persist auditor-verifiable evidence source metadata. | Done | F-AUD-002, F-AUD-003, F-AUD-004 | Paginated recompute; evidence source hashes; control mapping version; runtime action source inclusion; tests. |
| Phase 3: Violations | Ensure runtime/tool governance issues create compliance violations and are auditable. | Done | F-AUD-004 | Tool runtime violation mapping; runtime action audit linkage; SDK error telemetry correlation; tests. |
| Phase 4: Report Builder | Generate reports/exports with verification manifests, source hashes, completeness metadata, and UI warnings. | Done | F-AUD-002, F-AUD-003, F-AUD-004 | Verification manifest in reports; UI warnings; report JSON/Markdown proof fields; final validation. |

## 2. Current Phase Checklist

- [x] Re-read Phase 2 log and execution index before starting.
- [x] Verify Phase 2 is Done.
- [x] Confirm Tool Gateway runtime actions feed compliance evidence.
- [x] Add violation creation rules for denied/high-risk Tool Gateway runtime actions if missing.
- [x] Ensure violation status changes still emit audit events.
- [x] Ensure runtime action identifiers and policy decision identifiers are preserved in violation/evidence payloads.
- [x] Add SDK telemetry tests proving error/denied events preserve request and correlation IDs where gateway responses include them.
- [x] Add backend tests for runtime action compliance violation creation.
- [x] Run focused runtime audit, compliance violation, and SDK tests.
- [x] Inspect output and fix failures.
- [x] Update selected audit report remediation status for Phase 3 findings.
- [x] Update execution index.

## 3. Implementation Notes

Phase 3 started after the combined Phase 1/2 backend validation passed.

Phase 3 implementation notes:

- Files modified:
  - `packages/product-platform/src/product_platform/compliance/repository.py`
  - `packages/product-platform/tests/test_compliance_phase3.py`
  - `packages/product-platform/src/ophanix_tool_gateway/sdk.py`
  - `packages/product-platform/tests/test_tool_gateway_sdk_phase2.py`
  - `packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py`
  - `packages/ophanix-tool-gateway-sdk/tests/test_sdk_behavior.py`
  - `docs/audits/features/audit-compliance-evidence/report-v1`
- Key functions/classes/modules changed:
  - `ComplianceRepository.refresh_violations` now creates violations from denied/high-risk `tool_runtime_actions`.
  - SDK sync and async `call_tool` telemetry now includes response `request_id` and `correlation_id` on error/denied events where provided by the gateway.
- Behavior added or changed:
  - Denied Tool Gateway runtime action rows create LOG-1 compliance violations.
  - Runtime action identifiers and reason/error codes are preserved in violation source fields and reason text.
  - SDK telemetry error paths include gateway request/correlation IDs without exposing payloads or tokens.

## 4. Commands Run

| Command | Exit code | Result | Relevant output summary |
|---|---:|---|---|
| `PYTHONPATH=src python3 -m pytest tests/test_audit_phase3.py tests/test_compliance_phase1.py tests/test_compliance_phase2.py tests/test_compliance_phase3.py` | 0 | Phase 2 gate passed | 27 tests passed before Phase 3 began. |
| `PYTHONPATH=src python3 -m pytest tests/test_compliance_phase3.py` | 1 | Failed | New runtime action violation test failed because `agent_runtime` was not present in the test `agents` table. |
| `PYTHONPATH=src python3 -m pytest tests/test_compliance_phase3.py` | 0 | Passed | 5 tests passed after seeding a minimal runtime test agent. |
| `PYTHONPATH=src python3 -m pytest tests/test_sdk_behavior.py` | 0 | Passed | 44 standalone SDK behavior tests passed in `packages/ophanix-tool-gateway-sdk`. |
| `PYTHONPATH=src python3 -m pytest tests/test_tool_gateway_sdk_phase2.py` | 0 | Passed | 35 product-platform vendored SDK tests passed. |
| `PYTHONPATH=src python3 -m pytest tests/test_tool_gateway_runtime_audit_phase1.py tests/test_tool_gateway_runtime_audit_phase2.py tests/test_tool_gateway_runtime_audit_phase3.py` | 0 | Passed | 15 Tool Gateway runtime audit tests passed. |

## 5. Observed Output

Startup inspection found Tool Gateway runtime actions are stored in `tool_runtime_actions` and are not directly part of compliance recompute/export flows.

Phase 3 observed output:

- Runtime action evidence from Phase 2 is confirmed.
- A denied `tool_runtime_actions` row now creates an open LOG-1 violation with `source_type=tool_runtime_action`.
- SDK telemetry tests confirm `tool_call.error` and `tool_call.denied` events include response request/correlation IDs.
- Existing runtime audit persistence tests still pass.

## 6. Issues Encountered and Fixes

- Issue: New runtime action violation test used `agent_runtime` without a seeded agent row.
- Why it failed: `tool_runtime_actions.agent_id` has a foreign key to `agents`.
- Fix: Inserted a minimal test agent before creating the runtime action.
- Verified by: `PYTHONPATH=src python3 -m pytest tests/test_compliance_phase3.py` passed 5 tests.

## 7. Deviations From Plan

No Phase 3 deviations. Runtime action violation creation and SDK telemetry correlation were implemented within existing repositories and SDK clients.

## 8. Remaining Work for Next Phase

Phase 4 can start. It should render the verification, completeness, source hash, and runtime evidence data added in Phases 1 through 3.

## 9. Phase Completion Criteria

A phase is complete only when:

1. All related findings are fixed or explicitly blocked.
2. All acceptance criteria are satisfied.
3. Relevant tests are added or updated.
4. Relevant tests pass.
5. Type checks pass where applicable.
6. Lint passes where applicable.
7. Build passes where applicable.
8. The audit report is updated.
9. The execution log is updated.
10. The execution index is updated.
