# Feature 09: Marketplace Plugins

## Feature Goal and Expected User Outcome

Validate that an ecosystem operator can import marketplace plugin manifests, inspect plugin versions, run policy gates, submit and decide reviews, manage signing keys, assess quality, recompute plugin trust, install a plugin into an environment or agent target, and uninstall it.

The expected outcome is a plugin in the catalog, a selected version, policy and quality records, review queue state, signing key state, trust events, and installation records.

## Implementation Surface

- Frontend route: `/marketplace`.
- Frontend page: `frontend/src/features/marketplace/MarketplacePage.tsx`.
- API endpoints include:
  - `POST /api/v1/marketplace/plugins/import`
  - `GET /api/v1/marketplace/plugins`
  - `GET /api/v1/marketplace/plugins/{plugin_id}`
  - `POST /api/v1/marketplace/plugins/{version_id}/check-policy`
  - `POST /api/v1/marketplace/plugins/{version_id}/submit-review`
  - `GET /api/v1/marketplace/reviews`
  - `POST /api/v1/marketplace/reviews/{review_id}/approve`
  - `POST /api/v1/marketplace/reviews/{review_id}/reject`
  - `GET /api/v1/marketplace/signing-keys`
  - `POST /api/v1/marketplace/signing-keys`
  - `POST /api/v1/marketplace/signing-keys/{key_id}/revoke`
  - `POST /api/v1/marketplace/plugins/{version_id}/assess-quality`
  - `POST /api/v1/marketplace/plugins/{version_id}/recompute-trust`
  - `GET /api/v1/marketplace/installations`
  - `POST /api/v1/marketplace/installations`
  - `POST /api/v1/marketplace/installations/{installation_id}/uninstall`
- Domain modules: `marketplace/models.py`, `marketplace/repository.py`, `marketplace/policy.py`, `marketplace/quality.py`, `marketplace/signing.py`, `marketplace/usage_trust.py`.
- Migrations: `0023_marketplace_catalog.up.sql`, `0024_marketplace_policy_results.up.sql`, `0025_marketplace_installations.up.sql`, `0026_marketplace_trust.up.sql`.
- Tests: `test_marketplace_catalog_*.py`, `test_plugin_review_signing_trust_*.py`, `frontend/src/features/marketplace/MarketplacePage.test.tsx`.

## Prerequisites and Required Test Data

- Sign in as `admin@example.com` with `Platform Admin`.
- Use environment `Development`.
- Optional: create an agent from Feature 02 if you want to install a plugin to an agent target.
- Use this manifest:

```json
{
  "name": "claims-workflow-pack",
  "version": "1.0.0",
  "description": "Claims workflow governance pack",
  "publisher": "Ophanix",
  "plugin_type": "integration",
  "package_ref": "registry://claims-workflow-pack",
  "signature_status": "signed",
  "required_capabilities": ["claims.lookup"],
  "permissions": ["mcp.invoke"]
}
```

## UI Validation Steps

1. Click `Marketplace` in the left navigation.
2. Expected URL change: current route changes to `/marketplace`.
3. Confirm page title `Marketplace Operations` and description `Review, govern, install, sign, assess, and monitor trusted marketplace plugins.`
4. Confirm summary metrics:
   - `Plugins`
   - `Installed`
   - `Pending Reviews`
   - `Active Keys`
5. In `Plugin Catalog`, use filters if needed:
   - `Type`: leave blank or select `integration`
   - `Status`: leave blank or select `available`
   - Click `Filter`
6. In the import form, enter:
   - `Manifest JSON`: paste the manifest from prerequisites
   - `Package Ref`: `registry://claims-workflow-pack`
   - `Status`: `available`
7. Click `Import`.
8. Expected UI response:
   - Plugin row appears in the catalog.
   - If this is the first plugin, empty state `No plugins` disappears.
   - Columns show `Name`, `Type`, `Status`, `Latest`, and an `Open` action.
9. Click `Open` on `claims-workflow-pack`.
10. Expected URL change: no route change is expected; selection happens inside `/marketplace`.
11. Expected UI response:
    - Plugin detail shows publisher, signature status, trust tier, versions, required capabilities, permissions, and manifest preview.
12. Click `Assess Quality`.
13. Expected UI response:
    - Success message `Quality assessment completed`.
    - `Quality And Trust` shows `Latest Assessment` with score and dimensions.
14. Click `Submit Review`.
15. Expected UI response:
    - A review appears in `Review Queue`.
    - Status is `pending`.
16. In `Review Queue`, set:
    - `Status`: `pending`
    - Click `Filter`
17. In the pending review row, enter reason `validation approval`.
18. Click the `approved` review action.
19. Expected UI response: review status changes to approved and the action buttons become disabled for that row.
20. In `Signing Keys`, enter:
    - `Key Name`: `validation-key`
    - `Public Key`: `-----BEGIN PUBLIC KEY-----validation-----END PUBLIC KEY-----`
21. Click `Add Key`.
22. Expected UI response:
    - Signing key row appears.
    - Status is active.
    - `Active Keys` metric increments.
23. Click `Revoke` on the key row.
24. Expected UI response: key status changes to revoked and `Revoke` becomes disabled.
25. In `Policy And Installation`, run a policy gate:
    - Check `Require Signature`.
    - Check `Require Review`.
    - `Allowed Types`: `integration,agent`
    - `Allowed Capabilities`: `claims.lookup`
26. Click `Check Policy`.
27. Expected UI response:
    - Gate section shows signature, policy, and trust gate statuses.
    - If the result is denied, the `Install` button is disabled.
    - If the result is allowed, the `Install` button is enabled.
28. Install the plugin:
    - `Environment`: `env_default`
    - `Target Agent`: leave blank for environment install, or enter an agent ID
29. Click `Install`.
30. Expected UI response:
    - Success message `Plugin installation created`.
    - Row appears in `Installations` with plugin name/version, target, status, and `Uninstall`.
31. Click `Uninstall`.
32. Expected UI response: installation status changes away from `installed`, and `Uninstall` is disabled.
33. In `Quality And Trust`, enter:
    - `Daily Active Users`: `5`
    - `Invocations`: `100`
    - `Errors`: `0`
    - `Incidents`: `0`
    - `Days Since Update`: `7`
    - `Adoption Trend`: `0`
    - `Source Event`: `marketplace-validation`
34. Click `Recompute Trust`.
35. Expected UI response: a trust event row appears with reason, delta, score, and tier.

## Expected Backend Effects

- Import normalizes and stores the manifest, plugin metadata, and version metadata.
- Policy checks store plugin policy result records with result and findings.
- Review submission creates a pending review; approve or reject updates status, reviewer, reason, and decided timestamp.
- Signing key creation stores public key metadata; revocation updates key status and revoked timestamp.
- Quality assessment stores score, dimensions, and findings.
- Trust recompute stores usage-derived trust event with score delta and tier.
- Installation creates environment or agent installation state; uninstall updates installation status and timestamp.

## Programmatic Verification

```bash
API=http://127.0.0.1:8088
COOKIE=/tmp/ophanix.cookies

curl -s -c "$COOKIE" \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.com","roles":["Platform Admin"]}' \
  "$API/api/v1/auth/dev-login" >/dev/null
```

Import and inspect a plugin:

```bash
PLUGIN_JSON=$(curl -s -b "$COOKIE" \
  -H 'Content-Type: application/json' \
  -H 'X-Environment-ID: env_default' \
  -d '{
    "manifest":{
      "name":"claims-workflow-pack-api",
      "version":"1.0.0",
      "description":"Claims workflow governance pack",
      "publisher":"Ophanix",
      "plugin_type":"integration",
      "package_ref":"registry://claims-workflow-pack-api",
      "signature_status":"signed",
      "required_capabilities":["claims.lookup"],
      "permissions":["mcp.invoke"]
    },
    "package_ref":"registry://claims-workflow-pack-api",
    "status":"available"
  }' \
  "$API/api/v1/marketplace/plugins/import")

echo "$PLUGIN_JSON" | jq
PLUGIN_ID=$(echo "$PLUGIN_JSON" | jq -r '.id')
VERSION_ID=$(echo "$PLUGIN_JSON" | jq -r '.versions[0].id')

curl -s -b "$COOKIE" -H 'X-Environment-ID: env_default' "$API/api/v1/marketplace/plugins/$PLUGIN_ID" | jq
```

Check policy, review, assess, install, and recompute trust:

```bash
curl -s -b "$COOKIE" -H 'Content-Type: application/json' -H 'X-Environment-ID: env_default' \
  -d '{"require_signature":true,"require_review_approval":false,"allowed_plugin_types":["integration","agent"],"allowed_capabilities":["claims.lookup"]}' \
  "$API/api/v1/marketplace/plugins/$VERSION_ID/check-policy" | jq

REVIEW_JSON=$(curl -s -b "$COOKIE" -H 'Content-Type: application/json' -H 'X-Environment-ID: env_default' \
  -d '{"findings":[{"code":"manual_review","message":"Manual review requested"}]}' \
  "$API/api/v1/marketplace/plugins/$VERSION_ID/submit-review")
REVIEW_ID=$(echo "$REVIEW_JSON" | jq -r '.id')

curl -s -b "$COOKIE" -H 'Content-Type: application/json' -H 'X-Environment-ID: env_default' \
  -d '{"decision_reason":"validation approval"}' \
  "$API/api/v1/marketplace/reviews/$REVIEW_ID/approve" | jq

curl -s -b "$COOKIE" -H 'Content-Type: application/json' -H 'X-Environment-ID: env_default' \
  -d '{"name":"validation-key-api","public_key":"-----BEGIN PUBLIC KEY-----validation-----END PUBLIC KEY-----"}' \
  "$API/api/v1/marketplace/signing-keys" | jq

curl -s -b "$COOKIE" -H 'Content-Type: application/json' -H 'X-Environment-ID: env_default' \
  -d '{}' "$API/api/v1/marketplace/plugins/$VERSION_ID/assess-quality" | jq

curl -s -b "$COOKIE" -H 'Content-Type: application/json' -H 'X-Environment-ID: env_default' \
  -d '{"plugin_version_id":"'"$VERSION_ID"'","environment_id":"env_default"}' \
  "$API/api/v1/marketplace/installations" | jq

curl -s -b "$COOKIE" -H 'Content-Type: application/json' -H 'X-Environment-ID: env_default' \
  -d '{"daily_active_users":5,"total_invocations":100,"error_count":0,"incident_count":0,"days_since_update":7,"adoption_trend":0,"source_event_id":"marketplace-validation"}' \
  "$API/api/v1/marketplace/plugins/$VERSION_ID/recompute-trust" | jq
```

Focused automated tests:

```bash
cd packages/product-platform
PYTHONPATH=src python3 -m unittest \
  tests.test_marketplace_catalog_overall \
  tests.test_plugin_review_signing_trust_overall \
  -v

cd frontend
npm test -- MarketplacePage.test.tsx
```

## Edge Cases and Alternative Flows

- Invalid manifest JSON: enter malformed JSON or an array. Expected result: error `Manifest JSON must be an object.`
- Invalid plugin name: names must contain only letters, numbers, hyphens, or underscores.
- Invalid version: versions must use `MAJOR.MINOR` or `MAJOR.MINOR.PATCH`.
- Unsupported plugin type: only `policy_template`, `integration`, `agent`, and `validator` are supported.
- Require review before approval: policy check can deny install until the review is approved.
- Unsigned plugin with `Require Signature`: policy check should deny or flag the signature gate.
- Revoked signing key: revoked keys remain visible but cannot be revoked again.

## Integration Setup Required: Real Package Registry and Signatures

Local validation stores manifests and package references. It does not prove that a real package registry artifact was fetched or that a production signature chain was verified.

To validate a real marketplace integration:

1. Publish or identify a plugin package in the registry.
2. Put the exact package URI in `package_ref`.
3. Register the plugin publisher public key in `Signing Keys`.
4. Import a manifest with `signature_status` reflecting the actual signature result.
5. Run `Check Policy` with `Require Signature`.
6. Confirm the policy result accepts only signed and allowed plugins.
7. Install into `env_default` or a known agent.
8. Confirm the target runtime or integration layer can load the package. This final runtime loading behavior needs environment verification.

## Troubleshooting

- Import fails: validate manifest fields against the supported model and ensure `package_ref` exists either in the request or manifest.
- `Install` is disabled: inspect policy gate findings, signature status, review requirement, allowed type, and allowed capability.
- Review action fails: confirm the review is still pending.
- Trust event does not appear: select a plugin version first and run `Recompute Trust`.
- Installation row targets the environment instead of an agent: enter a valid `Target Agent` ID before clicking `Install`.

