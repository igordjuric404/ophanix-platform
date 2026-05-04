# Feature 10: Compliance, Audit, Evidence, Reports, and Attestation

## Feature Goal and Expected User Outcome

Validate that a compliance user can search audit events, export audit data, verify event hashes, map audit events to compliance controls, recompute evidence, triage violations, generate a report, download it, and attest the generated report.

The expected outcome is a filtered audit event list, an audit export artifact URI, hash verification status, mapped evidence, violation queue behavior, a generated report artifact, and a report attestation.

## Implementation Surface

- Frontend route: `/compliance`.
- Frontend page: `frontend/src/features/compliance/CompliancePage.tsx`.
- API endpoints include:
  - `GET /api/v1/audit/events`
  - `POST /api/v1/audit/events`
  - `GET /api/v1/audit/events/{event_id}`
  - `POST /api/v1/audit/events/{event_id}/verify`
  - `POST /api/v1/audit/verify-range`
  - `POST /api/v1/audit/export`
  - `GET /api/v1/compliance/frameworks`
  - `POST /api/v1/compliance/frameworks`
  - `GET /api/v1/compliance/controls`
  - `POST /api/v1/compliance/control-mappings`
  - `GET /api/v1/compliance/evidence`
  - `POST /api/v1/compliance/evidence/recompute`
  - `GET /api/v1/compliance/violations`
  - `PATCH /api/v1/compliance/violations/{violation_id}`
  - `GET /api/v1/compliance/reports`
  - `POST /api/v1/compliance/reports`
  - `GET /api/v1/compliance/reports/{report_id}`
  - `POST /api/v1/compliance/reports/{report_id}/generate`
  - `GET /api/v1/compliance/reports/{report_id}/download`
  - `POST /api/v1/compliance/reports/{report_id}/attest`
- Domain modules: `audit/store.py`, `audit/hash_chain.py`, `compliance/repository.py`.
- Default frameworks seeded by repository: `SOC 2`, `GDPR`, `EU AI Act`, and `Internal Governance`.
- Migrations: `0043_audit_exports.up.sql`, `0044_compliance_controls.up.sql`, `0045_compliance_violations.up.sql`, `0046_compliance_reports.up.sql`.
- Tests: `test_audit_*.py`, `test_compliance_*.py`, `frontend/src/features/compliance/CompliancePage.test.tsx`.

## Prerequisites and Required Test Data

- Sign in as `admin@example.com` with `Platform Admin` or `Compliance Admin`.
- Use environment `Development`.
- Generate audit events by completing earlier features, especially policy simulation, agent lifecycle, MCP proxy calls, runtime actions, and report generation.
- If no audit events exist, create one through the API before UI validation.

Suggested audit event for evidence mapping:

```json
{
  "organization_id": "org_default",
  "environment_id": "env_default",
  "event_type": "policy.decision",
  "source_component": "policy-engine",
  "actor_type": "user",
  "actor_id": "user_policy",
  "agent_id": "agent_compliance",
  "resource_type": "policy_evaluation",
  "resource_id": "peval_validation",
  "decision": "deny",
  "severity": "warning",
  "correlation_id": "corr-compliance-validation",
  "policy_id": "policy_validation",
  "payload_json": {
    "matched_rule": "deny_delete",
    "reason": "blocked for validation"
  }
}
```

## UI Validation Steps

1. Click `Compliance` in the left navigation.
2. Expected URL change: current route changes to `/compliance`.
3. Confirm page title `Compliance` and description `Audit explorer, control evidence, violations, and report attestations.`
4. In `Audit Events`, enter filters:
   - `Event`: `policy.decision`
   - `Source`: `policy-engine`
   - `Actor`: `user_policy`
   - `Resource Type`: `policy_evaluation`
   - `Resource`: `peval_validation`
   - `Decision`: `deny`
   - `Severity`: `warning`
   - `Correlation`: `corr-compliance-validation`
5. Click `Filter`.
6. Expected UI response:
   - A table row appears for the matching event.
   - If no records match, the empty state `No events` appears.
7. In the audit export form, set:
   - `Format`: `json`
8. Click `Export`.
9. Expected UI response: an output value appears, usually an artifact URI beginning with `audit-export://`.
10. Click `Open` on an audit row.
11. Expected UI response:
    - Event detail opens.
    - `Hash Verification` appears with status `verified`, `failed`, or `pending`.
    - `Correlation Timeline` appears and shows related events with the same correlation ID, or `Single event`.
12. In `Framework Controls`, confirm framework badges are visible:
    - `SOC 2 2026`
    - `GDPR Article 32`
    - `EU AI Act 2026`
    - `Internal Governance demo`
13. Confirm the controls table has columns:
    - `Framework`
    - `Control`
    - `Required Evidence`
    - `Fresh Evidence`
14. In `Mapped Evidence`, click `Recompute Evidence`.
15. Expected UI response:
    - A result line appears like `<evidence_count> mapped / <refreshed_count> refreshed`.
    - Evidence rows appear if mapped audit events exist.
    - If no evidence is mapped, empty state `No evidence` is visible.
16. Filter evidence:
    - `Control`: choose a control such as `CC6.6` if present, or leave `Any`.
    - `Status`: `fresh`
    - Click `Filter`
17. Expected UI response: matching evidence rows show control, evidence, source, and status.
18. In `Violation Queue`, filter:
    - `Status`: `open`
    - `Severity`: `warning`
    - Click `Filter`
19. Expected UI response:
    - Violations appear if the recompute produced open violations.
    - If no violations exist, empty state title `No violations` and description `Queue is clear.` appear.
20. For an open violation, click `Acknowledge`.
21. Expected UI response: status changes to acknowledged.
22. In the same violation or another open violation, enter `validation resolved` in `Resolution reason`.
23. Click `Resolve`.
24. Expected UI response: status changes to resolved and resolution reason appears.
25. In `Report Builder`, create a draft:
    - `Framework`: choose `SOC 2`
    - `Name`: `SOC 2 Evidence Report`
    - `From`: `2026-01-01`
    - `To`: `2026-12-31`
26. Click `Create Draft`.
27. Expected UI response: report row appears with status draft, framework, evidence count, and actions.
28. Click `Open` on the report row.
29. Expected UI response: report preview shows `Generate report`.
30. Click `Generate`.
31. Expected UI response:
    - Success message `Generated SOC 2 Evidence Report`.
    - Report status updates.
    - Artifact URI appears in the preview badge.
    - Preview shows rendered markdown content.
    - `Download` link appears in the report row.
32. In the preview attestation form, enter:
    - `Statement`: `I attest this report`
    - `Signature`: `validation-signature-ref`
33. Click `Attest`.
34. Expected UI response: attestation ID appears beside the button.
35. Click `Download`.
36. Expected URL or request: browser requests `/api/v1/compliance/reports/<report_id>/download`.
37. Expected UI response: Markdown report content downloads or opens, depending on browser settings.

## Expected Backend Effects

- Audit event creation appends canonical event records and hash-chain metadata.
- Audit event filtering reads tenant-scoped audit records.
- Export creates an audit export row and artifact metadata with `audit-export://...` URI.
- Event verification checks hash-chain integrity for the selected event.
- Compliance framework and control listing seeds default controls if they do not exist.
- Evidence recompute maps audit events to controls using control mappings.
- Violation refresh creates open violations for deny decisions, missing evidence, or stale evidence according to repository rules.
- Acknowledge and resolve update violation status and write compliance audit events.
- Report creation stores a draft report.
- Report generation renders markdown, stores artifact metadata, links it to the report, and writes `compliance.report.generated`.
- Attestation stores statement, optional signature reference, attesting user, and writes `compliance.report.attested`.

## Programmatic Verification

```bash
API=http://127.0.0.1:8088
COOKIE=/tmp/ophanix.cookies

curl -s -c "$COOKIE" \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.com","roles":["Compliance Admin"]}' \
  "$API/api/v1/auth/dev-login" >/dev/null
```

Create a mapped audit event:

```bash
curl -s -b "$COOKIE" \
  -H 'Content-Type: application/json' \
  -d '{
    "organization_id":"org_default",
    "environment_id":"env_default",
    "event_type":"policy.decision",
    "source_component":"policy-engine",
    "actor_type":"user",
    "actor_id":"user_policy",
    "agent_id":"agent_compliance",
    "resource_type":"policy_evaluation",
    "resource_id":"peval_validation",
    "decision":"deny",
    "severity":"warning",
    "correlation_id":"corr-compliance-validation",
    "policy_id":"policy_validation",
    "payload_json":{"matched_rule":"deny_delete","reason":"blocked for validation"}
  }' \
  "$API/api/v1/audit/events" | jq
```

Filter, export, verify, and recompute:

```bash
EVENT_ID=$(curl -s -b "$COOKIE" \
  "$API/api/v1/audit/events?event_type=policy.decision&source_component=policy-engine&decision=deny&correlation_id=corr-compliance-validation" \
  | jq -r '.[0].id')

curl -s -b "$COOKIE" -X POST "$API/api/v1/audit/events/$EVENT_ID/verify" | jq

curl -s -b "$COOKIE" -H 'Content-Type: application/json' -H 'X-Environment-ID: env_default' \
  -d '{"format":"json","filters":{"source_component":"policy-engine","decision":"deny"}}' \
  "$API/api/v1/audit/export" | jq

curl -s -b "$COOKIE" -H 'X-Environment-ID: env_default' "$API/api/v1/compliance/frameworks" | jq
curl -s -b "$COOKIE" -H 'X-Environment-ID: env_default' "$API/api/v1/compliance/controls" | jq

curl -s -b "$COOKIE" -H 'X-Environment-ID: env_default' -X POST \
  "$API/api/v1/compliance/evidence/recompute" | jq

curl -s -b "$COOKIE" -H 'X-Environment-ID: env_default' "$API/api/v1/compliance/evidence?status=fresh" | jq
curl -s -b "$COOKIE" -H 'X-Environment-ID: env_default' "$API/api/v1/compliance/violations?status=open" | jq
```

Create, generate, download, and attest a report:

```bash
FRAMEWORK_ID=$(curl -s -b "$COOKIE" -H 'X-Environment-ID: env_default' "$API/api/v1/compliance/frameworks" \
  | jq -r '.[] | select(.name=="SOC 2") | .id' | head -n 1)

REPORT_JSON=$(curl -s -b "$COOKIE" \
  -H 'Content-Type: application/json' \
  -H 'X-Environment-ID: env_default' \
  -d "{\"framework_id\":\"$FRAMEWORK_ID\",\"name\":\"SOC 2 Evidence Report API\",\"date_from\":\"2026-01-01\",\"date_to\":\"2026-12-31\"}" \
  "$API/api/v1/compliance/reports")

echo "$REPORT_JSON" | jq
REPORT_ID=$(echo "$REPORT_JSON" | jq -r '.id')

curl -s -b "$COOKIE" -H 'X-Environment-ID: env_default' -X POST \
  "$API/api/v1/compliance/reports/$REPORT_ID/generate" | jq

curl -s -b "$COOKIE" -H 'Content-Type: application/json' -H 'X-Environment-ID: env_default' \
  -d '{"statement":"I attest this report","signature_ref":"validation-signature-ref"}' \
  "$API/api/v1/compliance/reports/$REPORT_ID/attest" | jq

curl -s -b "$COOKIE" -H 'X-Environment-ID: env_default' \
  "$API/api/v1/compliance/reports/$REPORT_ID/download" | head
```

Focused automated tests:

```bash
cd packages/product-platform
PYTHONPATH=src python3 -m unittest \
  tests.test_audit_overall \
  tests.test_compliance_phase1 \
  tests.test_compliance_phase2 \
  tests.test_compliance_phase3 \
  tests.test_compliance_phase4 \
  -v

cd frontend
npm test -- CompliancePage.test.tsx
```

## Edge Cases and Alternative Flows

- No audit events: `Audit Events` shows `No events`; create events through earlier features or the API.
- Export with no filters: creates an export for the full accessible event set.
- Hash verification failure: treat as a serious integrity issue; inspect audit hash-chain records and do not use the report for evidence until resolved.
- Missing evidence: `Mapped Evidence` shows `No evidence`; recompute and confirm relevant audit events match control mappings.
- Resolve without reason: API validation requires a reason for status `resolved`.
- Attest before generate: `Attest` is disabled until `artifact_uri` exists.
- Invalid date range: report creation should reject `From` later than `To`.

## Integration Setup Required: External Evidence and Report Storage

Local validation stores export and report artifact metadata in the product-platform database and uses generated artifact URIs. Production evidence export may require external storage, SIEM, or GRC integration.

To validate external evidence delivery:

1. Configure object storage or the required artifact backend for the deployment.
2. Configure any SIEM/GRC destination outside the product platform.
3. Generate audit events through governed workflows.
4. Run audit export in `json`, `csv`, and `markdown`.
5. Confirm exported artifacts are retrievable outside the UI.
6. Generate a compliance report and download it.
7. Confirm artifact checksum and retention behavior in the external storage system.

Needs verification: exact production artifact backend settings and external GRC delivery are deployment-specific.

## Troubleshooting

- Framework dropdown is empty: call `GET /api/v1/compliance/frameworks`; the repository seeds defaults on list.
- Evidence count remains zero: check that audit event type and source component match a control mapping, for example `policy.decision` plus `policy-engine`.
- Violation queue unexpectedly fills with missing-evidence warnings: run enough feature flows to create fresh evidence for the default controls.
- Report generation fails: confirm the framework ID exists and evidence recompute has completed.
- Download link does not appear: generate the report first; drafts have no artifact URI.

