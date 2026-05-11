# Tool Gateway Production Runbook

Status: operational baseline for production adoption planning.

## Required Production Configuration

- `OPHANIX_SESSION_SECRET`: non-default high-entropy value.
- `OPHANIX_DATABASE_URL`: managed production database URL. SQLite is rejected in production.
- `OPHANIX_SECRET_MANAGER_REF`: `env` or `env:<ENV_VAR_PREFIX>` in this worktree.
- `OPHANIX_GATEWAY_TOKEN_HASH_PEPPER`: high-entropy pepper stored outside source control.
- `OPHANIX_TOOL_GATEWAY_UPSTREAM_HOST_ALLOWLIST`: comma-separated approved upstream hosts or wildcard patterns.
- `OPHANIX_TOOL_GATEWAY_MAX_BODY_BYTES`: positive request body cap.
- `OPHANIX_TOOL_GATEWAY_MAX_UPSTREAM_RESPONSE_BYTES`: positive upstream response cap.
- `OPHANIX_TOOL_GATEWAY_RATE_LIMIT_MAX_REQUESTS`, `OPHANIX_TOOL_GATEWAY_RATE_LIMIT_WINDOW_SECONDS`, `OPHANIX_TOOL_GATEWAY_RATE_LIMIT_MAX_KEYS`: positive local safety limits.

Production startup rejects legacy gateway-token hash acceptance and unresolved upstream host bypass.

## Incident Playbooks

### Gateway Token Compromise

1. Revoke or expire the affected agent credential.
2. Rotate the raw gateway token through the credential issuance workflow.
3. Clear SDK discovery caches in long-running agents.
4. Review `gateway.token_verification.failed` and tool runtime audit events for suspicious use.
5. Rotate `OPHANIX_GATEWAY_TOKEN_HASH_PEPPER` only through a staged previous/current pepper migration.

### Upstream Secret Compromise

1. Rotate the secret in the external secret source backing `secret_ref`.
2. Update the environment-injected secret value and restart or reload gateway workers.
3. Verify target health and perform a controlled invocation.
4. Review runtime responses and audit summaries for exposure.

### Upstream Outage

1. Run the upstream health check endpoint for the affected target.
2. Pause or disable the upstream target if failures are sustained.
3. Notify SDK consumers that invocations can return gateway `503` or upstream errors.
4. Re-enable only after a successful health check and controlled invocation.

### Rate-Limit Spike

1. Inspect `429` rates and `Retry-After` behavior.
2. Check whether traffic is concentrated by credential, client IP, or invalid authorization attempts.
3. Apply ingress/edge limits if the in-process limiter is insufficient.
4. Rotate exposed credentials if spikes correlate with one agent token.

### Response Data Exposure

1. Disable `store_full_response` on affected response policies.
2. Tighten redaction keys/patterns and add PII-aware policy rules.
3. Purge or quarantine affected runtime action records according to retention policy.
4. Add a regression test with the representative sensitive payload.

### Release Rollback

1. Identify package versions and artifact hashes from `release-manifest.json`.
2. Reinstall the prior validated artifact from the package index or artifact store.
3. Verify SDK import, gateway startup, discovery, invocation, and auth failure paths.
4. Record rollback reason and attach validator output, SBOM, and provenance references.

## Validation Drills

- Quarterly token rotation drill.
- Quarterly upstream secret rotation drill.
- Load test before every broad rollout.
- Multi-worker limiter and SQLite-contention test until production DB support lands.
- Release dry-run including `--strict-git`, SBOM, manifest, and clean install verification.
