# Execution Log: Phase 2 - Control Map And Evidence Recompute

## 1. Phase Overview

| Phase | Goal | Status | Related Findings | Key Checklist Items |
|---|---|---|---|---|
| Phase 1: Audit Explorer Page And Export | Make audit records append-only, export complete verifiable audit data, and surface completeness/integrity metadata. | Done | F-AUD-001, F-AUD-002 | Append-only audit tables; hash checkpoints; export chain proof; complete export pagination; partial export metadata; tests. |
| Phase 2: Control Map And Evidence Recompute | Recompute evidence over complete source histories and persist auditor-verifiable evidence source metadata. | Done | F-AUD-002, F-AUD-003, F-AUD-004 | Paginated recompute; evidence source hashes; control mapping version; runtime action source inclusion; tests. |
| Phase 3: Violations | Ensure runtime/tool governance issues create compliance violations and are auditable. | Done | F-AUD-004 | Tool runtime violation mapping; runtime action audit linkage; SDK error telemetry correlation; tests. |
| Phase 4: Report Builder | Generate reports/exports with verification manifests, source hashes, completeness metadata, and UI warnings. | Done | F-AUD-002, F-AUD-003, F-AUD-004 | Verification manifest in reports; UI warnings; report JSON/Markdown proof fields; final validation. |

## 2. Current Phase Checklist

- [x] Re-read Phase 1 log and execution index before starting.
- [x] Verify Phase 1 is Done.
- [x] Add migration fields for evidence source hashes, source manifest, control mapping version, predicate snapshot, trace/run/tool/policy identifiers, and artifact digest where available.
- [x] Add repository helpers to page all audit events for recompute.
- [x] Replace fixed 500-event recompute windows with complete pagination.
- [x] Replace fixed 500-event violation refresh windows with complete pagination or a shared source iterator.
- [x] Add Tool Gateway runtime action source inclusion for compliance evidence.
- [x] Persist source event hashes and verification metadata on evidence items.
- [x] Preserve deterministic recompute for fixed inputs.
- [x] Add or update evidence response models.
- [x] Add tests for recompute with more than 500 events.
- [x] Add tests for evidence source hashes and control versions.
- [x] Add tests for runtime action evidence inclusion.
- [x] Run focused compliance phase 2 tests.
- [x] Inspect output and fix failures.
- [x] Update selected audit report remediation status for Phase 2 findings.
- [x] Update execution index.

## 3. Implementation Notes

Phase 2 started after Phase 1 validation passed. Phase 1 introduced checkpoint/proof helpers that Phase 2 should reuse for evidence source hash metadata.

Phase 2 implementation notes:

- Files created:
  - `packages/product-platform/src/product_platform/db/migrations/0071_evidence_source_verification.up.sql`
  - `packages/product-platform/src/product_platform/db/migrations/0071_evidence_source_verification.down.sql`
- Files modified:
  - `packages/product-platform/src/product_platform/compliance/models.py`
  - `packages/product-platform/src/product_platform/compliance/repository.py`
  - `packages/product-platform/tests/test_compliance_phase2.py`
  - `docs/audits/features/audit-compliance-evidence/report-v1`
- Key functions/classes/modules changed:
  - `EvidenceItemResponse` now exposes source hash, source manifest, control mapping, trace/run/tool/policy, artifact checksum, and chain proof fields.
  - `EvidenceRecomputeResponse` now includes run id, runtime action count, completeness, cursor, and source range metadata.
  - `ComplianceRepository.recompute_evidence` now pages audit events and persists a `compliance_recompute_runs` row.
  - `ComplianceRepository.refresh_violations` now pages audit events instead of scanning a single 500-event window.
  - `ComplianceRepository._upsert_evidence` persists source hashes, mapping snapshots, and source manifests.
  - Runtime action evidence is created from `tool_runtime_actions` under the LOG-1 control.
- Behavior added or changed:
  - Recompute processes all matching audit events for each mapping.
  - Violation refresh can see denied/high-risk events beyond the first 500 rows.
  - Evidence items are auditor-verifiable against source event hashes and mapping snapshots.
  - Tool Gateway runtime actions appear in compliance evidence.

## 4. Commands Run

| Command | Exit code | Result | Relevant output summary |
|---|---:|---|---|
| `PYTHONPATH=src python3 -m pytest tests/test_audit_phase3.py tests/test_compliance_phase1.py` | 0 | Phase 1 gate passed | 14 tests passed before Phase 2 began. |
| `PYTHONPATH=src python3 -m pytest tests/test_compliance_phase2.py` | 0 | Existing tests passed | 5 tests passed before adding Phase 2 report-specific regression coverage. |
| `PYTHONPATH=src python3 -m pytest tests/test_compliance_phase2.py` | 0 | Expanded tests passed | 8 tests passed after adding recompute pagination, source hash, and runtime action evidence tests. |
| `PYTHONPATH=src python3 -m pytest tests/test_compliance_phase2.py` | 0 | Final Phase 2 tests passed | 9 tests passed after adding violation refresh pagination coverage. |
| `PYTHONPATH=src python3 -m pytest tests/test_compliance_phase3.py` | 0 | Regression check passed | 4 existing violation tests passed after recompute/refresh changes. |
| `PYTHONPATH=src python3 -m pytest tests/test_audit_phase3.py tests/test_compliance_phase1.py tests/test_compliance_phase2.py tests/test_compliance_phase3.py` | 0 | Combined validation passed | 27 tests passed in 43.34s before moving to Phase 3. |

## 5. Observed Output

Startup inspection found `ComplianceRepository.recompute_evidence` and `refresh_violations` use `limit=500`, and `evidence_items` lacks source hash/proof fields.

Phase 2 observed output:

- Existing Phase 2 tests passed before remediation-specific tests were added.
- Recompute with 505 policy decision events scanned 1010 mapping-event pairs and created 1010 evidence items.
- Violation refresh found a denied event older than the first 500-event page.
- Evidence API responses now include source event hashes, mapping versions, source manifests, and chain proof data.
- Runtime action evidence appears with `source_type=tool_runtime_action` and control code `LOG-1`.

## 6. Issues Encountered and Fixes

None encountered in Phase 2 implementation. The first focused run after code changes passed.

## 7. Deviations From Plan

No Phase 2 deviations. Recompute and violation refresh were implemented as complete paginated scans within the existing synchronous API path.

## 8. Remaining Work for Next Phase

Phase 3 can start. Runtime action evidence sources are now available, but violation creation for runtime action rows and SDK error telemetry correlation still need Phase 3 work.

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
