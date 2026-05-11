# Tool Gateway Threat Model

Status: baseline threat model for the current product-platform worktree.

## Trust Boundaries

- External agents call `/api/v1/gateway/tools` and `/api/v1/tools/{name}/invoke` with gateway bearer credentials.
- Product operators configure tools, permissions, upstream targets, response policies, and upstream secret references through product-authenticated APIs.
- The gateway forwards allowed calls to external upstream HTTPS services.
- Runtime action/audit records persist request summaries, decisions, upstream status, and response summaries.
- Secret values are retrieved through the configured secret provider and must never be stored in tool target configuration.

## Assets

- Gateway bearer tokens and token hash pepper material.
- Upstream bearer/API-key secrets.
- Tool catalog, schemas, descriptions, required scopes, and permission bindings.
- Agent payloads, upstream responses, response summaries, runtime actions, and audit events.
- Release artifacts, SBOMs, provenance attestations, and package index uploads.

## Primary Abuse Cases And Controls

| Abuse case | Current control | Remaining requirement |
| --- | --- | --- |
| Stolen or weak gateway token | High-entropy token guidance, peppered HMAC lookup, production pepper requirement, no token logging in SDK diagnostics | Managed token rotation workflow and alerting on failed verification spikes |
| Overbroad tool credential | Resource-bound scopes and runtime permission checks | Issuance-time wildcard approval/audit workflow |
| SSRF through upstream target | HTTPS-only URLs, no userinfo/query/fragment, forbidden IP/host rejection, production host allowlist, runtime URL revalidation | Network egress policy and DNS rebinding validation in deployment |
| Secret leakage through target config | `secret_ref` only, inline secret rejection, read API redaction | Managed secret-provider backend beyond environment injection |
| Sensitive response persistence | Response policies, redaction rules, response-size caps | PII-aware policy presets, retention jobs, encryption policy |
| Duplicate side effects after retry | SDK does not auto-retry invocations | Durable idempotency key/replay contract |
| Rate-limit bypass or process multiplication | In-process limiter, `Retry-After`, invalid-token key overflow guard | Distributed or edge-enforced limiter |
| Malicious large body/response | ASGI body cap and streaming upstream/SDK response caps | Ingress-level body cap conformance test |
| Release artifact tampering | Build validation, SBOM, sigstore/provenance workflow, release manifest | Actual package-index publish proof and advisory coverage |

## Security Invariants

- Gateway runtime endpoints must authenticate with gateway credentials, not product-user sessions.
- Product control-plane APIs must remain product-authenticated and permission-checked.
- Upstream target writes must not persist raw upstream secrets.
- Runtime invocation must revalidate persisted upstream URLs before forwarding.
- SDK exception messages and diagnostics must not include raw bearer tokens or upstream secrets.
- Production startup must reject demo/local defaults that change security posture.

## Open Risks

- The runtime is still SQLite-backed in this worktree and needs production database support before broad adoption.
- No durable idempotency/replay contract exists for mutating tool invocations.
- The in-process rate limiter is not a distributed abuse-control layer.
- Environment-backed secret retrieval is safer than the demo provider but is not a full managed secret-manager integration with audit/rotation APIs.
- DNS validation is not a complete SSRF boundary without network egress enforcement.
