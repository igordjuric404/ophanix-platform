# Artifact And Attestation Store

## Feature Scope

Persist artifacts produced by workflows and compliance reports, attach them as evidence, and support governance attestations. Artifacts include reports, lint outputs, SBOMs, scan results, integrity manifests, and exported audit bundles.

## Existing Repo Assets To Reuse

- Compliance attestation models from `packages/agent-compliance`.
- Integrity and verify outputs from `agt`.
- Generated report artifacts from compliance report builder.

## Out Of Scope

- Long-term WORM storage.
- External notary or ledger.

## Data Model

Tables:

- `artifacts`: id, organization_id, environment_id, artifact_type, name, content_type, storage_uri, checksum, size_bytes, created_by, created_at.
- `artifact_links`: id, artifact_id, target_type, target_id, link_type, created_at.
- `attestations`: id, artifact_id, attested_by, statement, signature_ref, created_at.

## API Surface

Implement:

- `POST /api/v1/artifacts`
- `GET /api/v1/artifacts`
- `GET /api/v1/artifacts/{id}`
- `GET /api/v1/artifacts/{id}/download`
- `POST /api/v1/artifacts/{id}/links`
- `POST /api/v1/artifacts/{id}/attest`

## UI Surface

Workflows -> Artifacts.

Workflows -> Attestations.

Compliance report and evidence pages consume artifact links.

## Implementation Phases

### Phase 1: Artifact Storage Interface

Steps:

1. Define storage provider interface.
2. Implement local filesystem provider for demo.
3. Calculate checksum and size.
4. Store artifact metadata in DB.

Tests:

- Unit test checksum is calculated.
- Integration test artifact is stored and downloadable.
- Security test path traversal is rejected.

### Phase 2: Artifact Linking

Steps:

1. Add link table.
2. Link artifacts to workflow runs, compliance reports, audit exports, plugin assessments, and evidence items.
3. Add API to create and list links.

Tests:

- API test links artifact to workflow run.
- API test invalid target type rejected.
- Integration test linked artifacts are returned in target detail.

### Phase 3: Attestations

Steps:

1. Add attestation API requiring statement.
2. Store signer user and optional signature reference.
3. Emit audit event.
4. Display attestation history.

Tests:

- API test attestation requires statement.
- API test unauthorized user cannot attest.
- Integration test attestation emits audit event.

### Phase 4: UI

Steps:

1. Build artifact table with filters.
2. Build artifact detail with checksum, links, download.
3. Build attestation form.
4. Show linked artifacts on workflow and compliance pages.

Tests:

- Component test artifact table renders.
- Component test download link appears.
- Component test attestation form validates statement.

## Overall Validation

- Run workflow that produces artifact.
- Download artifact.
- Link it to evidence item.
- Attest artifact and confirm audit event.

## Dependencies

- Workflow runner.
- Event pipeline.
- Local or object storage.

## Definition Of Done

- Product outputs are durable, checksumed, linkable, and attestable.
