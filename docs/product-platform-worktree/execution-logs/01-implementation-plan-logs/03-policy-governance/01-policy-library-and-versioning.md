# Policy Library And Versioning Execution Log

Source plan: `docs/product-platform-worktree/02-policy-governance/01-policy-management/01-policy-library-and-versioning.md`

## Phase Overview

| Phase | Goal | Status | Biggest Checklist Items |
| --- | --- | --- | --- |
| Phase 1: Policy Persistence | Create persistent policy/version storage with immutable bodies and checksums. | Done | Create tables; repository create/list/get/version methods; checksum function; organization-scoped API tests. |
| Phase 2: Import Existing YAML Policies | Import uploaded policy bodies or known repo paths through validation and create initial versions. | Done | Import endpoint; YAML/JSON parser; schema validation; import summary and warnings. |
| Phase 3: Activation And Rollback | Support one active version per policy, rollback to previous versions, and audit events. | Done | Active-version invariants; activation audit events; rollback action; archived-version guard. |
| Phase 4: Library UI | Build the policy library product surface. | Done | Policy table filters; version drawer; import dialog; activate/rollback/archive/export actions. |

## Detailed Checklist

### Phase 1: Policy Persistence

- [x] Add migration for `policies`, `policy_versions`, and `policy_imports`.
- [x] Add indexes for organization-scoped policy lookups and version history.
- [x] Implement checksum utility for version bodies.
- [x] Implement `PolicyRepository.create_policy`.
- [x] Implement `PolicyRepository.list_policies` with organization scope and filters.
- [x] Implement `PolicyRepository.get_policy` and not-found handling.
- [x] Implement `PolicyRepository.create_version` with immutable body/checksum storage.
- [x] Implement `PolicyRepository.list_versions`.
- [x] Add Pydantic request/response models for policy library APIs.
- [x] Add `POST /api/v1/policies`.
- [x] Add `GET /api/v1/policies`.
- [x] Add `GET /api/v1/policies/{id}`.
- [x] Add `POST /api/v1/policies/{id}/versions`.
- [x] Add `GET /api/v1/policies/{id}/versions`.
- [x] Test integration policy creation.
- [x] Test multiple versions.
- [x] Test checksum changes when body changes.
- [x] Test policy list is scoped by organization.

### Phase 2: Import Existing YAML Policies

- [x] Add request model accepting body text/body format or repo path.
- [x] Parse YAML and JSON without adding product-platform runtime dependency drift.
- [x] Validate native Agent OS policy documents where applicable.
- [x] Create imported policy and initial version.
- [x] Store a `policy_imports` record with status and summary JSON.
- [x] Return import summary including warnings.
- [x] Test valid YAML import.
- [x] Test invalid YAML validation error.
- [x] Test imported body is stored exactly.

### Phase 3: Activation And Rollback

- [x] Add active-version repository method.
- [x] Ensure one active version per policy.
- [x] Add archived-version guard.
- [x] Emit `policy.version.activated` audit event.
- [x] Implement rollback by activating a previous version.
- [x] Emit `policy.version.rolled_back` audit event.
- [x] Test activation deactivates prior active version.
- [x] Test rollback activates previous version.
- [x] Test archived version cannot be activated.
- [x] Test activation emits audit event.

### Phase 4: Library UI

- [x] Add frontend API client methods for policies, versions, import, export, activate, rollback, and archive.
- [x] Build policy table with filters for scope, owner, backend, status, and tag.
- [x] Build version history drawer/section.
- [x] Build import dialog/form.
- [x] Add activate, rollback, archive, and export controls.
- [x] Wire policy library route into existing shell/navigation.
- [x] Component test policy rows render.
- [x] Component test import dialog submits body.
- [x] Component test version drawer shows active version.

## Progress Notes

- 2026-05-01: Created initial execution log from the implementation plan and started Phase 1.
- 2026-05-01: Verified logs are stored under `ophanix-platform/docs/product-platform-execution-log/02-policy-governance`; corrected an initial path mistake where files were created one directory too high.
- 2026-05-01: Added `0006_policy_library` migration with `policies`, `policy_versions`, `policy_imports`, organization-scoped indexes, version-history indexes, and a partial unique index for one active version per policy. Updated `test_db_phase1.py` for migration `0006`. Validation command: `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_db_phase1.py' -v`; result: 3 tests passed.
- 2026-05-01: Removed user-table foreign keys from policy owner/creator fields to match existing dev-auth behavior where authenticated principals may not be seeded DB users. Re-ran `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_db_phase1.py' -v`; result: 3 tests passed.
- 2026-05-01: Added `product_platform.policies` package with Pydantic models, checksum/slug helpers, `PolicyRepository`, and row serializers. Added `test_policy_library_phase1.py` covering checksum changes, policy creation, multiple versions, and organization-scoped listing. Validation command: `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_policy_library_phase1.py' -v`; result: 4 tests passed.
- 2026-05-01: Added policy persistence API endpoints in `api/app.py` and `test_policy_library_api_phase1.py`. Validation command: `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_policy_library_api_phase1.py' -v`; result: 3 tests passed.
- 2026-05-01: Added policy import models/service, `POST /api/v1/policies/import`, import records, and `GET /api/v1/policies/{id}/export`. Validation command: `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_policy_library_phase2.py' -v`; result: 3 tests passed.
- 2026-05-01: Added activation, rollback, and archive repository methods and API endpoints with policy-version audit events. Initial Phase 3 tests exposed missing `environment_id` on policy audit events; fixed by using selected environment or the organization default environment from `TenantStore`. Validation command: `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_policy_library_phase3.py' -v`; result: 4 tests passed.
- 2026-05-01: Added frontend `policies.js`, policy route rendering, app loading/handlers, policy API client methods, package typecheck/lint coverage, and `test/policy-library.test.js`. Initial targeted command used the wrong test path; reran `node --test test/policy-library.test.js`; result: 6 tests passed. Full frontend validation command `npm run validate`; result: lint/typecheck passed and 68 tests passed.
- 2026-05-01: Added overall backend validation `test_policy_library_overall.py` for import, second version creation, activation, rollback, and audit API visibility. Validation command: `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_policy_library*.py' -v`; result: 15 tests passed.

## Completion Summary

- Implemented policy persistence in migration `0006_policy_library`.
- Implemented policy library repository, checksum, import parsing, export serialization, activation, rollback, archive, and audit events.
- Implemented FastAPI endpoints for policy CRUD/list/detail, versions, import, export, activate, rollback, and archive.
- Implemented frontend policy library surface with table filters, version history, import form, export panel, and action controls.
- Overall validation confirms the required plan flow: import existing policy, create a second version, activate it, roll back to the first version, and confirm audit events are visible through the audit event API.

## Next Feature

- Continue with `02-policy-editor-and-linting.md`, Phase 1: Lint Service.
