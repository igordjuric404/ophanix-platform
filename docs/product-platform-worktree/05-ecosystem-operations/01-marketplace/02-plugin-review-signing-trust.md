# Plugin Review, Signing, And Trust

## Feature Scope

Add plugin review workflow, signing key management, quality assessment, and usage-trust updates. This feature makes marketplace plugins evaluable and governable before and after installation.

## Existing Repo Assets To Reuse

- Trust tiers from `packages/agent-marketplace/src/agent_marketplace/trust_tiers.py`.
- Usage trust from `packages/agent-marketplace/src/agent_marketplace/usage_trust.py`.
- Quality assessment from `packages/agent-marketplace/src/agent_marketplace/quality_assessment.py`.
- Installer signature verification.

## Out Of Scope

- Commercial billing/licensing.
- External vulnerability feeds unless available through workflow runner.

## Data Model

Tables:

- `plugin_reviews`: id, plugin_version_id, status, reviewer_id, findings_json, decision_reason, created_at, decided_at.
- `plugin_signing_keys`: id, organization_id, name, public_key, status, created_by, created_at, revoked_at.
- `plugin_trust_events`: id, plugin_version_id, source_event_id, delta, reason, score_before, score_after, created_at.
- `plugin_quality_assessments`: id, plugin_version_id, score, dimensions_json, findings_json, created_at.

## API Surface

Implement:

- `POST /api/v1/marketplace/plugins/{version_id}/submit-review`
- `GET /api/v1/marketplace/reviews`
- `POST /api/v1/marketplace/reviews/{id}/approve`
- `POST /api/v1/marketplace/reviews/{id}/reject`
- `POST /api/v1/marketplace/signing-keys`
- `GET /api/v1/marketplace/signing-keys`
- `POST /api/v1/marketplace/plugins/{version_id}/assess-quality`
- `POST /api/v1/marketplace/plugins/{version_id}/recompute-trust`

## UI Surface

Marketplace -> Review Queue.

Marketplace -> Signing Keys.

Marketplace -> Usage Trust.

Plugin Detail -> Trust and Quality tabs.

## Implementation Phases

### Phase 1: Review Workflow

Steps:

1. Add review table and statuses.
2. Allow plugin version submission for review.
3. Allow reviewer approval/rejection with reason.
4. Prevent install of plugin versions requiring review until approved.

Tests:

- API test submit review.
- API test approve requires reviewer role.
- API test reject requires reason.
- Integration test unapproved plugin cannot be installed when review required.

### Phase 2: Signing Keys

Steps:

1. Add signing key table.
2. Store public keys and status.
3. Validate plugin signature against active keys.
4. Emit audit event for key add/revoke.

Tests:

- API test add signing key.
- Unit test plugin signature verifies with active key.
- Unit test revoked key does not verify.

### Phase 3: Quality Assessment

Steps:

1. Wrap existing quality assessment logic.
2. Feed manifest metadata, tests, docs, permissions, and scan results.
3. Store quality score and findings.
4. Show quality warnings in review and install flows.

Tests:

- Unit test low documentation score generates finding.
- API test quality assessment persists score.
- Component test quality findings render.

### Phase 4: Usage Trust

Steps:

1. Consume plugin usage events and incidents.
2. Apply usage trust scoring.
3. Store plugin trust events.
4. Update plugin version trust tier.

Tests:

- Unit test successful usage increases trust.
- Unit test incident decreases trust.
- Integration test trust recomputation updates tier.

### Phase 5: UI

Steps:

1. Build review queue.
2. Build signing key management page.
3. Add plugin Trust and Quality tabs.
4. Show review/signature/trust gates in install flow.

Tests:

- Component test review queue actions require reason.
- Component test signing key table renders status.
- Component test plugin trust tab shows event history.

## Overall Validation

- Submit plugin for review.
- Verify signature.
- Run quality assessment.
- Approve plugin.
- Generate usage event and recompute trust.

## Dependencies

- Plugin catalog.
- Event pipeline.
- Workflow runner for optional scans.

## Definition Of Done

- Plugin marketplace trust is based on review, signature, quality, and usage signals.
