# Feature 04: Trust Scores, Trust Cards, Thresholds, and Handshakes

## Feature Goal and Expected User Outcome

Validate that a governance operator can calculate trust scores, inspect signal events, issue and verify trust cards, configure protected-action thresholds, and simulate peer handshakes.

The expected outcome is visible trust score state for agents, persisted card records, threshold records, and handshake attempts with allow or deny decisions.

## Implementation Surface

- Frontend route: `/trust`.
- Frontend page: `frontend/src/features/trust/TrustPage.tsx`.
- API endpoints include:
  - `GET /api/v1/trust/scores`
  - `GET /api/v1/trust/scores/{agent_id}`
  - `GET /api/v1/trust/events`
  - `POST /api/v1/trust/recalculate`
  - `GET /api/v1/trust/rules`
  - `PATCH /api/v1/trust/rules/{rule_id}`
  - `GET /api/v1/trust/thresholds`
  - `POST /api/v1/trust/thresholds`
  - `PATCH /api/v1/trust/thresholds/{threshold_id}`
  - `POST /api/v1/trust/handshakes/simulate`
  - `POST /api/v1/trust/handshakes/record`
  - `GET /api/v1/trust/handshakes`
  - `GET /api/v1/trust/cards`
  - `POST /api/v1/trust/cards`
  - `GET /api/v1/trust/cards/{card_id}`
  - `POST /api/v1/trust/cards/{card_id}/verify`
  - `POST /api/v1/trust/cards/{card_id}/revoke`
  - `GET /api/v1/agents/{agent_id}/trust-card`
- Domain modules: `trust/pipeline.py`, `trust/repository.py`, `trust/cards.py`, `trust/handshakes.py`.
- Migrations: `0009_trust_score_pipeline.up.sql`, `0010_trust_cards.up.sql`, `0011_trust_handshakes.up.sql`.
- Tests: `test_trust_score_pipeline_*.py`, `test_trust_card_management_*.py`, `test_handshakes_thresholds_*.py`, `frontend/src/features/trust/TrustPage.test.tsx`.

## Prerequisites and Required Test Data

- Sign in as `admin@example.com` with `Platform Admin`.
- Create and activate at least two agents from Feature 02:
  - Source agent for handshakes.
  - Target agent for handshakes.
- If you only have one agent, create a second agent using the same registration flow with a different name, for example `Claims Reviewer`.

## UI Validation Steps

1. Click `Trust` in the left navigation.
2. Expected URL change: current route changes to `/trust`.
3. Confirm page title `Trust` and description `Trust scores, cards, thresholds, and handshakes.`
4. Confirm summary metrics:
   - `Average Score`
   - `Trusted Agents`
   - `Signals`
5. In `Agent Trust Scores`, click `Recalculate`.
6. Expected UI response:
   - If agents exist, the score table populates or refreshes.
   - If no agents exist, the table shows `No scores` and `Run recalculation to populate scores.`
7. If an agent row appears, click `Recalculate Agent`.
8. Expected UI response: that row's score, tier, or updated timestamp refreshes.
9. In `Signal Mapping`, confirm trust rules are listed.
10. Click `Disable` on a rule.
11. Expected UI response: the rule status changes and the action becomes `Enable`.
12. Click `Enable` to restore it.
13. In `Score Events`, filter:
    - `Dimension`: `policy_compliance`
    - `Agent`: enter a known agent ID
    - Click `Filter`
14. Expected UI response:
    - Matching score events appear, or the empty state `No events` is visible.
    - Rows show agent, dimension, delta, reason, and source.
15. In `Card Inventory`, issue a trust card:
    - `Card Agent`: enter a known agent ID
    - `Issuer`: `ophanix-demo-issuer`
    - Click `Issue`
16. Expected UI response:
    - A card row appears with agent, issuer, status, valid-until date, and actions.
17. Click `Open` on the card row.
18. Expected UI response:
    - `Card Detail` shows DID, score, signature, and raw JSON.
19. Click `Verify`.
20. Expected UI response: verification message starts with `Verified` for a valid card, or `Invalid` with a reason if validation fails.
21. In `Revocation Reason`, enter `validation cleanup`.
22. Click `Revoke`.
23. Expected UI response:
    - The card status changes to revoked.
    - A revoked banner or revoked state appears.
24. In `Protected Actions`, create a threshold:
    - `Threshold Type`: `handoff`
    - `Target Type`: `environment`
    - `Target ID`: leave blank for environment-wide threshold or enter `env_default`
    - `Minimum Score`: `700`
    - `Required Tier`: `trusted`
25. Click `Create`.
26. Expected UI response: a threshold row appears.
27. In the threshold row, change minimum score or required tier and click `Save`.
28. Expected UI response: row updates without disappearing.
29. In `Peer Attempts`, simulate a handshake:
    - `Sim Source`: source agent ID
    - `Sim Target`: target agent ID
    - `Type`: `handoff`
    - `Capabilities`: `claims:read,tools:run`
    - Check `Card` if the source or target has a valid card.
    - Check `Credential` if credentials should be considered.
30. Click `Simulate`.
31. Expected UI response:
    - Message `Handshake simulated`.
    - Result displays `allowed`, `denied`, or equivalent result text with a reason.
32. Use filters:
    - `Source`: source agent ID
    - `Target`: target agent ID
    - `Result`: `allowed` or `denied`
    - Click `Filter`
33. Expected UI response: matching handshake attempts appear in the table.
34. Open a handshake detail.
35. Expected UI response: detail includes route, reason, required score or tier, source score, target score, and raw metadata.

## Expected Backend Effects

- Recalculation writes or refreshes trust score records for agents.
- Rule enable/disable updates persisted trust rule state.
- Score events are recorded for calculated deltas and mapped signals.
- Card issue creates a signed card payload and stores issuer, score, tier, status, and JSON.
- Card verification checks stored card integrity and returns validity state.
- Card revocation records status and reason.
- Threshold creation persists protected-action requirements.
- Handshake simulation evaluates scores, card, credential, threshold, and capability context and stores or returns an attempt result.

## Programmatic Verification

```bash
API=http://127.0.0.1:8088
COOKIE=/tmp/ophanix.cookies

curl -s -c "$COOKIE" \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.com","roles":["Platform Admin"]}' \
  "$API/api/v1/auth/dev-login" >/dev/null

AGENT_ID=$(curl -s -b "$COOKIE" -H 'X-Environment-ID: env_default' "$API/api/v1/agents" | jq -r '.[0].id')
TARGET_ID=$(curl -s -b "$COOKIE" -H 'X-Environment-ID: env_default' "$API/api/v1/agents" | jq -r '.[1].id // .[0].id')
```

Recalculate and inspect trust:

```bash
curl -s -b "$COOKIE" -H 'Content-Type: application/json' -H 'X-Environment-ID: env_default' \
  -d "{\"agent_id\":\"$AGENT_ID\"}" \
  "$API/api/v1/trust/recalculate" | jq

curl -s -b "$COOKIE" -H 'X-Environment-ID: env_default' "$API/api/v1/trust/scores" | jq
curl -s -b "$COOKIE" -H 'X-Environment-ID: env_default' "$API/api/v1/trust/events?agent_id=$AGENT_ID" | jq
```

Issue and verify a trust card:

```bash
CARD_JSON=$(curl -s -b "$COOKIE" \
  -H 'Content-Type: application/json' \
  -H 'X-Environment-ID: env_default' \
  -d "{\"agent_id\":\"$AGENT_ID\",\"issuer\":\"ophanix-demo-issuer\"}" \
  "$API/api/v1/trust/cards")

echo "$CARD_JSON" | jq
CARD_ID=$(echo "$CARD_JSON" | jq -r '.id')

curl -s -b "$COOKIE" -H 'Content-Type: application/json' -H 'X-Environment-ID: env_default' \
  -d '{}' \
  "$API/api/v1/trust/cards/$CARD_ID/verify" | jq
```

Create threshold and simulate handshake:

```bash
curl -s -b "$COOKIE" -H 'Content-Type: application/json' -H 'X-Environment-ID: env_default' \
  -d '{"threshold_type":"handoff","target_type":"environment","target_id":"env_default","min_score":700,"required_tier":"trusted","enabled":true}' \
  "$API/api/v1/trust/thresholds" | jq

curl -s -b "$COOKIE" -H 'Content-Type: application/json' -H 'X-Environment-ID: env_default' \
  -d "{
    \"source_agent_id\":\"$AGENT_ID\",
    \"target_agent_id\":\"$TARGET_ID\",
    \"purpose\":\"handoff\",
    \"threshold_type\":\"handoff\",
    \"target_type\":\"environment\",
    \"target_id\":\"env_default\",
    \"required_capabilities\":[\"claims:read\",\"tools:run\"],
    \"require_trust_card\":true,
    \"require_active_credential\":true
  }" \
  "$API/api/v1/trust/handshakes/simulate" | jq

curl -s -b "$COOKIE" -H 'X-Environment-ID: env_default' "$API/api/v1/trust/handshakes" | jq
```

Focused automated tests:

```bash
cd packages/product-platform
PYTHONPATH=src python3 -m unittest \
  tests.test_trust_score_pipeline_overall \
  tests.test_trust_card_management_overall \
  tests.test_handshakes_thresholds_overall \
  -v

cd frontend
npm test -- TrustPage.test.tsx
```

## Edge Cases and Alternative Flows

- No agents: recalculation cannot populate useful score rows; create agents first.
- One agent only: handshake simulation may use the same source and target if allowed by the backend, but a realistic validation should use two agents.
- Revoked card: verifying a revoked card should show invalid or revoked state.
- Disabled trust rule: recalculation should stop applying that rule until it is re-enabled.
- Threshold too high: handshake simulation should deny or require escalation when scores or tiers do not meet the threshold.

## Troubleshooting

- Card issue fails: verify the agent ID exists in `GET /api/v1/agents`.
- Trust score remains empty: run recalculation for a specific agent and inspect `GET /api/v1/trust/events`.
- Handshake result is unexpected: inspect threshold type, required tier, source score, target score, and whether card/credential checkboxes were selected.
- Rule toggle does not persist: refresh `/trust/rules` through the API and confirm the rule ID exists.
