# Discovery Findings Reconciliation

## Feature Scope

Normalize raw discovery findings into product findings, calculate risk, match them against the agent registry, and provide triage actions: assign owner, register as agent, suppress, mark decommissioned, or create follow-up workflow.

## Existing Repo Assets To Reuse

- Inventory and risk models from `packages/agent-discovery`.
- `Reconciler` and registry provider abstraction from `packages/agent-discovery/src/agent_discovery/reconciler.py`.
- Risk scoring from `packages/agent-discovery/src/agent_discovery/risk.py`.

## Out Of Scope

- Running scans. Covered by scan runner.
- Building new enterprise scanners.

## Data Model

Tables:

- `discovery_findings`: id, organization_id, environment_id, fingerprint, detected_name, agent_type, source, owner_hint, registry_agent_id, status, risk_score, risk_level, first_seen_at, last_seen_at.
- `discovery_evidence`: id, finding_id, run_id, evidence_type, evidence_value, confidence, created_at.
- `discovery_suppressions`: id, finding_id, reason, expires_at, created_by, created_at.
- `reconciliation_actions`: id, finding_id, action_type, status, actor_id, result_json, created_at.

## API Surface

Implement:

- `GET /api/v1/discovery/findings`
- `GET /api/v1/discovery/findings/{id}`
- `POST /api/v1/discovery/findings/{id}/assign-owner`
- `POST /api/v1/discovery/findings/{id}/register-agent`
- `POST /api/v1/discovery/findings/{id}/suppress`
- `POST /api/v1/discovery/findings/{id}/mark-decommissioned`
- `POST /api/v1/discovery/reconcile-run/{run_id}`

## UI Surface

Discovery -> Findings:

- Findings table.
- Risk detail drawer.
- Evidence list.
- Reconciliation actions.

Discovery -> Risk Triage:

- High-risk queue.
- Suppression review.

## Implementation Phases

### Phase 1: Normalize Raw Findings

Steps:

1. Convert raw scanner payloads into normalized finding fields.
2. Deduplicate by fingerprint.
3. Update `first_seen_at` and `last_seen_at`.
4. Store evidence records linked to scan run.

Tests:

- Unit test same fingerprint updates existing finding.
- Integration test evidence is stored for finding.
- Unit test missing owner results in owner hint null.

### Phase 2: Risk Scoring

Steps:

1. Wrap existing discovery risk scorer.
2. Store risk score and risk level.
3. Include risk factors in finding detail.
4. Recalculate risk when finding status or owner changes.

Tests:

- Unit test unregistered no-owner finding is high risk.
- Unit test registered finding has lower risk.
- API test finding detail includes risk factors.

### Phase 3: Registry Reconciliation

Steps:

1. Implement product registry provider for discovery reconciler.
2. Match findings by DID, name, endpoint, config path, or fingerprint where possible.
3. Link matched findings to `agents`.
4. Mark unmatched findings as shadow candidates.

Tests:

- Integration test finding with matching DID links to agent.
- Integration test unmatched finding is shadow candidate.
- Unit test ambiguous match requires manual review.

### Phase 4: Triage Actions

Steps:

1. Implement assign owner action.
2. Implement register as agent action that opens or calls registration workflow.
3. Implement suppression with reason and optional expiry.
4. Implement mark decommissioned.
5. Emit audit event for every action.

Tests:

- API test assign owner updates finding.
- API test suppress requires reason.
- API test register creates agent draft or registered agent.
- Integration test triage action emits audit event.

### Phase 5: UI

Steps:

1. Build findings table with filters for risk, status, source, owner, registry match.
2. Build finding detail drawer with evidence and risk factors.
3. Add reconciliation action buttons.
4. Add suppression review view.

Tests:

- Component test high-risk finding renders.
- Component test action requires confirmation.
- Component test suppressed finding is hidden by default but can be filtered.

## Overall Validation

- Run discovery scan.
- Reconcile run.
- Find an unregistered agent.
- Register or suppress it.
- Confirm agent inventory and audit events update.

## Dependencies

- Discovery scan runner.
- Agent registration wizard.
- Agent inventory.
- Event pipeline.

## Definition Of Done

- Shadow AI findings become actionable product work items.
- Users can close the loop from discovery to governance registration or accepted suppression.
